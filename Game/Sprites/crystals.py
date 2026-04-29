from Game.utils.utils import *
from Game.Sprites.sprite import PhysicsSprite
import random

class Crystal(PhysicsSprite):
    def __init__(self, position, value, game=None):
        self.size = (16, 16)
        self.original_image = load_image("miscellaneous/crystal.png", size=self.size)
        self.image = self.original_image.copy()

        super().__init__(self.image, position)

        self.position = position
        self.value = value
        self.id = f"crystal_{id(self)}"
        self.collected = False

        self.game = game
        self.tilemap = None

        self.gravity = 20       # px/frame added to vel each frame; vel is in px/sec
        self.friction = -0.1

        self.vel.x = random.uniform(-150, 150)   # px/sec
        self.vel.y = random.uniform(-400, -200)  # px/sec (upward burst)

        self.rotation_angle = 0

    def draw(self, surf, offset=(0, 0)):
        surf.blit(self.image, (self.rect.x - offset[0], self.rect.y - offset[1]))

    def update(self, *args, **kwargs):
        if self.collected:
            return

        super().update(*args, **kwargs)

        if not self.collisions["bottom"] and abs(self.vel.y) > 0.1:
            self.image = pygame.transform.rotate(self.original_image, self.rotation_angle)

        if self.rect.colliderect(self.game.player.rect):
            self.game.player.crystals += self.value
            self.collected = True
            if self.tilemap:
                self.tilemap.crystals.remove(self)
