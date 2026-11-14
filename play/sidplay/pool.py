"""Bot workers: an interactive pool for calls, cards and claim checks, a background pool for Sid's own tables, and an
analysis pool for the post-mortem of each finished board.

Bot worker processes load the bundle once. The service runs at a raised scheduling priority (systemd Nice=), so an
interactive worker takes a core from the arena collectors only while it is computing. The background and analysis pools
add `background_nice` to that, so Sid's comparison tables and the analyses compete with the collectors on equal terms.
The analysis pool loads no models: only DDS from the bundle's source and the sure-trick binary.
"""
import asyncio
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from concurrent.futures.process import BrokenProcessPool
import logging
import multiprocessing as mp

log = logging.getLogger('sidplay.pool')


class Bots:
    def __init__(self, config):
        self.config = config
        self.fake = config.engine == 'fake'
        if self.fake:
            from . import fake_engine as module
        else:
            from . import engine as module
        self.module = module
        self.pools = {}
        self.busy = {'interactive': 0, 'background': 0, 'analysis': 0}
        self.decisions = 0

    def _make(self, kind):
        c = self.config
        workers = dict(interactive=c.interactive_workers, background=c.background_workers, analysis=c.analysis_workers)[kind]
        if self.fake:
            return ThreadPoolExecutor(max_workers=workers)
        nice = 0 if kind == 'interactive' else c.background_nice
        if kind == 'analysis':
            from . import analysis
            return ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context('spawn'),
                                       initializer=analysis.init_worker, initargs=(c.source, nice))
        return ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context('spawn'),
                                   initializer=self.module.init_worker, initargs=(str(c.bundle), nice))

    def pool(self, kind):
        if kind not in self.pools:
            self.pools[kind] = self._make(kind)
        return self.pools[kind]

    async def _run(self, kind, fn, *args):
        loop = asyncio.get_running_loop()
        self.busy[kind] += 1
        try:
            for attempt in (0, 1):
                try:
                    return await loop.run_in_executor(self.pool(kind), fn, *args)
                except BrokenProcessPool:
                    log.error('%s pool broke; restarting it', kind)
                    self.pools.pop(kind, None)
                    if attempt:
                        raise
        finally:
            self.busy[kind] -= 1

    async def warm(self):
        """Start every worker now, so the first player does not wait for the models to load."""
        jobs = []
        for kind, n in (('interactive', self.config.interactive_workers), ('background', self.config.background_workers)):
            jobs += [self._run(kind, self.module.info) for _ in range(n)]
        infos = await asyncio.gather(*jobs, return_exceptions=True)
        for x in infos:
            if isinstance(x, BaseException):
                raise x
        return infos

    async def bid(self, hand, seat, dealer, vul, calls):
        self.decisions += 1
        return await self._run('interactive', self.module.bid, hand, seat, dealer, vul, calls)

    async def play(self, observation, kind, systems, seed):
        self.decisions += 1
        return await self._run('interactive', self.module.play, observation, kind, systems, seed)

    async def side_tricks(self, hands, trump, leader, trick, side):
        return await self._run('interactive', self.module.side_tricks, hands, trump, leader, trick, side)

    async def sid_table(self, hands, dealer, vul, board_id, seed, systems):
        return await self._run('background', self.module.sid_table, hands, dealer, vul, board_id, seed, systems)

    async def analyse(self, hands, contract, declarer, play, focus, names, limits=None, auction=None):
        """auction: dict(calls, dealer, vul), read with the bundle's hand-fit scorer when there is one."""
        from . import analysis
        return await self._run('analysis', analysis.analyse_board, hands, contract, declarer, play, focus, names,
                               dict(self.config.analysis_limits, **(limits or {})), auction, self.config.scorer)

    def close(self):
        for p in self.pools.values():
            p.shutdown(wait=False, cancel_futures=True)
        self.pools.clear()
