D6: also needs 514e046 (held_systems restores the house bidders in a fresh checkout)

bill, 12 Nov 09:23 UTC. Task G9-D6.

From bill, 12 Nov. Same gap as d4515bd, in the profile statistic: cards.match.held_systems found only house-dds40k on a fresh checkout (git keeps Gen 5 and Gen 6 as parts), so profile_evidence would have scored neither house-gen5 nor house-gen6 and guest-b could never be mapped to Gen 5. Fixed at feature/gen9-bidding-cards 514e046; checked in a fresh worktree (all three held systems found).
