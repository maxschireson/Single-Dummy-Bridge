#!/usr/bin/env python3
"""Rebuild feature/gen9 on a new base: drop the Gen 8 snapshot commit, replay the Gen 9 commits (merges too).

    python3 tools/base_swap.py --repo /path/to/checkout --new-base origin/main            # dry run: report only
    python3 tools/base_swap.py --repo ... --new-base origin/main --apply                  # also build the new branch
    python3 tools/base_swap.py --repo ... --new-base origin/main --apply --also feature/gen9-bidding-filter ...

`feature/gen9` is `main` plus one snapshot commit of the Gen 8 prototype (default `7d301eb`) plus
Gen 9 commits. When Gen 8's real source is on main, this script:

1. Lists the **hooks**: files the snapshot changed that Gen 9 changed again (`git diff snapshot..branch`
   restricted to the snapshot's files). These are where Gen 9 reaches into Gen 8 code.
2. Lists the **drift**: snapshot files whose content on the new base differs from the snapshot's
   (Gen 8 as it landed is not the prototype Gen 9 was built on), and snapshot files the new base
   does not have. A hook that drifted is the first place to look by hand.
3. With `--apply`: in a temporary worktree (your checkout is not touched), runs
   `git rebase --rebase-merges --onto NEW_BASE SNAPSHOT BRANCH` and writes the result to a new local
   branch (default `feature/gen9-rebased-<new base sha>`). On a conflict it aborts, names the files
   and exits with status 2. Then it compares every Gen 9 file change before and after (same patch or
   not), so a reviewer sees exactly what the swap altered.
4. With `--also BRANCH ...`: rebases each branch cut from `feature/gen9` (an open PR, say) onto the new
   branch, from its merge base with the old `feature/gen9`.
5. With `--push`: pushes the new branches (never with force; it never rewrites `feature/gen9` or any
   existing remote branch). Pointing `feature/gen9` at the result is a separate decision for g9.

`--report PATH` writes the report as markdown. Needs git 2.22 or later; standard library only.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


class Git:
    def __init__(self, repo: Path):
        self.repo = repo

    def run(self, *args: str, cwd: Path | None = None, check: bool = True, input: str | None = None) -> subprocess.CompletedProcess:
        r = subprocess.run(["git", *args], cwd=cwd or self.repo, capture_output=True, text=True, input=input)
        if check and r.returncode != 0:
            raise SystemExit(f"git {' '.join(args[:3])} failed: {r.stderr.strip() or r.stdout.strip()}")
        return r

    def out(self, *args: str, **kw) -> str:
        return self.run(*args, **kw).stdout.strip()

    def lines(self, *args: str, **kw) -> list[str]:
        return [l for l in self.out(*args, **kw).splitlines() if l]

    def sha(self, ref: str) -> str:
        return self.out("rev-parse", "--verify", f"{ref}^{{commit}}")

    def patch_id(self, a: str, b: str, path: str) -> str:
        diff = self.run("diff", a, b, "--", path).stdout
        if not diff:
            return ""
        pid = self.run("patch-id", "--stable", input=diff).stdout.split()
        return pid[0] if pid else ""


def analyse(g: Git, snapshot: str, branch: str, new_base: str) -> dict:
    parent = g.sha(f"{snapshot}^")
    if g.run("merge-base", "--is-ancestor", snapshot, branch, check=False).returncode != 0:
        raise SystemExit(f"{snapshot} is not an ancestor of {branch}")
    first_parents = g.lines("rev-list", "--first-parent", f"{snapshot}^..{branch}")
    if g.sha(snapshot) not in first_parents:
        if g.out("rev-parse", "--is-shallow-repository") == "true":
            raise SystemExit(f"the checkout is shallow and its history stops before {snapshot}; fetch more "
                             f"(git fetch --depth=500 origin <branch>) and run again")
        raise SystemExit(f"{snapshot} is not on {branch}'s first-parent line; this script expects main + snapshot + Gen 9")
    snap_files = set(g.lines("diff", "--name-only", parent, snapshot))
    gen9_files = set(g.lines("diff", "--name-only", snapshot, branch))
    hooks = sorted(snap_files & gen9_files)
    base_has = set(g.lines("ls-tree", "-r", "--name-only", new_base))
    snap_has = set(g.lines("ls-tree", "-r", "--name-only", snapshot))
    drift = sorted(f for f in snap_files if f in base_has and f in snap_has and g.run("diff", "--quiet", snapshot, new_base, "--", f, check=False).returncode)
    gone = sorted(f for f in snap_files if f in snap_has and f not in base_has)
    commits = g.lines("rev-list", "--reverse", f"{snapshot}..{branch}")
    merges = g.lines("rev-list", "--merges", f"{snapshot}..{branch}")
    stats = {}
    for f in hooks:
        s = g.out("diff", "--numstat", snapshot, branch, "--", f).split()
        stats[f] = f"+{s[0]} -{s[1]}" if len(s) >= 2 else ""
    return dict(snapshot=g.sha(snapshot), parent=parent, branch=branch, branch_sha=g.sha(branch), new_base=g.sha(new_base),
                commits=len(commits), merges=len(merges), snap_files=sorted(snap_files), gen9_files=sorted(gen9_files),
                hooks=hooks, hook_stats=stats, drift=drift, gone=gone)


def rebase(g: Git, onto: str, upstream: str, branch_sha: str, out_branch: str) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="base-swap-"))
    wt = tmp / "wt"
    try:
        g.run("worktree", "add", "--detach", str(wt), branch_sha)
        env_args = ["-c", "user.name=base-swap", "-c", "user.email=base-swap@invalid"]
        r = g.run(*env_args, "rebase", "--rebase-merges", "--onto", onto, upstream, cwd=wt, check=False)
        if r.returncode != 0:
            conflicts = g.lines("diff", "--name-only", "--diff-filter=U", cwd=wt, check=False)
            stopped_at = g.out("rev-parse", "--short", "REBASE_HEAD", cwd=wt, check=False)
            g.run("rebase", "--abort", cwd=wt, check=False)
            return dict(ok=False, conflicts=conflicts, stopped_at=stopped_at, detail=(r.stderr or r.stdout).strip()[-800:])
        new = g.out("rev-parse", "HEAD", cwd=wt)
        g.run("branch", "-f", out_branch, new)
        return dict(ok=True, sha=new, branch=out_branch)
    finally:
        g.run("worktree", "remove", "--force", str(wt), check=False)
        shutil.rmtree(tmp, ignore_errors=True)


def compare(g: Git, a: dict, new_sha: str) -> list[tuple[str, str]]:
    rows = []
    for f in a["gen9_files"]:
        before = g.patch_id(a["snapshot"], a["branch_sha"], f)
        after = g.patch_id(a["new_base"], new_sha, f)
        rows.append((f, "same change" if before == after else ("change gone" if not after else "change differs")))
    extra = sorted(set(g.lines("diff", "--name-only", a["new_base"], new_sha)) - set(a["gen9_files"]))
    rows += [(f, "changed only after the swap") for f in extra]
    return rows


def render(a: dict, result: dict | None, cmp: list | None, also: list) -> str:
    s = lambda x: x[:9]
    L = ["# Base swap report", "",
         f"`{a['branch']}` at `{s(a['branch_sha'])}`: main `{s(a['parent'])}` + snapshot `{s(a['snapshot'])}` + "
         f"{a['commits']} Gen 9 commits ({a['merges']} merges). New base `{s(a['new_base'])}`.", "",
         f"The snapshot changed {len(a['snap_files'])} files; Gen 9 changed {len(a['gen9_files'])}.", "",
         "## Hooks: snapshot files Gen 9 changed again", ""]
    L += [f"- `{f}` ({a['hook_stats'].get(f, '')})" + ("  **drifted on the new base**" if f in a["drift"] else "")
          + ("  **missing on the new base**" if f in a["gone"] else "") for f in a["hooks"]] or ["None."]
    L += ["", "## Drift: snapshot files that differ on the new base", ""]
    L += [f"- `{f}`" + (" (a hook)" if f in a["hooks"] else "") for f in a["drift"]] or ["None: the new base has the snapshot's content for every file it touched."]
    if a["gone"]:
        L += ["", "Missing on the new base: " + ", ".join(f"`{f}`" for f in a["gone"])]
    L += [""]
    if result is not None:
        L += ["## Replay", ""]
        if result["ok"]:
            L += [f"Rebuilt as local branch `{result['branch']}` at `{s(result['sha'])}`.", ""]
            changed = [r for r in cmp if r[1] != "same change"]
            L += [f"Every Gen 9 file change is the same patch as before ({len(cmp)} files)." if not changed else
                  f"{len(cmp) - len(changed)} of {len(cmp)} file changes are the same patch; these are not:"]
            L += [f"- `{f}`: {why}" for f, why in changed]
        else:
            L += [f"**Stopped on a conflict** at `{result.get('stopped_at')}`; nothing was written. Files: "
                  + ", ".join(f"`{f}`" for f in result["conflicts"]), "", "```", result["detail"], "```"]
        L.append("")
    for b in also:
        L += [f"- `{b['name']}`: " + (f"rebased as `{b['branch']}` at `{s(b['sha'])}`" if b["ok"] else
                                      f"conflict in {', '.join(b['conflicts'])}; not rebased")]
    if also:
        L.append("")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo", type=Path, default=Path.cwd(), help="a checkout with the branches fetched")
    ap.add_argument("--branch", default="origin/feature/gen9")
    ap.add_argument("--snapshot", default="7d301eb")
    ap.add_argument("--new-base", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--out-branch")
    ap.add_argument("--also", nargs="*", default=[], help="branches cut from feature/gen9 to rebase onto the result")
    ap.add_argument("--push", action="store_true", help="push the new branches (no force)")
    ap.add_argument("--report", type=Path)
    a = ap.parse_args()
    g = Git(a.repo.resolve())
    info = analyse(g, a.snapshot, a.branch, a.new_base)
    result = cmp = None
    also = []
    if a.apply:
        out = a.out_branch or f"feature/gen9-rebased-{info['new_base'][:7]}"
        if g.run("rev-parse", "--verify", f"refs/heads/{out}", check=False).returncode == 0:
            raise SystemExit(f"local branch {out} exists; pass --out-branch or delete it")
        result = rebase(g, info["new_base"], info["snapshot"], info["branch_sha"], out)
        if result["ok"]:
            cmp = compare(g, info, result["sha"])
            for b in a.also:
                base = g.out("merge-base", b, info["branch_sha"])
                name = f"{b.split('/', 1)[-1] if b.startswith('origin/') else b}-rebased-{info['new_base'][:7]}"
                r = rebase(g, result["sha"], base, g.sha(b), name)
                also.append(dict(name=b, **r))
            if a.push:
                for br in [result["branch"]] + [x["branch"] for x in also if x["ok"]]:
                    g.run("push", "origin", f"refs/heads/{br}:refs/heads/{br}")  # fails if it exists: no overwrite
    text = render(info, result, cmp, also)
    print(text)
    if a.report:
        a.report.write_text(text + "\n")
    if result is not None and not result["ok"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
