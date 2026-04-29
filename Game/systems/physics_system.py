from Game.system import System
from Game.components.position import Position
from Game.components.velocity import Velocity

class PhysicsSystem(System):
    def __init__(self, world, tilemaps):
        super().__init__(world)
        self.tilemaps = tilemaps
        self.gravity = 500  # pixels per second squared

    def update(self, dt):
        for entity in self.world.entities:
            pos = entity.get_component(Position)
            vel = entity.get_component(Velocity)
            if pos and vel:
                vel.vy += self.gravity * dt

                pos.x += vel.vx * dt
                pos.y += vel.vy * dt

                self.check_collisions(entity)

    def check_collisions(self, entity):
        pos = entity.get_component(Position)
        vel = entity.get_component(Velocity)
        if not pos or not vel:
            return

        if pos.y > 500:
            pos.y = 500
            vel.vy = 0