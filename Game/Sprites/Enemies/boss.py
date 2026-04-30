"""Undead Executioner boss + the skeleton it summons.

Both classes use the shared :class:`EnemyCombatMixin` so the player's existing
sword hit-test code (which iterates ``tilemap.enemies``) works unchanged.

The spritesheets live in
``Game/assets/monsters/boss_spritesheet_(undead_executioner)/`` and are
sliced into 100x100 frames for the boss and 50x50 frames for the summoned
skeleton. Frames load lazily on first construction so menu time stays low.
"""

from __future__ import annotations

import math
import os
import random
from typing import Any

import pygame

from Game.Sprites.sprite import Sprite
from Game.Sprites.Enemies._combat import EnemyCombatMixin

_BOSS_BASE = os.path.join(
    "Game", "assets", "monsters", "boss_spritesheet_(undead_executioner)"
)

_BOSS_FRAME = 100
_SUMMON_FRAME = 50

_BOSS_SCALE = 3
_SUMMON_SCALE = 2

def _slice_sheet(filename, frame_w, frame_h, count, scale=1, colorkey=None):
    """Return up to ``count`` Surfaces sliced left→right, top→bottom from a sheet."""
    path = os.path.join(_BOSS_BASE, filename)
    sheet = pygame.image.load(path).convert_alpha()
    sw, sh = sheet.get_size()
    cols = sw // frame_w
    out = []
    for i in range(count):
        col = i % cols
        row = i // cols
        rect = pygame.Rect(col * frame_w, row * frame_h, frame_w, frame_h)
        if rect.bottom > sh:
            break
        frame = pygame.Surface((frame_w, frame_h), pygame.SRCALPHA)
        frame.blit(sheet, (0, 0), rect)
        if scale != 1:
            frame = pygame.transform.scale(
                frame, (frame_w * scale, frame_h * scale)
            )
        out.append(frame)
    return out

_BOSS_FRAMES: dict | None = None
_SUMMON_FRAMES: dict | None = None

def _load_boss_frames():
    """Lazy-load every executioner animation. Cached after first call."""
    global _BOSS_FRAMES
    if _BOSS_FRAMES is not None:
        return _BOSS_FRAMES

    f = _BOSS_FRAME
    s = _BOSS_SCALE
    _BOSS_FRAMES = {
        "idle":      _slice_sheet("idle.png",      f, f, 4,  s),
        "idle2":     _slice_sheet("idle2.png",     f, f, 8,  s),
        "summon":    _slice_sheet("summon.png",    f, f, 5,  s),
        "death":     _slice_sheet("death.png",     f, f, 18, s),
        "teleport":  _slice_sheet("skill1.png",    f, f, 12, s),
        "attack":    _slice_sheet("attacking.png", f, f, 13, s),
    }
    return _BOSS_FRAMES

def _load_summon_frames():
    """Lazy-load the summoned skeleton's animations."""
    global _SUMMON_FRAMES
    if _SUMMON_FRAMES is not None:
        return _SUMMON_FRAMES

    f = _SUMMON_FRAME
    s = _SUMMON_SCALE
    _SUMMON_FRAMES = {
        "appear": _slice_sheet("summonAppear.png", f, f, 6, s),
        "idle":   _slice_sheet("summonIdle.png",   f, f, 4, s),
        "death":  _slice_sheet("summonDeath.png",  f, f, 5, s),
    }
    return _SUMMON_FRAMES

_BOSS_ANIM_MS = {
    "idle":     140,
    "idle2":    110,
    "summon":   100,
    "death":    90,
    "teleport": 60,
    "attack":   75,
}
_BOSS_LOOP = {
    "idle":     True,
    "idle2":    True,
    "summon":   False,
    "death":    False,
    "teleport": False,
    "attack":   False,
}

_SUMMON_ANIM_MS = {"appear": 90, "idle": 140, "death": 110}
_SUMMON_LOOP = {"appear": False, "idle": True, "death": False}

