# Player manual

## The turn

1. Your faction's turn begins: income ticks, oil upkeep is paid, unit action
   flags reset (and any "Hunkered" stance from last round clears).
2. Move and attack your units in any order. Build at HQ.
3. Press **E** or click **END TURN**. If any unit can still act, you'll be
   asked to confirm. **Y / Enter** to commit, **N / Esc** to keep playing.
4. AI factions take their turns visibly, one action every ~half-second so you
   can watch what they do.

## Movement

- Each unit has a `move` value (movement points per turn).
- Terrain has a per-category move cost. Mountains are impassable to wheeled
  and tracked. Rivers block most ground units (except foot at higher cost,
  or amphibious vehicles). Roads are cheap.
- Flying units pay 1 per hex regardless of terrain.
- Enemy units block; friendly units block stopping but allow pass-through.
- The destination must be empty.

### Zone of Control (engagement)

If a unit starts its turn **adjacent to any enemy**, its movement is
capped at **1 hex** for that turn. You cannot just walk away from a fight.
The HUD shows `ENGAGED -- movement limited to 1 hex` on the selected
unit's panel.

Flying units are exempt — they always move at full speed.

This rewards careful positioning and makes screening units genuinely
useful: pin an enemy with a cheap infantry, then bring up artillery.

## Combat

- Damage: `round(base × atk_hp/10 × (1 − total_def/10))`
  - `base` from the [damage matrix](../data/damage_matrix.json)
    (attacker class × defender class)
  - `atk_hp/10` — wounded units hit softer
  - `total_def` = terrain bonus + stance bonus (max 9)
- Defender automatically counter-attacks if they're alive AND have the
  attacker in range AND their class can hurt the attacker's class.
- Kamikaze units (Guerilla drones) skip the counter — they explode.
- Indirect-fire artillery (range_min > 1) can shoot from cover and cannot
  be counter-attacked when out of melee range.

## Stances (XCOM-style)

- **Attack** (default): normal move + attack.
- **Hunker Down** (`H`): +2 effective DEF; the unit cannot initiate
  attacks this turn; it **still counter-attacks** if engaged. Action ends
  immediately. Persists through the enemy turn so the bonus actually
  matters. Auto-clears next time the unit's faction starts its turn.

## Veterancy (XP -> level -> rank)

Inspired by Warhammer 40k Gladius. Every unit tracks `xp` and `level`
(capped at **25**).

**Earning XP:**
- +1 XP per HP of damage dealt
- +10 XP on a killing blow
- +2 XP for surviving a counter-attack
- +8 XP when an engineer flips a capture target

**Ranks** (every 5 levels):

| Level | Rank | Bonuses |
|---|---|---|
| 1–4 | Rookie | none |
| 5–9 | Veteran | +1 atk |
| 10–14 | Elite | +1 atk / +1 def |
| 15–19 | Heroic | +2 atk / +1 def / +2 hp |
| 20–24 | Legendary | +2 atk / +2 def / +3 hp / +1 vis |
| 25 | Mythic | +3 atk / +2 def / +5 hp / +1 vis |

Tooltip shows `Lv N (RankName) XP a/b` plus pips (`*`) for current rank.
Selected-unit panel shows the same.

On rank-up, max HP gains are immediate (the unit heals by the delta), so
a Heroic-rank unit immediately benefits from its +2 HP cap.

## Healing

Two ways to recover HP:

1. **Passive — owned capturable tiles**: standing on a city, oil well,
   airfield or HQ that **your faction owns** heals +2 HP per turn at
   turn start. This is why capturing matters beyond just income.
2. **Active — engineer medic (`J`)**: select an engineer adjacent to a
   wounded friendly and press `J`. Heals +3 HP. Consumes the engineer's
   attack slot (move is preserved). The HUD hint `J heal` shows up
   automatically when valid targets are in range.

Heals respect veterancy-adjusted max HP (so a Heroic-rank Mythic unit can
top off above the base 10 HP).

## Retreat (`R`)

Auto-pathfinds the selected unit toward your own HQ. Picks the reachable
hex with the smallest distance to HQ; ties broken on lowest enemy threat.
Consumes both move and attack.

## Capturing tiles

- Engineers, sappers and similar `can_capture` units can sit on neutral or
  enemy capturable tiles (cities, oil wells, airfields, enemy HQ).
- Capture takes 3 turns. The HUD shows `n/3` on tiles under capture.
- Move off the tile and progress resets.
- Once flipped, the tile changes faction colour and starts ticking its
  income for you the same turn.

## Building units

Click your HQ → build menu. Rows show every faction unit:

- **Green** = affordable + tier-unlocked → click to build
- **Red** = tier-unlocked but you can't afford it
- **Grey** = locked behind a higher tier

There's also a `Upgrade tier` row: T1→T2 costs 1000cr, T2→T3 costs 2500cr.
Newly built units spawn exhausted on the first empty passable adjacent hex.

## Victory conditions

A scenario can mix and match these; check the mission tooltip:

- **Destroy HQ** — take out the named faction's HQ tile.
- **Hold tiles** — own a set of hexes for N consecutive turns.
- **Own all of terrain** — capture every tile of some type (e.g. oil wells).
- **Eliminate faction** — wipe out a faction's army.
- **Destroy unit type** — kill a specific unit type (e.g. Iskander missile).

You can lose by symmetric conditions (lose your own HQ, fail to defend).

## Difficulty

| Tier | AI bonus | Personality |
|---|---|---|
| Normal | none | balanced |
| Hard | +400 cr, +3 oil | aggressive |
| Insane | +900 cr, +6 oil | predator (more attack, less retreat) |

## Save / load

- Autosave fires every end-turn to `saves/<scenario>_autosave.json`.
- **F5** writes to a manual slot, cycling 1 → 2 → 3 → 1.
- Load from the main menu → LOAD.
- Saves include unit stance, capture progress, fog memory, victory counters.
  Everything round-trips.
