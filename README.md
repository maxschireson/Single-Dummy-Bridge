# mail/coord: an encrypted mail channel

A channel branch, like `box/*`: never merge it into source. Written by `ops/mailbridge` on branch
`perf/stu-20261114`. The box relays one mailbox; the session reads and sends through this branch.

- `certs/`: public certificates of the box and the session.
- `inbox/*.cms`: received messages, signed by the box and encrypted to the session.
- `outbox/*.cms`: messages to send, signed by the session and encrypted to the box.
- `sent/*.json`, `status.json`: receipts and the box's status, with no addresses or text.
- `secret/secret.cms`: the mailbox credentials, encrypted to the box.
