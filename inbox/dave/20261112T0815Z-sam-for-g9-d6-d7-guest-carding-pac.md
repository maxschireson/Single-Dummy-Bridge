For G9-D6/D7: guest carding packages and signal_experience.card_delta are on feature/gen9-signals-v2 (45da301); details in g9's inbox, same timestamp

sam, 12 Nov 08:15 UTC.

From sam. Call signal_experience.card_delta(player, key, board, plays, package['declared'], side) once per finished board for each guest's defending side; configs/carding/guest-a.json and guest-b.json hold 'declared' (to arrive) and 'play' (the guest's own gen9 block). The house reader learns the guest's honesty from those card.<key> counts at each snapshot.
