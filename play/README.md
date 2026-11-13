# Play against Sid

A web server where people play bridge against Sid. Sid is not any of the project's current bots: it does not exist
yet, and this server is ready for it. Until it does, a stand-in plays Sid's seats: `8s-32`, Gen 8 standard. The
page says so, and names the stand-in, whenever the installed bundle is marked `stand_in`. Guests can play
straight away: they sit South and Sid takes the other three seats. Account holders can also bring a partner: the
two of them play North–South against two Sids. Each finished board shows the score and the IMPs against a "Sid
table", where Sid plays the same deal at all four seats. Accounts keep every board with its auction and play.
There are no matches or events.

## How a table works

- **Seats.** Humans always sit North–South. A solo player is South. At a partner table the host is South and the
  invited partner North.
- **Boards.** Random deals; dealer and vulnerability follow the standard 16-board cycle.
- **Declaring.** When North–South win the contract, the human side declares. At a partner table, the human at the
  declarer's seat plays both hands. Solo, the human plays both hands even when Sid-North won the auction, as on
  BBO robot tables. A human dummy sees only their own hand.
- **Claims.** Declarer can claim any number of the remaining tricks at any time. The claim is accepted when
  declarer's side can take that many double dummy from the current position (as BBO robots judge claims). A refusal
  does not say how many tricks were there, since that would reveal the hidden hands.
- **Scoring.** The score is North–South's. After each board a background worker plays the deal with Sid at all
  four seats (Sid's own auction, Sid's play). IMPs = IMP(your score − Sid table score). So a plus means the humans
  did better than Sid would have in their seats.
- **Sid's systems.** A solo table declares Sid's system (`house-gen6` for `8s-32`) for North–South, because the
  human bids with Sid. A human pair declares nothing. East–West declare Sid's system. Sid makes no alerts and
  gives no explanations.
- **Guests.** A guest's boards are tied to a browser cookie. On sign-up or sign-in in that browser they move to the
  account, and so does an open table.

## The information boundary

The server holds the deal; a browser only gets what its seat may see (`Table.view`). That means its own hand, dummy
after the opening lead, declarer's hand when this human plays it, and every hand once the board is over. A bot gets
the same `Observation` the game gives the seat controlling the card, and the bidder gets one hand and the calls.
The full deal reaches a worker only in two places: the claim check (the referee, not a player) and Sid's own table,
where every seat is Sid. The tests and `smoke.py` check each response for a hand the viewer should not have.

## Pieces

| File | Role |
| --- | --- |
| `sidplay/app.py` | FastAPI: the page, accounts, tables (long-polled), history |
| `sidplay/tables.py` | Seating, auction and play, Sid's turns, claims, per-viewer views |
| `sidplay/engine.py` | Runs in worker processes: loads the bundle, bids, plays, checks claims, plays Sid's table |
| `sidplay/pool.py` | Interactive and background worker pools |
| `sidplay/store.py` | SQLite: users (scrypt hashes), sessions, boards, participants |
| `sidplay/fake_engine.py` | A stand-in bot with no models, for tests and interface work |
| `sidplay/static/` | The page (vanilla JS, self-hosted OFL fonts) |
| `bundle.py` | Builds a Sid bundle: a bot spec, its artifacts checked by sha256, and the source that runs it |
| `bundles/8s-32.json` | Recipe for Gen 8 standard: the spec copied from the `gen8-s7-azure1` cohort manifest |
| `smoke.py` | Plays whole boards through the public API (standard library only) |
| `deploy/` | `install.sh`, `sidplay.service`, `sidplay.env`, `expose.sh`, `caddy.sh` |

**The bundle is what makes Sid swappable.** The server does not name a generation. It loads one bundle: the bot's
spec, its artifacts, a source checkout at the commit the bot was frozen with (`8s-32`: `792c4cb` on
`feature/gen8-prototype-20261112`), an entry point, and the `stand_in` flag. To install Sid: add a recipe
(`bundles/sid-….json`, `stand_in` false), run `install.sh` with its source commit, and the symlink
`/opt/sidplay/bundle` moves. Finished boards record the bot and its identity, so the stand-in's boards stay
separable from Sid's.

## The Sid contract

The entry point (`entry` in the recipe, `module:callable`, importable from the bot's source) builds an object with
two methods. The full text is in [`sidplay/engine.py`](sidplay/engine.py).

- `bid(hand, seat, dealer, vulnerability, calls) -> call`: one seat's 13 cards (ints, `bridge_harness.core`
  order), seats 0–3 for N E S W, `'None' | 'NS' | 'EW' | 'Both'`, and the calls so far (`'PASS'`, `'X'`, `'XX'`,
  `'1C'` … `'7N'`).
- `play(observation, facing, systems, rng) -> card`: a `bridge_harness.core.Observation` for the seat that controls
  the card, `'human'` or `'sid'` for who the opponents are, the declared systems `(NS, EW)`, and a seeded
  `random.Random`.

One object serves many tables in turn, so it must not carry table state that its arguments do not determine. The
server checks every call and card for legality. With no `entry`, `ArenaSid` is used: the bot exactly as the
source's arena runtime builds it (a BEN-format bidding net or a Gen 8 system bidder, and
`ops/gen5_runtime.player`). Any bot the arena can run needs only a recipe. A bot the arena cannot build needs one
small class in its own source. `tests/toy_sid.py` is the smallest example.

