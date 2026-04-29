from Game.system import System
from Game.components.animation import Animation
from Game.components.sprite import Sprite

class AnimationSystem(System):
    def __init__(self, world):
        super().__init__(world)

    def update(self, dt):
        for entity in self.world.entities:
            anim = entity.get_component(Animation)
            sprite = entity.get_component(Sprite)
            if anim:
                anim.update(dt)
                if sprite and anim.image:
                    sprite.image = anim.image
                    sprite.rect = sprite.image.get_rect()