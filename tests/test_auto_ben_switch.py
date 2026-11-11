from copy import deepcopy
import configparser
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from bridge_harness.corpus import generate,load
from bridge_harness.bidding_env import deal_key
from bridge_harness.loop_registry import sha
from bridge_harness.mixed_arena import verify_generation
from bridge_harness.selfplay import atomic_json
from bridge_harness.training import digest
from bridge_harness.gen5_arena import run_board
from ops.auto_ben_switch import paired_evidence,tick,dashboard_patch
from ops.gen5_runtime import ben_pair
from ops.prepare_gen6_ben_expansion import build,prepare
from ops.prepare_ben_round5 import OVERRIDES
from ops.watch_gen5 import ben_services
from tests.test_gen6_launch import source_run


def row(i,value,pair='6-256~ben',family=None):
    return dict(index=i,id=str(i),family=family or str(i),pair=pair,own_imps=value,imps=0,completed_epoch=i)


def snapshot(rows,cohort='one'):
    return dict(cohort=cohort),dict(manifest_identity=cohort,generated_epoch=100,completed=len(rows)),rows


class AutoBenTests(unittest.TestCase):
    def test_freeze_preserves_completed_evidence_and_excludes_its_family(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);source=tmp/'source';m=source_run(source)
            for key,samples in [('6-32',32),('6-256',256),('2',32),('1',32)]:
                spec=deepcopy(m['bots']['5RZ32']);spec.pop('identity');spec.update(id=key,samples=samples)
                spec['identity']=digest(spec);m['bots'][key]=spec
            (source/'assets/ben-16.conf').write_text('old profile')
            b=deepcopy(m['bots']['5RZ32']);b.pop('identity');b.update(id='ben16',engine='ben',samples=16,url='http://127.0.0.1:8087',config='assets/ben-16.conf')
            b['artifact_sha256']['config']=sha(source/b['config']);b['identity']=digest(b);m['bots']['ben']=b
            m.update(variant='6',model_note='Gen6',labels={k:k for k in m['bots']},order=list(m['bots']),interpretation='Paired',pair_weights={'6-32~5RZ32':8,'6-32~6-256':3,'6-256~ben':3,'6-32~3':2,'6-32~2':2,'6-32~1':2})
            m.pop('identity');m['identity']=digest(m);atomic_json(source/'manifest.json',m)
            boards=list(load(source/'corpus.jsonl'));episode=source/'episodes/000000.json.gz';atomic_json(episode,{'saved':'unchanged'},compressed=True);before=episode.read_bytes()
            atomic_json(source/'receipts/000000.json',dict(index=0,manifest_identity=m['identity'],family=deal_key(boards[0].hands,True),episode_sha256=sha(episode)))
            profile=tmp/'32.conf';c=configparser.ConfigParser();c.read_dict(OVERRIDES)
            with profile.open('w') as f:c.write(f)
            n=prepare(tmp/'new',source,profile,{'significant':True,'ci':[.1,1.]});verify_generation(tmp/'new',n)
            self.assertEqual(n['target'],5);self.assertEqual(n['source_completed'],1)
            self.assertEqual(json.loads((tmp/'new/source-indices.json').read_text()),[1,2,3,4,5])
            self.assertEqual(episode.read_bytes(),before)
            for k,spec in m['bots'].items():self.assertEqual(n['bots'][k],spec)

    def test_trigger_uses_total_with_paired_uncertainty_and_deduplicates(self):
        data=[row(i,5+(i%3)) for i in range(20)]
        s=paired_evidence([snapshot(data),snapshot([dict(data[0],own_imps=-100)],'two')])
        self.assertEqual(s['n'],20);self.assertTrue(s['significant']);self.assertGreater(s['ci'][0],0)
        self.assertFalse(paired_evidence([snapshot(data)],'play')['significant'])
        self.assertFalse(paired_evidence([snapshot([row(0,0),row(1,1),row(2,-1)])])['significant'])
        self.assertFalse(paired_evidence([snapshot([row(0,10)])])['significant'])
        reversed_s=paired_evidence([snapshot([row(i,-5,'ben~6-256') for i in range(20)])])
        self.assertEqual(reversed_s['mean'],5);self.assertTrue(reversed_s['significant'])

    def test_no_trigger_leaves_run_alone_and_trigger_durably_drains(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);source=tmp/'source';source.mkdir();(source/'manifest.json').write_text('{}')
            control=tmp/'control';control.mkdir();c=dict(source=str(source),control=str(control),target=str(tmp/'new'),condition='total')
            with patch('ops.auto_ben_switch.evidence',return_value=dict(significant=False)):
                state=tick(c,dict(phase='watching'))
            self.assertEqual(state['phase'],'watching');self.assertFalse((source/'STOP').exists())
            with patch('ops.auto_ben_switch.evidence',return_value=dict(significant=True,n=100,ci=[1,2])),patch('ops.auto_ben_switch.free',return_value=False):
                state=tick(c,state)
            self.assertEqual(state['phase'],'draining');self.assertTrue((source/'STOP').exists());self.assertTrue((source/'WATCHDOG_STOP').exists())
            self.assertTrue((control/'trigger.json').exists())

    def test_exact_allocation_and_separate_ben32_service(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile=Path(tmp)/'32.conf';c=configparser.ConfigParser();c.read_dict(OVERRIDES)
            with profile.open('w') as f:c.write(f)
            old=dict(variant='6',identity='old',pair_weights={'6-32~5RZ32':8,'6-32~6-256':3,'6-256~ben':3,'6-32~3':2,'6-32~2':2,'6-32~1':2},
                bots={'ben':dict(id='ben16',identity='ben16',samples=16,engine='ben',url='http://127.0.0.1:8087',config='assets/ben-16.conf',artifact_sha256={'config':'old'})},
                roster=['6-32','6-256','ben'],order=['6-32','6-256','ben'],labels={'ben':'BEN (16)'},audit_references={},model_note='Gen6')
            n=build(old,profile)
            self.assertEqual(n['bots']['ben'],old['bots']['ben']);self.assertEqual(n['bots']['ben32']['samples'],32)
            self.assertNotIn('6-256~ben',n['pair_weights']);self.assertEqual(sum(n['pair_weights'].values()),40)
            self.assertEqual(n['pair_weights']['6-256~ben32'],3);self.assertEqual(n['pair_weights']['6-32~ben'],3)
            self.assertEqual(n['pair_weights']['6-32~5RZ32'],16)
            self.assertEqual(set(ben_services(n,Path(tmp))),{8087,8088})
            n['bots']['6-256']={}
            self.assertTrue(ben_pair(n,'6-256~ben32'))

    def test_positive_trigger_runs_entire_handoff_and_does_not_repeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);source=tmp/'source';source.mkdir();control=tmp/'control';control.mkdir()
            (source/'manifest.json').write_text(json.dumps({'identity':'old'}));(source/'state.json').write_text(json.dumps({'completed':123}))
            c=dict(source=str(source),control=str(control),target=str(tmp/'new'),condition='total',source_checkout=str(tmp),source_publication=str(tmp/'pub'),profile32='32.conf',python='python',publication=str(tmp/'next-pub'),branch='new-feed',ben_dir=str(tmp/'ben'))
            def freeze(root,*args):
                root.mkdir();(root/'manifest.json').write_text(json.dumps({'identity':'new','source_generation':'old'}));return {'identity':'new'}
            with patch('ops.auto_ben_switch.evidence',return_value=dict(significant=True,n=123,ci=[.1,1.])),patch('ops.auto_ben_switch.free',return_value=True),patch('ops.auto_ben_switch.alive',return_value=False),patch('ops.auto_ben_switch.command',return_value='revision'),patch('ops.auto_ben_switch.prepare',side_effect=freeze) as prep,patch('ops.auto_ben_switch.initialize_publication'),patch('ops.auto_ben_switch.publish_dashboard',return_value='dashboard-sha') as dash,patch('ops.auto_ben_switch.launch') as launch:
                s=tick(c,{'phase':'watching'});self.assertEqual(s['phase'],'switched')
                tick(c,s);self.assertEqual(prep.call_count,1);self.assertEqual(dash.call_count,1);self.assertEqual(launch.call_count,1)
            self.assertTrue((source/'PUBLISH_STOP').exists())
            self.assertEqual(json.loads((source/'statistics-policy.json').read_text())['target'],123)

    def test_ben32_uses_ben_audit_budget(self):
        board=next(generate(1,342));seen=[]
        bots={k:dict(id=k,identity=k,engine='ben' if k=='ben32' else '') for k in ('6-256','ben32','3')}
        m=dict(identity='test',roster=['6-256','3'],target=1,seed=11,bots=bots,pair_schedule=['6-256~ben32'],audit_references={'6-256':'3'},common_bidder='6-256',audit=dict(probability=1,multiplier=3,max_depth=2,max_forks=64),ben_audit=dict(probability=0,multiplier=1,max_depth=0,max_forks=0))
        class Player:
            def close(self):pass
        def collector(b,players,assignments,seed,budget,versions):
            seen.append(budget.probability)
            return dict(schema_version='v4-passed-out-v1',board=b.to_dict(),assignments=assignments,tables=[dict(ns_score=0,actions=[])],audits=[])
        with patch('bridge_harness.gen5_arena.auction',lambda b,actors:(b,[])):
            run_board('.',m,board.to_dict(),0,{k:object() for k in bots},player_factory=lambda *a:Player(),collector=collector)
        self.assertTrue(seen);self.assertEqual(set(seen),{0})


if __name__=='__main__':unittest.main()
