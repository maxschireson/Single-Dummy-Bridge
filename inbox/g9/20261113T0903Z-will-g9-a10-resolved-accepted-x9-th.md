G9-A10 resolved (accepted): X9: the Gen 9 shell on the 8X engine

will, 13 Nov 09:03 UTC. Task G9-A10.

Reviewed by will. New checkout of feature/gen9-x9 at ed2806f with DDS built and nets restored (run_tests.py taken from feature/gen9, since the 8X base has none): test_x9 5 passed and 1 skipped, test_x8 31 (7 skipped), test_gen9_player 20, test_gen9_player_model 19; 68 passed, 0 failed. The class is X9Player(X8Player, Gen9Player). meet passes the id to 8X and the model to Gen 9 (test_meet_gives_8x_the_id_and_gen9_the_model). A declared scheme is read and not pooled (test). Card for card with the wrapped 8X bot, nothing declared and with rollouts and the blend: both pass. Not verified by me: the winning-line card-for-card test, which skips without sure_cpp (SURE_BIN); your log says it passed with 2e6ed6d's binary. Done-when item not done here: x8.names taking the arrival mixture's profile for a newcomer, moved by you to E9-22. Accepted on that basis.
