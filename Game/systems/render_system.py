from Game.system import System
from Game.components.position import Position
from Game.components.sprite import Sprite

class RenderSystem(System):
    def __init__(self, world):
        super().__init__(world)

    def draw(self, surface):
        for entity in self.world.entities:
            pos = entity.get_component(Position)
            sprite = entity.get_component(Sprite)
            if pos and sprite and sprite.image:
                surface.blit(sprite.image, (pos.x, pos.y))