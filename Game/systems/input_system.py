import pygame

from Game.system import System
from Game.components.velocity import Velocity
from Game.components.animation import Animation

class InputSystem(System):
    def __init__(self, world):
        super().__init__(world)
        self.keys = pygame.key.get_pressed()

    def update(self, dt):
        self.keys = pygame.key.get_pressed()
        for entity in self.world.entities:
            vel = entity.get_component(Velocity)
            anim = entity.get_component(Animation)
            if vel:
                vel.vx = 0
                moving = False
                if self.keys[pygame.K_a]:
                    vel.vx = -200
                    moving = True
                if self.keys[pygame.K_d]:
                    vel.vx = 200
                    moving = True
                if self.keys[pygame.K_w] and vel.vy == 0:  # Only jump if on ground
                    vel.vy = -300

                if anim:
                    if vel.vy < 0:
                        anim.current = "jump"
                    elif vel.vy > 0:
                        anim.current = "fall"
                    elif moving:
                        anim.current = "run"
                    else:
                        anim.current = "idle"