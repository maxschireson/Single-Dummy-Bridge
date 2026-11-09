"""Play missing bidding outcomes once with a frozen clean cardplay bot."""
from dataclasses import replace
import gzip
import json
from pathlib import Path
import time
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

from .bidding_env import deal_key
from .bidding_refresh import BAD_POLICY, board_key, digest, sha
from .core import Board, auction_contract
from .mixed_arena import ArenaPlayer
from .runner import play_table, replay
from .bidding_loop import atomic_json


class MissingPlayCache:
    def __init__(self, root, player_root, spec, *, dds_library, event=None, workers=2):
        import os
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.player_root = Path(player_root)
        self.spec = dict(spec)
        self.dds_library = str(dds_library)
        self.workers = workers
        self.pool = None
        if spec.get('artifact_sha256', {}).get('policy') == BAD_POLICY or spec.get('id') in {'gen4','4','4p'}:
            raise ValueError('Regressed policy is forbidden')
        for kind in ('belief', 'policy'):
            if sha(self.player_root/spec[kind]) != spec['artifact_sha256'][kind]:
                raise ValueError('Cardplay artifact mismatch')
        os.environ['BRIDGE_DDS_LIBRARY'] = str(dds_library)
        os.environ['BRIDGE_DDS_CACHE'] = str((self.root/'dds-positions.sqlite').resolve())
        self.identity = digest([spec, sha(dds_library)])
        self.event = event
        self.players = {}
        self.hits = self.plays = 0
        self.seconds = 0.

    def key(self,board,calls):
        contract=auction_contract(board.dealer,calls)
        return digest([self.identity, board_key(board), contract.trump, contract.declarer])

    def resolve_many(self,requests):
        pending={}
        for b,calls in requests:
            key=self.key(b,calls)
            if not (self.root/(key+'.json.gz')).exists():
                pending.setdefault(key,(b.to_dict(),calls))
        if pending:
            if self.pool is None:
                self.pool=ProcessPoolExecutor(max_workers=self.workers,
                    mp_context=multiprocessing.get_context('spawn'), initializer=_init_worker,
                    initargs=(str(self.root),str(self.player_root),self.spec,self.dds_library))
            for record in self.pool.map(_play_worker,list(pending.values())):
                self.plays+=1; self.seconds+=record['seconds']
                if self.event:
                    self.event(phase='missing_contract_played',new_plays=self.plays,
                               seconds=record['seconds'],family=record['family'])
        return [self.score(b,calls) for b,calls in requests]

    def score(self, board, calls):
        contract = auction_contract(board.dealer, calls)
        if contract is None:
            return [0], 'passed_out'
        # Explicit temporary assumption: reuse tricks across contract levels and
        # auctions for the same deal/strain/declarer. Preserve the exact first
        # auction actually played in each cache record for later reanalysis.
        key = self.key(board,calls)
        path = self.root/(key+'.json.gz')
        if path.exists():
            with gzip.open(path, 'rt') as f:
                record = json.load(f)
            if record['player_identity'] != self.identity:
                raise ValueError('Play cache identity mismatch')
            self.hits += 1
        else:
            if not self.players:
                self.players = {'clean': ArenaPlayer(self.spec, self.player_root)}
            b = replace(board, contract=contract, auction=tuple(calls), opening_lead=None,
                        auction_source='clean-bidding-refresh-on-demand')
            start = time.monotonic()
            table = play_table(b, ['clean']*4, self.players, seed=int(key[:12],16))
            if table['status'] != 'ok':
                raise RuntimeError(table['error'])
            record = dict(schema='clean-bidding-contract-play-v1', player_identity=self.identity,
                          spec=self.spec, family=deal_key(b.hands,True), board=b.to_dict(), tables=[table],
                          cache_key=key, seconds=time.monotonic()-start)
            replay(record)
            temp = path.with_suffix('.tmp')
            with gzip.open(temp, 'wt') as f:
                json.dump(record,f)
            temp.replace(path)
            self.plays += 1
            self.seconds += record['seconds']
            if self.event:
                self.event(phase='missing_contract_played', family=record['family'], contract=contract.text(),
                           declarer=contract.declarer, seconds=record['seconds'], new_plays=self.plays,
                           cache_hits=self.hits)
        from .core import score, vulnerable
        tricks = record['tables'][0]['declarer_tricks']
        value = score(contract,tricks,vulnerable(board.vulnerability,contract.declarer))
        value *= 1 if contract.declarer % 2 == 0 else -1
        return [value], 'clean_play_new_or_cached'

    def close(self):
        if self.pool is not None:
            self.pool.shutdown()
        for player in self.players.values():
            player.close()


_worker_cache=None


def _init_worker(root,player_root,spec,dds_library):
    import os
    global _worker_cache
    _worker_cache=MissingPlayCache(root,player_root,spec,dds_library=dds_library)
    # Each process owns its DDS solver and SQLite write stream.
    os.environ['BRIDGE_DDS_CACHE']=str(Path(root).resolve()/f'dds-worker-{os.getpid()}.sqlite')


def _play_worker(request):
    board,calls=request
    b=Board.from_dict(board)
    _worker_cache.score(b,calls)
    with gzip.open(_worker_cache.root/(_worker_cache.key(b,calls)+'.json.gz'),'rt') as f:
        r=json.load(f)
    return {'seconds':r['seconds'],'family':r['family']}
