from typing import Any, Optional
import pygame

class Sprite(pygame.sprite.Sprite):
    image: pygame.Surface  # pyright: ignore
    rect: pygame.Rect  # pyright: ignore

    def __init__(self, img, pos=(0, 0), identifier=None):
        super().__init__()
        self.image = img  # pyright: ignore[reportIncompatibleMethodOverride]
        self.rect = self.image.get_rect(topleft=pos)  # pyright: ignore[reportIncompatibleMethodOverride]
        self.z = 0
        self.id = identifier

    def move_to(self, dx, dy):
        self.rect.x += dx
        self.rect.y += dy

    def draw(self, surf, offset=(0, 0)):
        surf.blit(self.image, self.rect.topleft - pygame.math.Vector2(offset))

    def update(self, *args: Any, **kwargs: Any) -> None:
        pass

class PhysicsSprite(Sprite):
    def __init__(self, img, pos=(0, 0), tilemap=None, identifier=None):
        super().__init__(img, pos, identifier)
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, 0)
        self.friction = -0.12
        self.gravity = 0.5
        self.tilemap: Any = tilemap
        self.game: Any = None

        self.collisions = {
            "top": False,
            "bottom": False,
            "left": False,
            "right": False,
        }

    def apply_gravity(self):
        self.acc.y += self.gravity

    def apply_friction(self):
        self.acc.x += self.vel.x * self.friction

    def check_wall_collisions(self):
        if not self.game or not hasattr(self.game, 'tilemaps'):
            return False

        collision_occurred = False

        for tilemap in self.game.tilemaps.values():
            if not tilemap.rendered:
                continue

            left_tile = int(self.rect.left - tilemap.pos.x * tilemap.tile_size) // tilemap.tile_size
            right_tile = int(self.rect.right - 1 - tilemap.pos.x * tilemap.tile_size) // tilemap.tile_size
            top_tile = int(self.rect.top - tilemap.pos.y * tilemap.tile_size) // tilemap.tile_size
            bottom_tile = int(self.rect.bottom - 1 - tilemap.pos.y * tilemap.tile_size) // tilemap.tile_size

            for tile_y in range(top_tile, bottom_tile + 1):
                for tile_key, tile_data in tilemap.tile_map.items():
                    if (tile_data['x'] - tilemap.pos.x == left_tile and
                        tile_data['y'] - tilemap.pos.y == tile_y):
                        if 'no_collision' not in tile_data.get('properties', []):
                            tile_right = (tile_data['x'] + 1) * tilemap.tile_size
                            if self.rect.left < tile_right and self.rect.right > tile_data['x'] * tilemap.tile_size:
                                self.rect.left = tile_right
                                self.vel.x = 0
                                self.collisions["left"] = True
                                collision_occurred = True

            for tile_y in range(top_tile, bottom_tile + 1):
                for tile_key, tile_data in tilemap.tile_map.items():
                    if (tile_data['x'] - tilemap.pos.x == right_tile and
                        tile_data['y'] - tilemap.pos.y == tile_y):
                        if 'no_collision' not in tile_data.get('properties', []):
                            tile_left = tile_data['x'] * tilemap.tile_size
                            if self.rect.right > tile_left and self.rect.left < (tile_data['x'] + 1) * tilemap.tile_size:
                                self.rect.right = tile_left
                                self.vel.x = 0
                                self.collisions["right"] = True
                                collision_occurred = True

            for breakable in tilemap.breakables.sprite_dict.values():
                if breakable.is_solid() and self.rect.colliderect(breakable.rect):
                    if self.vel.x > 0 and self.rect.right > breakable.rect.left and self.rect.left < breakable.rect.left:
                        self.rect.right = breakable.rect.left
                        self.vel.x = 0
                        self.collisions["right"] = True
                        collision_occurred = True
                    elif self.vel.x < 0 and self.rect.left < breakable.rect.right and self.rect.right > breakable.rect.right:
                        self.rect.left = breakable.rect.right
                        self.vel.x = 0
                        self.collisions["left"] = True
                        collision_occurred = True

        if not collision_occurred:
            self.collisions["left"] = False
            self.collisions["right"] = False

        return collision_occurred

    def check_ground_collisions(self):
        if not self.game or not hasattr(self.game, 'tilemaps'):
            return False

        collision_occurred = False

        for tilemap in self.game.tilemaps.values():
            if not tilemap.rendered:
                continue

            left_tile = int(self.rect.left - tilemap.pos.x * tilemap.tile_size) // tilemap.tile_size
            right_tile = int(self.rect.right - 1 - tilemap.pos.x * tilemap.tile_size) // tilemap.tile_size
            top_tile = int(self.rect.top - tilemap.pos.y * tilemap.tile_size) // tilemap.tile_size
            bottom_tile = int(self.rect.bottom - 1 - tilemap.pos.y * tilemap.tile_size) // tilemap.tile_size

            if self.vel.y >= 0:
                for tile_x in range(left_tile, right_tile + 1):
                    for tile_key, tile_data in tilemap.tile_map.items():
                        x = tile_data['x'] - tilemap.pos.x == tile_x
                        y = tile_data['y'] - tilemap.pos.y >= bottom_tile
                        y_off = tile_data['y'] - tilemap.pos.y <= bottom_tile + 1
                        if x and y and y_off:
                            if 'no_collision' not in tile_data.get('properties', []):
                                tile_top = tile_data['y'] * tilemap.tile_size
                                tile_bottom = tile_top + tilemap.tile_size
                                tile_left = tile_data['x'] * tilemap.tile_size
                                tile_right = tile_left + tilemap.tile_size

                                if (self.rect.bottom > tile_top and
                                    self.rect.top < tile_bottom and
                                    self.rect.right > tile_left and
                                    self.rect.left < tile_right):
                                    self.rect.bottom = tile_top
                                    self.vel.y = 0
                                    self.collisions["bottom"] = True
                                    collision_occurred = True

            if self.vel.y < 0:
                for tile_x in range(left_tile, right_tile + 1):
                    for tile_key, tile_data in tilemap.tile_map.items():
                        if (tile_data['x'] - tilemap.pos.x == tile_x and
                            tile_data['y'] - tilemap.pos.y == top_tile):
                            if 'no_collision' not in tile_data.get('properties', []):
                                tile_bottom = (tile_data['y'] + 1) * tilemap.tile_size
                                tile_left = tile_data['x'] * tilemap.tile_size
                                tile_right = tile_left + tilemap.tile_size

                                if (self.rect.top <= tile_bottom and
                                    self.rect.right > tile_left and
                                    self.rect.left < tile_right):
                                    self.rect.top = tile_bottom
                                    self.vel.y = 0
                                    self.collisions["top"] = True
                                    collision_occurred = True

            for breakable in tilemap.breakables.sprite_dict.values():
                if breakable.is_solid() and self.rect.colliderect(breakable.rect):
                    if self.vel.y > 0 and self.rect.bottom > breakable.rect.top and self.rect.top < breakable.rect.top:
                        self.rect.bottom = breakable.rect.top
                        self.vel.y = 0
                        self.collisions["bottom"] = True
                        collision_occurred = True
                    elif self.vel.y < 0 and self.rect.top < breakable.rect.bottom and self.rect.bottom > breakable.rect.bottom:
                        self.rect.top = breakable.rect.bottom
                        self.vel.y = 0
                        self.collisions["top"] = True
                        collision_occurred = True

        if not collision_occurred:
            self.collisions["bottom"] = False
            self.collisions["top"] = False

        return collision_occurred

    def check_collisions(self):
        wall_collision = self.check_wall_collisions()
        ground_collision = self.check_ground_collisions()
        return wall_collision or ground_collision

    def update(self, *args: Any, **kwargs: Any) -> None:
        dt = args[0] if args else kwargs.get("dt", 0)
        self.apply_gravity()
        self.apply_friction()

        self.vel += self.acc

        self.rect.x += self.vel.x * dt
        self.check_wall_collisions()

        self.rect.y += self.vel.y * dt
        self.check_ground_collisions()

        self.acc = pygame.math.Vector2(0, 0)
