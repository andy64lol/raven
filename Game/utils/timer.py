import pygame


class Timer:
    def __init__(self, duration, func=None):
        self.duration_ms = int(duration * 1000)
        self.func = func
        self.start_time = 0
        self.active = False

    def activate(self):
        self.active = True
        self.start_time = pygame.time.get_ticks()

    def deactivate(self):
        self.active = False
        self.start_time = 0

    def finished(self):
        if not self.active:
            return False
        return pygame.time.get_ticks() - self.start_time >= self.duration_ms

    def update(self):
        if not self.active:
            return False
        if self.finished():
            if self.func:
                self.func()
            self.deactivate()
            return True
        return False
