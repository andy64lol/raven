import math
import os
from typing import Any
import pygame

from Game.Sprites.sprite import Sprite
from Game.Sprites.Enemies._combat import EnemyCombatMixin


_BAT_BASE = os.path.join("Game", "assets", "monsters", "bat(flying)")
_BAT_FRAMES = None  # lazily populated dict: {state: [Surface, ...]}

_BAT_ANIM_SPEC = {
    "idle":   ("Idle",          120, True),
    "windup": ("Attack Windup", 70,  False),
    "attack": ("Attack",        60,  False),
    "hit":    ("Hit",           80,  False),
    "death":  ("Death",         100, False),
}

_ATTACK_RANGE = 110          # px; bat starts windup when player is this close
_ATTACK_COOLDOWN_MS = 1100   # min gap between attack windups
_BAT_SCALE = 3               # render the bat 3× larger than the source frames


def _load_bat_frames():
    """Load every bat animation folder once and cache the frames (scaled)."""
    global _BAT_FRAMES
    if _BAT_FRAMES is not None:
        return _BAT_FRAMES
    frames = {}
    for state, (folder, _dur, _loop) in _BAT_ANIM_SPEC.items():
        full_dir = os.path.join(_BAT_BASE, folder)
        if not os.path.isdir(full_dir):
            frames[state] = []
            continue
        files = []
        for fn in os.listdir(full_dir):
            if not fn.lower().endswith(".png"):
                continue
            if "spritesheet" in fn.lower():
                continue
            files.append(fn)
        def _frame_index(name):
            stem = os.path.splitext(name)[0]
            tail = stem.rsplit("_", 1)[-1]
            try:
                return int(tail)
            except ValueError:
                return 0
        files.sort(key=_frame_index)

        loaded = []
        for fn in files:
            path = os.path.join(full_dir, fn)
            img = pygame.image.load(path)
            try:
                img = img.convert_alpha()
            except pygame.error:
                pass
            if _BAT_SCALE != 1:
                w, h = img.get_size()
                img = pygame.transform.scale(img, (w * _BAT_SCALE, h * _BAT_SCALE))
            loaded.append(img)
        frames[state] = loaded
    _BAT_FRAMES = frames
    return _BAT_FRAMES


