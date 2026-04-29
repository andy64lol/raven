import pygame
from Game.Sprites.sprite import Sprite
from Game.utils.items_db import ITEMS, make_inv_item, _draw_item_icon

_ICON_SIZE = 20


class Item(Sprite):
    """A world-space item drop the player can walk over to collect.

    ``item_key`` must be a key from items_db.ITEMS, e.g. "sword", "crystal".
    ``qty``      is the stack quantity added to the inventory (or crystals counter).
    """

    def __init__(self, pos, game, tilemap, item_key: str, qty: int = 1):
        data = ITEMS.get(item_key, {})
        color = data.get("color", (200, 200, 200))

        img = self._build_image(item_key, color)
        super().__init__(img, pos, identifier=id(self))
        self.rect = img.get_rect(center=(int(pos[0]), int(pos[1])))

        self.item_key = item_key
        self.qty = qty
        self.collected = False
        self.game = game
        self.tilemap = tilemap

        self._bob_t = 0.0
        self._base_y = float(self.rect.y)

        self._editor_grid_pos: tuple[int, int] | None = None
        self._is_placed: bool = False

    @staticmethod
    def _build_image(item_key: str, color: tuple) -> pygame.Surface:
        size = _ICON_SIZE
        surf = pygame.Surface((size + 6, size + 6), pygame.SRCALPHA)
        glow_col = (*color, 70)
        pygame.draw.circle(surf, glow_col, (size // 2 + 3, size // 2 + 3), size // 2 + 3)
        icon = _draw_item_icon(item_key, size)
        surf.blit(icon, (3, 3))
        return surf

    def draw(self, surf, offset=(0, 0)):
        surf.blit(self.image, (self.rect.x - offset[0], self.rect.y - offset[1]))

    def collect(self):
        if self.collected:
            return False
        self.collected = True

        player = self.game.player
        data = ITEMS.get(self.item_key, {})
        itype = data.get("type", "misc")

        if self.item_key == "crystal":
            player.crystals += self.qty
        else:
            existing = next(
                (it for it in player.inventory if it.get("id") == self.item_key),
                None,
            )
            if existing and data.get("stackable"):
                existing["qty"] = existing.get("qty", 1) + self.qty
            else:
                inv_item = make_inv_item(self.item_key, self.qty)
                inv_item["icon"] = _draw_item_icon(self.item_key, 32)
                player.inventory.append(inv_item)

        self.tilemap.items.remove(self)
        return True

    def update(self, dt):
        self._bob_t += dt
        import math
        self.rect.y = int(self._base_y + math.sin(self._bob_t * 3.0) * 4)
        if self.rect.colliderect(self.game.player.rect):
            self.collect()
