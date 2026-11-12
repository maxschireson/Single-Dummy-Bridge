G9-B2 submitted for your review: Rule filter: the card as a scorer over hand types

bill, 12 Nov 07:15 UTC. Task G9-B2.

PR #18 into feature/gen9. Done-when: the rule bidder's own auctions never break their IR card on covered calls (standard, precision, 12-14 NT, lighter openings, precision without relays/jumps/2D; 400 deals each in tests, 1,500 by hand; 0 breaks); cards generated from Settings by rb_cards.card_from_settings, Settings round trip exact; types = concrete hands on 10,000 hands; 1NT share 4.7% as its range says; no card = zeros; about 1.2M types/s per seat (rule bidder tables via rb_meanings 7k cold, 300k warm). Coverage of the rb cards: openings, overcalls/doubles, defence to 1NT, responses to 1NT/2NT, relay answers, about 30% of all calls; its responses to suit openings are not covered (support-point valuation: next). 48 tests pass with test_rule_bidder and test_bidding_systems. Two crashes in rule_bidder.py when it replays foreign auctions (plan() ~685, response_table() ~363) reported, not edited.

Branch: feature/gen9-bidding-cards, commit f1b731e.

Accept: `workq.py resolve G9-B2 --resolution accepted`. Send back: `workq.py reopen G9-B2 --note ...` (add `--same-holder` to return it to bill).
