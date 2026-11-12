E9-16 part 1b: which equal card we play is worth 0.038 +- 0.013 tricks a board to a reader of our strength; 0.023 of it is our defenders' spots read by declarer; partner gets 0.004 from them

sam, 12 Nov 16:04 UTC. Task E9-15.

From sam, 12 Nov 16:04 UTC. reports/gen9-leakage-classes-2026-11-12 on feature/gen9-reading-bench (47de109): README, tables.md, report.json. p41's 530 house tables, 21,417 decisions, standard errors by deal, tricks a board (four seats of a table, p41's unit), paired against the reading of the actual cards.
1. Check: the stage's 'card' reading (8p-32, net v4, factor 1) gives +0.185 +- 0.029, p41's figure, and reproduces the stored v4 fits to 6e-6.
2. Every hidden seat by class (E9-3 spots, the card inside chosen evenly): -0.038 +- 0.013 (-0.22 nats); declarer deciding -0.023 +- 0.010, a defender deciding -0.014 +- 0.008.
3. Touching cards of the suit held, honours included (touching through played cards; done in my stage): -0.036 +- 0.017; no more than the spots.
4. Opponents' plays only: spots -0.028 +- 0.012 (declarer reading the defenders -0.023 +- 0.010; defenders reading declarer -0.005 +- 0.005); touching -0.021 +- 0.016 (-0.020, -0.001). Partner's plays only: spots -0.004 +- 0.007, touching -0.003 +- 0.006.
So: randomizing inside spot classes would cost an opponent of our strength about 0.02 to 0.03 tricks a board, and our own partnership about 0.004. Declarer's equal cards leak 0.001 to 0.005 here, so a declarer-only concealment setting would buy little against a reader like ours; the defenders' spots are where the leak is. This is the leak to the house net, not to BEN.
