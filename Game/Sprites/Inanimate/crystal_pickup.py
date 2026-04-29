import pygame
import math

from Game.Sprites.sprite import Sprite
from Game.utils.utils import load_image


class CrystalPickup(Sprite):
    """A static collectible crystal placed in the editor.

    Sits on its tile, bobs gently up and down, and disappears the moment
    the player walks through it (adding ``value`` to the crystal counter).
    Persists in the level JSON between sessions.
    """

    def __init__(self, pos, game, tilemap, value=1):
        size = (24, 24)
        try:
            base_img = load_image("miscellaneous/crystal.png", size=size)
        except Exception:
            base_img = pygame.Surface(size, pygame.SRCALPHA)
            pygame.draw.polygon(
                base_img, (140, 220, 255),
                [(12, 0), (24, 12), (12, 24), (0, 12)],
            )
            pygame.draw.polygon(
                base_img, (240, 250, 255),
                [(12, 0), (24, 12), (12, 24), (0, 12)], 1,
            )

        super().__init__(base_img, pos)
        self._base_image = base_img
        self.rect = self._base_image.get_rect(topleft=pos)
        self._home_y = self.rect.y
        self._t = 0.0

        self.game = game
        self.tilemap = tilemap
        self.value = int(value)
        self.collected = False
        self.id = f"crystal_pickup_{id(self)}"

        self._editor_grid_pos = None
        if tilemap is not None and getattr(tilemap, "tile_size", 0):
            ts = tilemap.tile_size
            self._editor_grid_pos = (
                int(pos[0] // ts) - int(tilemap.pos.x),
                int(pos[1] // ts) - int(tilemap.pos.y),
            )

    def draw(self, surf, offset=(0, 0)):
        surf.blit(self.image, (self.rect.x - offset[0], self.rect.y - offset[1]))

    def update(self, dt):
        self._t += dt
        bob = math.sin(self._t * 4.0) * 3
        self.rect.y = int(self._home_y + bob)

        if self.collected:
            return

        player = getattr(self.game, "player", None)
        if player is not None and self.rect.colliderect(player.rect):
            player.crystals += self.value
            self.collected = True
            if self.tilemap is not None and hasattr(self.tilemap, "crystal_pickups"):
                self.tilemap.crystal_pickups.remove(self)
