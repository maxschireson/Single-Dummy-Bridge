G9-X2 bench jobs submitted: four, priority 3, 4 cores, preemptible (resume from saved parts)

sam, 12 Nov 14:51 UTC. Task G9-X2.

From sam, 12 Nov 14:51 UTC. On feature/gen9-reading-bench at 144b59f. The sandbox stopped at 245 BEN 16 and 253 BEN 64 tables, so:
- g9-x2-ben16: held-out tables 245-299 (55 tables)
- g9-x2-ben64: held-out tables 253-299 (47 tables)
- g9-x2-rel-std-80, g9-x2-rel-std-50: E9-4 part 1's 300 house tables relabelled (each relabels from the pinned feed, then solves declarer's decisions)
Each fetches its feed branches once into {work}/ben-feeds or {work}/house-feeds and adds the readings after solving. Progress counts saved tables (targets 55, 47, 300, 300). If the deploy reports CANNOT for https fetches, tell me and I will move the episodes to a transfer branch.
