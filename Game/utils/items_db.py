"""Central item definitions and crafting recipes for Raven."""

import pygame

ITEMS = {
    "crystal": {
        "name": "Cristal",
        "desc": "Un fragmento de cristal mágico. Combina 5 con una Espada para forjar el Tetrahaxal.",
        "type": "material",
        "stackable": True,
        "color": (100, 200, 255),
        "damage": 0,
    },
    "sword": {
        "name": "Espada",
        "desc": "Una espada de hierro básica. Equípala para hacer 1 de daño por golpe.",
        "type": "weapon",
        "stackable": False,
        "color": (180, 180, 210),
        "damage": 1,
    },
    "tetrahaxal": {
        "name": "Tetrahaxal",
        "desc": "Una hoja encantada de poder ancestral. Hace 2 de daño por golpe.",
        "type": "weapon",
        "stackable": False,
        "color": (255, 160, 60),
        "damage": 2,
    },
    "wrench": {
        "name": "Llave Inglesa",
        "desc": "Una pesada llave inglesa de hierro. Útil para abrir cosas a la fuerza.",
        "type": "tool",
        "stackable": False,
        "color": (190, 155, 60),
        "damage": 0,
    },
    "chest": {
        "name": "Cofre",
        "desc": "Un pequeño cofre cerrado. Combínalo con una Llave Inglesa para obtener una Llave.",
        "type": "tool",
        "stackable": False,
        "color": (150, 100, 45),
        "damage": 0,
    },
    "key": {
        "name": "Llave",
        "desc": "Una llave maestra fabricada con un cofre y una llave inglesa.",
        "type": "tool",
        "stackable": False,
        "color": (220, 200, 70),
        "damage": 0,
    },
}

RECIPES = [
    {
        "result": "tetrahaxal",
        "qty": 1,
        "ingredients": {"crystal": 5, "sword": 1},
        "label": "5 Cristales + Espada  →  Tetrahaxal",
    },
    {
        "result": "key",
        "qty": 1,
        "ingredients": {"wrench": 1, "chest": 1},
        "label": "Llave Inglesa + Cofre  →  Llave",
    },
]


def make_inv_item(key: str, qty: int = 1) -> dict:
    """Return an inventory dict for the named item key."""
    data = ITEMS.get(key, {})
    return {
        "id":   key,
        "name": data.get("name", key.capitalize()),
        "desc": data.get("desc", ""),
        "qty":  qty,
        "type": data.get("type", "misc"),
        "color": data.get("color", (160, 160, 160)),
        "damage": data.get("damage", 0),
        "icon": None,
    }


_TEXTURE_FILES = {
    "sword": "metal_sword.png",
    "tetrahaxal": "tetrahaxal_sword.png",
    "wrench": "wrench.png",
    "chest": "chest_only_unlocked_by_wrench.png",
    "key": "key.png",
}

_TEXTURE_BASE: dict[str, pygame.Surface | None] | None = None
_SCALED_CACHE: dict[tuple[str, int], pygame.Surface] = {}


def _load_base_texture(filename: str) -> pygame.Surface | None:
    """Load (and cache) a raw item texture from Game/assets/items/."""
    import os
    global _TEXTURE_BASE
    if _TEXTURE_BASE is None:
        _TEXTURE_BASE = {}
    if filename not in _TEXTURE_BASE:
        path = os.path.join("Game", "assets", "items", filename)
        try:
            img = pygame.image.load(path)
            try:
                img = img.convert_alpha()
            except pygame.error:
                pass
            _TEXTURE_BASE[filename] = img
        except (pygame.error, FileNotFoundError):
            _TEXTURE_BASE[filename] = None
    return _TEXTURE_BASE[filename]


def _draw_item_icon(key: str, size: int) -> pygame.Surface:
    """Return an icon surface for an item.

    Uses a real PNG texture from Game/assets/items/ when one is registered
    for the key (sword, tetrahaxal, wrench, chest, key); falls back to the
    procedural drawing for items without a texture (e.g. crystal).
    """
    cache_key = (key, int(size))
    cached = _SCALED_CACHE.get(cache_key)
    if cached is not None:
        return cached

    tex_file = _TEXTURE_FILES.get(key)
    if tex_file is not None:
        base = _load_base_texture(tex_file)
        if base is not None:
            scaled = pygame.transform.scale(base, (size, size))
            _SCALED_CACHE[cache_key] = scaled
            return scaled


    data = ITEMS.get(key, {})
    color = data.get("color", (160, 160, 160))
    surf = pygame.Surface((size, size), pygame.SRCALPHA)

    itype = data.get("type", "misc")
    if itype == "weapon":
        pygame.draw.rect(surf, color, (size // 2 - 2, 4, 4, size - 8), border_radius=1)
        pygame.draw.rect(surf, color, (4, size // 2 - 2, size - 8, 4), border_radius=1)
        tip_col = tuple(min(255, c + 60) for c in color)
        pygame.draw.polygon(surf, tip_col, [
            (size // 2, 2),
            (size // 2 - 3, size // 2),
            (size // 2 + 3, size // 2),
        ])
    elif key == "crystal":
        cx, cy = size // 2, size // 2
        r = size // 2 - 3
        pts = []
        import math
        for i in range(6):
            a = math.radians(60 * i - 30)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        pygame.draw.polygon(surf, color, pts)
        inner = tuple(min(255, c + 80) for c in color)
        pygame.draw.polygon(surf, inner, pts, 2)
    elif key == "key":
        pygame.draw.circle(surf, color, (size // 3, size // 2), size // 4)
        pygame.draw.circle(surf, (0, 0, 0, 0), (size // 3, size // 2), size // 4 - 3)
        pygame.draw.rect(surf, color, (size // 3, size // 2 - 3, size // 2, 6))
        pygame.draw.rect(surf, color, (size - 10, size // 2, 4, 6))
        pygame.draw.rect(surf, color, (size - 16, size // 2, 4, 6))
    elif key == "wrench":
        pygame.draw.rect(surf, color, (size // 2 - 3, 4, 6, size - 8), border_radius=3)
        pygame.draw.circle(surf, color, (size // 2, 6), 6)
        pygame.draw.circle(surf, (0, 0, 0, 0), (size // 2, 6), 3)
    elif key == "chest":
        pygame.draw.rect(surf, color, (3, size // 3, size - 6, size // 2), border_radius=2)
        lid_col = tuple(min(255, c + 40) for c in color)
        pygame.draw.rect(surf, lid_col, (3, 3, size - 6, size // 3), border_radius=2)
        lock = (220, 200, 80)
        pygame.draw.circle(surf, lock, (size // 2, size // 2), 4)
    else:
        pygame.draw.rect(surf, color, (4, 4, size - 8, size - 8), border_radius=4)

    return surf
