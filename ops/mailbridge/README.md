# mailbridge: a mailbox for a Claude session, relayed by a box

Claude's cloud sessions reach GitHub but not mail servers. A box relays one mailbox (a
dedicated Gmail account with an app password; the box itself cannot send mail directly,
because Azure blocks outbound port 25 and its host name cannot carry SPF or DKIM records).

- `mailbridge.py` runs on the box as unit `mailbridge` (one process, polls every 60 s).
- `client.py` runs in the session.
- Branch `mail/coord` is the channel. The repository is public, so every message is signed
  by its sender and encrypted to its reader (CMS through the openssl CLI); receipts and status
  carry no addresses or text. The mailbox credentials reach the box by SSH or encrypted on
  the branch, never in a boxctl command (those are public).
- The box sends only to addresses in `~/.mailbridge/allow`.

Install on a box (through boxctl): `ops/mailbridge/install.sh <commit> <box>`.
Remove: `sudo systemctl disable --now mailbridge && rm -rf ~/mailbridge ~/.mailbridge`.

Tested scope: `tests/test_mailbridge.py` runs the box loop and the client against a local
bare repository with a fake mail transport (relay in and out, no duplicate relay, allow
list, a forged outbox file refused, nothing readable on the branch). The Gmail transport
(IMAP and SMTP) is tested only on the live box.
