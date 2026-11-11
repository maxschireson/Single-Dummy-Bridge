from copy import deepcopy
import configparser
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bridge_harness.bidding_env import deal_key
from bridge_harness.corpus import load
from bridge_harness.gen6 import Gen6Config
from bridge_harness.loop_registry import sha
from bridge_harness.training import digest
from ops.prepare_gen6_ben_followups import prepare
from ops.watch_gen6_ben_gate import evaluate,merge_records
from ops import watch_gen6_ben_gate as controller
from ops.publish_gen5 import publish
from ops.watch_v7_logging_updates import relevant
from tests.test_gen6_launch import source_run

ROOT=Path(__file__).resolve().parents[1]


class FollowupTests(unittest.TestCase):
    def test_gate_uses_total_and_requires_enough_independent_deals(self):
        gate=dict(alpha=.05,minimum_deals=200,note='test')
        positive=[dict(value=1+i%2) for i in range(200)]
        self.assertFalse(evaluate(positive[:199],gate)['qualified'])
        self.assertTrue(evaluate(positive,gate)['qualified'])
        self.assertFalse(evaluate([dict(value=-1+i%2) for i in range(200)],gate)['qualified'])
        self.assertFalse(evaluate([dict(value=2) for _ in range(200)],gate)['qualified'])

    def test_reexports_keep_the_earliest_family_without_erasing_old_cohorts(self):
        old=[dict(family='a',completed_epoch=1,cohort='old',index=0,value=-2)]
        new=[dict(family='a',completed_epoch=2,cohort='new',index=1,value=20),
             dict(family='b',completed_epoch=3,cohort='new',index=2,value=1)]
        merged=merge_records(old,new)
        self.assertEqual(len(merged),2);self.assertEqual(merged[0]['value'],-2)
        self.assertEqual(merge_records(merged,[]),merged)

    def test_published_gate_values_use_native_total_even_when_play_is_positive(self):
        gate=json.loads((ROOT/'configs/round6-ben-followups.json').read_text())['gate'];cohort='c'*64
        manifest={'generation':6,'identity':cohort,'common_bidder':'6-32','bots':{
            '6-256':{'identity':gate['medium_identity']},'6-32':{'identity':gate['fast_identity']},'ben':{'identity':gate['ben16_identity']}}}
        row=dict(pair='6-256~ben',imps=15,own_imps=-2,index=1,family='f'*64,completed_epoch=1,episode_sha256='d'*64)
        data=dict(manifest_identity=cohort,generated_epoch=2,completed=1,own_views={'0':{'groups':{'6-256~ben':{'n':1,'total':-2}}}})
        index=dict(cohort=cohort,records=[row])
        def response(url):return json.dumps(manifest if url.endswith('manifest.json') else data if url.endswith('data.json') else index).encode()
        with patch.object(controller,'request',side_effect=response):
            rows,_=controller.source_records('test','a'*40,gate)
        self.assertEqual(rows[0]['value'],-2)
        data['own_views']['0']['groups']['6-256~ben']['total']=99
        with patch.object(controller,'request',side_effect=response),self.assertRaises(ValueError):controller.source_records('test','a'*40,gate)

    def test_preflight_cannot_publish_and_untracked_logs_do_not_create_empty_commits(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'manifest.json').write_text(json.dumps({'preflight_only':True}))
            with self.assertRaises(ValueError):publish(root,root/'out')
            (root/'.git').mkdir();(root/'status.json').write_text('{}');(root/'controller.log').write_text('untracked')
            with patch.object(controller,'git',return_value='') as mocked:
                controller.publish_control(root)
            self.assertFalse(any('commit' in call.args for call in mocked.call_args_list))

    def test_v7_observer_recognizes_logging_or_forking_updates(self):
        self.assertTrue(relevant('transfer/v7-logging',{'files':[]}))
        self.assertTrue(relevant('transfer/gen6-launch-package',{'files':[{'filename':'bridge_harness/fork_audit.py'}]}))
        self.assertFalse(relevant('research/policy-fit',{'commit':{'message':'Save training chart'},'files':[{'filename':'reports/loss.png'}]}))

    def test_ben32_changes_only_sample_counts_and_keeps_neural_bidding(self):
        before=configparser.ConfigParser();before.read(ROOT/'configs/ben-gen5-16.conf')
        after=configparser.ConfigParser();after.read(ROOT/'configs/ben-gen6-32.conf')
        changes={(s,k) for s in before for k in before[s] if before[s][k]!=after[s][k]}
        expected={('cardplay','sample_hands_play'),('cardplay','min_sample_hands_play'),('cardplay','min_sample_hands_play_bad'),
                  ('sampling','sample_hands_opening_lead'),('sampling','sample_hands_for_review')}
        self.assertEqual(changes,expected)
        for s,k in changes:self.assertEqual(after[s][k],'32')
        self.assertEqual(after['bidding']['search_threshold'],'-1')
        self.assertEqual(after['bidding']['no_search_threshold'],'1')

    def test_freeze_preserves_gen6_actors_and_only_consumes_unplayed_families(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);source=root/'source';old=source_run(source)
            bots=old['bots']
            for key,n,cut in [('6-32',32,7),('6-256',256,6)]:
                b=deepcopy(bots['5RZ32']);b.pop('identity');b.update(id=key,engine='gen6',samples=n,
                    gen6=asdict(Gen6Config(mid_from_trick=14,mid_samples=n,list_from_trick=cut)))
                b['identity']=digest(b);bots[key]=b
            (source/'assets/ben-16.conf').write_bytes((ROOT/'configs/ben-gen5-16.conf').read_bytes())
            b=dict(id='ben-16',engine='ben',url='http://127.0.0.1:8087',samples=16,bidding='artifacts/v5/bidder.keras',config='assets/ben-16.conf',
                artifact_sha256=dict(bidding=sha(source/'artifacts/v5/bidder.keras'),config=sha(source/'assets/ben-16.conf')))
            b['identity']=digest(b);bots['ben']=b
            old.update(generation=6,labels={k:k for k in bots});old.pop('identity');old['identity']=digest(old)
            (source/'manifest.json').write_text(json.dumps(old))
            boards=load(source/'corpus.jsonl');episode=source/'episodes/000001.json.gz';episode.write_bytes(b'completed fixture')
            receipt=dict(index=1,manifest_identity=old['identity'],family=deal_key(boards[1].hands,True),episode_sha256=sha(episode))
            (source/'receipts/000001.json').write_text(json.dumps(receipt))
            plan=json.loads((ROOT/'configs/round6-ben-followups.json').read_text())
            plan.update(roster=['6-32','6-256','5RZ32','3','ben','ben32'],pair_weights={'6-256~ben32':1,'6-32~ben':1})
            plan['gate'].update(fast_identity=bots['6-32']['identity'],medium_identity=bots['6-256']['identity'],ben16_identity=bots['ben']['identity'])
            path=root/'plan.json';path.write_text(json.dumps(plan))
            run=root/'run';m=prepare(run,source,path)
            self.assertEqual(m['target'],5);self.assertEqual(json.loads((run/'source-indices.json').read_text()),[0,2,3,4,5])
            for key in ('6-32','6-256','ben'):self.assertEqual(m['bots'][key],bots[key])
            self.assertEqual(m['bots']['ben32']['samples'],32)
            self.assertEqual(m['bots']['ben32']['artifact_sha256']['bidding'],bots['ben']['artifact_sha256']['bidding'])
            with self.assertRaises(ValueError):prepare(run,source,path)
            (source/'STOP').unlink()
            with self.assertRaises(ValueError):prepare(root/'live-refused',source,path)
            staging=prepare(root/'stage',source,path,preflight=True)
            self.assertTrue(staging['preflight_only']);self.assertEqual(staging['target'],6)


if __name__=='__main__':unittest.main()
