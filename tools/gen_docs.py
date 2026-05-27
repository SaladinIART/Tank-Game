"""
Generate docs/UNITS.md and docs/TERRAIN.md from the JSON data tables.

Idempotent -- safe to re-run after balance changes.  Outputs include a
header note so readers know it's auto-generated.

Usage::

    python tools/gen_docs.py
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"

UNIT_HDR = """# Unit reference

> Auto-generated from `data/units.json` by `tools/gen_docs.py`. Do not edit
> by hand -- rerun the tool after balance changes.

Stats columns: **HP / ATK / DEF / MOV / VIS / RNG / Cost (cr+oil)**.

"""

TERRAIN_HDR = """# Terrain reference

> Auto-generated from `data/terrain.json` by `tools/gen_docs.py`. Do not
> edit by hand -- rerun the tool after balance changes.

"""

MOVE_COL = ("foot", "wheeled", "tracked", "towed", "air")


def _unit_row(u: dict) -> str:
    rng = f"{u['range_min']}-{u['range_max']}" if u['range_min'] != u['range_max'] else str(u['range_max'])
    tags = []
    if u.get("can_capture"):     tags.append("capture")
    if u.get("stealth"):         tags.append("stealth")
    if u.get("flying"):          tags.append("flying")
    if u.get("amphibious"):      tags.append("amphib")
    if u.get("self_destruct"):   tags.append("KAMIKAZE")
    if u.get("range_min", 1) > 1: tags.append("indirect")
    tag_s = ", ".join(tags) if tags else ""
    cost = f"{u['cost_credits']}" + (f"+{u['cost_oil']}o" if u['cost_oil'] else "")
    return (
        f"| {u['id']} | {u['name']} | T{u['tier']} | {u['unit_class']} | "
        f"{u['hp']} | {u['atk']} | {u['def']} | "
        f"{u['move']} | {u['vision']} | {rng} | "
        f"{cost} | {tag_s} |"
    )


def gen_units() -> str:
    raw = json.loads((DATA / "units.json").read_text(encoding="utf-8"))
    units = [u for u in raw["unit_types"] if "id" in u]

    by_faction: dict[str, list[dict]] = {}
    for u in units:
        by_faction.setdefault(u["faction"], []).append(u)

    out = [UNIT_HDR]
    for faction in ("NATO", "BRICS", "GUERILLA"):
        ulist = sorted(by_faction.get(faction, []),
                       key=lambda u: (u["tier"], u["unit_class"]))
        if not ulist:
            continue
        out.append(f"## {faction}\n")
        out.append("| id | name | tier | class | HP | ATK | DEF | MOV | VIS | RNG | Cost | Tags |")
        out.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
        for u in ulist:
            out.append(_unit_row(u))
        out.append("")
    return "\n".join(out) + "\n"


def gen_terrain() -> str:
    raw = json.loads((DATA / "terrain.json").read_text(encoding="utf-8"))
    terrains = raw["terrain_types"]

    out = [TERRAIN_HDR]
    out.append("| id | name | DEF | VIS+ | LOS-block | Capturable | Income | "
               + " | ".join(f"mv-{c}" for c in MOVE_COL) + " |")
    out.append("|" + "---|" * (7 + len(MOVE_COL)))
    for t in terrains:
        mc = t["move_cost"]
        mc_cells = [str(mc.get(c, "X") if mc.get(c) is not None else "X")
                    for c in MOVE_COL]
        inc_bits = []
        if t.get("income_credits"): inc_bits.append(f"+{t['income_credits']}cr")
        if t.get("income_oil"):     inc_bits.append(f"+{t['income_oil']}oil")
        inc = " ".join(inc_bits) if inc_bits else "-"
        out.append(
            f"| {t['id']} | {t['name']} | +{t['defense_bonus']} | "
            f"{t['vision_modifier']:+d} | "
            f"{'Y' if t.get('blocks_los') else 'N'} | "
            f"{'Y' if t.get('capturable') else 'N'} | "
            f"{inc} | " + " | ".join(mc_cells) + " |"
        )
    return "\n".join(out) + "\n"


def main() -> None:
    DOCS.mkdir(exist_ok=True)
    (DOCS / "UNITS.md").write_text(gen_units(), encoding="utf-8")
    (DOCS / "TERRAIN.md").write_text(gen_terrain(), encoding="utf-8")
    print(f"Wrote {DOCS / 'UNITS.md'}")
    print(f"Wrote {DOCS / 'TERRAIN.md'}")


if __name__ == "__main__":
    main()
