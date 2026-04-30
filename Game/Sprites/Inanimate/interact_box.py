import pygame

from Game.Sprites.sprite import Sprite
from Game.Sprites.crystals import Crystal

class InteractBox(Sprite):
    """A wooden crate the player can open with the Z key.

    Stays on the map until interacted with. When the player is overlapping
    it and presses Z, it pops open: spawns a small burst of physics-y
    Crystal sprites the player can collect, and shows a tiny "+N" floater
    above the crate. Persists in the level JSON between sessions.
    """

    SIZE = (32, 32)

    def __init__(self, pos, game, tilemap, reward=5):
        self._closed_image = self._build_image(opened=False)
        self._opened_image = self._build_image(opened=True)
        super().__init__(self._closed_image, pos)
        self.rect = self._closed_image.get_rect(topleft=pos)

        self.game = game
        self.tilemap = tilemap
        self.reward = int(reward)
        self.opened = False
        self._float_text = None
        self._float_t = 0.0
        self.id = f"interact_box_{id(self)}"

        self._editor_grid_pos = None
        if tilemap is not None and getattr(tilemap, "tile_size", 0):
            ts = tilemap.tile_size
            self._editor_grid_pos = (
                int(pos[0] // ts) - int(tilemap.pos.x),
                int(pos[1] // ts) - int(tilemap.pos.y),
            )

    @staticmethod
    def _build_image(opened):
        """Hand-drawn crate art so we don't depend on a shipped asset."""
        w, h = InteractBox.SIZE
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        wood = (139, 90, 43) if not opened else (95, 60, 30)
        wood_dark = (86, 55, 26)
        plank_line = (60, 38, 20)
        rim = (40, 25, 12)

        pygame.draw.rect(surf, wood, (1, 1, w - 2, h - 2))
        pygame.draw.rect(surf, rim, (0, 0, w, h), 2)
        pygame.draw.line(surf, plank_line, (0, h // 2), (w, h // 2), 1)
        pygame.draw.line(surf, plank_line, (w // 2, 0), (w // 2, h), 1)
        pygame.draw.line(surf, wood_dark, (1, h - 2), (w - 2, h - 2), 1)
        pygame.draw.line(surf, wood_dark, (w - 2, 1), (w - 2, h - 2), 1)
        if opened:
            pygame.draw.rect(surf, (25, 15, 5), (4, 4, w - 8, h - 8))
        else:
            font = pygame.font.SysFont("Arial", 12, bold=True)
            z = font.render("Z", True, (255, 220, 120))
            surf.blit(z, z.get_rect(center=(w // 2, h // 2)))
        return surf

    def draw(self, surf, offset=(0, 0)):
        surf.blit(self.image, (self.rect.x - offset[0], self.rect.y - offset[1]))

        if self._float_text is not None:
            tx = self.rect.centerx - self._float_text.get_width() // 2 - offset[0]
            ty = int(self.rect.top - 14 - self._float_t * 18) - offset[1]
            alpha = max(0, 255 - int(self._float_t * 220))
            tinted = self._float_text.copy()
            tinted.set_alpha(alpha)
            surf.blit(tinted, (tx, ty))

    def player_overlapping(self):
        player = getattr(self.game, "player", None)
        if player is None:
            return False
        return self.rect.inflate(8, 8).colliderect(player.rect)

    def interact(self):
        """Called by the game loop when Z is pressed while overlapping."""
        if self.opened:
            return False
        self.opened = True
        self.image = self._opened_image
        self.game.player.crystals += self.reward
        try:
            self._float_text = self.game.fonts["workbench_small"].render(
                f"+{self.reward}", True, (255, 230, 120))
        except Exception:
            self._float_text = None
        self._float_t = 0.0

        if hasattr(self.tilemap, "crystals"):
            for _ in range(min(5, max(1, self.reward // 2))):
                c = Crystal(
                    position=pygame.Vector2(self.rect.center),
                    value=0,
                    game=self.game,
                )
                c.tilemap = self.tilemap
                self.tilemap.crystals.append(c)
        return True

    def update(self, dt):
        if self._float_text is not None:
            self._float_t += dt
            if self._float_t > 1.4:
                self._float_text = None
