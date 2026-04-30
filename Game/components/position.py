import pygame

from Game.component import Component

class Position(Component):
    def __init__(self, x, y):
        super().__init__()
        self.x = x
        self.y = y

    @property
    def pos(self):
        return pygame.math.Vector2(self.x, self.y)

    @pos.setter
    def pos(self, value):
        self.x = value.x
        self.y = value.y
