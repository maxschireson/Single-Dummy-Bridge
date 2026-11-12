Simpler: card_delta now writes the emission counts too (one call per board), feature/gen9-signals-v2 at 7ef3cb8

sam, 12 Nov 09:02 UTC.

From sam. Ignore the separate emission_stats call in my last message; card_delta(player, key, board, plays, declared, side) returns both card.<key> and card.<key>.emit.
