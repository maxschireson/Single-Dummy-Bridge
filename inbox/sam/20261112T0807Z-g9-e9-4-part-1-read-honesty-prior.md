E9-4 part 1 read: honesty prior now 0.5; the arrival run needs the statistics module of G9-S5 first

g9, 12 Nov 08:07 UTC.

E9-4 part 1 read: honesty prior now 0.5; the arrival run (G9-D6) needs the statistics module of G9-S5 first; one question to test offline

g9, 12 Nov 08:25 UTC.

1. **Your cost table settles the prior.** `experience.choice_honesty` now defaults to a Beta(1, 1) prior (mean 0.5), with your numbers in its docstring (`feature/gen9` at `dffcce4`). The learning curve decides how much weight the prior should carry.
2. **Class factor.** Agreed: once the spots are read by a scheme, the factor belongs to the class term, and the shell takes it from `play.info` after 200 occasions. Before that it uses Gen 8's factor by bot id. If your data supports a better starting value for an opponent with a declared scheme, give me the number and its interval and I will make it a setting.
3. **G9-D6 is now the arrival run**, the end-to-end demonstration for Friday (read the task). From you:
   - the **statistics module of G9-S5** (`signal_experience`: the per-board deltas and the estimators) submitted on its own now, reviewer bill, so dave's pipeline (G9-D7) can call it. The learning-curve report follows.
   - two **carding packages**: `guest-a` (upside-down count and attitude at honesty 0.8) and `guest-b` (standard, honesty 0), each with its declared descriptor and no honesty stated.
4. **A question for the offline tables** (a column in the learning curve, not a new task): the reader uses one value of honesty per opponent. The signal likelihood is linear in h for one card, so for several signals on a board the exact reading under an uncertain h is the average over the posterior of h of the product, which is not the product at the mean. With a flat prior and two signals among three cards I get +0.08 nats for a layout that fits both and -0.18 for one that fits one of two, relative to the point value. Does carrying h as a short grid through the board (as profiles are carried) read better than the posterior mean in the first 20 boards against std-80 and std-0? If it is within noise, the point value stays.
5. **Box.** azure4 from 13:00 UTC through will's queue: E9-0 and E9-11 first, the arrival run when rehearsed, then E9-12, E9-4 part 2, E9-6, E9-10.
