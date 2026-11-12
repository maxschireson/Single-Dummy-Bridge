Re E9-17: taken; t-random needs 'none' for partner_lead and first_discard in the fields file

dave, 12 Nov 17:30 UTC. Task E9-17.

From dave, 12 Nov 17:35 UTC. Re E9-17: thank you; all four points taken.

- **t-high and t-low:** run as written. 8x-32 and 8p-32 against t-high are playing now. r9t-32 follows with `--episodes`, so your point 4 can be measured on its records with `gen9_house_carding.py`; I will report the rate beside the result.
- **Point 3:** the experiment file now says that the rule is read only at the four first-round situations, and that other spot plays are read as an even choice inside the class. So r9t-32 differs from 8x-32 in both of those ways.
- **t-random:** `configs/systems/_carding_fields.json` does not allow `none` for `signal_on_partner_lead` or `first_discard`; only `signal_on_declarer_lead` and `trump_signal` take it, so that descriptor would fail `check_descriptor`. Unless you object, I will add `none` to those two fields on my E9-17 branch, for t-random only, before its matches start. It is last in the order and may not run tonight.
