"""
Mission balance simulator for CP-26.

Plays each campaign mission AI-vs-AI across all difficulty tiers, records
outcome / turn-length / per-faction stats, and prints a summary table that
makes balance pressure points obvious.

Usage
-----
::

    python tools/sim_missions.py                 # all missions, all diffs
    python tools/sim_missions.py --trials 5      # multiple trials per cell
    python tools/sim_missions.py --missions m1 m3
    python tools/sim_missions.py --turn-cap 80   # default 60

How it works
------------
1. Load scenario JSON → GameState.
2. Override every faction (incl. NATO) to ``is_ai=True`` so both sides play.
3. Loop ``take_turn`` then ``state.end_turn`` until ``state.game_over`` or
   ``turn_cap`` reached.
4. Record: outcome (NATO/BRICS/GUERILLA win, draw, or timeout), total
   ``state.turn_number``, units alive per faction, credits per faction.

Notes
-----
- AI is fog-blind (cheaty v0) — same as in play.  Sim numbers therefore reflect
  what the player faces from the AI, not perfect play.
- Hard / Insane apply credit + personality bumps via ``_apply_difficulty`` so
  the sim measures the same difficulty curve the player sees.
- Random seeding: tie-broken-by-enumeration-order deterministic per game; we
  don't seed RNG because there is no RNG in combat (matrix is deterministic).
  Multiple trials therefore produce identical outcomes — useful for regression
  detection, less so for win-rate distributions.  If we want jitter later, we
  can shuffle action ordering before _pick_best.
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Allow running from project root.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.ai.heuristic import take_turn
from src.ai.personality import Personality, from_dict as personality_from_dict
from src.engine.scenario import load_scenario
from src.engine.state import GameState
from src.engine.victory import Outcome

# Re-use the same difficulty modifier the game uses.
sys.path.insert(0, str(ROOT))
import main as game_main


# ---------------------------------------------------------------------------
# Mission registry
# ---------------------------------------------------------------------------

MISSIONS: list[dict] = [
    {"slug": "m1", "path": ROOT / "data" / "scenarios" / "m1.json"},
    {"slug": "m2", "path": ROOT / "data" / "scenarios" / "m2.json"},
    {"slug": "m3", "path": ROOT / "data" / "scenarios" / "m3.json"},
    {"slug": "m4", "path": ROOT / "data" / "scenarios" / "m4.json"},
    {"slug": "m5", "path": ROOT / "data" / "scenarios" / "m5.json"},
]

DIFFICULTIES = ["normal", "hard", "insane"]


# ---------------------------------------------------------------------------
# Result data
# ---------------------------------------------------------------------------

@dataclass
class SimResult:
    mission:   str
    difficulty: str
    winner:    Optional[str]    # faction id, or None if timeout / draw
    turns:     int
    timed_out: bool
    units_alive: dict[str, int]  = field(default_factory=dict)
    credits:     dict[str, int]  = field(default_factory=dict)
    duration_s:  float           = 0.0

    @property
    def outcome_str(self) -> str:
        if self.timed_out:
            return "TIMEOUT"
        return self.winner or "DRAW"


# ---------------------------------------------------------------------------
# Single-game runner
# ---------------------------------------------------------------------------

def run_one(scenario_path: Path, difficulty: str, turn_cap: int = 60) -> SimResult:
    """Play one full game AI-vs-AI; return SimResult."""
    state, meta = load_scenario(scenario_path)

    # Force the human faction to AI so both sides play themselves.
    for f in state.factions:
        f.is_ai = True

    # Apply the same difficulty bumps the player would see.
    game_main._apply_difficulty(state, meta, difficulty)

    def _pers(fid: str) -> Optional[Personality]:
        pd = meta.get("personalities", {}).get(fid)
        return personality_from_dict(pd) if pd else None

    start = time.perf_counter()
    while not state.game_over and state.turn_number <= turn_cap:
        fid = state.active_faction.id
        take_turn(state, fid, _pers(fid))
        state.end_turn()

    elapsed = time.perf_counter() - start
    timed_out = not state.game_over

    units_alive = {f.id: len(state.units_of(f.id)) for f in state.factions}
    credits     = {f.id: f.credits for f in state.factions}

    return SimResult(
        mission     = scenario_path.stem,
        difficulty  = difficulty,
        winner      = state.winner() if not timed_out else None,
        turns       = state.turn_number,
        timed_out   = timed_out,
        units_alive = units_alive,
        credits     = credits,
        duration_s  = elapsed,
    )


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def print_results(results: list[SimResult]) -> None:
    print()
    print(f"{'MISSION':<6} {'DIFF':<8} {'OUTCOME':<10} {'TURNS':>6} {'TIME':>7}  UNITS  CREDITS")
    print("-" * 80)
    for r in results:
        units_str   = "/".join(f"{r.units_alive.get(k, 0)}" for k in r.units_alive)
        credits_str = "/".join(f"{r.credits.get(k, 0)}" for k in r.credits)
        time_str    = f"{r.duration_s:5.2f}s"
        print(f"{r.mission:<6} {r.difficulty:<8} {r.outcome_str:<10} "
              f"{r.turns:>6} {time_str:>7}  {units_str:<8} {credits_str}")
    print()


def summary_pressure(results: list[SimResult]) -> None:
    """Highlight balance pressure points — things to fix."""
    by_diff: dict[str, list[SimResult]] = {}
    for r in results:
        by_diff.setdefault(r.difficulty, []).append(r)

    print("=== BALANCE PRESSURE ===")
    for diff, rs in by_diff.items():
        timeouts = sum(1 for r in rs if r.timed_out)
        avg_turns = sum(r.turns for r in rs) / len(rs)
        winners   = [r.winner for r in rs if r.winner]
        print(f"{diff:<8} avg_turns={avg_turns:5.1f}  timeouts={timeouts}/{len(rs)}  "
              f"winners={winners}")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Mission balance simulator")
    parser.add_argument("--missions",   nargs="+", default=None,
                        help="Subset of mission slugs (e.g. m1 m3). Default: all.")
    parser.add_argument("--difficulties", nargs="+", default=None,
                        help="Subset of difficulties. Default: all.")
    parser.add_argument("--trials",     type=int, default=1,
                        help="Trials per (mission, difficulty). Default: 1.")
    parser.add_argument("--turn-cap",   type=int, default=60,
                        help="Hard timeout per game in turns. Default: 60.")
    args = parser.parse_args()

    mission_slugs = args.missions  if args.missions  else [m["slug"] for m in MISSIONS]
    diffs         = args.difficulties if args.difficulties else DIFFICULTIES
    missions      = [m for m in MISSIONS if m["slug"] in mission_slugs]

    results: list[SimResult] = []
    total = len(missions) * len(diffs) * args.trials
    n     = 0
    for m in missions:
        for diff in diffs:
            for t in range(args.trials):
                n += 1
                print(f"[{n}/{total}] {m['slug']} {diff} trial {t + 1}...",
                      end="", flush=True)
                r = run_one(m["path"], diff, args.turn_cap)
                print(f" -> {r.outcome_str} in {r.turns} turns ({r.duration_s:.2f}s)")
                results.append(r)

    print_results(results)
    summary_pressure(results)


if __name__ == "__main__":
    main()
