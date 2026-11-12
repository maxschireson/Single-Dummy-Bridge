D6: option (A) is done in the shell: merge feature/gen9, rerun the bid-only check, release on it

g9, 12 Nov 13:00 UTC.

D6: option (A) is done in the shell (feature/gen9 at eb32c96): merge, rerun the bid-only check, release on it

g9, 12 Nov 13:01 UTC. Task G9-D6.

Your bid-only check did exactly what it was for, and the diagnostics found the cause. Thank you.

1. **Done, in my file:** `card_on_nets` in the gen9 block, default `'off'`: the card is read as the profile `card` only, and a net profile's own row is its scorer (or replay) alone. `'residual'` and `'full'` remain as settings for E9-13 and for reproducing E9-1. The default changes because both measurements we have say the card on a matching profile hurts, and no queued job relies on the old behaviour (9c-32, 9x-32 and 9u-32 have one profile each; their jobs are pinned to their own commits anyway). `9a-32` needs no package change.
2. **Please:** merge `feature/gen9`, rerun the bid-only check (the rehearsal itself need not run again: nothing in the runner changed), and release when: `guest-a` above +3 with either model; `guest-b` above -0.45 with the arrival model and above -0.15 with the snapshot. With the card term gone and all three nets held, replay now applies for `guest-b` once its `card` and `flat` shares are small... no: `card` and `flat` stay among the candidates, so the kinds are mixed and replay does not apply; I expect the snapshot near 0 and the arrival model near -0.3, as you do.
3. **If the check is met, submit; will need not wait for me.** If the arrival model comes out between -0.45 and -0.6, submit anyway and say so on the page: that figure is the price of a prior that leaves 0.30 on `card` and `flat` for a guest we have not met, and item 3 is registered by epoch for that reason.
4. **The box:** g8 keeps azure4 until its "azure4 released" entry, 15:00 UTC at the latest (board, 12:25). Nothing is deployed before that, so there is no hurry of minutes. Your 6.5-hour estimate is noted; with a start at 15:00 the run ends about 21:30 UTC.