`ArenaSid` builds two player instances in each worker. One faces humans: Gen 8 reads unknown opponents' plays at the
`opponent_play_weight` `'*'` factor, 0.3 for `8s-32`. The other faces Sid, at factor 1.0. A Sid seat whose partner is human
still reads partner's cards as Sid's, as the engine always does for partners.

## Run it locally

```sh
python3 -m venv .venv && . .venv/bin/activate
pip install -r play/requirements.txt pytest httpx

# Without models (a stand-in bot), from the repository root:
SIDPLAY_ENGINE=fake SIDPLAY_DATA=/tmp/sidplay uvicorn sidplay.app:app --app-dir play --port 8090

# With Sid: build a bundle from a checkout of the bot's source commit, with DDS built there
git clone --depth 1 --branch feature/gen8-prototype-20261112 https://github.com/maxschireson/Single-Dummy-Bridge.git /tmp/sdb-gen8
(cd /tmp/sdb-gen8 && python scripts/build_dds.py)
python play/bundle.py from-models --recipe play/bundles/8s-32.json --source /tmp/sdb-gen8 --out /tmp/bundle-8s32 --allow-commit
SIDPLAY_BUNDLE=/tmp/bundle-8s32 SIDPLAY_DATA=/tmp/sidplay SIDPLAY_WORKERS=1 uvicorn sidplay.app:app --app-dir play --port 8090

# Tests (stand-in bot) and a smoke run against a live server
cd play && python -m pytest tests -q
python play/smoke.py http://127.0.0.1:8090 --boards 2 --sid
```

`--allow-commit` is needed above only because the branch head is two documentation-only commits past `792c4cb`.
The installer fetches `792c4cb` itself.

## Deploy on a box

All through [boxctl](../docs/boxctl.md); nothing needs SSH.

1. **Install** on the host box (listens on 127.0.0.1:8090 only):
   `bash play/deploy/install.sh <app commit> 792c4cb3f647ec71273f0cc57d95be1d0a0a5954`.
   It creates the unprivileged `sidplay` user and puts code, venv and bundle under `/opt/sidplay` (root-owned) and
   data in `/var/lib/sidplay`. Then it installs and starts `sidplay.service` and waits for `/api/health`. The bundle is built
   from the model releases in the source checkout, not copied from any arena run directory.
2. **Expose**, from the box whose Azure CLI is signed in: `bash play/deploy/expose.sh <VM name> <dns label>`. One
   NSG rule (TCP 80/443 from the internet to that VM's private address only) and a DNS label on its public IP.
3. **HTTPS** on the host: `bash play/deploy/caddy.sh <label>.eastus.cloudapp.azure.com`. Installs Caddy (automatic
   Let's Encrypt), proxies to the server and turns on secure cookies.

**Cost on a shared box.** The service runs at `Nice=-10`. While someone is playing, an interactive worker preempts
an arena collector for about one core. Idle, it uses nothing but memory: about 0.85 GB per worker, so about 2.6 GB
with the default three. Sid's own table runs at Nice 0, level with the collectors. Measured locally (2 cores, no
other load): a Sid decision averages 0.14 s (1.5 s worst on one table); a whole Sid table takes about 9 s; a board
against Sid takes 20–35 s of wall time, most of it the deliberate pause between bot cards (`SIDPLAY_PACE`). Wall-clock
timings recorded by a collector on the host box are inflated while people play.

## Operating

```sh
systemctl status sidplay; journalctl -u sidplay -n 100       # service and its log
curl -s http://127.0.0.1:8090/api/health                      # bot, open tables, busy workers, decisions
sudo systemctl restart sidplay                                # drops live tables (finished boards are saved)
sudo sqlite3 /var/lib/sidplay/sidplay.sqlite '.backup /tmp/sidplay-backup.sqlite'
```

| Setting (`/etc/sidplay.env`) | Default | Meaning |
| --- | --- | --- |
| `SIDPLAY_BUNDLE` | — | Bundle directory (`SIDPLAY_ENGINE=fake` runs without one) |
| `SIDPLAY_DATA` | `~/sidplay-data` | Where `sidplay.sqlite` lives |
| `SIDPLAY_WORKERS` | 2 | Interactive bot processes |
| `SIDPLAY_BACKGROUND_WORKERS` | 1 | Processes for Sid's own tables |
| `SIDPLAY_BACKGROUND_NICE` | 10 | Added to the service's niceness for the background processes |
| `SIDPLAY_MAX_TABLES` | 12 | Open tables at once, everyone together |
| `SIDPLAY_IDLE_MINUTES` | 30 | A table with no human action this long closes |
| `SIDPLAY_INVITE_MINUTES` | 60 | An unanswered partner invitation expires |
| `SIDPLAY_SID_TABLES` | 1 | Play Sid's own table on each deal (0: no IMP comparison) |
| `SIDPLAY_PACE`, `SIDPLAY_TRICK_PAUSE` | 0.5, 1.2 | Seconds between bot cards, and after a finished trick |
| `SIDPLAY_SECURE_COOKIES` | 0 | 1 behind HTTPS |

## Limits

- Live tables are held in memory: a restart ends them. Finished boards and Sid tables are in SQLite.
- No password reset and no email. Lost passwords mean a new account.
- No undo, no alerts or explanations, no chat, no claims by defenders.
- Abuse limits are basic: per-IP limits on sign-ups, sign-ins and new tables, one open table per person, a global
  table cap.
- Every board is stored with the full deal, auction, play and the bot's identity. Human-against-Sid boards could
  become evaluation or training data later. Nothing reads them yet.
