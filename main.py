"""
CP-6 scaffold: 30×20 test hex map with terrain, units, GameState, end-turn.

Controls:
  WASD / arrows  — pan
  Scroll wheel   — zoom (cursor-anchored)
  Right-drag     — pan
  Left-click     — print hovered hex (q, r)
  SPACE          — end turn (cycles factions)
  ESC            — quit
"""
import asyncio
import random

import pygame

from src.engine.combat import (
    attack_targets,
    load_damage_matrix,
    predict_exchange,
    resolve_attack,
)
from src.engine.fog import can_faction_see_unit
from src.engine.hex import Hex
from src.engine.movement import Movement, compute_movement
from src.engine.state import Faction, GameState
from src.engine.tile import Tile, load_terrain
from src.engine.unit import Unit, load_units
from src.render.camera import Camera
from src.render.hex_renderer import HexRenderer

WIDTH, HEIGHT = 1280, 720
FPS = 60
BG = (18, 24, 38)

MAP_W, MAP_H = 30, 20

_TERRAIN_WEIGHTS = [
    ("plain",    55), ("forest",   12), ("mountain",  6),
    ("road",      8), ("river",     5), ("city",      5),
    ("oil_well",  4), ("airfield",  3),
]


def build_test_map(seed: int = 42) -> dict[Hex, Tile]:
    rng = random.Random(seed)
    ids  = [t for t, _ in _TERRAIN_WEIGHTS]
    wgts = [w for _, w in _TERRAIN_WEIGHTS]
    tiles: dict[Hex, Tile] = {}
    for q in range(MAP_W):
        for r in range(MAP_H):
            h = Hex(q, r)
            tiles[h] = Tile(hex=h, terrain_id=rng.choices(ids, wgts)[0])
    # Place HQs and starting territory at opposite corners.
    tiles[Hex(2, 2)]              = Tile(Hex(2, 2),              "hq",       owner_faction="NATO")
    tiles[Hex(MAP_W - 3, MAP_H - 3)] = Tile(Hex(MAP_W - 3, MAP_H - 3), "hq", owner_faction="BRICS")
    tiles[Hex(3, 2)]              = Tile(Hex(3, 2),              "city",     owner_faction="NATO")
    tiles[Hex(MAP_W - 4, MAP_H - 3)] = Tile(Hex(MAP_W - 4, MAP_H - 3), "city", owner_faction="BRICS")
    tiles[Hex(2, 3)]              = Tile(Hex(2, 3),              "oil_well", owner_faction="NATO")
    tiles[Hex(MAP_W - 3, MAP_H - 4)] = Tile(Hex(MAP_W - 3, MAP_H - 4), "oil_well", owner_faction="BRICS")
    return tiles


def build_initial_state() -> GameState:
    load_terrain()
    load_units()
    load_damage_matrix()
    tiles = build_test_map()
    factions = [
        Faction(id="NATO",  name="NATO",  color=(30, 80, 200), credits=1500, oil=10, is_ai=False),
        Faction(id="BRICS", name="BRICS", color=(200, 30, 30), credits=1500, oil=10, is_ai=True),
    ]
    state = GameState(factions=factions, tiles=tiles)

    # Starting NATO units near (2, 2).
    state.add_unit(Unit("nato_inf_l",   "NATO", Hex(2, 2)))
    state.add_unit(Unit("nato_engineer","NATO", Hex(3, 2)))
    state.add_unit(Unit("nato_recon",   "NATO", Hex(2, 3)))

    # Starting BRICS units near opposite corner (using NATO unit types as placeholder
    # until CP-17 adds BRICS roster).
    state.add_unit(Unit("nato_inf_l",   "BRICS", Hex(MAP_W - 3, MAP_H - 3)))
    state.add_unit(Unit("nato_recon",   "BRICS", Hex(MAP_W - 4, MAP_H - 3)))

    return state