class FlyingEnemy(Sprite, EnemyCombatMixin):
    tilemaps: Any
    tilemap: Any

    """Bat-style flying enemy.

    Patrols along an arbitrary `move_axis` vector inside a fixed range from
    its spawn. When the player enters line of sight it switches to `chase`
    and steers toward them in 2D. When close enough it plays a windup +
    attack animation. Hits stun + knock it back via the shared combat mixin.
    """

    def __init__(
        self,
        game,
        pos,
        image=None,
        tilemaps=None,
        tilemap=None,
        move_axis=pygame.Vector2(0, 0),
        drop=0,
    ):
        bat_frames = _load_bat_frames()
        idle_frames = bat_frames.get("idle") or []
        first_frame = idle_frames[0] if idle_frames else pygame.Surface((32, 32), pygame.SRCALPHA)

        super().__init__(first_frame, pos)
        self.id = f"flying_enemy_{id(self)}"
        self.game = game
        self.tilemaps = tilemaps
        self.tilemap = tilemap
        self.base_speed = 1
        self.speed = self.base_speed
        self.drop = drop
        self.movement_range = 300
        self._idle_bob_phase = 0.0
        self._idle_bob_speed = 2.0
        self._idle_bob_amplitude = 6.0
        self.start_x = pos[0]
        self.start_y = pos[1]
        self.z = 1

        self.move_axis = move_axis
        self.attributes = {"flying": True}
        self._editor_grid_pos = None
        if tilemap is not None and getattr(tilemap, "tile_size", 0):
            ts = tilemap.tile_size
            self._editor_grid_pos = (
                int(pos[0] // ts) - int(tilemap.pos.x),
                int(pos[1] // ts) - int(tilemap.pos.y),
            )

        shrink = max(10, self.rect.width // 4)
        self.hitbox = self.rect.inflate(-shrink, -shrink)
        self.hitbox.center = self.rect.center

        self.camera_offset = pygame.Vector2(0, 0)
        self.screen_pos = pygame.Vector2(0, 0)

        self.direction_x = 1
        self.direction_y = 1

        self.setup_combat(
            health=1,
            knockback_force=80,
            hit_cooldown_ms=400,
            stun_duration_ms=400,
            sight_range=600,           # wider FOV — bats spot the player from much further
            chase_speed_mult=1.6,
        )

        self._anim_state = "idle"
        self._anim_frame = 0.0       # float frame index
        self._anim_done = False      # set when a non-looping animation finishes
        self._facing = 1             # 1 = facing right, -1 = facing left
        self._attack_cooldown_until = 0
        self._death_played = False


    def _set_anim(self, state):
        if state == self._anim_state:
            return
        self._anim_state = state
        self._anim_frame = 0.0
        self._anim_done = False

    def _advance_anim(self, dt):
        spec = _BAT_ANIM_SPEC.get(self._anim_state)
        frames = (_BAT_FRAMES or {}).get(self._anim_state) or []
        if not spec or not frames:
            return
        _folder, frame_ms, loop = spec
        self._anim_frame += (dt * 1000.0) / max(1, frame_ms)
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

        old_center = self.rect.center
        self.image = frame
        self.rect = frame.get_rect(center=old_center)
        self.hitbox.center = self.rect.center

    def _pick_anim_state(self):
        """Decide which animation should be playing this frame."""
        if self.ai_state == "dead":
            return "death"
        if self.is_hit and self._anim_state not in ("hit", "death"):
            return "hit"
        if self._anim_state == "hit" and not self._anim_done:
            return "hit"
        if self._anim_state == "windup":
            if not self._anim_done:
                return "windup"
            return "attack"
        if self._anim_state == "attack" and not self._anim_done:
            return "attack"
        now = pygame.time.get_ticks()
        if (
            self.ai_state == "chase"
            and now >= self._attack_cooldown_until
            and self.distance_to_player() <= _ATTACK_RANGE
        ):
            self._attack_cooldown_until = now + _ATTACK_COOLDOWN_MS
            return "windup"
        return "idle"


    def tilemap_collisions(self):
        for tilemap in self.tilemaps:
            if not tilemap.rendered:
                continue
            left_tile = (
                int(self.hitbox.left - tilemap.pos.x * tilemap.tile_size)
                // tilemap.tile_size
            )
            right_tile = (
                int(self.hitbox.right - 1 - tilemap.pos.x * tilemap.tile_size)
                // tilemap.tile_size
            )
            top_tile = (
                int(self.hitbox.top - tilemap.pos.y * tilemap.tile_size)
                // tilemap.tile_size
            )
            bottom_tile = (
                int(self.hitbox.bottom - 1 - tilemap.pos.y * tilemap.tile_size)
                // tilemap.tile_size
            )

            for tile_key, tile_data in tilemap.tile_map.items():
                if "solid" in tile_data["properties"]:
                    tile_x = tile_data["x"] - tilemap.pos.x
                    tile_y = tile_data["y"] - tilemap.pos.y

                    if (
                        left_tile <= tile_x <= right_tile
                        and top_tile <= tile_y <= bottom_tile
                    ):
                        tile_world_x = (
                            tile_x * tilemap.tile_size
                            + tilemap.pos.x * tilemap.tile_size
                        )
                        tile_world_y = (
                            tile_y * tilemap.tile_size
                            + tilemap.pos.y * tilemap.tile_size
                        )
                        tile_rect = pygame.Rect(
                            tile_world_x,
                            tile_world_y,
                            tilemap.tile_size,
                            tilemap.tile_size,
                        )

                        if self.hitbox.colliderect(tile_rect):
                            overlap_left = self.hitbox.right - tile_rect.left
                            overlap_right = tile_rect.right - self.hitbox.left
                            overlap_top = self.hitbox.bottom - tile_rect.top
                            overlap_bottom = tile_rect.bottom - self.hitbox.top

                            min_overlap = min(
                                overlap_left, overlap_right, overlap_top, overlap_bottom
                            )

                            if min_overlap == overlap_left:
                                self.hitbox.right = tile_rect.left - 2
                                self.rect.right = self.hitbox.right - 5
                                self.direction_x = -1
                            elif min_overlap == overlap_right:
                                self.hitbox.left = tile_rect.right + 2
                                self.rect.left = self.hitbox.left + 5
                                self.direction_x = 1
                            elif min_overlap == overlap_top:
                                self.hitbox.bottom = tile_rect.top - 2
                                self.rect.bottom = self.hitbox.bottom - 5
                                self.direction_y = -1
                            elif min_overlap == overlap_bottom:
                                self.hitbox.top = tile_rect.bottom + 2
                                self.rect.top = self.hitbox.top + 5
                                self.direction_y = 1

                            return

    def update(self, dt):
        if self.ai_state == "dead":
            self._set_anim("death")
            self._advance_anim(dt)
            return

        self.tick_combat_state()
        if self.is_stunned:
            new_state = self._pick_anim_state()
            self._set_anim(new_state)
            self._advance_anim(dt)
            return

        if self.can_see_player():
            self.ai_state = "chase"
        elif self.ai_state == "chase":
            if self.distance_to_player() > self.sight_range * 1.4:
                self.ai_state = "patrol"

        if self.ai_state == "chase":
            player = self.get_player()
            if player is not None:
                dx = player.rect.centerx - self.rect.centerx
                dy = player.rect.centery - self.rect.centery
                norm = (dx * dx + dy * dy) ** 0.5
                if norm > 0:
                    chase_speed = self.base_speed * self.chase_speed_mult
                    self.rect.x += (dx / norm) * chase_speed
                    self.rect.y += (dy / norm) * chase_speed
                if dx != 0:
                    self._facing = 1 if dx >= 0 else -1
        else:
            if self.move_axis.x == 0 and self.move_axis.y == 0:
                self._idle_bob_phase += self._idle_bob_speed * dt
                target_y = self.start_y + math.sin(self._idle_bob_phase) * self._idle_bob_amplitude
                self.rect.y += (target_y - self.rect.y) * min(1.0, dt * 6.0)
                self.rect.x += (self.start_x - self.rect.x) * min(1.0, dt * 4.0)
            else:
                movement_vector = self.move_axis * self.base_speed
                self.rect.x += movement_vector.x * self.direction_x
                self.rect.y += movement_vector.y * self.direction_y
                if self.move_axis.x != 0:
                    self._facing = 1 if self.direction_x >= 0 else -1

        self.tilemap_collisions()

        if self.move_axis.x != 0:
            left_boundary = self.start_x - self.movement_range
            right_boundary = self.start_x + self.movement_range

            if self.rect.x <= left_boundary:
                self.rect.x = left_boundary
                self.direction_x = 1
            elif self.rect.x >= right_boundary:
                self.rect.x = right_boundary
                self.direction_x = -1

        if self.move_axis.y != 0:
            top_boundary = self.start_y - self.movement_range
            bottom_boundary = self.start_y + self.movement_range

            if self.rect.y <= top_boundary:
                self.rect.y = top_boundary
                self.direction_y = 1
            elif self.rect.y >= bottom_boundary:
                self.rect.y = bottom_boundary
                self.direction_y = -1

        self.hitbox.center = self.rect.center

        new_state = self._pick_anim_state()
        self._set_anim(new_state)
        self._advance_anim(dt)

    def update_camera_position(self, camera_offset):
        self.camera_offset = camera_offset
        self.screen_pos.x = self.rect.x - camera_offset.x
        self.screen_pos.y = self.rect.y - camera_offset.y

    def draw(self, surf, offset=pygame.Vector2(0, 0)):
        draw_pos = (self.rect.x - offset[0], self.rect.y - offset[1])
        surf.blit(self.image, draw_pos)

        if getattr(self.game, "debug_mode", False) or (
            hasattr(self.game, "config")
            and self.game.config.get("debug", {}).get("show_hitboxes", False)
        ):
            debug_hitbox_pos = (self.hitbox.x - offset.x, self.hitbox.y - offset.y)
            pygame.draw.rect(
                surf,
                (255, 0, 0),
                (*debug_hitbox_pos, self.hitbox.width, self.hitbox.height),
                2,
            )

    def get_out(self, times: int) -> None:
        print(("GET OUT!!!!!!!!!!!!!!!!!!\n") * times)
