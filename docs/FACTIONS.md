# Factions

Three asymmetric factions. They share a roster of *unit roles* (infantry,
recon, vehicle, artillery, AA, jet, etc.) but each role is statted
differently per faction, plus 1–3 unique flagship units per side.

## NATO — quality

- **Doctrine**: expensive premium units, balanced everything, full air tree
  through T3.
- **Strengths**: best per-unit stats; well-rounded; T3 jets and bombers
  give it the strongest air game.
- **Weaknesses**: low unit count; engineer scarcity; loses if forced into
  a long attritional fight without map control.
- **Flagships**: T2 jets and helicopters that out-DPS BRICS analogues.

## BRICS — quantity

- **Doctrine**: cheaper units everywhere, you'll always field more bodies
  than the enemy. Premium T3 in indirect fire instead of air.
- **Strengths**: pressure across the whole front; cheap engineers; the
  flagship **Hypersonic Missile** (Iskander-M, T3, range 4–7, atk 9) is a
  threat from across the map.
- **Weaknesses**: every BRICS unit is `atk` ≤ its NATO equivalent. You win
  by overwhelming, not by dueling 1v1.
- **Flagships**: Iskander-M (T3 hypersonic missile), Swarm Drone (T2
  helicopter, range 1–2, fast).

## Guerilla — stealth + ambush

- **Doctrine**: cheap-and-disposable, with two **stealth** flagships that
  only appear to the AI if a friendly unit is within 1 hex. The kamikaze
  flagship trades a body for a guaranteed hit.
- **Strengths**: ambushes; the AI is fog-blind to most of the map but
  *cannot see stealth at all* unless adjacent — so you can pre-position
  death squads. Cheap engineers; long-range mortar at T1.
- **Weaknesses**: no T3 tier at all; weaker frontline; no air superiority.
- **Flagships**: Scout (T1 foot, stealth), Drone Recon (T2 flying, stealth),
  Kamikaze Drone (T2 flying, atk 9, **self_destruct**).

## Unit-class roles (shared across factions)

| Class | Best vs | Weak vs | Tactical role |
|---|---|---|---|
| infantry | infantry, engineer | jet, bomber | Cheap, holds ground, strong in cover |
| engineer | (rarely fights) | everything | Captures cities/oil — the actual win con |
| recon | engineer, infantry | vehicle | Scouts, big vision, fast |
| vehicle | recon, vehicle | jet, bomber | Front-line tank |
| artillery | infantry, vehicle | jet, melee | Indirect: shoots from range, no counter |
| aa | jet, helicopter, bomber | vehicle | Air-denial; soft target on ground |
| sniper | infantry | vehicle, jet | Glass cannon vs infantry |
| jet | helicopter, vehicle | aa | Air superiority; oil-hungry |
| helicopter | infantry, vehicle | jet, aa | Flies over terrain; flexible |
| bomber | everything ground | jet, aa | Crushes ground; helpless vs air |

All matchups are stored in [`data/damage_matrix.json`](../data/damage_matrix.json)
— change one number, recompile nothing.
