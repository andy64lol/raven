from Game.Sprites.sprite import PhysicsSprite
from Game.Sprites.Enemies._combat import EnemyCombatMixin
import pygame

class Enemy(PhysicsSprite, EnemyCombatMixin):
    """Ground-walking enemy.

    Patrols left/right, flips at walls and at ledges, and switches to a
    `chase` state when the player enters line of sight. While chasing it
    moves faster and ignores ledges (it'll happily jump off cliffs to
    catch up). Hits stun + knock it back via the shared combat mixin.
    """

    def __init__(self, image=None, pos=(0, 0), game=None,
                 tilemap=None, health=3, drop=0):
        if image is None:
            image = pygame.Surface((32, 32))
        image.fill((255, 0, 0))
        super().__init__(image, pos, tilemap)
        self.velocity = pygame.math.Vector2(0, 0)
        self.acceleration = pygame.math.Vector2(0, 0)
        self.image.fill("red")
        self.rect = self.image.get_rect(topleft=pos)
        self.tilemap = tilemap
        self.game = game

        self.id = f"enemy_{id(self)}"

        self.drop = drop

        self._editor_grid_pos = None
        if tilemap is not None and getattr(tilemap, "tile_size", 0):
            ts = tilemap.tile_size
            self._editor_grid_pos = (
                int(pos[0] // ts) - int(tilemap.pos.x),
                int(pos[1] // ts) - int(tilemap.pos.y),
            )

        self.direction = 1
        self.base_speed = 1
        self.speed = self.base_speed

        self.friction = -0.02
        self.gravity = 15

        self.attributes = {}

        self.setup_combat(
            health=health,
            knockback_force=150,
            hit_cooldown_ms=400,
            stun_duration_ms=300,
            sight_range=240,
            chase_speed_mult=2.5,
        )

    def update(self, dt=0):
        if self.ai_state == "dead":
            super().update(dt)
            return

        self.tick_combat_state()
        if self.ai_state in ("patrol", "idle", "chase"):
            if self.can_see_player():
                self.ai_state = "chase"
            elif self.ai_state == "chase":
                if self.distance_to_player() > self.sight_range * 1.4:
                    self.ai_state = "patrol"

        if self.is_stunned:
            self.acc.x = 0
        elif self.ai_state == "chase":
            player = self.get_player()
            if player is not None:
                self.direction = 1 if player.rect.centerx > self.rect.centerx else -1
            self.speed = self.base_speed * self.chase_speed_mult
            self.acc.x = self.direction * self.speed * 5
        else:
            self.speed = self.base_speed
            self.acc.x = self.direction * self.speed * 5

        super().update(dt)

        self.image.fill(self.body_color())

        if self.is_stunned:
            self.vel.x *= 0.9
            return

        if self.collisions["left"] or self.collisions["right"]:
            self.direction *= -1
            self.vel.x = 0

        if self.collisions["bottom"] and self.ai_state != "chase":
            check_distance = self.rect.width + 5
            check_x = self.rect.centerx + (self.direction * check_distance)
            check_y = self.rect.bottom + 10

            ground_ahead = False
            if self.game and hasattr(self.game, 'tilemaps'):
                for tilemap in self.game.tilemaps.values():
                    if not tilemap.rendered:
                        continue

                    tile_x = int((check_x - tilemap.pos.x * tilemap.tile_size) // tilemap.tile_size)
                    tile_y = int((check_y - tilemap.pos.y * tilemap.tile_size) // tilemap.tile_size)

                    for tile_key, tile_data in tilemap.tile_map.items():
                        if (tile_data['x'] - tilemap.pos.x == tile_x and
                            tile_data['y'] - tilemap.pos.y == tile_y):
                            if 'solid' in tile_data.get('properties', []):
                                ground_ahead = True
                                break

                    if ground_ahead:
                        break

            if not ground_ahead:
                self.direction *= -1
                self.vel.x = 0

    def draw(self, surf, offset=pygame.math.Vector2(0, 0)):
        screen_pos = (self.rect.x - offset[0], self.rect.y - offset[1])
        if self.image:
            surf.blit(self.image, screen_pos)
        else:
            pygame.draw.rect(surf, (255, 0, 0),
                             (screen_pos[0], screen_pos[1], 32, 32))

        if getattr(self.game, "debug_mode", False):
            pygame.draw.rect(surf, (255, 0, 0),
                             (screen_pos[0], screen_pos[1],
                              self.rect.width, self.rect.height), 1)
