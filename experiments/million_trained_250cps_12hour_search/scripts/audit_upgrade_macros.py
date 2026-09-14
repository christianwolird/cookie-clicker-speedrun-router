"""Check why minimum prerequisite bundles require full x10 clicks here."""
import json
import sys
from experiment_paths import ROOT, WORK
sys.path.insert(0, str(ROOT/'src'))
from ccsr.game.gamestate import Gamestate

state = Gamestate('2.031'); rows = []
for name, upgrade in state.upgrade_catalog.items():
    if upgrade.price >= 1_000_000: continue
    for building, required in upgrade.requirements:
        if required <= 0: continue
        # Starting below the requirement, the minimum number of full clicks
        # ends at most requirement+9. A smaller final partial click ends at
        # most requirement+8, where its next unit must cost more than the
        # still-unspent upgrade price for the partial quantity to be legal.
        next_price = state.building_price(building, required+8)
        row = dict(upgrade=name, building=building, required=required,
                   upgrade_price=upgrade.price, largest_next_price=next_price,
                   partial_is_impossible=upgrade.price >= next_price)
        rows.append(row); print(json.dumps(row))
assert rows and all(row['partial_is_impossible'] for row in rows)
WORK.mkdir(parents=True, exist_ok=True)
(WORK/'upgrade_macro_audit.json').write_text(json.dumps(rows, indent=2)+'\n')
