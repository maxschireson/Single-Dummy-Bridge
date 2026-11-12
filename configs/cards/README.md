# Convention-card descriptors (Gen 9 WIP)

One JSON file per card, schema `card-descriptor-v0` (`bridge_harness/cards/card.py`). A file states only
where it differs from the defaults (a natural 2/1-style base: five-card majors, 15-17 1NT, strong 2C,
weak twos). These are the project's own descriptions of common systems, written from general bridge
knowledge; nothing here comes from another program or its card files.

| File | System |
| --- | --- |
| `two-over-one.json` | 2/1 game force (the defaults) |
| `sayc.json` | Standard American Yellow Card |
| `acol.json` | Acol: 12-14 1NT, four-card suits |
| `precision.json` | Precision: 16+ 1C, nebulous 1D, 14-16 1NT, 2C natural, 2D three-suited |
| `polish-club.json` | Polish Club: multi-way 1C (12-14 balanced, 15-17 clubs, or 18+) |
