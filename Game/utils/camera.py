import pygame

class Camera:
    def __init__(self, width, height):
        self.offset = pygame.Vector2(0, 0)
        self.width = width
        self.height = height

    def apply(self, entity):
        return pygame.Rect(
            entity.rect.x - self.offset.x,
            entity.rect.y - self.offset.y,
            entity.rect.width,
            entity.rect.height
        )

    def update(self, target):
        self.offset.x = target.rect.centerx - (self.width // 2)
        self.offset.y = target.rect.centery - (self.height // 2)
