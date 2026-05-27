# Architecture

A short tour of the code for contributors and future-you.

## Top-level layout

```
main.py                  Pygbag entry; async loop; UI + state machine
data/                    All JSON: units, terrain, damage matrix, scenarios
src/
  engine/                Game rules. Zero Pygame. Fully picklable.
    hex.py               Axial hex coords, neighbours, distance, LOS line
    tile.py              TerrainType + Tile + global registry
    unit.py              UnitType + Unit + global registry; stance constants
    state.py             GameState: factions, tiles, units, turn cursor
    movement.py          Dijkstra reachable set per unit + path map
    fog.py               Per-faction visibility cache + stealth detection
    combat.py            Damage matrix lookup, predict/resolve, counter
    capture.py           Engineer capture progress, ownership flip
    tech.py              Build menu filtering, tier upgrades, spawn search
    victory.py           Outcome enum, pluggable conditions, VictoryConfig
    scenario.py          JSON -> GameState; HQ clearance pass
    procgen.py           Seeded random map for skirmish
    skirmish.py          Pre-match config -> map -> GameState
    stance_actions.py    Defend / retreat / actionable_units helpers
  ai/
    heuristic.py         Action enumeration + scoring + execution loop
    personality.py       JSON-tunable weight overrides
    threat.py            Simple "if I stand here, how much fire eats me?"
  render/
    camera.py            Pan / zoom / hex<->screen transforms
    hex_renderer.py      Map + units + overlays
    sprites.py           PNG cache with headless fallback
    tooltip.py           Hover bubble for units / terrain
  audio/
    sounds.py            SDL-mixer-safe SoundManager; focus pause
  persistence/
    save.py              JSON snapshot of GameState; 3 manual slots + auto

tools/
  gen_sprites.py         Procedural placeholder unit/terrain art
  gen_sounds.py          Procedural WAV SFX + faction music loops
  sim_missions.py        AI-vs-AI mission simulator (balance harness)
  build_itch.py          Wraps Pygbag build + zips for itch.io
tests/                   pytest, ~670 tests
```

## Core flow

```
input event ─► main.py state machine
                ├─► hex click → select / move / attack / build
                ├─► H        → set_defend(state, unit)
                ├─► R        → retreat(state, unit)
                ├─► E/Space  → confirm modal → state.end_turn()
                └─► AI turn  → take_turn_steps generator (one action/frame)

state.end_turn()
  ├─► advance active_faction_idx (skip defeated)
  ├─► _on_turn_start(next):
  │     1. capture progress + ownership flips (capture.process_captures)
  │     2. income (faction.credits/oil from owned tiles)
  │     3. upkeep (faction.oil -= sum(unit.upkeep))
  │     4. unit.reset_turn() -> clears action flags + stance
  └─► evaluate_victory()
```

## Why dataclasses everywhere

`GameState`, `Faction`, `Tile`, `Unit`, `VictoryConfig` are all plain
mutable dataclasses with no Pygame surface, no open file handle, no
unpicklable object anywhere. This means:

- `pickle.dumps(state)` works at any moment.
- `state_to_dict` / `dict_to_state` round-trip without surprises.
- Tests can construct minimal states by hand.

## Why no AI in the engine

`engine/` knows nothing about `ai/`. The AI imports from the engine, never
the other way around. `take_turn` mutates `GameState` directly through
public methods (`move_unit`, `build_unit`, `upgrade_tier`, the combat
helpers). This keeps the engine reusable for replays, headless sims, or a
hypothetical multiplayer mode.

## Fog & stealth interaction

- Each faction has `explored: set[Hex]` (permanent memory) and a lazy
  `_visible_cache: set[Hex]` per turn.
- The cache invalidates on any unit add/remove/move and at every
  `end_turn`. Anything else is read-only against it.
- Stealth units are visible if and only if `distance(observer, target) <=
  STEALTH_DETECTION_RADIUS`. The AI's targeting filter (`_ai_can_target`)
  applies this independently, so the AI literally cannot "see" stealth
  ambushers when enumerating actions.

## Scoring (AI heuristic)

`_score_move` differs for capture units vs combat units:

- **Engineers / capture-flagged**: long-range pull toward nearest
  capturable tile (incl. enemy HQ) at `approach_capture_target / (dist+1)`.
  This was the fix that broke perpetual stalemate in CP-26.
- **Combat units**: pull toward nearest enemy HQ at `approach_enemy_hq /
  (dist+1)`. Plus threat aversion (more if wounded) so they don't walk
  into kill zones.

Personality weights overlay defaults; the difficulty tier picks which
personality to inject at scenario load (`main._apply_difficulty`).

## Save format

JSON v1. Schema documented in the header of `src/persistence/save.py`.
Includes:

- Factions (credits, oil, tier, defeated, is_ai)
- Tiles (terrain, owner, capture progress + capturing faction)
- Units (uid, type, hex, hp, action flags, **stance**)
- Per-faction explored hex sets (fog memory)
- Victory configs with stateful counters (HoldTiles consecutive_turns)
- Outcomes per faction

`_visible_cache` is *not* saved — it's transient and rebuilds lazily.

## Adding features

Most additions touch:

1. A JSON file in `data/`
2. The relevant `engine/` module
3. Optional: a render helper in `render/`
4. Tests in `tests/`

The plan file at the repo root tracks the full 27-checkpoint history;
new features should follow the same pattern (small CP, acceptance criteria,
tests).