class UndeadExecutionerBoss(Sprite, EnemyCombatMixin):
    """Heavy melee boss with frequent teleports and summoning.

    Behaviour cycle (once the player is in sight):
      1. ``chase``  — pause/face player; weighted-pick the next move.
      2. ``attack`` — close-range slash that damages player on the hit frame.
      3. ``summon`` — spawn a skeleton near the player.
      4. ``teleport`` — fade out, jump near the player, fade back in.

    The mixin gives us health + i-frames + the ``ai_state`` field, which we
    extend with our own animation-driven state values.
    """

    tilemaps: Any
    tilemap: Any

    SIGHT_RANGE = 850
    ATTACK_RANGE = 150
    ATTACK_HIT_FRAMES = (4, 5, 6)
    ATTACK_DAMAGE = 2
    TELEPORT_COOLDOWN_MS = 1300
    SUMMON_COOLDOWN_MS = 3200
    ATTACK_COOLDOWN_MS = 750
    DECISION_PAUSE_MS = 250

    def __init__(self, game, pos, tilemap=None, tilemaps=None, drop=15):
        frames = _load_boss_frames()
        first = frames["idle"][0] if frames["idle"] else pygame.Surface(
            (_BOSS_FRAME * _BOSS_SCALE, _BOSS_FRAME * _BOSS_SCALE), pygame.SRCALPHA
        )

        super().__init__(first, pos)
        self.id = f"boss_{id(self)}"
        self.game = game
        self.tilemap = tilemap
        self.tilemaps = tilemaps if tilemaps is not None else (
            [tilemap] if tilemap is not None else []
        )
        self.drop = drop
        self.attributes = {"boss": True}
        self.z = 4
        self._editor_grid_pos = None
        if tilemap is not None and getattr(tilemap, "tile_size", 0):
            ts = tilemap.tile_size
            self._editor_grid_pos = (
                int(pos[0] // ts) - int(tilemap.pos.x),
                int(pos[1] // ts) - int(tilemap.pos.y),
            )

        shrink_x = self.rect.width // 3
        shrink_y = self.rect.height // 4
        self.hitbox = self.rect.inflate(-shrink_x, -shrink_y)
        new_w = max(8, int(self.hitbox.width * 0.8))
        new_h = max(8, int(self.hitbox.height * 0.8))
        self.hitbox = pygame.Rect(0, 0, new_w, new_h)
        self.hitbox.center = self.rect.center

        self.setup_combat(
            health=40,
            knockback_force=0,
            hit_cooldown_ms=300,
            stun_duration_ms=0,
            sight_range=self.SIGHT_RANGE,
            chase_speed_mult=1.0,
        )

        self._anim_state = "idle"
        self._anim_frame = 0.0
        self._anim_done = False
        self._facing = 1
        self._invisible = False

        now = pygame.time.get_ticks()
        self._teleport_until = now + 800
        self._next_attack_at = now + self.ATTACK_COOLDOWN_MS
        self._next_summon_at = now + self.SUMMON_COOLDOWN_MS
        self._next_decision_at = now
        self._attack_landed_frames: set[int] = set()

        self._active_summons: list = []
        self._max_summons = 3

        self.death_done = False

    def _set_anim(self, state):
        if state == self._anim_state:
            return
        self._anim_state = state
        self._anim_frame = 0.0
        self._anim_done = False
        self._attack_landed_frames.clear()

    def _advance_anim(self, dt):
        frames = _load_boss_frames().get(self._anim_state) or []
        if not frames:
            return
        ms = _BOSS_ANIM_MS.get(self._anim_state, 100)
        self._anim_frame += (dt * 1000.0) / max(1, ms)
        loop = _BOSS_LOOP.get(self._anim_state, True)
        if loop:
            idx = int(self._anim_frame) % len(frames)
        else:
            if self._anim_frame >= len(frames):
                self._anim_frame = len(frames) - 1
                self._anim_done = True
            idx = int(self._anim_frame)
            if idx >= len(frames):
                idx = len(frames) - 1

        frame = frames[idx]
        if self._facing < 0:
            frame = pygame.transform.flip(frame, True, False)

        if self.is_hit and self._anim_state != "death":
            frame = frame.copy()
            flash = pygame.Surface(frame.get_size(), pygame.SRCALPHA)
            flash.fill((255, 235, 90, 110))
            frame.blit(flash, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        center = self.rect.center
        self.image = frame
        self.rect = frame.get_rect(center=center)
        self.hitbox.center = self.rect.center

    def _face_player(self):
        player = self.get_player()
        if player is not None:
            self._facing = 1 if player.rect.centerx >= self.rect.centerx else -1

    def _find_teleport_spot(self):
        """Find a sane ground spot within ~150-260 px of the player."""
        player = self.get_player()
        if player is None:
            return None
        for _ in range(12):
            angle = random.uniform(-math.pi, math.pi)
            dist = random.uniform(150, 260)
            tx = int(player.rect.centerx + math.cos(angle) * dist)
            ty = int(player.rect.centery + math.sin(angle) * dist * 0.4)
            spot = self._snap_to_ground(tx, ty)
            if spot is not None:
                return spot
        return (player.rect.centerx + random.choice([-200, 200]), player.rect.centery)

    def _snap_to_ground(self, world_x, world_y):
        """Drop ``world_y`` until just above the first solid tile in the column."""
        for tilemap in self.tilemaps or []:
            if not getattr(tilemap, "rendered", False):
                continue
            ts = tilemap.tile_size
            gx = int(world_x // ts)
            for gy in range(int(world_y // ts), int(world_y // ts) + 16):
                for tile in tilemap.get_tiles_at(gx, gy):
                    if "solid" in tile.get("properties", []):
                        return (world_x, gy * ts - self.rect.height // 2)
        return None

    def _attack_hitbox(self):
        """Forward-facing rectangle the boss hurts the player with."""
        reach = 90
        h = max(40, self.hitbox.height // 2)
        if self._facing > 0:
            return pygame.Rect(self.hitbox.right, self.hitbox.centery - h // 2, reach, h)
        return pygame.Rect(self.hitbox.left - reach, self.hitbox.centery - h // 2, reach, h)

    def _hurt_player_if_in_range(self):
        player = self.get_player()
        if player is None:
            return
        if player.timers.get("invulnerability", 0) > 0:
            return
        if self._attack_hitbox().colliderect(player.rect):
            attrs = getattr(player, "attributes", {})
            if "health" not in attrs:
                return
            attrs["health"] = max(0, attrs["health"] - self.ATTACK_DAMAGE)
            attrs["damaged"] = True
            player.timers["damage"] = 500
            player.timers["invulnerability"] = 2000
            if attrs["health"] <= 0:
                attrs["dead"] = True
                player.animation = "smoke_out"
                player.frame = 0
                player.velocity.x = 0
                player.velocity.y = 0
                attrs["can_move"] = False

    def _spawn_summon(self):
        """Drop a freshly-appeared skeleton near the player."""
        player = self.get_player()
        if player is None:
            return
        self._active_summons = [s for s in self._active_summons if s.is_alive]
        if len(self._active_summons) >= self._max_summons:
            return

        spawn_x = player.rect.centerx + random.choice([-90, 90])
        spawn_y = player.rect.centery
        ground = self._snap_to_ground(spawn_x, spawn_y)
        if ground is None:
            ground = (spawn_x, spawn_y)

        summon = SummonedSkeleton(
            self.game, ground, tilemap=self.tilemap, tilemaps=self.tilemaps
        )
        self._active_summons.append(summon)
        if self.tilemap is not None:
            self.tilemap.enemies.append(summon)

    def _start_teleport(self):
        self._set_anim("teleport")
        self._invisible = True
        self._teleport_relocate_at = pygame.time.get_ticks() + 250

    def _maybe_finish_teleport(self):
        """Mid-anim relocate, end-anim resume normal behaviour."""
        if self._anim_state != "teleport":
            return
        now = pygame.time.get_ticks()
        if self._invisible and now >= getattr(self, "_teleport_relocate_at", 0):
            spot = self._find_teleport_spot()
            if spot:
                self.rect.center = spot
                self.hitbox.center = self.rect.center
            self._invisible = False
            self._face_player()
        if self._anim_done:
            self._teleport_until = now + self.TELEPORT_COOLDOWN_MS
            self._next_decision_at = now + self.DECISION_PAUSE_MS
            self._set_anim("idle2")

    def update(self, dt):
        if self.ai_state == "dead":
            self._set_anim("death")
            self._advance_anim(dt)
            if self._anim_done and not self.death_done:
                self.death_done = True
                try:
                    from Game.utils.items_db import make_inv_item, _draw_item_icon
                    player = self.get_player()
                    if player is not None:
                        already_has = any(
                            it.get("id") == "key" for it in getattr(player, "inventory", [])
                        )
                        if not already_has:
                            key_item = make_inv_item("key", 1)
                            try:
                                key_item["icon"] = _draw_item_icon("key", 32)
                            except Exception:
                                key_item["icon"] = None
                            player.inventory.append(key_item)
                            if hasattr(self.game, "hud"):
                                self.game.hud.show_toast(
                                    "Boss derrotado — Llave obtenida"
                                )
                except Exception as _ce:
                    print(f"[boss] key drop failed: {_ce}")
            return

        self.tick_combat_state()
        now = pygame.time.get_ticks()

        if self._anim_state not in ("attack", "summon", "teleport", "death"):
            self._face_player()

        if self._anim_state == "attack":
            current_frame = int(self._anim_frame)
            if (
                current_frame in self.ATTACK_HIT_FRAMES
                and current_frame not in self._attack_landed_frames
            ):
                self._attack_landed_frames.add(current_frame)
                self._hurt_player_if_in_range()
            if self._anim_done:
                self._next_attack_at = now + self.ATTACK_COOLDOWN_MS
                self._next_decision_at = now + self.DECISION_PAUSE_MS
                self._set_anim("idle2")
            self._advance_anim(dt)
            return

        if self._anim_state == "summon":
            if self._anim_done:
                self._spawn_summon()
                self._next_summon_at = now + self.SUMMON_COOLDOWN_MS
                self._next_decision_at = now + self.DECISION_PAUSE_MS
                self._set_anim("idle")
            self._advance_anim(dt)
            return

        if self._anim_state == "teleport":
            self._maybe_finish_teleport()
            self._advance_anim(dt)
            return

        if not self.can_see_player():
            self._set_anim("idle")
            self._advance_anim(dt)
            return

        if now < self._next_decision_at:
            self._advance_anim(dt)
            return

        dist = self.distance_to_player()

        if dist <= self.ATTACK_RANGE and now >= self._next_attack_at:
            self._set_anim("attack")
            self._advance_anim(dt)
            return

        choices = []
        if now >= self._teleport_until:
            choices.append(("teleport", 4))
        if now >= self._next_summon_at and len(
            [s for s in self._active_summons if s.is_alive]
        ) < self._max_summons:
            choices.append(("summon", 2))
        if not choices:
            self._set_anim("idle2")
            self._advance_anim(dt)
            return

        total = sum(w for _, w in choices)
        roll = random.uniform(0, total)
        upto = 0
        pick = choices[0][0]
        for name, weight in choices:
            upto += weight
            if roll <= upto:
                pick = name
                break

        if pick == "teleport":
            self._start_teleport()
        else:
            self._set_anim("summon")
        self._advance_anim(dt)

    def draw(self, surf, offset=pygame.Vector2(0, 0)):
        if self._invisible:
            return
        surf.blit(self.image, (self.rect.x - offset[0], self.rect.y - offset[1]))
        if getattr(self.game, "debug_mode", False):
            r = pygame.Rect(
                self.hitbox.x - offset[0], self.hitbox.y - offset[1],
                self.hitbox.width, self.hitbox.height
            )
            pygame.draw.rect(surf, (255, 80, 80), r, 2)

class SummonedSkeleton(Sprite, EnemyCombatMixin):
    """Glass-cannon adds spawned by the boss.

    Lifecycle: ``appear`` (rises from the ground, can't move/be hurt) →
    ``idle`` (dashes toward the player; first contact deals 1 damage and
    triggers ``death``). Player can also kill it — single hit suffices.
    """

    tilemaps: Any
    tilemap: Any

    SIGHT_RANGE = 800
    MOVE_SPEED = 130
    CONTACT_DAMAGE = 1
    APPEAR_DURATION_MS = 600

    def __init__(self, game, pos, tilemap=None, tilemaps=None):
        frames = _load_summon_frames()
        first = frames["appear"][0] if frames["appear"] else pygame.Surface(
            (_SUMMON_FRAME * _SUMMON_SCALE, _SUMMON_FRAME * _SUMMON_SCALE),
            pygame.SRCALPHA,
        )
        super().__init__(first, pos)
        self.id = f"summon_{id(self)}"
        self.game = game
        self.tilemap = tilemap
        self.tilemaps = tilemaps if tilemaps is not None else (
            [tilemap] if tilemap is not None else []
        )
        self.attributes = {"summon": True}
        self.z = 4
        self.drop = 0
        self._editor_grid_pos = None

        shrink = max(8, self.rect.width // 4)
        self.hitbox = self.rect.inflate(-shrink, -shrink)
        self.hitbox.center = self.rect.center

        self.setup_combat(
            health=1,
            knockback_force=60,
            hit_cooldown_ms=200,
            stun_duration_ms=120,
            sight_range=self.SIGHT_RANGE,
            chase_speed_mult=1.0,
        )

        self._anim_state = "appear"
        self._anim_frame = 0.0
        self._anim_done = False
        self._facing = 1
        self._spawned_at = pygame.time.get_ticks()
        self._touched_player = False
        self.death_done = False

    def _set_anim(self, state):
        if state == self._anim_state:
            return
        self._anim_state = state
        self._anim_frame = 0.0
        self._anim_done = False

    def _advance_anim(self, dt):
        frames = _load_summon_frames().get(self._anim_state) or []
        if not frames:
            return
        ms = _SUMMON_ANIM_MS.get(self._anim_state, 100)
        self._anim_frame += (dt * 1000.0) / max(1, ms)
        loop = _SUMMON_LOOP.get(self._anim_state, True)
        if loop:
            idx = int(self._anim_frame) % len(frames)
        else:
            if self._anim_frame >= len(frames):
                self._anim_frame = len(frames) - 1
                self._anim_done = True
            idx = int(self._anim_frame)
            if idx >= len(frames):
                idx = len(frames) - 1

        frame = frames[idx]
        if self._facing < 0:
            frame = pygame.transform.flip(frame, True, False)

        if self.is_hit and self._anim_state != "death":
            frame = frame.copy()
            flash = pygame.Surface(frame.get_size(), pygame.SRCALPHA)
            flash.fill((255, 235, 90, 110))
            frame.blit(flash, (0, 0), special_flags=pygame.BLEND_RGBA_ADD)

        c = self.rect.center
        self.image = frame
        self.rect = frame.get_rect(center=c)
        self.hitbox.center = self.rect.center

    def _check_contact(self):
        """If we touch the player, trigger our own death (the player's contact
        damage check applies the HP loss). If they have i-frames we still die
        on contact so the summon truly is a one-shot threat."""
        player = self.get_player()
        if player is None or self._touched_player:
            return
        if self.hitbox.colliderect(player.rect):
            self._touched_player = True
            self.health = 0
            self.ai_state = "dead"

    def update(self, dt):
        if self.ai_state == "dead":
            self._set_anim("death")
            self._advance_anim(dt)
            if self._anim_done:
                self.death_done = True
            return

        if self._anim_state == "appear":
            self._advance_anim(dt)
            if self._anim_done:
                self._set_anim("idle")
            return

        self.tick_combat_state()

        player = self.get_player()
        if player is not None:
            dx = player.rect.centerx - self.rect.centerx
            dy = player.rect.centery - self.rect.centery
            norm = math.hypot(dx, dy)
            if norm > 0:
                self.rect.x += int((dx / norm) * self.MOVE_SPEED * dt)
                self.rect.y += int((dy / norm) * self.MOVE_SPEED * dt)
                self._facing = 1 if dx >= 0 else -1
            self.hitbox.center = self.rect.center
            self._check_contact()

        self._advance_anim(dt)

    def draw(self, surf, offset=pygame.Vector2(0, 0)):
        surf.blit(self.image, (self.rect.x - offset[0], self.rect.y - offset[1]))
        if getattr(self.game, "debug_mode", False):
            r = pygame.Rect(
                self.hitbox.x - offset[0], self.hitbox.y - offset[1],
                self.hitbox.width, self.hitbox.height,
            )
            pygame.draw.rect(surf, (255, 80, 80), r, 2)
