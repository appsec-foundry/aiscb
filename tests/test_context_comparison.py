#!/usr/bin/env python3
"""Boundary and scoring tests for the optional context experiment."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import context_comparison as comparison
import context_tools as tools


class ContextTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='aiscb-context-unit-')
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        self.root,self.config,self.initial=comparison.prepare(self.base/'case','bugfix','modular')
        self.tool=tools.FixtureTools(self.config)

    def test_reads_and_writes_only_fixture_files(self):
        self.assertFalse(self.tool.call('read_file',{'path':'labels.py'})['isError'])
        self.assertFalse(self.tool.call('write_file',{'path':'test_labels.py','content':'# local test\n'})['isError'])
        for name in ('../config.json','/etc/passwd','CLAUDE.md','.aiscb/policy.json','nested/test_x.py'):
            self.assertTrue(self.tool.call('write_file',{'path':name,'content':'bad'})['isError'],name)
        self.assertEqual((self.root/'CLAUDE.md').read_text(),self.initial)

    def test_rejects_symlinks_other_roots_unknown_fields_and_limits(self):
        (self.root/'test_link.py').symlink_to(self.base/'secret')
        for args in ({'path':'test_link.py'}, {'path':'labels.py','extra':True}, {'path':None}, {'path':'../labels.py'}):
            self.assertTrue(self.tool.call('read_file',args)['isError'])
        self.assertTrue(self.tool.call('write_file',{'path':'labels.py','content':'x'*(tools.LIMIT+1)})['isError'])
        self.assertTrue(self.tool.call('delete_file',{'path':'labels.py'})['isError'])
        self.tool.calls=80
        self.assertTrue(self.tool.call('read_file',{'path':'labels.py'})['isError'])

    def test_loader_is_verified_and_shell_syntax_never_executes(self):
        import shlex
        prefix=shlex.join(self.config['loader'])
        response=self.tool.call('run_command',{'command':prefix+' aiscb:mcp-clients-servers'})
        self.assertFalse(response['isError'])
        event=comparison.audits(self.base/'case')[-1]
        self.assertEqual(event['loaded'],['aiscb:data-handling','aiscb:mcp-clients-servers'])
        with patch.object(tools,'execute',side_effect=AssertionError('must not execute')):
            for cmd in (prefix+' unknown', prefix+' aiscb:data-handling; echo bad',
                        'cat /etc/passwd', 'python3 -c "print(1)"', 'python3 -m unittest -q && echo bad'):
                self.assertTrue(self.tool.call('run_command',{'command':cmd})['isError'])
        script=Path(self.config['loader'][1]); script.with_name('modules').joinpath('aiscb-data-handling.md').write_text('tampered')
        self.assertTrue(self.tool.call('run_command',{'command':prefix+' aiscb:data-handling'})['isError'])

    def test_unknown_tool_arguments_fail_closed(self):
        for args in (None,[],True,'text'):
            self.assertTrue(self.tool.call('read_file',args)['isError'])
        self.assertTrue(self.tool.call('run_command',{'command':[]})['isError'])

    def test_transport_lists_and_calls_actual_tools(self):
        request=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}},
                 {'jsonrpc':'2.0','method':'notifications/initialized'},
                 {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                 {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'read_file','arguments':{'path':'labels.py'}}},
                 {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'write_file','arguments':{'path':'../bad','content':'bad'}}}]
        proc=subprocess.run([sys.executable,str(Path(tools.__file__)),str(self.base/'case/config.json')],
                            input=''.join(json.dumps(r)+'\n' for r in request),capture_output=True,text=True,
                            env={'PATH':os.environ['PATH']},timeout=10)
        self.assertEqual(proc.returncode,0,proc.stderr)
        replies=[json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual([r['id'] for r in replies],[1,2,3,4])
        self.assertEqual(len(replies[1]['result']['tools']),3)
        self.assertFalse(replies[2]['result']['isError']); self.assertTrue(replies[3]['result']['isError'])

    def test_arms_are_distinct_and_read_only_policy_not_initial_modules(self):
        for arm in comparison.ARMS:
            _,config,initial=comparison.prepare(self.base/arm,'documentation',arm)
            self.assertEqual('baseline-id:' in initial,arm!='control')
            self.assertEqual('[aiscb-FILES-001]' in initial,arm=='complete')
            self.assertEqual(bool(config['loader']),arm=='modular')

    def test_unknown_usage_is_not_zero_and_errors_are_incomplete(self):
        log=self.base/'cli.jsonl'
        script="import json; print(json.dumps({'type':'result','subtype':'success','result':'done'}))"
        trace=comparison.capture([sys.executable,'-c',script],self.base,log,5)
        self.assertTrue(trace['complete']); self.assertIsNone(trace['total_tokens'])
        trace=comparison.capture([sys.executable,'-c','raise SystemExit(1)'],self.base,log,5)
        self.assertFalse(trace['complete'])

    def test_late_and_missing_are_not_confused(self):
        base=self.base/'endpoint'; root,config,_=comparison.prepare(base,'endpoint','modular')
        entries=[{'turn':1,'tool':'write_file','error':False,'path':'orders.py'},
                 {'turn':1,'tool':'run_command','error':False,'loaded':['aiscb:web','aiscb:data-handling']}]
        (base/'audit.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in entries))
        with patch.object(comparison,'execute',return_value=(0,'')):
            result=comparison.assess('endpoint','modular',1,base,config)
        self.assertFalse(result['missing']); self.assertEqual(len(result['late']),2)

    def test_cancellation_kills_cli_process_group_and_reaps_child(self):
        proc = Mock(pid=12345)
        proc.wait.side_effect = [KeyboardInterrupt, -signal.SIGKILL]
        with patch.object(comparison.subprocess, 'Popen', return_value=proc), \
             patch.object(comparison.os, 'killpg') as kill:
            with self.assertRaises(KeyboardInterrupt):
                comparison.capture(['unused'], self.base, self.base/'cancel.jsonl', 5)
        kill.assert_called_once_with(12345, signal.SIGKILL)
        self.assertEqual(proc.wait.call_count, 2)

    def test_sandbox_rejects_symlinks_before_setup(self):
        (self.root/'escape').symlink_to('/oldroot')
        with self.assertRaises(ValueError): tools.sandbox_args(self.root)

    def test_sandbox_definition_has_no_host_home_network_or_writable_project(self):
        argv=tools.sandbox_args(self.root)
        self.assertIn('--unshare-all',argv); self.assertIn('--clearenv',argv)
        i=argv.index(str(self.root)); self.assertEqual(argv[i-1],'--ro-bind')
        self.assertNotIn('--share-net',argv); self.assertNotIn('--bind',argv)
        self.assertNotIn(str(Path.home()),argv)


if __name__=='__main__': unittest.main()
