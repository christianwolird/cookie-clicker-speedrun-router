"""Exhaustively try bounded one/two-action edits, repartitioning each sequence.

This is a local neighborhood audit, not a proof of global optimality. Stops
after a complete non-improving pass or the requested wall-time budget.
"""
import argparse
from dataclasses import replace
import itertools
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src'))
from ccsr.routes import load_route, execute_route, write_route
from native_bridge import pack_actions, unpack_actions, partition_actions
from experiment_paths import WORK


def edits(sequence):
    a = list(sequence)
    buildings = [i for i, c in enumerate(a) if c < 256]
    for i in buildings:
        for q in range(1, 11):
            b = a.copy(); b[i] = a[i] // 16 * 16 + q
            yield 'quantity', tuple(b)
    for i, j in itertools.combinations(buildings, 2):
        for qi, qj in itertools.product(range(1, 11), repeat=2):
            b = a.copy(); b[i] = a[i] // 16 * 16 + qi; b[j] = a[j] // 16 * 16 + qj
            yield 'two_quantities', tuple(b)
    for i in range(len(a)):
        yield 'delete', tuple(a[:i] + a[i+1:])
        for j in range(len(a)):
            b = a.copy(); item = b.pop(i); b.insert(j, item)
            yield 'move', tuple(b)
            b = a.copy(); b[i], b[j] = b[j], b[i]
            yield 'swap', tuple(b)
    additions = [16*b + q for b in range(5) for q in range(1, 11)]
    additions += [256+u for u in range(16) if 256+u not in a]
    for item in additions:
        for i in range(len(a)+1):
            yield 'insert', tuple(a[:i] + [item] + a[i:])
    for size in (2, 3, 4):
        for i in range(len(a)-size+1):
            block = a[i:i+size]; rest = a[:i] + a[i+size:]
            for j in range(len(rest)+1):
                yield 'block_move', tuple(rest[:j] + block + rest[j:])


def main():
    p = argparse.ArgumentParser(); p.add_argument('name')
    p.add_argument('--source', default='/tmp/ccsr-trained-12h-20260914/session_best.route')
    p.add_argument('--seconds', type=float, default=120); p.add_argument('--width', type=int, default=4)
    args = p.parse_args(); work = WORK; work.mkdir(parents=True, exist_ok=True)
    base = load_route(args.source); current = tuple(pack_actions(tuple(itertools.chain.from_iterable(base.errands))))
    best = execute_route(base).final_gamestate.age; start = time.monotonic(); tried = passes = 0; rows = []
    while time.monotonic()-start < args.seconds:
        passes += 1; previous = best; seen = {current}; next_sequence = current; counts = {}
        for mode, candidate in edits(current):
            if not candidate or candidate in seen: continue
            seen.add(candidate)
            if tried % 1000 == 0 and time.monotonic()-start >= args.seconds: break
            errands, score = partition_actions(unpack_actions(candidate), width=args.width)
            tried += 1; counts[mode] = counts.get(mode, 0)+1
            if score < best - 1e-8:
                plan = replace(base, name=args.name, algorithm='experimental_systematic_partition_search', errands=errands)
                actual = execute_route(plan).final_gamestate.age
                if abs(actual-score) > 1e-8: raise AssertionError((actual, score))
                best = actual; next_sequence = tuple(pack_actions(tuple(itertools.chain.from_iterable(errands))))
                pending = work / f'{args.name}.pending.route'
                write_route(pending, plan, comment='Systematic local edits with native partition and Python replay.', overwrite=True)
                pending.replace(work / f'{args.name}.route')
                row = dict(event='improvement', finish=best, mode=mode, tried=tried, elapsed=time.monotonic()-start)
                rows.append(row); print(json.dumps(row), flush=True)
        row = dict(event='pass', finish=best, pass_number=passes, counts=counts, tried=tried, elapsed=time.monotonic()-start)
        rows.append(row); print(json.dumps(row), flush=True)
        if best == previous: break
        current = next_sequence
    result = dict(finish=best, elapsed=time.monotonic()-start, tried=tried, passes=passes, parameters=vars(args), events=rows)
    (work / f'{args.name}.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__': main()
