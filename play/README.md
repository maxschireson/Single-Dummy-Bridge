# Play with Sid

A web server where people play bridge with and against Sid. Sid is not any of the project's current bots: it does
not exist yet, and this server is ready for it. Until it does, a stand-in plays Sid's seats: `8s-32`, Gen 8 standard.
The page says so, and names the stand-in, whenever the installed bundle is marked `stand_in`.

You just show up: you sit South, Sid is your partner North, and two more Sids sit East–West. After each board:

- **Analysis** of your play: where tricks were lost double dummy and why, when you had a line that guaranteed the
  contract against any layout, and which card gave it away (as a defender: which card handed declarer a guaranteed
  line). See [The analysis](#the-analysis).
- **Sid in your seat**: Sid plays the same deal at all four seats (the "Sid table"). You see its auction, play, result
  and the same analysis, and your IMPs against it.
- **History** for your browser session (a cookie): step back and forth through your deals, and **play any deal again**
  at a new table. Deals played again are marked and kept out of the IMP totals; Sid's table is reused from the first
  time.
- **Sign up** gives you a username and password (suggested; both can be changed). The browser's boards move into the
  account, which you can then review from any device. There is no email and no password reset.

There are no partner tables, matches or events.

## How a table works

- **Seats.** The person sits South; Sid sits North, East and West.
- **Boards.** Random deals; dealer and vulnerability follow the standard 16-board cycle. A deal played again keeps its
  board number, dealer and vulnerability.
- **Declaring.** When North–South win the contract, the person plays both hands, even when Sid-North won the auction,
  as on BBO robot tables.
- **Claims.** Declarer can claim any number of the remaining tricks at any time. The claim is accepted when
  declarer's side can take that many double dummy from the current position (as BBO robots judge claims). A refusal
  does not say how many tricks were there, since that would reveal the hidden hands.
- **Scoring.** The score is North–South's. After each board a background worker plays the deal with Sid at all
  four seats (Sid's own auction, Sid's play). IMPs = IMP(your score − Sid table score). So a plus means the humans
  did better than Sid would have in their seats.
- **Sid's systems.** Both sides declare Sid's system (`house-gen6` for `8s-32`), since the person bids with Sid. Sid
  makes no alerts and gives no explanations.
- **Guests.** A guest's boards are tied to a browser cookie. On sign-up or sign-in in that browser they move to the
  account, and so does an open table.

## The analysis

`sidplay/analysis.py`, run in its own worker process (no models) after each board, once for the person's table and
once for Sid's table, from South's chair ("you", or "Sid in your seat"; dummy's cards count as declarer's).

- **Double dummy, every card** (DDS from the bundle's source): the value of each legal card at each card of the play.
  A card that is not double-dummy best costs its side the difference. Your losses are listed with the better cards;
  losses by the other seats are counted (partner's, and tricks the other side gave back).
- **Guarantees** (the pooled-defender sure-trick search, `native/sure.cpp`, vendored from
  `experiments/sure_tricks/sure.cpp` at `2e6ed6d` on `research/sure-trick-table-20261112`): what the declaring side can
  guarantee against every split of the unseen cards, knowing hand sizes and show-outs. Nothing is sampled; the auction
  is not used. At the declaring side's decisions: did a line guarantee the contract, and did the card played keep it
  ("gave away the guaranteed contract"), and with 10 or fewer cards left, the exact number of guaranteed tricks
  ("dropped the guaranteed tricks from 8 to 5"). At a defender's decisions: declarer's guarantee after each card the
  defender could have played ("handed declarer a guaranteed making line"; "raised declarer's guaranteed tricks").
  A guaranteed contract can be given away with no double-dummy loss (the test deal A6 in that directory).
- **Why a double-dummy loss happened.** If the card gave up a guarantee, that is the reason. Otherwise the analysis
  tries every exchange of two cards between the hands the player could not see that is consistent with the
  show-outs so far, and reports the card whose position decided it ("It turned on the ♦Q: with it in East's hand
  instead of West's, this card would have been right"), or that no single exchange makes the card right.
- **Cost and limits.** Exact guaranteed tricks from 10 cards left in the mover's hand; from 11 to 13 cards only the
  contract question, 1.5 s per question, for the person's play only (Sid's table: from 10 cards); at most 40 s of sure-trick search and 20 s of exchanges per board, cheapest
  decisions first. A question that runs out of time leaves that decision "not analysed" and the page says how many.
  Measured on random deals in a 2-core sandbox: 5 to 16 s for a whole analysis. A defender's own guarantee to beat
  the contract (two defenders with hidden hands) is not computed.
- Analyses are stored with the board. A board without one (from before this version, or cut off by a restart) gets
  it when its page is opened.

## The information boundary

The server holds the deal; a browser only gets what its seat may see (`Table.view`). That means its own hand, dummy
after the opening lead, declarer's hand when this human plays it, and every hand once the board is over. A bot gets
the same `Observation` the game gives the seat controlling the card, and the bidder gets one hand and the calls.
The full deal reaches a worker only in three places: the claim check (the referee, not a player), Sid's own table,
where every seat is Sid, and the analysis of a finished board. The tests and `smoke.py` check each response for a hand the viewer should not have.

## Pieces

| File | Role |
| --- | --- |
| `sidplay/app.py` | FastAPI: the page, accounts, tables (long-polled), history |
| `sidplay/tables.py` | Seating, auction and play, Sid's turns, claims, replays, analyses, per-viewer views |
| `sidplay/engine.py` | Runs in worker processes: loads the bundle, bids, plays, checks claims, plays Sid's table |
| `sidplay/analysis.py` | Runs in the analysis process: double dummy, sure tricks and exchanges for a finished board |
| `native/sure.cpp` | The sure-trick search (vendored; `install.sh` builds `native/sure_cpp`) |
| `sidplay/pool.py` | Interactive, background and analysis worker pools |
| `sidplay/store.py` | SQLite: users (scrypt hashes), sessions, boards with their analyses, participants |
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

# The analyses need DDS in the source checkout and the sure-trick binary
python scripts/build_dds.py
g++ -O2 -std=c++17 -o play/native/sure_cpp play/native/sure.cpp

# Tests (stand-in bot; the analysis tests skip without DDS or sure_cpp) and a smoke run against a live server
cd play && python -m pytest tests -q
python play/smoke.py http://127.0.0.1:8090 --boards 2 --sid --analysis
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
| `SIDPLAY_SID_TABLES` | 1 | Play Sid's own table on each deal (0: no IMP comparison) |
| `SIDPLAY_ANALYSIS` | 1 | Analyse each finished board (yours and Sid's table) |
| `SIDPLAY_ANALYSIS_WORKERS` | 1 | Analysis processes (no models: about 0.1 GB each) |
| `SIDPLAY_SURE_CARDS`, `SIDPLAY_SURE_NEED_CARDS` | 10, 13 | Exact guaranteed tricks up to this many cards left; the contract question up to the second |
| `SIDPLAY_SURE_BUDGET`, `SIDPLAY_SWAP_BUDGET` | 40, 20 | Seconds per analysis for the sure-trick search and for the exchanges |
| `SIDPLAY_PACE`, `SIDPLAY_TRICK_PAUSE` | 0.5, 1.2 | Seconds between bot cards, and after a finished trick |
| `SIDPLAY_SECURE_COOKIES` | 0 | 1 behind HTTPS |

## Limits

- Live tables are held in memory: a restart ends them. Finished boards and Sid tables are in SQLite.
- No password reset and no email. Lost passwords mean a new account.
- No undo, no alerts or explanations, no chat, no claims by defenders.
- The analysis judges single-dummy play by guarantees (hand sizes and show-outs only) and double dummy by the real
  layout; neither reads the auction. Odds between lines that guarantee nothing are not computed.
- Abuse limits are basic: per-IP limits on sign-ups, sign-ins and new tables, one open table per person, a global
  table cap.
- Every board is stored with the full deal, auction, play and the bot's identity. Human-against-Sid boards could
  become evaluation or training data later. Nothing reads them yet.
