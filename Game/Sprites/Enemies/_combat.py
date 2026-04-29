"""Shared combat / awareness logic for enemies.

`EnemyCombatMixin` provides health, hit-flash, stun, knockback, an AI state
machine (idle/patrol/chase/hurt/dead), and line-of-sight helpers that any
enemy class can mix in alongside its own movement code. The mixin makes no
assumptions about gravity or movement style, so it works for both the
ground-walking `Enemy` (PhysicsSprite) and the `FlyingEnemy` (Sprite).
"""

from typing import Any
import pygame


class EnemyCombatMixin:
    rect: pygame.Rect
    vel: Any
    velocity: Any
    direction: Any
    direction_x: Any
    game: Any

    def setup_combat(
        self,
        *,
        health=3,
        knockback_force=150,
        hit_cooldown_ms=400,
        stun_duration_ms=300,
        sight_range=240,
        chase_speed_mult=2.0,
    ):
        self.health = health
        self.max_health = health
        self.knockback_force = knockback_force
        self.hit_cooldown_ms = hit_cooldown_ms
        self.stun_duration_ms = stun_duration_ms
        self.sight_range = sight_range
        self.chase_speed_mult = chase_speed_mult

        self.ai_state = "patrol"
        self._hit_until = 0
        self._stun_until = 0

    @property
    def is_hit(self):
        return pygame.time.get_ticks() < self._hit_until

    @property
    def is_stunned(self):
        return pygame.time.get_ticks() < self._stun_until

    @property
    def is_alive(self):
        return self.health > 0

    def take_damage(self, amount, source_x=None):
        """Apply damage with i-frames + stun + knockback. Returns True if landed."""
        if self.is_hit:
            return False
        now = pygame.time.get_ticks()
        self.health -= amount
        self._hit_until = now + self.hit_cooldown_ms
        self._stun_until = now + self.stun_duration_ms
        if self.health <= 0:
            self.ai_state = "dead"
            return True
        self.ai_state = "hurt"

        if source_x is None:
            source_x = self.rect.centerx
        kb_dir = 1 if self.rect.centerx >= source_x else -1
        if hasattr(self, "vel"):
            self.vel.x = kb_dir * self.knockback_force
        if hasattr(self, "velocity"):
            self.velocity.x = kb_dir * self.knockback_force
        if hasattr(self, "direction"):
            self.direction = kb_dir
        if hasattr(self, "direction_x"):
            self.direction_x = kb_dir
        return True

    def tick_combat_state(self):
        """Drop out of 'hurt' once the stun expires."""
        if self.ai_state == "hurt" and not self.is_stunned:
            self.ai_state = "patrol"

    def get_player(self):
        return getattr(getattr(self, "game", None), "player", None)

    def distance_to_player(self):
        player = self.get_player()
        if player is None:
            return float("inf")
        dx = player.rect.centerx - self.rect.centerx
        dy = player.rect.centery - self.rect.centery
        return (dx * dx + dy * dy) ** 0.5

    def can_see_player(self):
        """Player within sight_range AND no solid tile blocks the line of sight."""
        player = self.get_player()
        if player is None:
            return False
        if self.distance_to_player() > self.sight_range:
            return False
        return self._segment_clear(
            (self.rect.centerx, self.rect.centery),
            (player.rect.centerx, player.rect.centery),
        )

    def _segment_clear(self, a, b):
        """Cheap raycast: sample the segment every ~12 px and check tiles."""
        game = getattr(self, "game", None)
        if game is None or not hasattr(game, "tilemaps"):
            return True
        length = ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        steps = max(2, int(length / 12))
        for s in range(1, steps):
            t = s / steps
            px = a[0] + (b[0] - a[0]) * t
            py = a[1] + (b[1] - a[1]) * t
            for tilemap in game.tilemaps.values():
                if not getattr(tilemap, "rendered", False):
                    continue
                ts = tilemap.tile_size
                gx = int(px // ts)
                gy = int(py // ts)
                if not hasattr(tilemap, "get_tiles_at"):
                    continue
                for tile in tilemap.get_tiles_at(gx, gy):
                    if "solid" in tile.get("properties", []):
                        return False
        return True

    def body_color(self):
        """State-aware tint used while we don't have proper enemy sprite sheets."""
        if self.ai_state == "dead":
            return (60, 60, 60)
        if self.is_hit:
            return (255, 235, 90)
        if self.is_stunned:
            return (255, 160, 60)
        if self.ai_state == "chase":
            return (240, 60, 60)
        if self.ai_state == "patrol":
            return (190, 60, 60)
        return (140, 60, 60)
