import tempfile
import unittest
from pathlib import Path
from bridge_harness.selfplay import atomic_json
from bridge_harness.loop_registry import sha
from ops.shared_bidding import prepare_shared_bidder,bind_shared_bidder


class SharedBiddingTests(unittest.TestCase):
    def test_all_versions_share_frozen_latest_and_reject_mutation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);model=root/'latest.keras';model.write_bytes(b'fixture-actor')
            cfg=root/'base.conf';cfg.write_text('[bidding]\nbidder=old.keras\nalert_supported=False\nsearch_threshold=-1\ncheck_final_contract=False\n')
            registry=root/'registry.json';atomic_json(registry,dict(model=str(model),sha256=sha(model),trained_pairs=40000))
            config=dict(bidding_registry=str(registry),ben_config=str(cfg))
            shared=prepare_shared_bidder(root/'generation',config)
            bots={v:dict(id=v,artifact_sha256={}) for v in ('new','prior','older')}
            bind_shared_bidder(bots,shared)
            self.assertEqual({v['bidding'] for v in bots.values()},{shared['model']})
            self.assertEqual({v['artifact_sha256']['bidding'] for v in bots.values()},{sha(model)})
            self.assertEqual(prepare_shared_bidder(root/'generation',config),shared)
            (root/'generation'/shared['model']).write_bytes(b'changed')
            with self.assertRaises(ValueError):prepare_shared_bidder(root/'generation',config)


if __name__=='__main__':unittest.main()
