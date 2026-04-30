import pygame

from Game.component import Component

class Sprite(Component):
    def __init__(self, image=None):
        super().__init__()
        self.image = image
        if self.image:
            self.rect = self.image.get_rect()

    def draw(self, surface, offset=(0, 0)):
        if self.image:
            if hasattr(self, 'rect'):
                surface.blit(self.image, self.rect.topleft - pygame.math.Vector2(offset))
            else:
                surface.blit(self.image, -pygame.math.Vector2(offset))
