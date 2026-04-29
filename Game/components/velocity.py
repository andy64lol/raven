import pygame

from Game.component import Component

class Velocity(Component):
    def __init__(self, vx=0, vy=0):
        super().__init__()
        self.vx = vx
        self.vy = vy

    @property
    def vel(self):
        return pygame.math.Vector2(self.vx, self.vy)

    @vel.setter
    def vel(self, value):
        self.vx = value.x
        self.vy = value.y