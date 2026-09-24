#!/usr/bin/env python3
"""CWEval Table I/II protocol: all languages, direct API, n=100, T=0.8.

Only reviewed task text and literal prompt templates cross the API boundary.
Reference solutions, compilation and generated code stay in offline containers.
"""
import argparse
import ast
from collections import Counter
from datetime import datetime, timezone
import hashlib
import http.client
import io
import json
import math
import os
from pathlib import Path
import re
import selectors
import shlex
import shutil
import signal
import ssl
import subprocess
import sys
import tarfile
import tempfile
import time
from urllib.parse import urlsplit
import uuid

import cweval_runner as legacy

CONFIG = Path(__file__).with_name('cweval.full.local.json')
SAMPLES = 100
TEMPERATURE = 0.8
KS = (1, 10, 50)
EXPECTED = {'core/py': 25, 'core/js': 23, 'core/cpp': 21,
            'core/c': 20, 'core/go': 19, 'lang/c': 11}
TASK_PATH = re.compile(r'(core/(py|js|cpp|c|go)|lang/c)/cwe_[0-9]+_[0-9]+(?:_(?:c|cpp|go|js))?_task\.(py|js|cpp|c|go)\Z')
ENV_NAME = re.compile(r'[A-Z][A-Z0-9_]{0,99}\Z')
MAX_RESPONSE = 1_000_000
MAX_JSON = 8_000_000
OPTIONS = {'cweval_root': str, 'revision': str, 'image': str, 'model': str,
           'api_url': str, 'api_key_env': str, 'max_completion_tokens': int,
           'timeout': int, 'eval_timeout': int}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read_file(path, limit, root=None):
    path = Path(path)
    if root is not None:
        relative = path.relative_to(root)
        if any((root / Path(*relative.parts[:i])).is_symlink()
               for i in range(1, len(relative.parts) + 1)):
            raise ValueError('linked input is not permitted')
    if path.is_symlink() or not path.is_file():
        raise ValueError('expected a regular input file')
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError('input exceeds its size limit')
    return raw


def config_args(path=CONFIG):
    if not path.exists() and not path.is_symlink():
        return []
    config = json.loads(read_file(path, 4096))
    if not isinstance(config, dict) or set(config) - set(OPTIONS):
        raise ValueError('full config contains unsupported options (never store API keys)')
    args = []
    for key, value in config.items():
        if type(value) is not OPTIONS[key]:
            raise ValueError('full config option has the wrong type')
        args.extend(['--' + key.replace('_', '-'), str(value)])
    return args


def tasks(root):
    """Enumerate every task; no filename supplied by a model becomes a path."""
    benchmark = root / 'benchmark'
    found = {}
    for directory, dirs, files in os.walk(benchmark, followlinks=False):
        if any((Path(directory) / name).is_symlink() for name in dirs + files):
            raise ValueError('linked benchmark content is not permitted')
        for name in files:
            if '_task.' not in name:
                continue
            path = Path(directory) / name
            rel = path.relative_to(benchmark).as_posix()
            if not TASK_PATH.fullmatch(rel) or path.suffix[1:] != path.parent.name:
                raise ValueError('unsupported benchmark task path')
            if len(found) >= 119:
                raise ValueError('paper profile requires exactly 119 tasks')
            raw = read_file(path, legacy.MAX_TASK_BYTES, root)
            test = path.with_name(path.stem.removesuffix('_task') + '_test.py')
            test_raw = read_file(test, 200_000, root)
            source = raw.decode('utf-8')
            # Same BEGIN PROMPT / solution-line boundary as upstream Gener._get_cases.
            boundaries = [line for line in source.splitlines() if 'BEGIN SOLUTION' in line]
            if not boundaries:
                raise ValueError('task must contain a solution boundary')
            prompt = source.split('BEGIN PROMPT')[-1].split(boundaries[0])[0].strip()
            if not prompt:
                raise ValueError('empty task prompt')
            found[rel] = {'prompt': prompt, 'language': path.suffix[1:],
                          'task_sha256': digest(raw), 'test_sha256': digest(test_raw)}
    counts = Counter(str(Path(rel).parent) for rel in found)
    if counts != EXPECTED:
        raise ValueError(f'paper profile requires the 119-task distribution: {dict(counts)}')
    return dict(sorted(found.items()))


