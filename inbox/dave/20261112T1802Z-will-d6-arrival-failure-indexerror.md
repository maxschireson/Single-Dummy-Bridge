d6-arrival failure: IndexError in rule_bidder.response_table (line 363), the crash bill reported at 07:15 and g8 fixed in r3 (5b007c3); log attached; job retry coming

will, 12 Nov 18:02 UTC. Task G9-D6.

From will, 12 Nov 18:02 UTC.

**d6-arrival: the failure.** It failed at 17:53 UTC with exit 1 on all three tries. The first try ran from 15:04; the restarts started at about 17:47, 17:50:44 and later. Every try failed the same way, in a pool worker during epoch 3. Nothing else was wrong on the box: 22 GB of memory available, 101 GB of disk, and no OOM kill in dmesg.

**Where it stands.** `control/CURRENT` is 3. Epoch 3 has 515 rows in `slot0.jsonl`, epochs 1 and 2 are complete (600 and 1,200 rows), and `results.jsonl` has 2,315 rows. Nothing is deleted. The queue then started `e9-0-n02` and `e9-0-n02e` on the freed cores.

**Traceback** (last try, 17:53:18; the earlier tries are the same):

```
Traceback (most recent call last):
  File "/usr/lib/python3.12/concurrent/futures/process.py", line 263, in _process_worker
    r = call_item.fn(*call_item.args, **call_item.kwargs)
  File "/usr/lib/python3.12/concurrent/futures/process.py", line 212, in _process_chunk
    return [fn(*args) for args in chunk]
  File "/home/bridgebots/work/g9/src/8cb0348/scripts/arena9.py", line 74, in _worker_play
    r = run_board(source, m, board.to_dict(), index, G.g8.STATE['bidders'], player_factory=G.player)
  File "/home/bridgebots/work/g9/src/8cb0348/bridge_harness/gen5_arena.py", line 81, in run_board
    b,decisions=(auction(board,[bidders[v] for v in native]) if regime=='native' else (common,common_bids))
  File "/home/bridgebots/work/g9/src/8cb0348/scripts/gen9_match.py", line 63, in auction_any
    return _auction(board, bidders)
  File "/home/bridgebots/work/g9/src/8cb0348/scripts/gen8_match.py", line 123, in auction_any
    action = int(b.call(board.hands[seat], seat, board.dealer, VUL.index(board.vulnerability), [CALL_ID[normalize_bid(c)] for c in calls]))
  File "/home/bridgebots/work/g9/src/8cb0348/bridge_harness/rule_bidder.py", line 890, in call
    st = self.state(int(seat) % 2, int(dealer), int(vul), tuple(int(c) for c in calls))
  File "/home/bridgebots/work/g9/src/8cb0348/bridge_harness/rule_bidder.py", line 885, in state
    st.push(token)
  File "/home/bridgebots/work/g9/src/8cb0348/bridge_harness/rule_bidder.py", line 212, in push
    m = explain(self, seat, token)
  File "/home/bridgebots/work/g9/src/8cb0348/bridge_harness/rule_bidder.py", line 839, in explain
    entries = [m for t, m in table_for(st, me) if t == token]
  File "/home/bridgebots/work/g9/src/8cb0348/bridge_harness/rule_bidder.py", line 594, in table_for
    return response_table(st, me, g)
  File "/home/bridgebots/work/g9/src/8cb0348/bridge_harness/rule_bidder.py", line 363, in response_table
    real = st.shown[seat].len[s][0]
           ~~~~~~~~~~~~~~~~~~^^^
IndexError: list index out of range
"""
The above exception was the direct cause of the following exception:
Traceback (most recent call last):
  File "/home/bridgebots/work/g9/src/8cb0348/scripts/arena9.py", line 527, in <module>
    main()
  File "/home/bridgebots/work/g9/src/8cb0348/scripts/arena9.py", line 509, in main
    arrival(a.out, a.players, a.rules, a.capsule, a.events, a.epochs, a.workers)
  File "/home/bridgebots/work/g9/src/8cb0348/scripts/arena9.py", line 429, in arrival
    a9.play_epoch(control, backend, workers=workers, mirror=out / 'results.jsonl')
  File "/home/bridgebots/work/g9/src/8cb0348/bridge_harness/arena9.py", line 596, in play_epoch
    for (k, idx, g), (got, row) in zip(items, backend.play(m, pair, [x[1] for x in items], seed, workers)):
  File "/home/bridgebots/work/g9/src/8cb0348/scripts/arena9.py", line 210, in play
    for idx, row in zip(indices, pool.map(_worker_play, indices, [seed] * len(indices))):
  File "/usr/lib/python3.12/concurrent/futures/process.py", line 642, in _chain_from_iterable_of_lists
    for element in iterable:
  File "/usr/lib/python3.12/concurrent/futures/_base.py", line 619, in result_iterator
    yield _result_or_cancel(fs.pop())
  File "/usr/lib/python3.12/concurrent/futures/_base.py", line 317, in _result_or_cancel
    return fut.result(timeout)
  File "/usr/lib/python3.12/concurrent/futures/_base.py", line 456, in result
    return self.__get_result()
  File "/usr/lib/python3.12/concurrent/futures/_base.py", line 401, in __get_result
    raise self._exception
IndexError: list index out of range
```

**What it looks like.** This is the second of the two rule-bidder crashes bill reported this morning (G9-B2 log, 07:15: `response_table()` at about line 363, when it replays a foreign auction). g8 says on the board (11:27) that both are fixed in r3 at `5b007c3` on `feature/gen8-prototype-20261112`. The arrival source bids the guest with the prototype rule bidder from before that fix. A deal on which a guest has to explain an auction this way fails every time, so every restart hit it again.

**Resuming in the same folder.** A failed job is final in the queue today, and a new job id would start in a new, empty folder. I am adding `workq job retry ID --box B` now: it sets the job waiting again in the same `runs/d6-arrival`, so `arena9.py arrival` resumes from its control directory. Combined with `job submit --replace` it can move the job to a new source commit. I will tell you when it is pushed. Nothing will be restarted until you say so.
