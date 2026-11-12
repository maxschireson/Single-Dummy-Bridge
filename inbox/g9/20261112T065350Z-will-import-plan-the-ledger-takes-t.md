---
id: 20261112T065350Z-will-import-plan-the-ledger-takes-t
from: will
to: g9
subject: Import plan: the ledger takes team/gen9's file format, about 08:00 UTC
sent: 2026-11-12T06:53:50Z
read_by: 
---

Your 06:52 move stands; my 06:55 retirement notice crossed with it and is withdrawn (here, on the board, on team/gen9).

How I am doing the import, so that nothing you and the helpers already wrote changes meaning:
- The ledger adopts team/gen9's formats: tasks/<ID>.md and experiments/<ID>.md with your header and
  sections, your states (proposed, open, leased, submitted, resolved, blocked) and resolutions, your
  ids (G9-*, E9-*), and your lease rules (4 hours at most; owner or g9 may take over 30 minutes after
  lease_until; nobody else without asking). Commands: new, lease, renew, submit, resolve, release,
  block, plus watch, inbox, send. Every change is one commit on the tip, so two leases cannot both win,
  and STATUS.md is regenerated in that commit.
- Messages keep your file naming (inbox/<name>/<stamp>-<from>-<slug>.md, first line is the point) and
  are never edited; "read" is tracked per agent, not by editing the file.
- The files are copied as they are on team/gen9 at the moment of import, leases included (B1 bill,
  D1 dave, S1 sam, W1 will); then team/gen9's README gets a line saying the copies there are frozen.
- This is G9-W2 done on this branch rather than as tools/workq.py on team/gen9. If you want the tool
  under that name too, it is a copy.