def prompt_template(root):
    """Read literal DirectPrompt fields without importing third-party Python."""
    raw = read_file(root / 'cweval/ppt/__init__.py', 50_000, root)
    tree = ast.parse(raw)
    classes = [node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == 'DirectPrompt']
    if len(classes) != 1:
        raise ValueError('missing upstream DirectPrompt')
    values = {}
    for node in classes[0].body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in ('PPT', 'LANG_INSTR'):
                values[target.id] = ast.literal_eval(node.value)
    if (type(values.get('PPT')) is not str or type(values.get('LANG_INSTR')) is not dict
            or set(values['LANG_INSTR']) != {'py', 'js', 'c', 'cpp', 'go'}
            or any(type(value) is not str for value in values['LANG_INSTR'].values())):
        raise ValueError('unsupported upstream direct prompt template')
    return values, digest(raw)


def messages(task, template, baseline=None):
    prompt = template['PPT'].format(lang=task['language'],
                                   lang_instr=template['LANG_INSTR'][task['language']],
                                   code_prompt=task['prompt'])
    result = [{'role': 'user', 'content': prompt}]
    if baseline is not None:
        result.insert(0, {'role': 'system', 'content': baseline})
    return result


def endpoint(url):
    # This is operator configuration, never task/model input. No redirect or proxy
    # support: the credential goes only to this exact TLS-verified endpoint.
    if any(ord(char) <= 32 or ord(char) == 127 for char in url):
        raise ValueError('API URL contains invalid characters')
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.query or parsed.fragment
            or not parsed.path.endswith('/chat/completions')):
        raise ValueError('API URL must be an HTTPS Chat Completions endpoint without credentials or query')
    _ = parsed.port
    return parsed


