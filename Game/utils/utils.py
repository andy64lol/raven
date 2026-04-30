import pygame
import os
import json

BASE_IMG_PATH = "Game/assets/"
TILE_SIZE = 48

def load_image(path, colorkey=None, size=None):
    img = pygame.image.load(BASE_IMG_PATH + path)
    if size is not None:
        img = pygame.transform.scale(img, size)
    try:
        img = img.convert_alpha()
    except FileNotFoundError:
        pass
    if colorkey is not None:
        img.set_colorkey(colorkey)
    if "icon_" in path:
        img = pygame.transform.scale(img, (16, 16))
    return img

_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp")

def load_images(path):
    """Load every image file in a directory (sorted, image-extensions only).

    Skips subdirectories and non-image files so callers don't blow up on
    folders like Adobe After Effects auto-save dirs that may sit next to
    the frame PNGs.
    """
    images = []
    full = BASE_IMG_PATH + path
    for img_name in sorted(os.listdir(full)):
        full_path = os.path.join(full, img_name)
        if not os.path.isfile(full_path):
            continue
        if not img_name.lower().endswith(_IMAGE_EXTS):
            continue
        images.append(load_image(path + '/' + str(img_name)))
    return images

class PlantPack:
    """SpriteSheet-compatible wrapper around a folder of plant frames.

    Loads every Nth PNG in the folder so we get a representative animation
    without ballooning memory (plant folders can have 60-90 frames each).
    Exposes ``images`` (dict) and ``get_images_list()`` so it slots into
    code that already speaks the SpriteSheet duck type (like the in-game
    editor palette and the ECS Animation component).
    """

    def __init__(self, folder, every_n=1, max_frames=None):
        self.folder = folder
        full = BASE_IMG_PATH + folder
        files = []
        for f in sorted(os.listdir(full)):
            full_f = os.path.join(full, f)
            if os.path.isfile(full_f) and f.lower().endswith(_IMAGE_EXTS):
                files.append(f)
        files = files[::max(1, int(every_n))]
        if max_frames is not None:
            files = files[:max_frames]
        self.images = {}
        for f in files:
            self.images[f] = load_image(folder + '/' + f)

    def get_images_list(self):
        return list(self.images.values())

def load_json_as_dict(path):
    with open(BASE_IMG_PATH + path, 'r') as f:
        data = json.load(f)
    return data

class SpriteSheet:
    def __init__(self, path, tile_size=None, cut=None, colorkey=None):
        self.images = {}
        self.path = path
        self.tile_size = tile_size
        self.colorkey = colorkey

        self.cut = cut if cut is not None else {"0": (0, 0, 64, 64)}

        if tile_size:
            self.get_images()
        else:
            self.cut_images()

    def get_images(self):
        assert self.tile_size is not None, "get_images() requires tile_size"
        ts = int(self.tile_size)
        base = load_image(self.path, colorkey=self.colorkey)
        rect = base.get_rect()

        for y in range(0, rect.height, ts):
            for x in range(0, rect.width, ts):
                temp = pygame.Surface((ts, ts), flags=pygame.SRCALPHA)
                temp.blit(base, (0, 0), pygame.Rect(x, y, ts, ts))
                self.images[(x, y)] = temp

    def cut_images(self):
        base = load_image(self.path, colorkey=self.colorkey)
        for key, rect_vals in self.cut.items():
            try:
                x, y, w, h = tuple(rect_vals)
            except (TypeError, ValueError):
                continue
            if w > 0 and h > 0:
                temp = pygame.Surface((w, h), flags=pygame.SRCALPHA)
                temp.blit(base, (0, 0), pygame.Rect(x, y, w, h))
                self.images[str(key)] = temp

    def get_images_list(self):
        sprites = []
        for key in self.images.keys():
            sprites.append(self.images[key])
        return sprites

    def get_debug_image(self):
        base = load_image(self.path, colorkey=self.colorkey)
        base_copy = base.copy()
        rect = base_copy.get_rect()
        pygame.draw.rect(base_copy, (255, 0, 0), rect, 4)

        for key, (x, y, w, h) in self.cut.items():
            if w > 0 and h > 0:
                temp_rect = pygame.Rect(x, y, w, h)
                pygame.draw.rect(base_copy, (255, 0, 0), temp_rect, 4)

        return base_copy

class Animation:
    def __init__(self, images, img_dur=5, loop=True):
        self.images = images
        self.loop = loop
        self.img_duration = img_dur
        self.done = False
        self.frame = 0

    def copy(self):
        return Animation(self.images, self.img_duration, self.loop)

    def update(self):
        if self.loop:
            self.frame = (self.frame + 1) % (self.img_duration * len(self.images))
        else:
            self.frame = min(self.frame + 1, self.img_duration * len(self.images))
            if self.frame >= self.img_duration * len(self.images) - 1:
                self.done = True

    def img(self):
        return self.images[int(self.frame / self.img_duration)]
