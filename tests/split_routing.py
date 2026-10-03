#!/usr/bin/env python3
"""Four opt-in planning tasks: verified module delivery, no generated-code run."""
import argparse
import json
from pathlib import Path
import shutil
import tempfile
import uuid

import context_comparison as harness

CASES = {
    'web': ('Plan changing Referrer-Policy to strict-origin-when-cross-origin on an existing public HTML response. No account, session, cookie or cryptographic changes are involved.', ['aiscb:web']),
    'authentication': ('Plan validating malformed and expired records in an existing internal shared-session adapter. Session IDs are opaque secret tokens. No HTTP or browser code changes; reuse the existing session store and authentication library.', ['aiscb:authentication', 'aiscb:cryptography', 'aiscb:data-handling', 'aiscb:secrets-initialization']),
    'cryptography': ('Plan replacing a deprecated encryption algorithm in an existing in-memory helper using its maintained cryptographic library and externally configured persistent key. No files, HTTP, browser or account flows are changed.', ['aiscb:cryptography', 'aiscb:secrets-initialization']),
    'mixed': ('Plan updating an existing browser login endpoint and its session cookie. Keep the existing authentication library, shared session store, password hashing and external key configuration. Cover malformed request bodies and invalid credentials.', ['aiscb:web', 'aiscb:authentication', 'aiscb:cryptography', 'aiscb:data-handling', 'aiscb:secrets-initialization']),
}


def assess(events, required):
    loaded = set()
    for event in events:
        if not event.get('error'):
            loaded.update(event.get('loaded', []))
            if event['tool'] == 'write_file' and event.get('path') == 'plan.md':
                return {'written': True, 'loaded_before_write': sorted(loaded),
                        'missing': sorted(set(required)-loaded)}
    return {'written': False, 'loaded_before_write': [], 'missing': sorted(required)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not args.run:
        print(json.dumps({'tasks': CASES, 'runs': 4, 'preflights': 1, 'judges': 0}, indent=2)); return 0
    if not args.output: parser.error('--run requires --output')
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=False)
    snapshot = out/'policy-snapshot'; (snapshot/'scripts').mkdir(parents=True)
    shutil.copytree(harness.ROOT/'baseline', snapshot/'baseline')
    shutil.copyfile(harness.ROOT/'scripts/policy_loader.py', snapshot/'scripts/policy_loader.py')
    harness.install_policy.ROOT = snapshot
    harness.dump(out/'plan.json', {'model': harness.MODEL, 'cases': CASES, 'runs': 4,
                                  'catalog_sha256': harness.digest((snapshot/'baseline/catalog.json').read_bytes())})
    results = []
    with tempfile.TemporaryDirectory(prefix='aiscb-split-routing-') as temp, harness.isolated_profile():
        for name, (task, required) in CASES.items():
            harness.CASES[name] = {'files': {'plan.md': ''}}
            base = Path(temp)/name
            work, config, initial = harness.prepare(base, name, 'modular')
            (out/(name+'-initial.md')).write_text(initial)
            if name == 'web':
                trace = harness.capture(harness.command(base, harness.MODEL, str(uuid.uuid4()), 1,
                                        harness.runner.PROBE_PROMPT, True), work, out/'preflight.jsonl', 90)
                if not trace['complete'] or set(harness.runner.id_family('aiscb-0.1.19').findall(trace['reply'])) != {'aiscb-0.1.19'}:
                    raise SystemExit('Preflight failed; no tasks started.')
            config['turn'] = 1; harness.dump(base/'config.json', config)
            prompt = task+' Write a concise implementation plan to plan.md. This is a synthetic existing-project planning fixture; do not implement or run application code, install packages or read secret values.'
            trace = harness.capture(harness.command(base, harness.MODEL, str(uuid.uuid4()), 1, prompt), work, out/(name+'.jsonl'), 120)
            trace.pop('events', None)
            events = harness.audits(base)
            assessment = assess(events, required)
            passed = trace['complete'] and assessment['written'] and not assessment['missing']
            results.append({'case': name, 'passed': passed, 'assessment': assessment, 'trace': trace, 'audit': events})
            (out/(name+'-plan.md')).write_text((work/'plan.md').read_text())
            harness.dump(out/'results.json', results)
            print(f'{name}: passed={passed}, modules={assessment["loaded_before_write"]}', flush=True)
    return 0 if all(r['passed'] for r in results) else 1


if __name__ == '__main__': raise SystemExit(main())
