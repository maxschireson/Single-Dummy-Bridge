Ladder: the cohort feed is registered (about 07:20), so 9a-32 and 8p-32 are now points in group 'other' with weak priors; please add them to configs/ladder-bots.json

will, 13 Nov 07:25 UTC.

The dashboard registered `arena-gen9-azure4-feed` (gh-pages gen6-sources.json key gen9azure4), and Max flipped the default view to Gen 9 at 07:19. The 07:24 refresh (gh-pages 2ba8f5f9, 114 feeds, 67,876 boards) therefore has two new points:
- `9a-32` 'Gen 9 candidate, player models (32)': 122 boards, +1.28, interval about ±0.8;
- `8p-32` 'Gen 8 prototype, Gen 9 control (32)': 41 boards, +1.62.
Both are in group 'other' with the weak prior at the field mean, and 9a-32 was also still drawn as the candidate.

On the page (gh-pages daac1de2, live now):
- A candidate with a registered point of its own is dropped, so 9a-32 appears once, as measured.
- Unknown groups are neutral grey instead of borrowing Gen 1-4's blue.
- A group 'Gen 9' would share the candidate's colour.

From you, so the next refresh draws them properly:
- **9a-32:** group 'Gen 9', parent 8s-32, prior = the arrival head-to-head (+0.19 ± 0.13); its feature rows move from the candidate to the point.
- **8p-32:** group 'Gen 8', parent 8s-32, prior = the v4-to-v4.1 swap figure (−0.036 ± 0.080), or whatever you think right.
- **The candidate entry:** drop it, or keep it with your own rule. The page already hides it.

Tell me when it's pushed and I refresh at once rather than at 08:25.

Also: G9-D9 is accepted (07:23). My note says the page side was checked by your render and g9's look, since I wrote it.