async def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Modern Warfare 4X — CP-6 GameState")
    clock = pygame.time.Clock()
    font_ui = pygame.font.SysFont("consolas", 18)
    font_hud = pygame.font.SysFont("consolas", 22, bold=True)

    state = build_initial_state()
    camera = Camera(WIDTH, HEIGHT, hex_size=36, offset_x=60.0, offset_y=60.0)
    renderer = HexRenderer(camera)

    hovered: Hex | None = None
    selected_unit: Unit | None = None
    movement: Movement | None = None
    path_preview: list[Hex] = []
    attack_target_uids: set[int] = set()   # enemy uids the selection can hit from current hex
    fog_enabled = True                     # F to toggle

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if selected_unit is not None:
                        selected_unit = None
                        movement = None
                        path_preview = []
                        attack_target_uids = set()
                    else:
                        running = False
                elif event.key == pygame.K_SPACE:
                    selected_unit = None
                    movement = None
                    path_preview = []
                    attack_target_uids = set()
                    state.end_turn()
                    print(f"End turn → {state.active_faction.id} "
                          f"(turn {state.turn_number}, "
                          f"credits={state.active_faction.credits}, "
                          f"oil={state.active_faction.oil})")
                elif event.key == pygame.K_f:
                    fog_enabled = not fog_enabled
                    print(f"Fog {'on' if fog_enabled else 'off'}")
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                clicked = camera.screen_to_hex(*pygame.mouse.get_pos())
                active_id = state.active_faction.id
                clicked_unit = state.unit_at(clicked)

                if selected_unit is not None:
                    # --- Selected: try attack, then move, then reselect/deselect ---
                    if clicked_unit is not None and clicked_unit.uid in attack_target_uids:
                        # Attack
                        result = resolve_attack(state, selected_unit, clicked_unit)
                        print(
                            f"Attack: {selected_unit.unit_type.name} → "
                            f"{clicked_unit.unit_type.name}  "
                            f"{result.damage_dealt} dmg"
                            + (" (killed)" if result.defender_killed else "")
                            + (f"  • counter {result.counter_damage}"
                               if result.counter_damage else "")
                            + (" (attacker killed)" if result.attacker_killed else "")
                        )
                        selected_unit = None
                        movement = None
                        path_preview = []
                        attack_target_uids = set()
                    elif movement is not None and clicked in movement.reachable:
                        # Move, then recompute attack targets from new hex.
                        state.move_unit(selected_unit.uid, clicked)
                        selected_unit.has_moved = True
                        movement = None
                        path_preview = []
                        new_targets = {t.uid for t in attack_targets(state, selected_unit)}
                        if new_targets:
                            attack_target_uids = new_targets
                        else:
                            selected_unit = None
                            attack_target_uids = set()
                    elif (clicked_unit is not None
                          and clicked_unit.faction == active_id
                          and clicked_unit.can_act()):
                        # Reselect a different own unit.
                        selected_unit = clicked_unit
                        movement = (None if clicked_unit.has_moved
                                    else compute_movement(state, clicked_unit))
                        path_preview = []
                        attack_target_uids = {
                            t.uid for t in attack_targets(state, clicked_unit)
                        }
                    else:
                        # Click on empty / unreachable / wrong faction → deselect.
                        selected_unit = None
                        movement = None
                        path_preview = []
                        attack_target_uids = set()
                else:
                    # --- Idle: select own actable unit, or print info ---
                    if (clicked_unit is not None
                        and clicked_unit.faction == active_id
                        and clicked_unit.can_act()):
                        selected_unit = clicked_unit
                        movement = (None if clicked_unit.has_moved
                                    else compute_movement(state, clicked_unit))
                        path_preview = []
                        attack_target_uids = {
                            t.uid for t in attack_targets(state, clicked_unit)
                        }
                    elif clicked_unit is not None:
                        print(f"Unit at {clicked}: {clicked_unit.unit_type.name} "
                              f"({clicked_unit.faction}) HP={clicked_unit.hp}")
                    else:
                        tile = state.tiles.get(clicked)
                        if tile:
                            print(f"Tile at {clicked}: {tile.terrain.name} "
                                  f"(owner={tile.owner_faction})")
            else:
                camera.handle_event(event)

        camera.handle_keys(pygame.key.get_pressed(), dt)
        hovered = camera.screen_to_hex(*pygame.mouse.get_pos())

        # Update path preview toward hovered hex.
        if selected_unit is not None and movement is not None:
            if hovered in movement.reachable:
                path_preview = movement.path_to(hovered)
            else:
                path_preview = []

        # Fog: render from the active faction's POV (hot-seat for now;
        # CP-13 AI will automate non-human factions).
        viewer_id = state.active_faction.id
        if fog_enabled:
            visible_set = state.visible_to(viewer_id)
            explored_set = state.explored.get(viewer_id, set())
            def _can_see(u: Unit, _vid=viewer_id) -> bool:
                return can_faction_see_unit(state, _vid, u)
        else:
            visible_set = None
            explored_set = None
            _can_see = None

        # Render
        screen.fill(BG)
        renderer.draw_map(
            screen, state.tiles, hovered_hex=hovered,
            visible=visible_set, explored=explored_set,
        )
        if selected_unit is not None and movement is not None:
            renderer.draw_movement_overlay(
                screen, movement.reachable, path_preview, selected_unit.hex
            )
        if selected_unit is not None and attack_target_uids:
            target_hexes = [
                state.units[uid].hex
                for uid in attack_target_uids
                if uid in state.units
            ]
            renderer.draw_attack_overlay(screen, target_hexes, hovered_hex=hovered)
        renderer.draw_units(screen, list(state.units.values()), can_see=_can_see)

        # HUD top-left
        af = state.active_faction
        hud_lines = [
            (f"Turn {state.turn_number}  —  {af.name}", af.color),
            (f"Credits: {af.credits}", (220, 220, 100)),
            (f"Oil: {af.oil}", (220, 160, 80)),
            (f"Tier: {af.tier}", (180, 220, 180)),
            (f"Units: {len(state.units_of(af.id))}", (200, 200, 200)),
        ]
        y = 10
        for txt, col in hud_lines:
            lbl = font_hud.render(txt, True, col)
            screen.blit(lbl, (12, y))
            y += 24

        # Selected unit info panel.
        if selected_unit is not None:
            y += 4
            sel_lines = [
                (f"[ {selected_unit.unit_type.name} ]", (255, 255, 180)),
                (f"HP {selected_unit.hp}/{selected_unit.unit_type.hp}  "
                 f"Move {selected_unit.unit_type.move}  "
                 f"Rng {selected_unit.unit_type.range_min}-{selected_unit.unit_type.range_max}",
                 (200, 200, 200)),
            ]
            # Hover prediction on attack target.
            if hovered is not None:
                hover_unit = state.unit_at(hovered)
                if (hover_unit is not None
                    and hover_unit.uid in attack_target_uids):
                    atk_dmg, counter_dmg = predict_exchange(
                        state, selected_unit, hover_unit
                    )
                    sel_lines.append((
                        f"→ {atk_dmg} dmg  •  ← {counter_dmg} counter",
                        (255, 180, 180),
                    ))
            sel_lines.append(
                ("Click hex/enemy  •  ESC cancel", (140, 140, 110))
            )
            for txt, col in sel_lines:
                lbl = font_ui.render(txt, True, col)
                screen.blit(lbl, (12, y))
                y += 20

        # FPS + hover (bottom-left)
        fps_lbl = font_ui.render(f"FPS {clock.get_fps():.0f}", True, (160, 160, 160))
        screen.blit(fps_lbl, (12, HEIGHT - 44))
        if hovered:
            hov_lbl = font_ui.render(
                f"Hover q={hovered.q}, r={hovered.r}", True, (180, 180, 100)
            )
            screen.blit(hov_lbl, (12, HEIGHT - 22))

        # Help (bottom-right)
        help_txt = "SPACE end turn  •  F fog toggle  •  WASD pan  •  scroll zoom  •  click info"
        h_lbl = font_ui.render(help_txt, True, (120, 120, 140))
        screen.blit(h_lbl, (WIDTH - h_lbl.get_width() - 12, HEIGHT - 22))

        pygame.display.flip()
        await asyncio.sleep(0)

    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
