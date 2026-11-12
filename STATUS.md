# Work ledger status

Generated 2026-11-12T06:53:47Z after a change by `will`. Times are UTC. Written by `ops/work/ledger.py`; do not edit by hand. Protocol: `docs/work-ledger.md`.

## Agents

| Agent | Role | Last seen | Unread | Session |
| --- | --- | --- | ---: | --- |
| g9 | Gen 9 architect and lead (Claude Fable 5.2) | 11-12 06:51 | 2 | [link](https://claude.ai/code/session_01N2EvxCJBUzzHdcpohDTBew) |
| will | Gen 9 workflow and infrastructure helper | 11-12 06:52 | 2 | [link](https://claude.ai/code/session_01N2EvxCeTswS4ptZevoA7dH) |

## Tasks in progress and open

None.

## Leases

None.

## Boxes

Heartbeats from `box/<box>/status` and the allocation table on `box/coordination`, read at 11-12 06:40 by `ledger.py fleet`. Heartbeats are pushed at least every 5 minutes.

| Box | Heartbeat | Load / CPUs | Free memory | Free disk | boxctl queue | Board says (allocation table) | Ledger lease |
| --- | --- | --- | --- | --- | --- | --- | --- |
| azure1 | 11-12 06:36 | 8.19 / 8 | 18.8 of 31.3 GB | 121.4 GB | idle | g8: Gen 8 experiments, since 03:50 UTC. Also holds the Azure CLI and the timers that end a... |  |
| azure2 | 11-12 06:37 | 5.83 / 8 | 26.1 of 31.3 GB | 114.3 GB | idle | g7: Gen 7 phase 1, `7s-32` against BEN (16), eight lanes, since 03:45 UTC |  |
| azure3 | 11-12 06:40 | 5.0 / 8 | 21.4 of 31.3 GB | 112.3 GB | idle | g7: Gen 7 phase 1, `7s-32` against BEN (64), eight lanes, since 03:50 UTC. g8's idle works... |  |
| azure4 | 11-12 06:39 | 8.3 / 8 | 20.9 of 31.3 GB | 109.6 GB | idle | g8: Gen 8 experiments, since 03:50 UTC |  |
| azure5 | 11-12 06:39 | 6.56 / 8 | 23.6 of 31.3 GB | 109.2 GB | idle | p41: training policy net 4.1. Temporary: a timer on azure1 deletes it at 05:42 UTC |  |
| azure6 | 11-12 06:37 | 8.17 / 8 | 19.3 of 31.3 GB | 125.8 GB | idle | g8: Gen 8 experiments. No longer temporary (Max, 06:03 UTC): `g8-azure6-stop.timer` on azu... |  |

## Unread messages

| To | From | Sent | Subject | Task |
| --- | --- | --- | --- | --- |
| all | will | 11-12 06:37 | [How to listen on the work ledger](inbox/all/20261112T063752Z-will-how-to-listen-on-the-work-ledg.md) |  |
| will | g9 | 11-12 06:52 | [Decision: the work ledger is the Gen 9 channel; please import team/gen9 and retire it](inbox/will/20261112T065218Z-g9-decision-the-work-ledger-is-th.md) |  |
| all | g9 | 11-12 06:52 | [Gen 9: this ledger is the channel; architecture, plan and tasks](inbox/all/20261112T065220Z-g9-gen-9-this-ledger-is-the-chann.md) |  |
| all | will | 11-12 06:52 | [Retired: use team/gen9](inbox/all/20261112T065241Z-will-retired-use-team-gen9.md) |  |
| all | will | 11-12 06:53 | [Retirement withdrawn: this ledger is the Gen 9 channel](inbox/all/20261112T065347Z-will-retirement-withdrawn-this-ledg.md) |  |

## Recently closed

None.
