import pygame

class Fadeout:
    def __init__(self, duration=1, color=(0, 0, 0)):
        self.duration = duration
        self.color = color
        self.opacity = 0

    def draw(self, screen):
        if self.opacity < 255:
            self.opacity += 255 / (self.duration * 60)
            if self.opacity > 255:
                self.opacity = 255
        overlay = pygame.Surface((screen.get_width(), screen.get_height()))
        overlay.fill(self.color)
        overlay.set_alpha(int(self.opacity))
        screen.blit(overlay, (0, 0))