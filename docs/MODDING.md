# Modding

Everything that matters lives in JSON. No code changes needed to tweak
balance, add units, or build new scenarios.

## Units — `data/units.json`

```json
{
  "id": "nato_inf_m",
  "name": "M-Inf",
  "faction": "NATO",
  "tier": 2,
  "unit_class": "infantry",
  "move_category": "foot",
  "hp": 10, "atk": 5, "def": 1,
  "move": 3, "vision": 3,
  "range_min": 1, "range_max": 1,
  "cost_credits": 500, "cost_oil": 0, "upkeep_oil": 0,
  "can_capture": false, "stealth": false,
  "flying": false, "amphibious": false,
  "self_destruct": false,
  "color": [60, 100, 200]
}
```

- `unit_class`: must be one of `infantry / engineer / recon / vehicle /
  artillery / aa / sniper / jet / helicopter / bomber` (drives damage
  matrix lookup).
- `move_category`: `foot / wheeled / tracked / towed / air` (drives terrain
  cost lookup).
- `range_min > 1` → indirect-fire, cannot be counter-attacked unless
  defender is also indirect at the same distance.
- `self_destruct` true → kamikaze, attacker dies after a successful hit.
- `stealth` true → invisible to AI fog unless an enemy is within
  `STEALTH_DETECTION_RADIUS` hexes.

## Terrain — `data/terrain.json`

```json
{
  "id": "city",
  "name": "City",
  "move_cost": {"foot": 1, "wheeled": 1, "tracked": 1, "towed": 1, "air": 1},
  "defense_bonus": 3,
  "vision_modifier": 0,
  "blocks_los": false,
  "capturable": true,
  "income_credits": 100, "income_oil": 0,
  "color": [180, 180, 180],
  "is_hq": false
}
```

- `move_cost`: per-category costs. `null` = impassable.
- `defense_bonus`: 0–5, added to defender's `total_def` clamp 9.
- `vision_modifier`: added to a unit's base vision while standing here.
- `blocks_los`: opaque to line-of-sight (mountains).
- `capturable`: engineers can flip ownership in 3 turns.
- `is_hq`: losing one ends some victory conditions.

## Damage matrix — `data/damage_matrix.json`

10×10 grid: `base_damage[attacker_class][defender_class]` → 0..10.
`0` means the attack is illegal (no effect, can't reach). Change values to
re-balance the rock-paper-scissors.

## Scenarios — `data/scenarios/m*.json`

```json
{
  "name": "Mission 1: First Contact",
  "description": "NATO vs BRICS. Destroy the BRICS field HQ.",
  "map": {
    "width": 21, "height": 15, "default_terrain": "plain",
    "tiles": [
      {"hex": [2, 3], "terrain": "hq", "owner": "NATO"},
      {"hex": [8, 7], "terrain": "bridge"},
      {"hex": [10, 4], "terrain": "mountain"}
    ]
  },
  "factions": [
    {"id": "NATO", "name": "NATO", "color": [30, 80, 200],
     "credits": 800, "oil": 5, "tier": 1, "is_ai": false},
    {"id": "BRICS", "name": "BRICS", "color": [200, 60, 60],
     "credits": 1200, "oil": 8, "tier": 1, "is_ai": true,
     "personality": {"name": "balanced", "weights": {"attack_damage": 4.0}}}
  ],
  "units": [
    {"type_id": "nato_inf_l", "faction": "NATO", "hex": [3, 3]},
    {"type_id": "brics_inf_l", "faction": "BRICS", "hex": [17, 11]}
  ],
  "victory": {
    "NATO":  {"win_conditions": [{"type": "destroy_hq",
                                  "target_faction": "BRICS"}],
              "lose_conditions": [{"type": "destroy_hq",
                                   "target_faction": "NATO"}]}
  }
}
```

- HQ-neighbour impassable terrain is auto-converted to `plain` on load —
  you don't need to worry about trapping engineers.
- Comment-only dicts (`{"_comment": "..."}`) in any array are skipped, so
  you can annotate your JSON files freely.
- Personalities are JSON-tunable; valid weight keys are listed in
  `src/ai/heuristic.py` (`DEFAULT_WEIGHTS`).

## Skirmish maps — `data/skirmish/map_*.json`

Same format as scenarios but without `units` / `factions` / `victory` —
the engine builds those at runtime from the player's pre-match config.

## Personalities

`Personality.weight_overrides` is a `dict[str, float]` that overlays the
default heuristic weights. The full list of valid keys is in
`src/ai/heuristic.py`. Tested presets:

- `balanced` — defaults
- `aggressive` — Hard tier
- `predator` — Insane tier
- `defensive` — turtles
- `guerrilla` — focuses on capture and ambush
- `blitz` — extreme attack weight (used by M4)
- `guardian` — sit on a flagship, defend it (used by M5)

See `src/ai/personality.py` for current values.

## Adding a new unit (worked example)

1. Add the entry to `data/units.json`.
2. Add row in `data/damage_matrix.json` if it's a new class — every
   matchup must have a value.
3. (Optional) Drop a 64×64 PNG at `assets/sprites/units/<class>.png` to
   render with art instead of a letter.
4. Tests should still pass — `pytest tests/`.

That's it. No code change.
