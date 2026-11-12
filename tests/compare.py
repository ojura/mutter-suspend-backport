#!/usr/bin/python3
"""Puts the results of a stock and a patched run of run_cases.py side by side.

usage: compare.py <stock results dir> <patched results dir>

For every case, phase and window it prints the state at the end of the
phase and the changes during it for both runs, marks the rows where the two
differ, and lists the libmutter that each case's shell mapped.
"""
import json
import sys
from pathlib import Path


def load(results):
    rows = {}
    order = []
    maps = {}
    for summary in sorted(results.glob('*/summary.json')):
        case = summary.parent.name
        maps[case] = [line for line in (summary.parent / 'maps.txt').read_text().splitlines()
                      if 'libmutter-14.so' in line]
        for row in json.loads(summary.read_text()):
            key = (row['case'], row['phase'], row['window'])
            rows[key] = row
            order.append(key)
    return rows, order, maps


def main():
    stock_rows, order, stock_maps = load(Path(sys.argv[1]))
    patched_rows, _, patched_maps = load(Path(sys.argv[2]))
    case = None
    for key in order:
        if key[0] != case:
            case = key[0]
            print(f'\n{case}')
            print(f'  stock shell mapped {", ".join(stock_maps[case])}')
            print(f'  patched shell mapped {", ".join(patched_maps[case])}')
        s, p = stock_rows[key], patched_rows.get(key)
        def cell(r):
            if r is None:
                return 'missing'
            changes = ', '.join(r['changes']) or 'no change'
            return f'{r["observed"]} ({changes}){"" if r["ok"] else " UNEXPECTED"}'
        differs = p is None or s['observed'] != p['observed']
        mark = 'DIFFERS' if differs else 'same   '
        print(f'  {mark} {key[1]} / {key[2]}: stock {cell(s)}; patched {cell(p)}')


if __name__ == '__main__':
    main()
