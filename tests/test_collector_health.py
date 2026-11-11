import fcntl
import json
from pathlib import Path
import tempfile
import unittest
from ops.export_gen5 import collection_status,gen6_differences
from ops.gen5_runtime import validate


class CollectorHealthTests(unittest.TestCase):
    def test_owner_lock_and_fresh_heartbeat_are_both_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);hb=dict(epoch=995,workers=4)
            (root/'heartbeat.json').write_text(json.dumps(hb))
            self.assertEqual(collection_status(root,hb,1000,{},1,10)['status'],'not_running')
            with (root/'.writer.lock').open('a+') as guard:
                fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
                value=collection_status(root,dict(epoch=1),1000,{},1,10)
                self.assertEqual(value['status'],'running');self.assertTrue(value['running'])
                self.assertEqual(collection_status(root,hb,1200,{},1,10)['status'],'heartbeat_overdue')
                (root/'STOP').write_text('Intentional drain')
                self.assertEqual(collection_status(root,hb,1000,{},1,10)['status'],'draining')
            self.assertEqual(collection_status(root,hb,1000,{},1,10)['status'],'stopped')
            self.assertEqual(collection_status(root,hb,1000,{'retired':True},1,10)['status'],'archived')

    def test_selfplay_requires_null_strength_outcomes(self):
        m=dict(identity='fixture',pair_schedule=['6-32~6-32'],seed=1,bots={'6-32':{'identity':'actor'}},common_bidder='6-32')
        e=dict(manifest_identity='fixture',index=0,pair='6-32~6-32',candidate='6-32',opponent='6-32',versions={'6-32':'actor'},
            regimes={'self':{'tables':['root'],'score_difference':None,'imps':None}},
            unique_tables={'root':{'schema_version':'v4-passed-out-v1','assignments':['candidate']*4,'board':{'auction':[]}}},
            bidding={'self/0':{'bidders':['6-32']*4,'calls':[]}})
        validate(e,m,0)
        self.assertEqual(gen6_differences(dict(imps=None,own_imps=None)),dict(play=None,bidding=None,total=None))
        e['regimes']['self']['imps']=0
        with self.assertRaises(ValueError):validate(e,m,0)


if __name__=='__main__':unittest.main()
