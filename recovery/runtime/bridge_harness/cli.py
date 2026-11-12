import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import time

from .core import Board
from .corpus import freeze_auction, generate, load, save
from .players import BenPlayer, make_player
from .runner import isolated_pair, play_table, replay
from .report import markdown, summarize


def records(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write_report(rows, dest):
    s = summarize(rows)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.with_suffix(".json").write_text(json.dumps(s, indent=2) + "\n")
    dest.with_suffix(".md").write_text(markdown(s))
    return s


def main(argv=None):
    parser = argparse.ArgumentParser(description="Single-dummy bridge experimentation harness")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("generate")
    p.add_argument("--count",type=int,default=1000)
    p.add_argument("--seed",type=int,default=1)
    p.add_argument("--family-size",type=int,default=1)
    p.add_argument("--out",required=True)
    p = sub.add_parser("convert")
    p.add_argument("input"); p.add_argument("output")
    p = sub.add_parser("freeze-auctions")
    p.add_argument("input"); p.add_argument("output")
    p.add_argument("--ben-url",default="http://127.0.0.1:8085")
    p.add_argument("--timeout",type=float,default=120)
    p.add_argument("--resume",action="store_true",help="Continue a validated frozen-auction prefix")
    p = sub.add_parser("match")
    p.add_argument("corpus"); p.add_argument("--out",required=True)
    p.add_argument("--mode",choices=("declarer","defence","partnership"),default="declarer")
    for key, default in (("candidate","pimc"),("baseline","greedy"),("common","greedy")):
        p.add_argument("--"+key,choices=("random","greedy","pimc","ben"),default=default)
    p.add_argument("--samples",type=int,default=32)
    p.add_argument("--objective",choices=("score","tricks","make"),default="score")
    p.add_argument("--near-tie",type=float,default=0.0,help="Uniform exploration within this objective-unit gap")
    p.add_argument("--serial-dds",dest="batch",action="store_false",help="Disable cross-world TT reuse")
    p.add_argument("--seed",type=int,default=731,help="Decision RNG; separate from corpus-generation seed")
    p.add_argument("--ben-url",default="http://127.0.0.1:8085")
    p.add_argument("--ben-label",default="unspecified external BEN configuration")
    p.add_argument("--timeout",type=float,default=120,help="HTTP request deadline")
    p.add_argument("--board-timeout",type=float,default=300,help="Hard deadline for both tables including native calls")
    p.add_argument("--limit",type=int)
    p.add_argument("--resume",action="store_true",help="Skip already recorded boards; require identical config/corpus")
    p = sub.add_parser("report")
    p.add_argument("records"); p.add_argument("--out",required=True)
    p = sub.add_parser("replay")
    p.add_argument("records"); p.add_argument("--board")
    p = sub.add_parser("branch")
    p.add_argument("records"); p.add_argument("--board",required=True)
    p.add_argument("--table",type=int,choices=(0,1),default=0)
    p.add_argument("--ply",type=int,help="Resume just before this decision; default first difference")
    p.add_argument("--player",choices=("random","greedy","pimc","ben"),required=True)
    p.add_argument("--out",required=True)
    args = parser.parse_args(argv)
    if args.command == "generate":
        save(generate(args.count,args.seed,args.family_size),args.out)
        print(f"Wrote {args.count} boards to {args.out}")
    elif args.command == "convert":
        save(load(args.input),args.output)
    elif args.command == "freeze-auctions":
        bidder = BenPlayer(args.ben_url,args.timeout)
        out = Path(args.output); out.parent.mkdir(parents=True,exist_ok=True)
        log_path = out.with_suffix(".auctions.jsonl")
        boards = load(args.input)
        if len({b.id for b in boards}) != len(boards):
            raise ValueError("Duplicate board IDs")
        if (out.exists() or log_path.exists()) and not args.resume:
            raise ValueError("Output exists; choose a new filename")
        frozen_prefix = load(out) if out.exists() else []
        logs = records(log_path) if log_path.exists() else []
        if len(frozen_prefix) != len(logs) or len(frozen_prefix) > len(boards):
            raise ValueError("Frozen-auction/transcript prefix length mismatch; repair explicitly")
        for original, frozen, logged in zip(boards, frozen_prefix, logs):
            identity = lambda b: (b.id, b.hands, b.dealer, b.vulnerability, b.family)
            if identity(original) != identity(frozen) or frozen.auction_source != "BEN" \
                    or frozen.opening_lead is not None or logged["board"] != original.id \
                    or tuple(t["bid"] for t in logged["transcript"]) != frozen.auction \
                    or [t["seat"] for t in logged["transcript"]] != [
                        "NESW"[(original.dealer+i)%4] for i in range(len(frozen.auction))]:
                raise ValueError("Frozen auction does not match original deal/transcript")
        mode = "a" if args.resume else "x"
        with out.open(mode) as f, log_path.open(mode) as log:
            for b in boards[len(frozen_prefix):]:
                frozen, transcript = freeze_auction(b,bidder)
                f.write(json.dumps(frozen.to_dict())+"\n"); f.flush()
                log.write(json.dumps(dict(board=b.id,transcript=transcript))+"\n"); log.flush()
                print(f"{b.id}: {frozen.contract}",flush=True)
    elif args.command == "match":
        boards = load(args.corpus)
        if len({b.id for b in boards}) != len(boards):
            raise ValueError("Board IDs must be unique")
        corpus_hash = hashlib.sha256(Path(args.corpus).read_bytes()).hexdigest()
        if args.limit:
            boards = boards[:args.limit]
        config = {k:v for k,v in vars(args).items() if k not in ("command","out","resume","limit","corpus")}
        config["corpus_sha256"] = corpus_hash
        out = Path(args.out); out.parent.mkdir(parents=True,exist_ok=True)
        existing = records(out) if args.resume and out.exists() else []
        if out.exists() and not args.resume:
            raise ValueError("Output exists; use --resume or a new filename")
        if any(r["config"] != config for r in existing):
            raise ValueError("Resume config/corpus does not match")
        done = {r["board"]["id"] for r in existing}
        start = time.perf_counter()
        with out.open("a" if args.resume else "x") as f:
            for i,b in enumerate(boards):
                if b.id in done:
                    continue
                r = isolated_pair(b,config,args.board_timeout)
                f.write(json.dumps(r,sort_keys=True)+"\n"); f.flush()
                existing.append(r)
                if (i+1)%10==0 or r["status"]!="ok" or i==len(boards)-1:
                    print(f"{i+1}/{len(boards)} board={b.id} status={r['status']} elapsed={time.perf_counter()-start:.1f}s",flush=True)
        s=write_report(existing,out.with_suffix(".report"))
        print(json.dumps({k:s[k] for k in ("completed_pairs","mean_imps","cluster_bootstrap_95_interval","failures")},indent=2))
        if s["failures"]:
            return 1
    elif args.command == "report":
        write_report(records(args.records),args.out)
    elif args.command == "replay":
        selected = [r for r in records(args.records) if not args.board or r["board"]["id"]==args.board]
        if not selected:
            raise ValueError("No matching board")
        for r in selected:
            replay(r)
        print(f"Validated {len(selected)} records")
    elif args.command == "branch":
        r=next(r for r in records(args.records) if r["board"]["id"]==args.board)
        ply=args.ply if args.ply is not None else r.get("first_difference")
        if ply is None or not 0<=ply<=len(r["tables"][args.table]["actions"]):
            raise ValueError("Specify a valid --ply; no first difference available")
        board=Board.from_dict(r["board"])
        assignment=list(r["assignments"][args.table])
        # Change the controller making the selected decision and its partnership.
        if ply < len(r["tables"][args.table]["actions"]):
            from .core import SEATS
            seat=SEATS.index(r["tables"][args.table]["actions"][ply]["controller"])
            for s in range(4):
                if s%2==seat%2: assignment[s]=args.player
        kwargs={k:r["config"][k] for k in ("samples","ben_url","timeout","objective","batch","near_tie") if k in r["config"]}
        players={p:make_player(p,**kwargs) for p in set(assignment)}
        try:
            table=play_table(board,assignment,players,r["config"]["seed"],r["tables"][args.table]["actions"][:ply])
        finally:
            for p in players.values():
                if hasattr(p,"close"): p.close()
        dest=Path(args.out);dest.parent.mkdir(parents=True,exist_ok=True)
        branched={**r,"tables":[table],"assignments":[assignment],"status":table["status"],
                  "branch":dict(parent=args.records,board=args.board,table=args.table,ply=ply,player=args.player)}
        for k in ("imps","score_difference","first_difference"):branched.pop(k,None)
        with dest.open("x") as f:f.write(json.dumps(branched)+"\n")
        print(f"Branch {table['status']}: {table.get('declarer_tricks')} tricks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
