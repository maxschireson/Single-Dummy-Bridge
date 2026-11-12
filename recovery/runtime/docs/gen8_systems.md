# Gen 8 system layer: systems as data, a system-aware scorer

> **Work in progress. Not the final form.** This is the first layer of the Gen 8 system work,
> pushed so other sessions can read it and build on it. The package schema, the scorer file
> format, the bidder interface, the carding field list and the system ids may all still
> change. Nothing here is adopted: no arena bot, config, manifest or runtime uses it, and
> [current system](current-system.md) is unchanged. Do not treat any of it as a cutover input.

Status, 11 November 2026: library, two commands and tests. **No arena bot uses it and no
existing engine, runtime or model file is changed.** Branch `feature/gen8-systems-20261111`.

The aim is a bot that plays with and against more than one bidding system and set of carding
agreements. This is the part every later step needs: a way to say what a partnership plays, a
way to plug in whatever bids that system, and an auction reader that takes the declaration as
an input. Nothing in the code names a system or assumes how many there are.

## Pieces

| Piece | Where | What it does |
| --- | --- | --- |
| System package | `configs/systems/<id>.json` | What one partnership plays: public bidding declaration (convention card in any format, structured descriptor, notes), public carding descriptor, and, kept apart, the generators (bidders) pinned to it by SHA-256 |
| Registry | `bridge_harness/systems.py` | Loads and validates the packages. An unregistered declaration fails closed. A generator can be pinned to one system only |
| Table declarations | `systems.TableSystems` | What North-South and East-West have declared at one table, with the three training views (declared, both hidden, each side hidden with probability 1/2) |
| Descriptor encoding | `systems.DescriptorVocabulary` | Turns open key/value descriptors (carding fields, convention-card switches) into a fixed vector; a net stores the vocabulary it was trained with |
| Bidder interface | `bridge_harness/system_bidders.py` | "Which call would this hand make next?" Adapters: the BEN-format LSTM bidder (every house bidder), a `python` factory hook for engines kept outside the repository, and a toy rule bidder used as a test fixture |
| Scorer | `bridge_harness/system_nets.py` | `SystemFitScorer`: the hand-fit scorer with the call table chosen by the declared system of the side that made each call. `bind(table)` returns an object with `FitScorer`'s interface |
| Data and trainer | `bridge_harness/system_fit.py`, `scripts/gen_system_fit.py`, `scripts/train_system_scorer.py` | Deals bid with a different system per side, labelled by replaying each seat's calls through its own side's bidder; trainer for any number of systems; adding a system without touching the others |

It replaces the integer system ids of the prototype on
`research/gen6-system-aware-policy-20261111` (`bidding_system_context.py`) and keeps that
prototype's rules: declarations are public, generator identity is provenance and never a model
input, and training hides declarations in the same three ways.

## The scorer file

`FitScorer`'s arrays, except:

- `Wa` is `(K, 28*38, H)`: K basis call tables. A 2-D `Wa` is a file made before systems
  existed; it loads as one table used for every system and scores **exactly** as `FitScorer`.
- `sys_ids`: the systems the file was trained on. `sys_ids[0]` is `unknown`.
- `sys_gate` `(S, K)`: each system's weights over the basis tables.

A slot's call table is `sum_k gate[k] * Wa[k]` with the gate of the side whose seat owns the
slot (own side: even seat-relative slots). The layers after the first are shared. The trainer
writes one shared table plus one correction per system, so `unknown` is the shared table alone.
A declared system the file has never seen is read as `unknown` and recorded in
`scorer.unseen`. The list of systems lives in the file, not in the code or the registry's
order, so files trained at different times on different sets of systems coexist.

## Adding a system

No code changes when its bidder kind already has an adapter.

1. Write `configs/systems/<id>.json` (copy an existing one). `status: "active"` requires every
   generator to carry its `sha256`. Carding fields must come from
   `configs/systems/_carding_fields.json` (provisional; extend it by editing the file).
2. Generator kinds: `ben-lstm-keras` (a `.keras` file; `external: true` for one in a BEN
   install), `python` (`factory: "module:callable"`, for a rule engine or anything else that
   implements `session()`/`act()` and reports its own `sha256`), `toy` (fixture).
