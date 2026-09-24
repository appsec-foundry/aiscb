#!/usr/bin/env python3
"""Boundary and scoring tests for the optional context experiment."""
from contextlib import nullcontext, redirect_stdout
import io
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

    def test_unittest_command_runs_only_in_the_sandbox_and_reports_its_exit(self):
        with patch.object(tools,'execute',side_effect=[(0,'OK'),(1,'FAILED')]) as run:
            passed=self.tool.call('run_command',{'command':'python3 -m unittest -q'})
            failed=self.tool.call('run_command',{'command':'python3 -m unittest -q'})
        self.assertFalse(passed['isError']); self.assertTrue(failed['isError'])
        self.assertEqual(passed['content'][0]['text'],'Exit 0\nOK')
        self.assertEqual(run.call_args.args[0][0],'/usr/bin/bwrap')
        self.assertEqual([e.get('test_exit') for e in comparison.audits(self.base/'case')[-2:]],[0,1])

    def test_execution_timeout_is_reported_not_raised(self):
        code,text=tools.execute([sys.executable,'-c','import time; time.sleep(30)'],timeout=0.3)
        self.assertEqual((code,text),(124,'Execution timed out.'))

    def serve(self, frames):
        stdin=Mock(); stdin.buffer=io.BytesIO(frames)
        out=io.StringIO()
        with patch.object(tools.sys,'stdin',stdin), redirect_stdout(out):
            tools.serve(self.config)
        return [json.loads(line) for line in out.getvalue().splitlines()]

    def test_server_answers_protocol_methods_and_rejects_unknown_ones(self):
        frames=[{'jsonrpc':'2.0','id':1,'method':'initialize'},
                {'jsonrpc':'2.0','method':'notifications/initialized'},
                {'jsonrpc':'2.0','id':2,'method':'ping'},
                {'jsonrpc':'2.0','id':3,'method':'resources/list'},
                {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'read_file','arguments':{'path':'labels.py'}}}]
        replies=self.serve(''.join(json.dumps(f)+'\n' for f in frames).encode())
        self.assertEqual([r['id'] for r in replies],[1,2,3,4])
        self.assertEqual(replies[0]['result']['serverInfo']['name'],'aiscb-context-fixture')
        self.assertEqual(replies[1]['result'],{})
        self.assertEqual(replies[2]['error']['code'],-32601)
        self.assertFalse(replies[3]['result']['isError'])

    def test_server_refuses_oversized_and_non_object_frames(self):
        with self.assertRaisesRegex(ValueError,'too large'):
            self.serve(b'x'*(2*tools.LIMIT+1))
        with self.assertRaisesRegex(ValueError,'invalid MCP frame'):
            self.serve(b'[]\n')

    def test_command_separates_preflight_tools_and_resumes_later_turns(self):
        first=comparison.command(self.base,'m','s',1,'prompt')
        preflight=comparison.command(self.base,'m','s',1,'prompt',preflight=True)
        later=comparison.command(self.base,'m','s',2,'prompt')
        self.assertIn('--allowedTools',first); self.assertNotIn('--disallowedTools',first)
        self.assertIn('--disallowedTools',preflight); self.assertNotIn('--allowedTools',preflight)
        self.assertEqual(first[-2:],['--session-id','s']); self.assertEqual(later[-2:],['--resume','s'])

    def test_timeout_is_incomplete_and_non_json_lines_are_ignored(self):
        log=self.base/'cli.jsonl'
        trace=comparison.capture([sys.executable,'-c','import time; time.sleep(30)'],self.base,log,0.3)
        self.assertEqual(trace['exit'],124); self.assertFalse(trace['complete'])
        script=("import json; print('progress text'); print(json.dumps({'type':'result','subtype':'success',"
                "'result':'ok','usage':{'input_tokens':1,'cache_creation_input_tokens':2,"
                "'cache_read_input_tokens':3,'output_tokens':4}}))")
        trace=comparison.capture([sys.executable,'-c',script],self.base,log,5)
        self.assertTrue(trace['complete']); self.assertEqual(trace['total_tokens'],10)
        self.assertEqual(len(trace['events']),1)

    def test_cancellation_tolerates_an_already_exited_process_group(self):
        proc=Mock(pid=12345); proc.wait.side_effect=[KeyboardInterrupt,0]
        with patch.object(comparison.subprocess,'Popen',return_value=proc), \
             patch.object(comparison.os,'killpg',side_effect=ProcessLookupError):
            with self.assertRaises(KeyboardInterrupt):
                comparison.capture(['unused'],self.base,self.base/'cancel.jsonl',5)
        self.assertEqual(proc.wait.call_count,2)

    def test_new_tests_in_a_documentation_task_count_as_scope_change(self):
        base=self.base/'docs'; root,config,_=comparison.prepare(base,'documentation','control')
        (root/'test_extra.py').write_text('pass\n')
        with patch.object(comparison,'execute',return_value=(0,'')):
            result=comparison.assess('documentation','control',1,base,config)
        self.assertEqual(result['scope_changes'],['test_extra.py'])
        self.assertIsNone(result['missing']); self.assertIsNone(result['late'])

    def test_report_keeps_incomplete_runs_and_unknown_usage_visible(self):
        def run(arm, complete, tokens, friction):
            turn={'assessment':{'functional_pass':True,'scope_changes':[],'missing':[],'late':[]},
                  'total_tokens':tokens,'seconds':2.0}
            return {'case':'documentation','arm':arm,'complete':complete,'turns':[turn],'friction':friction}
        runs=[run('control',True,100,[{'verdict':'pass'},{'verdict':'fail'}]),
              run('modular',True,None,None), run('modular',False,50,None)]
        plan={'model':'m','repeats':2,'seed':1,'cases':['documentation']}
        comparison.write_report(self.base,runs,plan)
        report=(self.base/'report.md').read_text()
        self.assertIn('| documentation | control | 1/1 | 1/1 | — | — | 100 | 2.0 | 0/1 scored | 1/1 scored |',report)
        self.assertIn('| documentation | modular | 1/2 | 1/2 | 0 | 0 | unknown | 2.0 | 0/0 scored | 0/0 scored |',report)
        self.assertNotIn('| documentation | complete |',report)
        self.assertEqual(json.loads((self.base/'runs.json').read_text()),runs)

    def test_sandbox_check_raises_when_isolation_fails(self):
        with patch.object(comparison,'execute',return_value=(0,'')) as run:
            comparison.verify_sandbox()
        oracle=Path(run.call_args.args[0][run.call_args.args[0].index('/oracle.py')-1])
        self.assertTrue(oracle.name=='oracle.py')
        with patch.object(comparison,'execute',return_value=(1,'host network reachable')):
            with self.assertRaisesRegex(ValueError,'isolation failed: host network reachable'):
                comparison.verify_sandbox()


class ContextMainTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='aiscb-context-main-')
        self.addCleanup(self.tmp.cleanup)
        self.base=Path(self.tmp.name)
        # main() swaps the installer's policy root for its snapshot.
        root=patch.object(comparison.install_policy,'ROOT',comparison.install_policy.ROOT)
        root.start(); self.addCleanup(root.stop)
        self.bwrap=self.base/'bwrap'; self.bwrap.write_bytes(b'fake bwrap')

    def main(self, *argv):
        out,err=io.StringIO(),io.StringIO()
        real=Path
        # A stand-in tokenizer: the real one may be absent or download its data.
        tokenizer=Mock(); tokenizer.get_encoding.return_value.encode=str.split
        with patch.object(comparison.sys,'argv',['context_comparison.py',*argv]), \
             patch.dict(sys.modules,{'tiktoken':tokenizer}), \
             patch.object(comparison,'Path',side_effect=lambda *a: self.bwrap if a==('/usr/bin/bwrap',) else real(*a)), \
             redirect_stdout(out), patch.object(comparison.sys,'stderr',err):
            try: code=comparison.main()
            except SystemExit as exit: code=exit.code
        return code,out.getvalue(),err.getvalue()

    def test_sandbox_check_dry_run_and_invalid_matrix_start_no_runs(self):
        with patch.object(comparison,'verify_sandbox') as verify:
            code,out,_=self.main('--check-sandbox')
        self.assertEqual(code,0); verify.assert_called_once(); self.assertIn('isolation passed',out)
        code,out,_=self.main('--dry-run','--repeats','2','--cases','documentation,bugfix')
        plan=json.loads(out)
        self.assertEqual((code,plan['runs'],len(plan['matrix'])),(0,12,12))
        self.assertEqual(plan['core_sha256'],comparison.digest((comparison.ROOT/'baseline/aiscb-core.md').read_bytes()))
        for argv in (('--repeats','0'),('--cases','unknown'),('--timeout','0')):
            self.assertEqual(self.main(*argv)[0],2)

    def fake_capture(self, reply_for_baseline):
        def capture(cmd, cwd, path, timeout):
            baseline='control' not in Path(cwd).parent.name
            reply=reply_for_baseline if '-p' in cmd and cmd[cmd.index('-p')+1]==comparison.runner.PROBE_PROMPT and baseline else 'done'
            path.write_text('{}\n')
            return {'complete':True,'exit':0,'reply':reply,'total_tokens':7,'seconds':1.0,'events':[]}
        return capture

    def test_matrix_runs_every_arm_after_preflight_and_writes_evidence(self):
        out_dir=self.base/'evidence'
        baseline_id=json.loads((comparison.ROOT/'baseline/catalog.json').read_text())['baseline_id']
        judge=[{'verdict':'pass'},{'verdict':'pass'}]
        with patch.object(comparison,'verify_sandbox'), \
             patch.object(comparison,'isolated_profile',nullcontext), \
             patch.object(comparison,'capture',side_effect=self.fake_capture(baseline_id)), \
             patch.object(comparison,'execute',return_value=(0,'')), \
             patch.object(comparison.runner,'judge_with_votes',return_value=judge) as votes:
            code,out,_=self.main('--repeats','1','--cases','documentation','--output',str(out_dir))
        self.assertEqual(code,0)
        runs=json.loads((out_dir/'runs.json').read_text())
        self.assertEqual(sorted(r['arm'] for r in runs),sorted(comparison.ARMS))
        self.assertTrue(all(r['complete'] and r['friction']==judge for r in runs))
        self.assertEqual(votes.call_count,3)
        plan=json.loads((out_dir/'plan.json').read_text())
        self.assertEqual(plan['baseline_id'],baseline_id)
        self.assertEqual(plan['bwrap_sha256'],comparison.digest(b'fake bwrap'))
        self.assertTrue((out_dir/'policy-snapshot/scripts/policy_loader.py').is_file())
        self.assertTrue(all(json.loads((out_dir/f'preflight-{a}.json').read_text())['passed'] for a in comparison.ARMS))
        self.assertIn('3/3 ',out)
        modular=next(r for r in runs if r['arm']=='modular')
        self.assertGreater(modular['initial_policy']['o200k_base_tokens'],0)

    def test_preflight_without_the_expected_baseline_stops_before_tasks(self):
        with patch.object(comparison,'verify_sandbox'), \
             patch.object(comparison,'isolated_profile',nullcontext), \
             patch.object(comparison,'capture',side_effect=self.fake_capture('no id')), \
             patch.object(comparison,'assess') as assess:
            code,_,_=self.main('--repeats','1','--cases','documentation','--output',str(self.base/'evidence'))
        self.assertEqual(code,'Preflight failed; no task runs started.')
        assess.assert_not_called()


if __name__=='__main__': unittest.main()