def completion(args, prompt_messages):
    parsed = endpoint(args.api_url)
    key = os.environ.get(args.api_key_env, '')
    if not key or any(ord(char) < 33 or ord(char) > 126 for char in key):
        raise ValueError('required API credential is missing or invalid')
    payload = {'model': args.model, 'messages': prompt_messages, 'n': 1,
               'temperature': TEMPERATURE,
               'max_completion_tokens': args.max_completion_tokens, 'stream': False}
    connection = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443,
                                             timeout=args.timeout,
                                             context=ssl.create_default_context())
    try:
        connection.request('POST', parsed.path, json.dumps(payload).encode(),
                           {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
        response = connection.getresponse()
        if response.status != 200:
            # Do not log provider error bodies, headers, or transport exceptions.
            raise RuntimeError(f'API returned HTTP {response.status}; no automatic retry')
        raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            raise RuntimeError('API response exceeds size limit')
        data = json.loads(raw)
        choices = data.get('choices') if isinstance(data, dict) else None
        if not isinstance(choices, list) or len(choices) != 1:
            raise RuntimeError('API must return exactly one choice')
        choice = choices[0]
        if not isinstance(choice, dict) or not isinstance(choice.get('message'), dict):
            raise RuntimeError('invalid API choice')
        message = choice['message']
        if message.get('tool_calls') or message.get('function_call'):
            raise RuntimeError('unexpected tool request; no tools are executed')
        content = message.get('content')
        if content is None and (message.get('refusal') or choice.get('finish_reason') == 'content_filter'):
            content = ''  # A refusal is a failed sample, never resampled.
        if not isinstance(content, str) or len(content.encode()) > legacy.MAX_CODE_BYTES:
            raise RuntimeError('invalid or oversized API content')
        # Retain only bounded, non-secret provenance fields, never response headers.
        metadata = {}
        for name, value in [('model', data.get('model')),
                            ('system_fingerprint', data.get('system_fingerprint')),
                            ('finish_reason', choice.get('finish_reason'))]:
            if value is not None:
                if not isinstance(value, str) or len(value) > 200 or any(ord(c) < 32 for c in value):
                    raise RuntimeError('invalid API provenance')
                metadata[name] = value
        return content, metadata
    except (OSError, http.client.HTTPException, UnicodeError, json.JSONDecodeError):
        raise RuntimeError('API transport or JSON failure; no automatic retry') from None
    finally:
        connection.close()


def raw_path(task):
    return Path(task.replace('_task.', '_raw.'))


def generate(args, selected, template, baseline, result):
    with (result / 'runs.jsonl').open('x', encoding='utf-8') as journal:
        for sample in range(SAMPLES):
            for task, info in selected.items():
                for arm in ('control', 'baseline'):
                    row = {'sample': sample, 'case': task, 'arm': arm, 'status': 'started'}
                    journal.write(json.dumps(row) + '\n'); journal.flush()
                    content, provenance = completion(args, messages(
                        info, template, baseline if arm == 'baseline' else None))
                    path = result / arm / f'generated_{sample}' / raw_path(task)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding='utf-8')
                    row.update(status='complete', sha256=digest(content.encode()), **provenance)
                    journal.write(json.dumps(row) + '\n'); journal.flush()
            print(f'Generated sample {sample + 1}/{SAMPLES} for both arms', flush=True)


# All shell text is fixed. Generated content enters only as regular archive files.
BOOT = r'''set -eu
cp -R /source/cweval /source/benchmark /source/third_party /source/go.mod /source/go.sum /work/
set -- /home/ubuntu/.nvm/versions/node/*/bin/node
test "$#" -eq 1 && test -x "$1"
node_bin=${1%/node}
export PATH="$node_bin:/home/ubuntu/miniforge3/envs/cweval/bin:/home/ubuntu/go/bin:/usr/local/go/bin:/usr/local/bin:/usr/bin:/bin"
export NODE_PATH="${node_bin%/bin}/lib/node_modules"
export PYTHONPATH=/work
export C_INCLUDE_PATH=/home/ubuntu/miniforge3/envs/cweval/include
export LIBRARY_PATH=/home/ubuntu/miniforge3/envs/cweval/lib
export LD_LIBRARY_PATH=/home/ubuntu/miniforge3/envs/cweval/lib
export GOPATH=/home/ubuntu/go
export GOMODCACHE=/home/ubuntu/go/pkg/mod
export GOCACHE=/tmp/go-cache
export GOMAXPROCS=2
export GOFLAGS=-p=2
export GOPROXY=off
export GOSUMDB=off
export GOTOOLCHAIN=local
'''
REFERENCE = '''python -c 'from cweval.commons import compile_all_in; results = compile_all_in("benchmark", check=False, num_proc=1); raise SystemExit(any(r[0] for r in results))'
python -m pytest benchmark -q --timeout=20
'''
EVALUATION = '''mkdir -p evals/full
tar -xf - -C evals/full
python cweval/evaluate.py pipeline --eval_path evals/full --num_proc 1 --docker False
'''
# Return bounded logs and score data as one JSON envelope, even when evaluation
# fails. Host never executes or interpolates the returned content.
ENVELOPE = '''
python3 - "$code" <<'END_ENVELOPE'
import json, pathlib, sys
p = pathlib.Path('/tmp/evaluation.log')
with p.open('rb') as f:
    head = f.read(32000)
    f.seek(max(len(head), p.stat().st_size - 32000))
    log = (head + b'\\n...\\n' + f.read(32000)).decode('utf-8', errors='replace')
r = pathlib.Path('/work/evals/full/res_all.json')
scores = None
if r.is_file() and not r.is_symlink() and r.stat().st_size <= 1000000:
    scores = json.loads(r.read_text())
print(json.dumps({'exit_code': int(sys.argv[1]), 'log': log, 'scores': scores}))
END_ENVELOPE
'''


def container_command(root, image, name, reference=False):
    if not legacy.IMAGE.fullmatch(image):
        raise ValueError('image must be pinned by SHA-256')
    body = BOOT + (REFERENCE if reference else EVALUATION)
    # A separate shell keeps set -e effective; a conditional subshell would not.
    script = 'code=0\n/bin/sh -c ' + shlex.quote(body) + ' >/tmp/evaluation.log 2>&1 || code=$?\n' + ENVELOPE
    return ['docker', 'run', '--rm', '-i', '--pull=never', '--name', name,
            '--network=none', '--read-only', '--cap-drop=ALL',
            '--security-opt=no-new-privileges', '--pids-limit=128', '--memory=2g',
            '--cpus=2', '--ulimit=nofile=1024:1024', '--user=1000:1000',
            '--tmpfs', '/tmp:rw,nosuid,noexec,size=512m,uid=1000,gid=1000,mode=0700',
            # Compiled C/C++/Go programs must execute, only inside this sandbox.
            '--tmpfs', '/work:rw,nosuid,exec,size=1g,uid=1000,gid=1000,mode=0700',
            '--env', 'HOME=/tmp', '--env', 'PYTHONDONTWRITEBYTECODE=1',
            '--mount', f'type=bind,src={root},dst=/source,readonly',
            '--workdir', '/work', image, '/bin/sh', '-c', script]


def sample_archive(result, arm, sample, selected):
    stream = tempfile.TemporaryFile()
    try:
        with tarfile.open(fileobj=stream, mode='w') as archive:
            for task in selected:
                rel = Path(f'generated_{sample}') / raw_path(task)
                raw = read_file(result / arm / rel, legacy.MAX_CODE_BYTES, result)
                info = tarfile.TarInfo(rel.as_posix())
                info.size, info.mode, info.uid, info.gid = len(raw), 0o600, 1000, 1000
                archive.addfile(info, io.BytesIO(raw))
        stream.seek(0)
        return stream
    except BaseException:
        stream.close()
        raise


def run_container(command, stream, cwd, timeout):
    """Bound both the lifetime and host memory used by container output."""
    proc = subprocess.Popen(command, cwd=cwd, stdin=stream,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True)
    buffers = {'out': bytearray(), 'err': bytearray()}
    deadline = time.monotonic() + timeout
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ, 'out')
            selector.register(proc.stderr, selectors.EVENT_READ, 'err')
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise RuntimeError('evaluation container timed out')
                for key, _ in selector.select(min(remaining, 1)):
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    buffer = buffers[key.data]
                    limit = MAX_JSON if key.data == 'out' else 64000
                    if len(buffer) + len(chunk) > limit:
                        raise RuntimeError('evaluation container output exceeds its limit')
                    buffer.extend(chunk)
        rc = proc.wait(timeout=max(0.01, deadline - time.monotonic()))
        return rc, buffers['out'].decode('utf-8'), buffers['err'].decode('utf-8', errors='replace')
    finally:
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait(timeout=20)
        proc.stdout.close()
        proc.stderr.close()