3. Data. Every ordered pairing of the listed systems, or explicit tables:

   ```bash
   python scripts/gen_system_fit.py val.npz   --seed 9    --deals 2700  --systems house-gen6,house-gen5,house-dds40k
   python scripts/gen_system_fit.py train.npz --seed 3100 --deals 18000 --systems house-gen6,house-gen5,house-dds40k
   python scripts/gen_system_fit.py new.npz   --seed 3200 --deals 20000 --tables new-id:house-gen6,house-gen6:new-id,new-id:new-id
   ```

   The command builds each system's generator, checks its identity against the pinned hash,
   and refuses to label auctions otherwise. The house bidders must be restored first
   (`python models/bidding/<release>/restore_model.py`) and need `h5py`.
4. Train. Start from a released scorer so that, before training, every system reads exactly as
   that scorer does; or add one system to a trained file with everything else frozen:

   ```bash
   python scripts/train_system_scorer.py out.npz --steps 600 --lr 2e-4,2e-5 --val val.npz --train train.npz \
       --init models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz --report out.json
   python scripts/train_system_scorer.py grown.npz --minutes 10 --val val_new.npz --train new.npz \
       --init out.npz --systems new-id --only new-id
   ```

   With `--only`, every array except the new system's own table is bit-for-bit unchanged, so
   the systems already in the file score as before. With validation data the run ends at its
   best checked state, the starting state included. The report lists validation loss per table
   three ways: declared, hidden, and with a wrong system declared on purpose. If "wrong" does
   not cost, the declaration is not being used.

## Using it in an engine (not wired)

Three small hooks, left for the Gen 7 to Gen 8 engine work because they touch `core.py`, the
runtime and the player:

1. A bot spec names the system its bidder plays (`system: "<id>"`). The runtime knows the four
   bidding actors of each auction, so it can form `TableSystems`: under common auctions both
   sides have the common bidder's system; under native auctions each side has its own.
2. `Observation` carries the two declarations. They are public information.
3. The player loads `SystemFitScorer(path)` once and uses `scorer.bind(table)` wherever it uses
   `FitScorer` today (layout weights in Gen 6, `Shown` in Gen 7).

The lead net is not system-aware. Until it is, `lead_source: 'scorer'` is the system-aware way
to make the opening lead.

## What was checked

`tests/test_bidding_systems.py`, 28 tests, about 45 s; every training test uses three or four
systems.

- A pre-system scorer file through `SystemFitScorer` equals `FitScorer` exactly, for every
  seat and dealer and whatever is declared. A Gen 6 player given the bound scorer plays four
  full tables card for card like the unchanged player (needs the built solver).
- Slots take the table of the side that called; unseen systems read as unknown; inference
  equals the trainer's forward pass.
- Mixed-table auctions are legal and complete by the harness's own validator, and each side
  follows its own bidder.
- The NumPy LSTM adapter's recurrent features equal `gen6_nets.BidderState` on the restored
  Gen 5 and Gen 6 bidders (skipped without `h5py` or the restored files). On 4,096 fresh deals
  the Gen 6 and Gen 5 bidders' auctions differ on 26.1% of deals (the bidder release note:
  26.7% on 16,384); Gen 5 and the DDS-40k bidder differ on 1.2%.
- Hand-written gradients against finite differences.
- Three toy systems (strong no-trump, weak no-trump with four-card majors, strong club):
  declared < hidden < wrong in all nine pairings.
- Adding a fourth system with `only`: all other arrays unchanged, old systems score
  identically, the new system's tables improve.

First run on real bidders: [reports/gen8-system-scorer-smoke-2026-11-11](../reports/gen8-system-scorer-smoke-2026-11-11/README.md).

## Not done

- The engine hooks above. Nothing reaches a table yet.
- Only the scorer is system-aware. Lead net, bidder (own and opposing system as inputs) and
  the Gen 7 net's carding inputs are not.
- Carding: the descriptor and its encoding exist. The rule that picks among equal cards
  according to the descriptor does not, and no net reads the descriptor.
- No system outside the house lineage has a generator. A rule engine or another bidder plugs in
  as a `python` factory; none is in use.
- Convention-card readers: none. ACBL and WBF cards, notes and system summary forms need a
  reader that produces a descriptor.
- A gate computed from a card's descriptor instead of a per-system row needs a population of
  systems to learn from. The file format and scorer already accept any gate matrix; the
  trainer writes only shared-plus-correction.
- System detection (Gen 9). When it is built, uncertainty over systems should mix the scores
  of the candidate systems, not their tables: the layers after the first are not linear.
- The scorer's architecture is unchanged. How one side's system changes the meaning of the
  other side's calls is left to the shared layers.
