import pygame

from Game.component import Component
from Game.utils.utils import SpriteSheet

class Animation(Component):
    def __init__(self, animations, current="idle"):
        super().__init__()
        self.animations = animations  # dict of name: (spritesheet, frame_duration, loop)
        self.current = current
        self.frame = 0
        self.image = None
        self.update_image()

    def update_image(self):
        if self.current in self.animations:
            spritesheet, frame_duration, loop = self.animations[self.current]
            images = spritesheet.get_images_list()
            if images:
                idx = int(self.frame) % len(images) if loop else min(int(self.frame), len(images) - 1)
                self.image = images[idx]

    def update(self, dt):
        if self.current in self.animations:
            _, frame_duration, _ = self.animations[self.current]
            self.frame += frame_duration / 60 * 60 * dt  # assuming 60 fps
            self.update_image()