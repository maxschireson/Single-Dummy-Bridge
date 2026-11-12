E9-15 interim: BEN's signals carry at most 0.07 to 0.12 bits in their best situations (none ten times declarer's lead's 0.04-0.05); the expert adds +0.05 nats a declarer decision over E9-7's tables

sam, 12 Nov 13:27 UTC. Task E9-15.

From sam, 12 Nov 13:27 UTC. reports/gen9-signal-expert-2026-11-12 on feature/gen9-signals-v2 (a14c37d); tables.md has the full honesty and bits tables, held-out and all tables.
- Bits a signal (all tables, description): declarer's lead 0.052 / 0.044 (BEN 16 / 64); declarer's lead when BEN could not win the trick 0.088 / 0.071, when it could 0.011 / 0.012; fourth hand 0.085 / 0.075; partner's lead at tricks 2-3 0.124 / 0.081, at trick 1 0.007 / 0.005; second round of declarer's suit with 2 spots left 0.066 / 0.091; first discards 0.001 / 0.007; trumps 0.008 / 0.000. So the situations differ, but the best carry two to two and a half times the average, not ten.
- Effective honesty: 0.12-0.14 (could win) against 0.31-0.35 (could not) on declarer's lead; 0.09-0.10 at trick 1 against 0.34-0.42 at tricks 2-3 on partner's lead. On the second round a high card says odd (h -0.31, -0.35): the completed count, which today's reader ignores.
- Reading gain at the house declarer's decisions (E9-7's 300 held-out tables, nats): M3 over E9-7's tables +0.054 +- 0.018 (BEN 16), +0.048 +- 0.021 (BEN 64); M2 +0.041, +0.052. On your rate that is about 0.002 tricks a board. The bench's figure (m1, m3, m3 with first rounds only) follows when the pools are done; I expect it to be indistinguishable from zero.
- One bug found and fixed: SignalModel.emitted gave a layout where the signaller held a single spot -0.1 nats instead of certainty (8be31d6). It is in E9-7's numbers and in r9b-32 at 67c59de; the effect on E9-7's reading is the +0.012 / +0.003 nats of 'M1 refitted' (refit and fix together).
- House control: house defenders' effective honesty is within 0.05 of zero on leads, +0.09 to +0.15 on first discards; reading them through their own expert was not scored.
E9-14's run restarted at 13:25 (faster fits, in parallel); results in about an hour.
