from typing import Any
import pygame
from Game.Sprites.sprite import Sprite

class Breakable(Sprite):
    tilemap: Any

    def __init__(self, image, pos=(0, 0), tilemap=None, health=3, id=None, properties=None):
        super().__init__(image, pos)
        self.image = image
        if tilemap is not None and image.get_rect().width > tilemap.tile_size:
            self.image = pygame.transform.scale(image, (tilemap.tile_size, tilemap.tile_size))
        self.rect = self.image.get_rect(topleft=pos)
        self.tilemap = tilemap
        self.health = health
        self.max_health = 3
        self.properties = properties or []

        self.last_damage_time = 0
        self.regen_delay = 5000
        self.regen_rate = 1000
        self.last_regen_time = 0

        if id is not None:
            self.id = id

    def is_solid(self):
        return 'solid' in self.properties

    def update(self, dt=0):
        current_time = pygame.time.get_ticks()

        if self.health < self.max_health:
            time_since_damage = current_time - self.last_damage_time
            if time_since_damage >= self.regen_delay:
                time_since_regen = current_time - self.last_regen_time
                if time_since_regen >= self.regen_rate:
                    self.health += 1
                    self.last_regen_time = current_time
                    if self.health > self.max_health:
                        self.health = self.max_health

    def take_damage(self, amount):
        self.health -= amount
        self.last_damage_time = pygame.time.get_ticks()
        if self.health <= 0:
            self.destroy()

    def destroy(self):
        if self.tilemap and hasattr(self.tilemap, 'breakables'):
            self.tilemap.breakables.remove(self)
