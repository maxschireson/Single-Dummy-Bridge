#!/usr/bin/env python3
"""Summarise gen8_budget.py rows: per budget, regret and CPU a decision by trick window, the difference from Gen 8's own
budget (32 from 512) paired by decision, and the per-table totals over tricks 1-6 (mean regret in each window times
Gen 8's decisions a table in that window, from decisions_per_table.json).

  python summarize.py rows.jsonl [--imps-per-trick 1.43]

IMPs use the loop's conversion (0.07 tricks a board is about 0.1 IMPs). In duplicate one bot's decisions over a board
(its side at both tables) are about one table's decisions, so a table's total regret reads as tricks a board for one bot.
"""
import argparse, json
from pathlib import Path
import numpy as np

WINDOWS = ('1-2', '3-4', '5-6')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('rows', type=Path)
    p.add_argument('--imps-per-trick', type=float, default=0.1 / 0.07)
    a = p.parse_args()
    rows = [json.loads(l) for l in a.rows.read_text().splitlines() if l.strip()]
    counts = json.loads((a.rows.parent / 'decisions_per_table.json').read_text())
    per_table = {w: float(np.mean([c[w] for c in counts])) for w in WINDOWS}
    budgets = [k for k in rows[0] if '/' in k]
    base = '32/512'
    win = lambda r: WINDOWS[min((r['trick'] - 1) // 2, 2)]
    print(f'{len(rows)} decisions from {len({(r["file"], r["table"]) for r in rows})} tables; Gen 8 decisions a table '
          + ', '.join(f'tricks {w}: {per_table[w]:.1f}' for w in WINDOWS))
    print(f'decisions where the reference ranks the cards apart: {np.mean([r["ref_spread"] > 1e-9 for r in rows]):.0%}; '
          f'reference CPU {np.mean([r["ref_cpu"] for r in rows]):.2f} s, layouts {np.mean([r["ref_layouts"] for r in rows]):.0f} distinct')
    out = {}
    print('\nbudget | regret a decision (all) | vs 32/512 paired | best card | gap error | CPU a decision | distinct layouts'
          ' | per table: regret vs 32/512, IMPs, CPU vs 32/512')
    for b in budgets:
        reg = np.array([r[b]['regret'] for r in rows])
        diff = np.array([r[b]['regret'] - r[base]['regret'] for r in rows])
        tot, var, cpu_tot = 0., 0., 0.
        for w in WINDOWS:
            sel = [r for r in rows if win(r) == w]
            if not sel:
                continue
            dw = np.array([r[b]['regret'] - r[base]['regret'] for r in sel])
            cw = np.array([r[b]['cpu'] - r[base]['cpu'] for r in sel])
            tot += per_table[w] * dw.mean()
            var += (per_table[w] * dw.std(ddof=1) / np.sqrt(len(dw))) ** 2
            cpu_tot += per_table[w] * cw.mean()
        gap = [r[b]['gap_mae'] for r in rows if r[b]['gap_mae'] is not None]
        out[b] = dict(regret=reg.mean(), regret_se=reg.std(ddof=1) / np.sqrt(len(reg)), diff=diff.mean(),
                      diff_se=diff.std(ddof=1) / np.sqrt(len(diff)), best=float(np.mean(reg <= 1e-9)), gap=float(np.mean(gap)),
                      cpu=float(np.mean([r[b]['cpu'] for r in rows])), unique=float(np.mean([r[b]['unique'] or 0 for r in rows])),
                      table=tot, table_se=var ** .5, imps=tot * a.imps_per_trick, imps_se=var ** .5 * a.imps_per_trick, table_cpu=cpu_tot)
        o = out[b]
        print(f'{b:>9} | {o["regret"]:.4f} +- {o["regret_se"]:.4f} | {o["diff"]:+.4f} +- {o["diff_se"]:.4f} | {o["best"]:.2f} | '
              f'{o["gap"]:.3f} | {o["cpu"]:.3f} s | {o["unique"]:.0f} | {o["table"]:+.3f} +- {o["table_se"]:.3f} tricks, '
              f'{o["imps"]:+.3f} +- {o["imps_se"]:.3f} IMPs, {o["table_cpu"]:+.2f} s')
    print('\nby window: regret vs 32/512 paired (n)')
    for b in budgets:
        cells = []
        for w in WINDOWS:
            sel = [r for r in rows if win(r) == w]
            dw = np.array([r[b]['regret'] - r[base]['regret'] for r in sel])
            cells.append(f'{w}: {dw.mean():+.4f} +- {dw.std(ddof=1) / np.sqrt(len(dw)):.4f} (n={len(dw)})' if len(dw) > 1 else f'{w}: -')
        print(f'{b:>9} | ' + ' | '.join(cells))
    (a.rows.parent / 'summary.json').write_text(json.dumps(dict(per_table=per_table, budgets=out, decisions=len(rows)), indent=1))


if __name__ == '__main__':
    main()