def sandbox(root, image, result, timeout, stream, label, reference=False):
    name = 'aiscb-cweval-full-' + uuid.uuid4().hex[:12]
    command = container_command(root, image, name, reference)
    try:
        rc, output, stderr = run_container(command, stream, result, timeout)
        if rc != 0 or len(output.encode()) > MAX_JSON:
            (result / f'{label}.log').write_text(stderr[-64000:], encoding='utf-8')
            raise RuntimeError('evaluation container failed or timed out')
        envelope = json.loads(output)
        if (not isinstance(envelope, dict) or set(envelope) != {'exit_code', 'log', 'scores'}
                or type(envelope['exit_code']) is not int or not isinstance(envelope['log'], str)
                or len(envelope['log'].encode()) > 256_000):
            raise ValueError('invalid evaluation envelope')
        (result / f'{label}.log').write_text(envelope['log'], encoding='utf-8')
        if envelope['exit_code'] != 0:
            raise RuntimeError(f'evaluation failed; inspect {label}.log')
        return envelope['scores']
    finally:
        subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=20, check=False)


def checked_sample(scores, selected):
    expected = {str(Path(task).with_suffix('.py')).replace('_task.py', '_test.py'): task
                for task in selected}
    if not isinstance(scores, dict):
        raise ValueError('missing evaluator score object')
    found = {}
    for key, values in scores.items():
        prefix = 'evals/full/generated_X/'
        if not isinstance(key, str) or not key.startswith(prefix):
            raise ValueError('unexpected evaluator path')
        rel = key[len(prefix):]
        if rel not in expected or expected[rel] in found or not isinstance(values, dict):
            raise ValueError('unexpected or duplicate evaluator case')
        for field in ('functional', 'secure', 'func_secure'):
            data = values.get(field)
            if not isinstance(data, list) or len(data) != 1 or type(data[0]) is not bool:
                raise ValueError('invalid evaluator sample')
        if values['func_secure'][0] != (values['functional'][0] and values['secure'][0]):
            raise ValueError('inconsistent evaluator joint success')
        found[expected[rel]] = values
    if set(found) != set(selected):
        # Never silently drop collection failures from a published denominator.
        raise ValueError('incomplete evaluator coverage; inspect retained log before reporting')
    return found


