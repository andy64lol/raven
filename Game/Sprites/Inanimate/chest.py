import pygame

from Game.Sprites.sprite import Sprite
from Game.Sprites.Inanimate.item import Item

class Chest(Sprite):
    """A chest that drops items when the player touches it.

    ``contains`` is a list of item-key strings from items_db.ITEMS,
    e.g. ["sword", "crystal", "crystal"].
    """

    def __init__(self, pos, game, tilemap, contains=None):
        self.image_closed = pygame.Surface((32, 32), pygame.SRCALPHA)
        self.image_opened = pygame.Surface((32, 32), pygame.SRCALPHA)
        self._draw_chest(self.image_closed, opened=False)
        self._draw_chest(self.image_opened, opened=True)

        super().__init__(self.image_closed, pos)

        self.id = f"chest_{id(self)}"
        self.game = game
        self.tilemap = tilemap

        self.contains = contains or []
        self.image = self.image_closed

        self.rect = self.image.get_rect()
        self.rect.topright = pos
        self.opened = False

    @staticmethod
    def _draw_chest(surf, opened: bool):
        w, h = surf.get_size()
        wood = (139, 90, 43) if not opened else (95, 60, 30)
        rim = (40, 25, 12)
        plank = (60, 38, 20)
        pygame.draw.rect(surf, wood, (1, 1, w - 2, h - 2))
        pygame.draw.rect(surf, rim, (0, 0, w, h), 2)
        pygame.draw.line(surf, plank, (0, h // 2), (w, h // 2), 1)
        pygame.draw.line(surf, plank, (w // 2, 0), (w // 2, h), 1)
        lock = (220, 200, 80)
        if not opened:
            pygame.draw.circle(surf, lock, (w // 2, h // 2), 5)
        else:
            pygame.draw.rect(surf, (25, 15, 5), (4, 4, w - 8, h - 8))

    def open(self):
        if not self.opened:
            self.opened = True
            self.image = self.image_opened
            for item_key in self.contains:
                drop_pos = (self.rect.centerx, self.rect.top - 8)
                item = Item(drop_pos, self.game, self.tilemap, item_key, qty=1)
                self.tilemap.items.append(item)

    def update(self, dt):
        if self.rect.colliderect(self.game.player.rect):
            self.open()
