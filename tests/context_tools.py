#!/usr/bin/env python3
"""Bounded stdio MCP fixture tools. Never expose shell or arbitrary host paths."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import shlex
import subprocess
import sys
import tempfile
import time

LIMIT = 65536


def sandbox_args(work, oracle=None):
    work = Path(work)
    if work.is_symlink() or any(p.is_symlink() for p in work.rglob('*')):
        raise ValueError('sandbox source contains a symlink')
    args = ['/usr/bin/bwrap', '--unshare-all', '--die-with-parent', '--new-session',
            '--ro-bind', '/usr', '/usr', '--ro-bind', '/lib', '/lib',
            '--ro-bind', '/lib64', '/lib64', '--proc', '/proc', '--dev', '/dev',
            '--tmpfs', '/tmp', '--ro-bind', str(work), '/work', '--chdir', '/work',
            '--clearenv', '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'LANG', 'C.UTF-8']
    if oracle:
        args += ['--ro-bind', str(oracle), '/oracle.py']
    payload = ['/oracle.py'] if oracle else ['-m', 'unittest', 'discover', '-s', '/work', '-p', 'test_*.py', '-q']
    # Apply the process limit after entering the new user namespace; applying it
    # on the host counts unrelated processes owned by the same login.
    bootstrap = "import os,resource,sys; resource.setrlimit(resource.RLIMIT_NPROC,(32,32)); os.execv('/usr/bin/python3',['python3','-I',*sys.argv[1:]])"
    return args + ['/usr/bin/python3', '-I', '-c', bootstrap, *payload]


def limits():
    for key, value in ((resource.RLIMIT_CPU, 8), (resource.RLIMIT_AS, 512*1024*1024),
                       (resource.RLIMIT_FSIZE, LIMIT), (resource.RLIMIT_NOFILE, 64),
                       (resource.RLIMIT_CORE, 0)):
        resource.setrlimit(key, (value, value))


def execute(args, timeout=15):
    with tempfile.TemporaryFile() as output:
        try:
            proc = subprocess.run(args, stdin=subprocess.DEVNULL, stdout=output,
                                  stderr=subprocess.STDOUT, timeout=timeout,
                                  env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'},
                                  preexec_fn=limits)
            output.seek(0)
            return proc.returncode, output.read(LIMIT).decode('utf-8', errors='replace')
        except subprocess.TimeoutExpired:
            return 124, 'Execution timed out.'


class FixtureTools:
    def __init__(self, config):
        self.config = config
        self.root = Path(config['root']).resolve()
        self.calls = 0

    def path(self, name, writing=False):
        if not isinstance(name, str) or not name or '\x00' in name:
            raise ValueError('invalid fixture path')
        p = Path(name)
        if p.is_absolute():
            p = p.relative_to(self.root)
        # Flat source files only; policy and harness artifacts cannot be modified.
        if len(p.parts) != 1 or p.name in ('.', '..'):
            raise ValueError('outside fixture file scope')
        allowed = set(self.config['files'])
        if not writing:
            allowed.add('CLAUDE.md')
        if p.name not in allowed and not re.fullmatch(r'test_[a-zA-Z0-9_]+\.py', p.name):
            raise ValueError('file not allow-listed')
        target = self.root / p
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError('not a regular fixture file')
        return target

    def call(self, name, args):
        self.calls += 1
        event = {'turn': self.config['turn'], 'tool': name, 'time_ns': time.monotonic_ns()}
        text, failed = '', False
        try:
            if self.calls > 80 or not isinstance(args, dict):
                raise ValueError('invalid arguments or tool budget exhausted')
            if name == 'read_file' and set(args) == {'path'}:
                p = self.path(args['path']); event['path'] = p.name
                with p.open('rb') as stream: raw = stream.read(LIMIT+1)
                if len(raw) > LIMIT: raise ValueError('file too large')
                text = raw.decode('utf-8')
            elif name == 'write_file' and set(args) == {'path', 'content'}:
                p = self.path(args['path'], writing=True)
                content = args['content']
                if not isinstance(content, str) or len(content.encode()) > LIMIT:
                    raise ValueError('invalid content or size')
                p.write_text(content); text = 'Written.'
                event.update(path=p.name, sha256=hashlib.sha256(content.encode()).hexdigest())
            elif name == 'run_command' and set(args) == {'command'} and isinstance(args['command'], str):
                argv = shlex.split(args['command'])
                prefix = self.config.get('loader', [])
                if prefix and argv[:len(prefix)] == prefix and len(argv) > len(prefix):
                    ids = argv[len(prefix):]
                    if len(ids) > 12 or any(i not in self.config['modules'] for i in ids):
                        raise ValueError('unknown module ID')
                    code, text = execute(['/usr/bin/python3', *prefix[1:], *ids])
                    if code: raise ValueError('verified loader refused policy')
                    event['loaded'] = re.findall(r'`module-id: ([^`]+)`', text)
                    if not event['loaded']: raise ValueError('loader returned no complete modules')
                elif argv == ['python3', '-m', 'unittest', '-q']:
                    code, text = execute(sandbox_args(self.root))
                    event['test_exit'] = code
                    text = f'Exit {code}\n{text}'
                    failed = code != 0
                else:
                    raise ValueError('Only the installed policy loader and python3 -m unittest -q are available; no shell execution.')
            else:
                raise ValueError('unknown tool or arguments')
        except (ValueError, OSError, UnicodeError) as exc:
            text, failed = str(exc)[:400], True
        event.update(error=failed, output=text)
        with Path(self.config['audit']).open('a') as stream:
            stream.write(json.dumps(event)+'\n')
        return {'content': [{'type': 'text', 'text': text}], 'isError': failed}


def tool_schema(name, description, fields):
    return {'name': name, 'description': description, 'inputSchema': {
        'type': 'object', 'properties': {k: {'type': 'string'} for k in fields},
        'required': fields, 'additionalProperties': False}}


TOOLS = [tool_schema('read_file', 'Read a named fixture file.', ['path']),
         tool_schema('write_file', 'Replace one fixture source or test file.', ['path', 'content']),
         tool_schema('run_command', 'Run the installed verified policy loader or python3 -m unittest -q. No other commands or shell syntax.', ['command'])]


def serve(config):
    fixture = FixtureTools(config)
    while True:
        line = sys.stdin.buffer.readline(2*LIMIT+1)
        if not line: return
        if len(line) > 2*LIMIT: raise ValueError('MCP frame too large')
        req = json.loads(line)
        if not isinstance(req, dict): raise ValueError('invalid MCP frame')
        if 'id' not in req: continue
        method = req.get('method')
        if method == 'initialize':
            result = {'protocolVersion': '2025-06-18', 'capabilities': {'tools': {}},
                      'serverInfo': {'name': 'aiscb-context-fixture', 'version': '1.0.0'}}
        elif method == 'ping': result = {}
        elif method == 'tools/list': result = {'tools': TOOLS}
        elif method == 'tools/call':
            params = req.get('params', {})
            result = fixture.call(params.get('name'), params.get('arguments', {}))
        else:
            print(json.dumps({'jsonrpc': '2.0', 'id': req['id'], 'error': {
                'code': -32601, 'message': 'Method not found'}}), flush=True)
            continue
        print(json.dumps({'jsonrpc': '2.0', 'id': req['id'], 'result': result}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('config'); args = parser.parse_args()
    serve(json.loads(Path(args.config).read_text()))