def evaluate(args, root, selected, result):
    scores = {arm: {task: {'functional': [], 'secure': [], 'func_secure': []}
                    for task in selected} for arm in ('control', 'baseline')}
    for sample in range(SAMPLES):
        for arm in scores:
            with sample_archive(result, arm, sample, selected) as stream:
                raw = sandbox(root, args.image, result, args.eval_timeout, stream,
                              f'{arm}-{sample}')
            (result / f'{arm}-{sample}.json').write_text(json.dumps(raw) + '\n')
            checked = checked_sample(raw, selected)
            for task, values in checked.items():
                for field in scores[arm][task]:
                    scores[arm][task][field].append(values[field][0])
        print(f'Evaluated sample {sample + 1}/{SAMPLES} for both arms', flush=True)
    return scores


def pass_at_k(values, k):
    n, c = len(values), sum(values)
    if not 1 <= k <= n or any(type(value) is not bool for value in values):
        raise ValueError('invalid pass@k inputs')
    return 1.0 if n - c < k else 1 - math.comb(n - c, k) / math.comb(n, k)


def metrics(scores):
    groups = {'all': list(next(iter(scores.values())))}
    for group in EXPECTED:
        groups[group] = [task for task in groups['all'] if str(Path(task).parent) == group]
    return {arm: {group: {f'{metric}@{k}': 100 * sum(
                pass_at_k(cases[task][field], k) for task in names) / len(names)
                for metric, field in [('func', 'functional'), ('func-sec', 'func_secure')]
                for k in KS} for group, names in groups.items() if names}
            for arm, cases in scores.items()}


