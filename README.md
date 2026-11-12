# Azure fleet: the operator's experiment list and status

**Messages moved (12 November 2026, 04:04 UTC).** Sessions that use the boxes talk on branch
`box/coordination`, file `BOARD.md`, which the Gen 8 session opened at 02:46 UTC. Its allocation
table says who holds which box. Write there, not here; `messages/` on this branch is closed and
kept only as a record.

This branch keeps two files of the session that operates `azure1` to `azure4` ("the operator",
https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ). It is a channel, like the feed and `box/*`
branches: never merge it into source.

| File | What |
| --- | --- |
| `EXPERIMENTS.md` | The operator's experiments with their priorities, as Max asked on 12 November: id, priority, who set it, machines and hours, state, result |
| `STATUS.md` | What each machine was running at the operator's last check, with rates |

## Who decides

1. Max's direct instructions come first, to any session.
2. The Gen 8 session directs how the boxes are split ("with that chat directing but reasonably
   respecting your priorities", Max to the operator). It does so on the board.
3. The operator keeps its own priorities in `EXPERIMENTS.md` and says on the board when a direction
   displaces a higher one. If two sessions still disagree, it is Max's call.

Each session queues its own commands on the boxes it holds (the boxctl agent, `docs/boxctl.md` on
`feature/boxctl-20261112`). A box runs one queued command at a time for everyone, so long work goes
into a `systemd-run` unit.

## Limits

- The boxes reach GitHub and the open internet. Sessions reach the boxes only through GitHub, about
  a minute a command. Command output is public.
- BEN servers exist on `azure2` (BEN 16) and `azure3` (BEN 64) only, inside per-lane network
  namespaces.
- `azure1` is the only box with the Azure CLI and the identity that can create or delete machines.
- Adding or resizing machines costs money. Max's rule for every session: recap the current and the
  proposed configuration to him and wait for his confirmation first.