def write_report(result, manifest, scores):
    rates = metrics(scores)
    report = {'manifest': manifest, 'scores': scores, 'metrics': rates,
              'delta_percentage_points': {key: rates['baseline']['all'][key] - value
                                         for key, value in rates['control']['all'].items()}}
    (result / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# CWEval multilingual comparison', '',
             'Profile: paper Tables I/II; 119 tasks; 100 samples per task/arm; temperature 0.8.',
             f'Model requested: `{manifest["model"]}`; revision: `{manifest["revision"]}`.',
             'Control: upstream direct prompt. Baseline: same prompt plus complete aiscb system message.',
             '', '| Arm | Group | func@1 | func-sec@1 | func@10 | func-sec@10 | func@50 | func-sec@50 |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for arm, groups in rates.items():
        for group, values in groups.items():
            numbers = [values[f'{metric}@{k}'] for k in KS for metric in ('func', 'func-sec')]
            lines.append(f'| {arm} | {group} | ' + ' | '.join(f'{v:.2f}' for v in numbers) + ' |')
    lines.extend(['', 'Baseline − control (percentage points): ' + ', '.join(
                      f'{key}: {value:+.2f}' for key, value in report['delta_percentage_points'].items()) + '.',
                  '', 'Scores are task-weighted, not averages of language percentages.',
                  'This implements the fixed-temperature profile, not the best-of-four-temperature figure.',
                  'Compare a published number only after matching its task revision, model/protocol, token budget and evaluator.',
                  'The baseline was developed using CWEval findings; these are not held-out results.',
                  'Provider-reported models and finish reasons are retained in runs.jsonl; requested settings do not prove provider compliance.',
                  'Reference checks passed before generation. Per-sample logs are retained; container limits differ from unconstrained upstream runs.', ''])
    (result / 'report.md').write_text('\n'.join(lines))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cweval-root', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--api-url', default='https://api.openai.com/v1/chat/completions')
    parser.add_argument('--api-key-env', default='OPENAI_API_KEY')
    parser.add_argument('--max-completion-tokens', type=int, default=2048)
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--eval-timeout', type=int, default=1800)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--reference-only', action='store_true', help='offline environment checks; no API calls')
    supplied = list(sys.argv[1:] if argv is None else argv)
    try:
        defaults = [] if any(x in supplied for x in ('-h', '--help')) else config_args()
        args = parser.parse_args(defaults + supplied)
        if (not legacy.MODEL.fullmatch(args.model) or not legacy.IMAGE.fullmatch(args.image)
                or not ENV_NAME.fullmatch(args.api_key_env)
                or not 1 <= args.max_completion_tokens <= 32768
                or not 1 <= args.timeout <= 600 or not 1 <= args.eval_timeout <= 7200):
            raise ValueError('invalid model, image, credential variable or resource limits')
        endpoint(args.api_url)
        root = legacy.checked_checkout(args.cweval_root, args.revision)
        selected = tasks(root)
        template, template_hash = prompt_template(root)
        baseline = read_file(legacy.baseline_run.BASELINE, 256_000).decode('utf-8')
        # Verify the generated artifact matches reviewed sources before it is sent.
        sys.path.insert(0, str(legacy.baseline_run.REPO / 'scripts'))
        import build_baseline
        _, _, complete = build_baseline.validate()
        if complete.decode() != baseline:
            raise ValueError('complete baseline is stale; run make build-full-baseline')
        manifest = {'profile': 'paper-tables-i-ii', 'model': args.model,
                    'started_at': datetime.now(timezone.utc).isoformat(),
                    'revision': args.revision, 'image': args.image,
                    'samples': SAMPLES, 'temperature': TEMPERATURE,
                    'max_completion_tokens': args.max_completion_tokens,
                    'api_url': args.api_url, 'api_key_env': args.api_key_env,
                    'timeout': args.timeout, 'eval_timeout': args.eval_timeout,
                    'prompt_template_sha256': template_hash,
                    'baseline_id': legacy.baseline_run.baseline_identifier(),
                    'baseline_sha256': digest(baseline.encode()),
                    'runner_sha256': digest(Path(__file__).read_bytes()),
                    'runner_support_sha256': digest(Path(legacy.__file__).read_bytes()),
                    'container_limits': {'cpus': 2, 'memory': '2g', 'pids': 128,
                                         'work_tmpfs': '1g', 'tmp_tmpfs': '512m',
                                         'go_parallelism': 2, 'evaluator_processes': 1},
                    'task_manifest': {key: {k: v for k, v in value.items() if k != 'prompt'}
                                      for key, value in selected.items()}}
        if args.dry_run:
            print('119 tasks × 100 samples × 2 arms = 23800 API completions')
            print('Languages/sets: ' + json.dumps(EXPECTED, sort_keys=True))
            print('Temperature: 0.8; k: 1, 10, 50; max completion tokens: ' + str(args.max_completion_tokens))
            print('No API, credential access, Docker, or generated-code execution in dry-run.')
            return 0
        if shutil.which('docker') is None:
            raise ValueError('Docker is required')
        if not args.reference_only and not os.environ.get(args.api_key_env):
            raise ValueError('required API credential is missing')
        results = legacy.RESULTS
        if results.is_symlink():
            raise ValueError('results directory must not be linked')
        results.mkdir(parents=True, exist_ok=True)
        result = Path(tempfile.mkdtemp(prefix='full-', dir=results))
        (result / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (result / 'baseline.md').write_text(baseline)
        # Store exact non-secret prompts for independent arm inspection.
        (result / 'prompts.json').write_text(json.dumps(
            {task: messages(info, template) for task, info in selected.items()}, indent=2) + '\n')
        print(f'Evidence: {result}', flush=True)
        with tempfile.TemporaryFile() as stream:
            sandbox(root, args.image, result, args.eval_timeout, stream, 'reference', reference=True)
        (result / 'reference.json').write_text('{"passed": true}\n')
        if args.reference_only:
            print('All reference tests passed; no API calls made.')
            return 0
        generate(args, selected, template, baseline, result)
        scores = evaluate(args, root, selected, result)
        manifest['completed_at'] = datetime.now(timezone.utc).isoformat()
        (result / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        write_report(result, manifest, scores)
        print(f'Report: {result / "report.md"}')
        return 0
    except (ValueError, OSError, RuntimeError, SyntaxError, subprocess.SubprocessError) as exc:
        # Configuration/validation messages are local. Provider bodies never escape completion().
        print(f'Incomplete CWEval full run: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
