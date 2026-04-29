import json
import pygame

from Game.Sprites.Enemies.flying_enemy import FlyingEnemy
from Game.Sprites.Enemies.boss import UndeadExecutionerBoss
from Game.utils.config import *
from Game.Sprites.Enemies.enemy import Enemy
from Game.Sprites.Inanimate.chest import Chest
from Game.Sprites.Inanimate.breakable import Breakable
from Game.Sprites.Inanimate.crystal_pickup import CrystalPickup
from Game.Sprites.Inanimate.interact_box import InteractBox
from Game.Sprites.Inanimate.item import Item as ItemDrop
from Game.utils.spritegroup import SpriteGroup

SHAPE_NAMES = [
    "full",
    "slab_top", "slab_bottom", "slab_left", "slab_right",
    "quarter_tl", "quarter_tr", "quarter_bl", "quarter_br",
    "slope_tl", "slope_tr", "slope_bl", "slope_br",
]

_SHAPE_MASK_CACHE = {}
_SHAPE_SUBRECT_CACHE = {}


def get_shape_mask(shape, tile_size):
    """Return a cached SRCALPHA mask Surface (white where tile is visible, transparent elsewhere)
    that can be blitted onto a tile image with BLEND_RGBA_MULT to clip it to the shape."""
    key = (shape, int(tile_size))
    if key in _SHAPE_MASK_CACHE:
        return _SHAPE_MASK_CACHE[key]
    ts = int(tile_size)
    mask = pygame.Surface((ts, ts), pygame.SRCALPHA)
    if shape == "full" or not shape:
        mask.fill((255, 255, 255, 255))
    elif shape == "slab_top":
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, ts, ts // 2))
    elif shape == "slab_bottom":
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, ts // 2, ts, ts - ts // 2))
    elif shape == "slab_left":
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, ts // 2, ts))
    elif shape == "slab_right":
        pygame.draw.rect(mask, (255, 255, 255, 255), (ts // 2, 0, ts - ts // 2, ts))
    elif shape == "quarter_tl":
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, 0, ts // 2, ts // 2))
    elif shape == "quarter_tr":
        pygame.draw.rect(mask, (255, 255, 255, 255), (ts // 2, 0, ts - ts // 2, ts // 2))
    elif shape == "quarter_bl":
        pygame.draw.rect(mask, (255, 255, 255, 255), (0, ts // 2, ts // 2, ts - ts // 2))
    elif shape == "quarter_br":
        pygame.draw.rect(mask, (255, 255, 255, 255), (ts // 2, ts // 2, ts - ts // 2, ts - ts // 2))
    elif shape == "slope_tl":
        pygame.draw.polygon(mask, (255, 255, 255, 255), [(0, 0), (ts, 0), (0, ts)])
    elif shape == "slope_tr":
        pygame.draw.polygon(mask, (255, 255, 255, 255), [(0, 0), (ts, 0), (ts, ts)])
    elif shape == "slope_bl":
        pygame.draw.polygon(mask, (255, 255, 255, 255), [(0, 0), (ts, ts), (0, ts)])
    elif shape == "slope_br":
        pygame.draw.polygon(mask, (255, 255, 255, 255), [(ts, 0), (ts, ts), (0, ts)])
    else:
        mask.fill((255, 255, 255, 255))
    _SHAPE_MASK_CACHE[key] = mask
    return mask


def get_shape_subrects(shape, tile_size):
    """Return a list of (x, y, w, h) tuples (tile-local coords) describing the solid AABBs
    that make up the shape. Slopes are approximated by 4 stacked rectangles."""
    key = (shape, int(tile_size))
    if key in _SHAPE_SUBRECT_CACHE:
        return _SHAPE_SUBRECT_CACHE[key]
    ts = int(tile_size)
    half = ts // 2
    other_half = ts - half  # handle odd tile sizes safely
    rects = []
    if shape == "full" or not shape:
        rects = [(0, 0, ts, ts)]
    elif shape == "slab_top":
        rects = [(0, 0, ts, half)]
    elif shape == "slab_bottom":
        rects = [(0, half, ts, other_half)]
    elif shape == "slab_left":
        rects = [(0, 0, half, ts)]
    elif shape == "slab_right":
        rects = [(half, 0, other_half, ts)]
    elif shape == "quarter_tl":
        rects = [(0, 0, half, half)]
    elif shape == "quarter_tr":
        rects = [(half, 0, other_half, half)]
    elif shape == "quarter_bl":
        rects = [(0, half, half, other_half)]
    elif shape == "quarter_br":
        rects = [(half, half, other_half, other_half)]
    elif shape in ("slope_tl", "slope_tr", "slope_bl", "slope_br"):
        steps = 4
        step_w = ts // steps
        for i in range(steps):
            strip_h = ts - i * (ts // steps)
            if strip_h <= 0:
                continue
            if shape == "slope_br":  # high at right, low at left, solid is below diagonal
                lx = ts - (i + 1) * step_w
                ly = i * (ts // steps)
                rects.append((lx, ly, step_w, ts - ly))
            elif shape == "slope_bl":  # high at left, low at right
                lx = i * step_w
                ly = i * (ts // steps)
                rects.append((lx, ly, step_w, ts - ly))
            elif shape == "slope_tr":  # solid top-right (hangs from ceiling), high right, low left
                lx = ts - (i + 1) * step_w
                rects.append((lx, 0, step_w, strip_h))
            elif shape == "slope_tl":  # solid top-left
                lx = i * step_w
                rects.append((lx, 0, step_w, strip_h))
    else:
        rects = [(0, 0, ts, ts)]
    _SHAPE_SUBRECT_CACHE[key] = rects
    return rects


FLOOR_SLOPE_SHAPES = ("slope_bl", "slope_br")


def slope_floor_y(tile_data, world_x, tile_size):
    """Return the world y-coordinate of the slope surface (top of solid) at
    `world_x`, for tiles whose shape is a floor slope (`slope_bl` / `slope_br`).

    Returns None for non-floor-slope tiles or for x outside the tile."""
    shape = tile_data.get('shape', 'full')
    if shape not in FLOOR_SLOPE_SHAPES:
        return None
    ts = int(tile_size)
    tile_left = tile_data['x'] * ts
    tile_top = tile_data['y'] * ts
    local_x = world_x - tile_left
    if local_x < 0:
        local_x = 0
    elif local_x > ts:
        local_x = ts
    if shape == "slope_bl":
        local_y = local_x
    else:  # slope_br — ◢ — high at right, low at left. surface_y_local(x) = ts - x
        local_y = ts - local_x
    return tile_top + local_y


AUTOTILE_MAP = {
    tuple(sorted([(1, 0), (0, 1)])): 0,
    tuple(sorted([(1, 0), (0, 1), (-1, 0)])): 1,
    tuple(sorted([(-1, 0), (0, 1)])): 2,
    tuple(sorted([(-1, 0), (0, -1), (0, 1)])): 3,
    tuple(sorted([(-1, 0), (0, -1)])): 4,
    tuple(sorted([(-1, 0), (0, -1), (1, 0)])): 5,
    tuple(sorted([(1, 0), (0, -1)])): 6,
    tuple(sorted([(1, 0), (0, -1), (0, 1)])): 7,
    tuple(sorted([(1, 0), (-1, 0), (0, 1), (0, -1)])): 8
}

NEIGHBOR_OFFSET = [(-1, 0), (-1, -1), (0, -1), (1, -1), (1, 0), (0, 0), (-1, 1), (0, 1), (1, 1)]
PHYSICS_TILES = ['solid']

scale_sizing = {
    "cave": {
        "platform": {
            "0": (54, 48),
            "1": (96, 24),
            "2": (154, 48),
            "3": (48, 24),
            "4": (24, 24),
            "5": (48, 24),
            "6": (24, 24),
            "7": (48, 24),
            "8": (48, 48),
        },
    },
    "mossy": {
        "platform": {
            "0": (48, 48),
            "1": (96, 24),
            "2": (144, 48),
            "3": (48, 24),
            "4": (24, 24),
            "5": (48, 24),
            "6": (24, 24),
            "7": (48, 24),
            "8": (48, 48),
        },
    }
}

class TileMap:
    def __init__(self, game, tile_size=48, pos=(0, 0), rendered=False, overlay=None):
        self.game = game
        self.tile_size = tile_size
        self.tile_map = {}
        self._tiles_by_xy = {}
        self._tiles_by_z = {}
        self._scaled_tile_cache = {}
        self._overlay_surface = None
        self.off_grid_tiles = []
        self.pos = pygame.math.Vector2(*pos)
        self.rendered = rendered

        self.sensors = {}
        self.enemies = SpriteGroup()
        self.crystals = SpriteGroup()
        self.items = SpriteGroup()
        self.chests = SpriteGroup()
        self.breakables = SpriteGroup()
        self.crystal_pickups = SpriteGroup()
        self.interact_boxes = SpriteGroup()

        self.overlay = overlay

        self.width = 0
        self.height = 0
        self.tile_size = 0

        self.spawnpoint = None

    def _register_tile(self, tile):
        """Insert/replace `tile` in tile_map and the (x,y) index.

        The tile's own 'x', 'y', and 'z' fields determine its key; if a tile
        already exists on the SAME (x, y, z) it is replaced (same-layer
        overwrite is intentional). Tiles on different z layers coexist."""
        x = int(tile['x'])
        y = int(tile['y'])
        z = int(tile.get('z', 1))
        self.tile_map[(x, y, z)] = tile
        self._tiles_by_xy.setdefault((x, y), {})[z] = tile
        self._tiles_by_z.setdefault(z, {})[(x, y, z)] = tile

    def _unregister_tile(self, x, y, z):
        x = int(x); y = int(y); z = int(z)
        self.tile_map.pop((x, y, z), None)
        cell = self._tiles_by_xy.get((x, y))
        if cell is not None:
            cell.pop(z, None)
            if not cell:
                self._tiles_by_xy.pop((x, y), None)
        layer = self._tiles_by_z.get(z)
        if layer is not None:
            layer.pop((x, y, z), None)
            if not layer:
                self._tiles_by_z.pop(z, None)

    def get_tiles_at(self, x, y):
        """Return list of tile dicts at cell (x, y) across all z layers."""
        return list(self._tiles_by_xy.get((int(x), int(y)), {}).values())

    def has_tile_at(self, x, y):
        return (int(x), int(y)) in self._tiles_by_xy

    def load_map(self, p):
        with open(p, 'r') as f:
            data = json.load(f)

        self.width = data['width']
        self.height = data['height']
        self.tile_size = data['tile_size']

        sp = data.get('spawnpoint')
        if sp and len(sp) == 2:
            self.spawnpoint = (int(sp[0]), int(sp[1]))

        for layer in data['layers']:
            if layer['type'] == 'breakables':
                for breakable in layer['data']:
                    self.breakables.append(Breakable(image=self.game.assets[data['environment']][breakable["type"]].get_images_list()[breakable["variant"]], pos=(int(breakable['x']) * self.tile_size + self.pos.x * self.tile_size, int(breakable['y']) * self.tile_size + self.pos.y * self.tile_size), tilemap=self, health=3, id=breakable.get("id"), properties=breakable.get("properties", [])))

            if layer['type'] == 'chests':
                for chest in layer['data']:
                    self.chests.append(Chest(pos=(int(chest['x']) * self.tile_size + self.pos.x * self.tile_size, int(chest['y']) * self.tile_size + self.pos.y * self.tile_size), game=self.game, tilemap=self, contains=chest["contains"]))

            if layer['type'] == 'crystal_pickups':
                for cp in layer['data']:
                    raw_gx = int(cp['x'])
                    raw_gy = int(cp['y'])
                    pos = (raw_gx * self.tile_size + self.pos.x * self.tile_size,
                           raw_gy * self.tile_size + self.pos.y * self.tile_size)
                    pickup = CrystalPickup(pos=pos, game=self.game, tilemap=self,
                                           value=int(cp.get('value', 1)))
                    pickup._editor_grid_pos = (raw_gx, raw_gy)
                    self.crystal_pickups.append(pickup)

            if layer['type'] == 'interact_boxes':
                for ib in layer['data']:
                    raw_gx = int(ib['x'])
                    raw_gy = int(ib['y'])
                    pos = (raw_gx * self.tile_size + self.pos.x * self.tile_size,
                           raw_gy * self.tile_size + self.pos.y * self.tile_size)
                    box = InteractBox(pos=pos, game=self.game, tilemap=self,
                                      reward=int(ib.get('reward', 5)))
                    box._editor_grid_pos = (raw_gx, raw_gy)
                    self.interact_boxes.append(box)

            if layer['type'] == 'item_drops':
                for entry in layer['data']:
                    raw_gx = int(entry['x'])
                    raw_gy = int(entry['y'])
                    ts = self.tile_size
                    world_x = raw_gx * ts + self.pos.x * ts + ts // 2
                    world_y = raw_gy * ts + self.pos.y * ts + ts // 2
                    item_key = entry.get('item_key', 'crystal')
                    drop = ItemDrop(pos=(world_x, world_y), game=self.game,
                                    tilemap=self, item_key=item_key, qty=1)
                    drop._editor_grid_pos = (raw_gx, raw_gy)
                    drop._is_placed = True
                    self.items.append(drop)

            if layer['type'] == 'enemies':
                for enemy in layer['data']:
                    props = enemy.get("properties", []) or []
                    drop = enemy.get("drop", 0)
                    raw_gx = int(enemy['x'])
                    raw_gy = int(enemy['y'])
                    enemy_pos = (raw_gx * self.tile_size + self.pos.x * self.tile_size,
                                 raw_gy * self.tile_size + self.pos.y * self.tile_size)
                    kind_label = enemy.get("type") or ""
                    is_boss = "boss" in props or kind_label == "boss"
                    is_flying = "flying" in props or kind_label == "flying"
                    if is_boss:
                        new_enemy = UndeadExecutionerBoss(
                            game=self.game, pos=enemy_pos,
                            tilemap=self, tilemaps=[self], drop=drop or 15,
                        )
                    elif is_flying:
                        new_enemy = FlyingEnemy(
                            pos=enemy_pos, game=self.game, tilemaps=[self], tilemap=self,
                            move_axis=pygame.Vector2(*enemy.get("move_axis", (1, 0))),
                            drop=drop,
                        )
                    else:
                        new_enemy = Enemy(pos=enemy_pos, game=self.game, tilemap=self, drop=drop)
                    new_enemy._editor_grid_pos = (raw_gx, raw_gy)
                    self.enemies.append(new_enemy)

            if layer['type'] == 'sensor_layer':
                for sensor in layer['data']:
                    sensor_id = sensor["id"]
                    if sensor_id is not None:
                        self.sensors[sensor_id] = {
                            "type": sensor['type'],
                            'x': float(sensor['x']),
                            'y': float(sensor['y']),
                            'w': float(sensor['w']),
                            'h': float(sensor['h']),
                            'properties': sensor.get('properties', []),
                            'triggered': False,
                            "id": sensor_id
                        }

            if layer['type'] == 'tilelayer':
                for tile in layer['data']:
                    props = tile.get("properties", [])
                    if "repeat" in props:
                        tile_w = tile.get("w", 1)
                        tile_h = tile.get("h", 1)
                        for x in range(tile_w):
                            for y in range(tile_h):
                                should_render = True
                                if "alternate" in props:
                                    should_render = (x & int(tile.get("alternate", 0))) == 0

                                world_x = int(tile['x'] + x)
                                world_y = int(tile['y'] + y)
                                tile_variant = tile.get("variant")

                                if should_render:
                                    render_cut = tile.get("render_cut", [0])
                                    self._register_tile({
                                        'x': world_x,
                                        'y': world_y,
                                        'z': int(tile['z']),
                                        'environment': data['environment'],
                                        'type': tile["type"],
                                        'variant': tile_variant,
                                        'properties': tile["properties"]
                                    })
                                else:
                                    self._register_tile({
                                        'x': world_x,
                                        'y': world_y,
                                        'z': int(tile['z']),
                                        'environment': data['environment'],
                                        'type': tile["type"],
                                        'variant': None,
                                        'properties': tile["properties"]
                                    })

                                if tile_variant is None:
                                    self._register_tile({
                                        'x': world_x,
                                        'y': world_y,
                                        'z': int(tile['z']),
                                        'environment': data['environment'],
                                        'type': tile["type"],
                                        'variant': None,
                                        'properties': tile["properties"]
                                    })

                                if "dark" in tile["properties"] and should_render:
                                    depth = int(tile.get("dark_depth", 0))
                                    try:
                                        solid = int(tile.get("solid_depth", depth))
                                    except (ValueError, TypeError):
                                        solid = depth
                                    if solid <= depth:
                                        for y1 in range(depth):
                                            tile_x = int(tile['x'] + x)
                                            tile_y = int(tile['y'] + y1)
                                            if not self.has_tile_at(tile_x, tile_y):
                                                if y1 <= solid:
                                                    self._register_tile({
                                                        'x': tile_x,
                                                        'y': tile_y,
                                                        'z': int(tile['z']),
                                                        'environment': data['environment'],
                                                        'type': tile["type"],
                                                        'variant': "dark",
                                                        'properties': ["solid"],
                                                    })
                                                else:
                                                    self._register_tile({
                                                        'x': tile_x,
                                                        'y': tile_y,
                                                        'z': int(tile['z']),
                                                        'environment': data['environment'],
                                                        'type': tile["type"],
                                                        'variant': "dark",
                                                        'properties': [],
                                                    })
                                    else:
                                        for y1 in range(solid):
                                            tile_x = int(tile['x'] + x)
                                            tile_y = int(tile['y'] + y1)
                                            if not self.has_tile_at(tile_x, tile_y):
                                                if y1 < solid:
                                                    self._register_tile({
                                                        'x': tile_x,
                                                        'y': tile_y,
                                                        'z': int(tile['z']),
                                                        'environment': data['environment'],
                                                        'type': tile["type"],
                                                        'variant': None,
                                                        'properties': ["solid"],
                                                    })

                                if tile.get("solid_depth") and "dark_depth" not in tile.get("properties", []):
                                    solid = int(tile.get("solid_depth", 0))
                                    for y1 in range(solid):
                                        tile_x = int(tile['x'] + x)
                                        tile_y = int(tile['y'] + y1)
                                        if not self.has_tile_at(tile_x, tile_y):
                                            if y1 < solid:
                                                self._register_tile({
                                                    'x': tile_x,
                                                    'y': tile_y,
                                                    'z': int(tile['z']),
                                                    'environment': data['environment'],
                                                    'type': tile["type"],
                                                    'variant': None,
                                                    'properties': ["solid"],
                                                })

                    else:
                        tx, ty, tz = tile['x'], tile['y'], tile['z']
                        self._register_tile({
                            'x': int(tx),
                            'y': int(ty),
                            'z': int(tz),
                            'environment': data['environment'],
                            'type': tile["type"],
                            'variant': tile.get("variant"),
                            'properties': tile["properties"],
                            'shape': tile.get("shape", "full"),
                        })

        for pos, tile in self.tile_map.items():
            if 'solid' in tile.get('properties', []):
                pass

        for tile in self.tile_map.values():
            tile['x'] += int(self.pos.x)
            tile['y'] += int(self.pos.y)

        shifted = list(self.tile_map.values())
        self.tile_map.clear()
        self._tiles_by_xy.clear()
        self._tiles_by_z.clear()
        for t in shifted:
            self._register_tile(t)

        for sensor in self.sensors.values():
            sensor['x'] += int(self.pos.x)
            sensor['y'] += int(self.pos.y)

    def get_tiles_around(self, pos):
        x, y = pos
        grid_x = x // self.tile_size
        grid_y = y // self.tile_size

        tiles = {}
        for dx, dy in NEIGHBOR_OFFSET:
            picked = None
            for cand in self.get_tiles_at(grid_x + dx, grid_y + dy):
                if cand.get('variant') is None:
                    continue
                if 'solid' in cand.get('properties', []):
                    picked = cand
                    break
            tiles[(dx, dy)] = picked
        return tiles

    def _visible_cell_range(self, camera_offset, surface):
        """Return inclusive (x_min, y_min, x_max, y_max) tile cell bounds
        currently visible on ``surface`` with ``camera_offset``. One tile of
        slack is added on each side so partially-visible tiles still draw."""
        ts = self.tile_size or 1
        sw = surface.get_width()
        sh = surface.get_height()
        x_min = int(camera_offset.x // ts) - 1
        y_min = int(camera_offset.y // ts) - 1
        x_max = int((camera_offset.x + sw) // ts) + 1
        y_max = int((camera_offset.y + sh) // ts) + 1
        return x_min, y_min, x_max, y_max

    def _get_scaled_tile_image(self, env, ttype, variant):
        """Return the (cached) scaled image for a tile descriptor, or None.
        Caches per (env, type, variant) so pygame.transform.scale fires once
        per unique tile, not once per tile per frame."""
        key = (env, ttype, variant)
        cached = self._scaled_tile_cache.get(key)
        if cached is not None:
            return cached
        try:
            img = self.game.assets[env][ttype].get_images_list()[variant]
        except (KeyError, IndexError, TypeError):
            return None
        if img is None:
            return None
        try:
            target = scale_sizing[env][ttype].get(str(variant), (self.tile_size, self.tile_size))
        except (TypeError, KeyError):
            target = (self.tile_size, self.tile_size)
        scaled = pygame.transform.scale(img, target)
        self._scaled_tile_cache[key] = scaled
        return scaled

    def render_supports(self, surface, camera_offset):
        """Draw chests, items, breakables, dark fills, and debug aids that are NOT tiles."""
        camera_offset = pygame.math.Vector2(camera_offset)
        ts = self.tile_size
        x_min, y_min, x_max, y_max = self._visible_cell_range(camera_offset, surface)
        for cy in range(y_min, y_max + 1):
            for cx in range(x_min, x_max + 1):
                cell = self._tiles_by_xy.get((cx, cy))
                if not cell:
                    continue
                for tile in cell.values():
                    if tile.get("variant") == "dark" or "dark" in tile.get("properties", []):
                        x = cx * ts - camera_offset.x
                        y = cy * ts - camera_offset.y
                        pygame.draw.rect(surface, (0, 0, 0), (x, y, ts, ts))
                        break  # one dark fill per cell is enough

        self.chests.draw(surface, camera_offset)
        self.breakables.draw(surface, (camera_offset.x, camera_offset.y))
        self.crystal_pickups.draw(surface, (camera_offset.x, camera_offset.y))
        self.interact_boxes.draw(surface, (camera_offset.x, camera_offset.y))

    def render_items(self, surface, camera_offset):
        """Draw world-space item drops on top of everything else."""
        self.items.draw(surface, (camera_offset.x, camera_offset.y))

    def render_tiles(self, surface, camera_offset, layer_id=None):
        """Draw only the tiles belonging to a specific layer id (`z``).
        Pass ``layer_id=None`` to render every layer (legacy behavior).

        Optimizations:
        - Iterate the per-z bucket so a single layer's render skips unrelated
          tiles entirely (no per-frame full-map sort).
        - Viewport-cull: skip any tile whose cell isn't on screen.
        - Reuse pre-scaled tile images via ``_get_scaled_tile_image``.
        """
        camera_offset = pygame.math.Vector2(camera_offset)
        ts = self.tile_size
        x_min, y_min, x_max, y_max = self._visible_cell_range(camera_offset, surface)

        if layer_id is not None:
            layers_iter = [self._tiles_by_z.get(layer_id, {})]
        else:
            layers_iter = [self._tiles_by_z[k] for k in sorted(self._tiles_by_z)]

        for layer in layers_iter:
            for tile in layer.values():
                tx = tile['x']; ty = tile['y']
                if tx < x_min or tx > x_max or ty < y_min or ty > y_max:
                    continue
                variant = tile.get("variant")
                if variant is None or variant == "dark":
                    continue
                try:
                    variant_int = int(variant)
                except (TypeError, ValueError):
                    continue
                img = self._get_scaled_tile_image(
                    tile.get('environment'), tile.get('type'), variant_int
                )
                if img is None:
                    continue
                screen_pos = (
                    int(tx * ts - camera_offset.x),
                    int(ty * ts - camera_offset.y),
                )
                surface.blit(img, screen_pos)

    def render_overlays(self, surface, camera_offset):
        """Crystals, debug rects, sensors, image overlay, etc.

        The hitbox/label debug pass is viewport-culled and only walks tiles
        when debug rendering is actually enabled. The whole-map decorative
        ``self.overlay`` image is loaded and scaled exactly once and cached
        on ``self._overlay_surface`` (it used to be reloaded from disk on
        every frame)."""
        camera_offset = pygame.math.Vector2(camera_offset)
        from Game.utils.config import get_config
        config = get_config()
        ts = self.tile_size

        show_solid_hitboxes = (
            getattr(self.game, "debug_mode", False)
            or config.get("debug", {}).get("show_platform_hitboxes", False)
        )
        if show_solid_hitboxes:
            layer_font = None
            try:
                layer_font = self.game.fonts.get("Arial")
            except AttributeError:
                layer_font = None
            x_min, y_min, x_max, y_max = self._visible_cell_range(camera_offset, surface)
            for cy in range(y_min, y_max + 1):
                for cx in range(x_min, x_max + 1):
                    cell = self._tiles_by_xy.get((cx, cy))
                    if not cell:
                        continue
                    for tile in cell.values():
                        if 'solid' not in tile.get('properties', []):
                            continue
                        screen_pos = (
                            int(cx * ts - camera_offset.x),
                            int(cy * ts - camera_offset.y),
                        )
                        subs = list(self.get_solid_subrects(tile))
                        for sub in subs:
                            debug_rect = pygame.Rect(
                                int(sub.x - camera_offset.x),
                                int(sub.y - camera_offset.y),
                                sub.width,
                                sub.height,
                            )
                            pygame.draw.rect(surface, (0, 255, 0), debug_rect, 1)
                        if layer_font is not None and subs:
                            label = f"L{tile.get('z', 1)}"
                            label_surf = layer_font.render(label, True, (0, 255, 0))
                            bg = pygame.Surface(label_surf.get_size(), pygame.SRCALPHA)
                            bg.fill((0, 0, 0, 160))
                            label_pos = (screen_pos[0] + 1, screen_pos[1] + 1)
                            surface.blit(bg, label_pos)
                            surface.blit(label_surf, label_pos)

        if config.get("debug", {}).get("show_sensors", False):
            for sensor in self.sensors.values():
                rect = pygame.Rect(
                    sensor["x"] * ts - camera_offset.x,
                    sensor["y"] * ts - camera_offset.y,
                    sensor["w"] * ts,
                    sensor["h"] * ts,
                )
                pygame.draw.rect(surface, (255, 0, 0), rect, 1)

        self.crystals.draw(surface, (camera_offset.x, camera_offset.y))

        if self.overlay and self.rendered:
            if self._overlay_surface is None:
                img = pygame.image.load(self.overlay).convert_alpha()
                self._overlay_surface = pygame.transform.scale(
                    img, (self.width * ts, self.height * ts)
                )
            surface.blit(self._overlay_surface, (-camera_offset.x, -camera_offset.y))

    def render(self, surface, camera_offset, layer=None):
        self.render_supports(surface, camera_offset)
        self.enemies.draw(surface, (pygame.math.Vector2(camera_offset).x, pygame.math.Vector2(camera_offset).y))
        self.render_tiles(surface, camera_offset, layer_id=layer)
        self.render_overlays(surface, camera_offset)

    def is_solid(self, pos, offset):
        x = pos[0] // self.tile_size + offset[0]
        y = pos[1] // self.tile_size + offset[1]
        for t in self.get_tiles_at(x, y):
            if "solid" in t.get("properties", []):
                return True
        return False

    def place_tile(self, grid_x, grid_y, tile_data):
        """Place or replace a tile at grid coordinates on its own z layer.

        Tiles on different z layers coexist in the same cell; placing on the
        same (x, y, z) replaces only that layer's tile."""
        self._register_tile({
            'x': int(grid_x),
            'y': int(grid_y),
            'z': int(tile_data.get('z', 5)),
            'environment': tile_data.get('environment', 'cave'),
            'type': tile_data.get('type', 'platform'),
            'variant': tile_data.get('variant', 0),
            'properties': tile_data.get('properties', ['solid']),
            'shape': tile_data.get('shape', 'full'),
        })

    def get_solid_subrects(self, tile_data):
        """Yield world-space pygame.Rect objects covering the solid sub-areas of a tile,
        respecting its shape. Returns the full-tile rect for shape=='full'."""
        ts = self.tile_size
        base_x = tile_data['x'] * ts
        base_y = tile_data['y'] * ts
        shape = tile_data.get('shape', 'full')
        for (lx, ly, lw, lh) in get_shape_subrects(shape, ts):
            yield pygame.Rect(base_x + lx, base_y + ly, lw, lh)

    def place_enemy(self, grid_x, grid_y, kind="ground", move_axis=(0, 0), drop=0):
        """Spawn a fresh enemy at a grid cell from the editor.

        ``grid_x``/``grid_y`` are unshifted (the same convention used by
        ``place_tile`` and ``save_map``); we apply ``self.pos`` here so the
        new sprite ends up at the same world coordinates a loaded enemy
        would land at. ``kind`` is one of ``"ground"``, ``"flying"``, or
        ``"boss"``."""
        gx = int(grid_x)
        gy = int(grid_y)
        px = (gx + int(self.pos.x)) * self.tile_size
        py = (gy + int(self.pos.y)) * self.tile_size
        if kind == "flying":
            enemy = FlyingEnemy(
                pos=(px, py), game=self.game, tilemaps=[self], tilemap=self,
                move_axis=pygame.Vector2(*move_axis), drop=drop,
            )
        elif kind == "boss":
            enemy = UndeadExecutionerBoss(
                game=self.game, pos=(px, py),
                tilemap=self, tilemaps=[self], drop=drop or 15,
            )
        else:
            enemy = Enemy(pos=(px, py), game=self.game, tilemap=self, drop=drop)
        enemy._editor_grid_pos = (gx, gy)
        self.enemies.append(enemy)
        return enemy

    def place_crystal_pickup(self, grid_x, grid_y, value=1):
        """Spawn a collectible crystal at a grid cell from the editor.

        Uses the same top-left-of-cell convention as ``place_enemy`` and the
        load path so that placing → saving → reloading lands the sprite at
        the exact same pixel position (no visual jump)."""
        gx = int(grid_x); gy = int(grid_y)
        ts = self.tile_size
        world_x = (gx + int(self.pos.x)) * ts
        world_y = (gy + int(self.pos.y)) * ts
        pickup = CrystalPickup(pos=(world_x, world_y), game=self.game,
                               tilemap=self, value=int(value))
        pickup._editor_grid_pos = (gx, gy)
        self.crystal_pickups.append(pickup)
        return pickup

    def place_interact_box(self, grid_x, grid_y, reward=5):
        """Spawn an interactable box at a grid cell from the editor.

        Uses the same top-left-of-cell convention as ``place_enemy`` and the
        load path so editor placement is stable across save/reload."""
        gx = int(grid_x); gy = int(grid_y)
        ts = self.tile_size
        world_x = (gx + int(self.pos.x)) * ts
        world_y = (gy + int(self.pos.y)) * ts
        box = InteractBox(pos=(world_x, world_y), game=self.game,
                          tilemap=self, reward=int(reward))
        box._editor_grid_pos = (gx, gy)
        self.interact_boxes.append(box)
        return box

    def place_item_drop(self, grid_x: int, grid_y: int, item_key: str):
        """Spawn a persistent world-space item drop at a grid cell from the editor."""
        gx = int(grid_x); gy = int(grid_y)
        ts = self.tile_size
        world_x = (gx + int(self.pos.x)) * ts + ts // 2
        world_y = (gy + int(self.pos.y)) * ts + ts // 2
        drop = ItemDrop(pos=(world_x, world_y), game=self.game,
                        tilemap=self, item_key=item_key, qty=1)
        drop._editor_grid_pos = (gx, gy)
        drop._is_placed = True
        self.items.append(drop)
        return drop

    def erase_object_near(self, grid_x, grid_y):
        """Remove crystal pickups, interact boxes, and placed item drops whose
        origin tile equals (grid_x, grid_y). Returns the number removed."""
        target = (int(grid_x), int(grid_y))
        removed = 0
        for group in (self.crystal_pickups, self.interact_boxes, self.items):
            to_remove = []
            for obj in group.sprite_dict.values():
                gp = getattr(obj, "_editor_grid_pos", None)
                if gp is None:
                    gp = (
                        obj.rect.x // self.tile_size - int(self.pos.x),
                        obj.rect.y // self.tile_size - int(self.pos.y),
                    )
                if (int(gp[0]), int(gp[1])) == target:
                    to_remove.append(obj)
            if to_remove:
                group.remove(*to_remove)
                removed += len(to_remove)
        return removed

    def erase_enemy_near(self, grid_x, grid_y):
        """Remove the enemy whose current position is closest to the clicked
        grid cell (within 2 tiles). Falls back to matching stored spawn coords
        if nothing is close enough. Returns the number of enemies removed."""
        ts = self.tile_size
        target_wx = (grid_x + 0.5) * ts
        target_wy = (grid_y + 0.5) * ts
        threshold = ts * 2  # accept clicks within 2 tile-widths

        best = None
        best_dist = float("inf")
        for enemy in self.enemies.sprite_dict.values():
            dx = enemy.rect.centerx - target_wx
            dy = enemy.rect.centery - target_wy
            d = (dx * dx + dy * dy) ** 0.5
            if d < best_dist:
                best_dist = d
                best = enemy

        if best_dist > threshold:
            best = None
            for enemy in self.enemies.sprite_dict.values():
                gp = getattr(enemy, "_editor_grid_pos", None)
                if gp is None:
                    continue
                if (int(gp[0]), int(gp[1])) == (int(grid_x), int(grid_y)):
                    best = enemy
                    break

        if best is not None:
            self.enemies.remove(best)
            return 1
        return 0

    def erase_tile(self, grid_x, grid_y, z=None):
        """Remove tile(s) at grid coordinates.

        If `z` is given, removes only the tile on that layer. If `z` is None,
        removes every tile in the cell (legacy behavior)."""
        gx = int(grid_x); gy = int(grid_y)
        if z is None:
            for tz in list(self._tiles_by_xy.get((gx, gy), {}).keys()):
                self._unregister_tile(gx, gy, tz)
        else:
            self._unregister_tile(gx, gy, int(z))

    def save_map(self, path):
        """Save the current tile_map back to a JSON file."""
        tile_layers = {}
        for (gx, gy, _kz), tile in self.tile_map.items():
            z = tile.get('z', 5)
            if z not in tile_layers:
                tile_layers[z] = []
            entry = {
                'x': gx - int(self.pos.x),
                'y': gy - int(self.pos.y),
                'z': z,
                'type': tile['type'],
                'variant': tile['variant'],
                'properties': tile.get('properties', []),
            }
            shape = tile.get('shape', 'full')
            if shape and shape != 'full':
                entry['shape'] = shape
            tile_layers[z].append(entry)

        layers = []
        for z in sorted(tile_layers.keys()):
            layers.append({
                'type': 'tilelayer',
                'name': f'Layer_{z}',
                'data': tile_layers[z]
            })

        sensor_data = []
        for sid, sensor in self.sensors.items():
            sensor_data.append({
                'x': sensor['x'] - int(self.pos.x),
                'y': sensor['y'] - int(self.pos.y),
                'z': 5,
                'w': sensor['w'],
                'h': sensor['h'],
                'id': sensor['id'],
                'type': sensor['type'],
                'properties': sensor.get('properties', []),
                'offset': [0, 0]
            })

        if sensor_data:
            layers.append({
                'type': 'sensor_layer',
                'name': 'Sensors',
                'data': sensor_data
            })

        enemies_data = []
        for enemy in self.enemies.sprite_dict.values():
            if hasattr(enemy, "is_alive") and not enemy.is_alive:
                continue
            gp = getattr(enemy, "_editor_grid_pos", None)
            if gp is None:
                gp = (
                    enemy.rect.x // self.tile_size - int(self.pos.x),
                    enemy.rect.y // self.tile_size - int(self.pos.y),
                )
            attrs = getattr(enemy, "attributes", {}) or {}
            is_boss = bool(attrs.get("boss", False))
            if attrs.get("summon"):
                continue
            is_flying = bool(attrs.get("flying", False))
            kind = "boss" if is_boss else ("flying" if is_flying else "ground")
            props_out = []
            if is_boss:
                props_out.append("boss")
            if is_flying:
                props_out.append("flying")
            entry = {
                'x': int(gp[0]),
                'y': int(gp[1]),
                'z': 5,
                'id': getattr(enemy, "id", None),
                'type': kind,
                'drop': getattr(enemy, "drop", 0),
                'properties': props_out,
            }
            if is_flying:
                ax = getattr(enemy, "move_axis", pygame.Vector2(0, 0))
                entry['move_axis'] = [int(ax.x), int(ax.y)]
            enemies_data.append(entry)

        if enemies_data:
            layers.append({
                'type': 'enemies',
                'name': 'Enemies',
                'data': enemies_data,
            })

        crystal_pickup_data = []
        for cp in self.crystal_pickups.sprite_dict.values():
            gp = getattr(cp, "_editor_grid_pos", None)
            if gp is None:
                gp = (
                    cp.rect.x // self.tile_size - int(self.pos.x),
                    cp.rect.y // self.tile_size - int(self.pos.y),
                )
            crystal_pickup_data.append({
                'x': int(gp[0]),
                'y': int(gp[1]),
                'value': int(getattr(cp, 'value', 1)),
            })
        if crystal_pickup_data:
            layers.append({
                'type': 'crystal_pickups',
                'name': 'CrystalPickups',
                'data': crystal_pickup_data,
            })

        interact_box_data = []
        for box in self.interact_boxes.sprite_dict.values():
            gp = getattr(box, "_editor_grid_pos", None)
            if gp is None:
                gp = (
                    box.rect.x // self.tile_size - int(self.pos.x),
                    box.rect.y // self.tile_size - int(self.pos.y),
                )
            interact_box_data.append({
                'x': int(gp[0]),
                'y': int(gp[1]),
                'reward': int(getattr(box, 'reward', 5)),
            })
        if interact_box_data:
            layers.append({
                'type': 'interact_boxes',
                'name': 'InteractBoxes',
                'data': interact_box_data,
            })

        item_drop_data = []
        for drop in self.items.sprite_dict.values():
            if not getattr(drop, '_is_placed', False):
                continue
            gp = getattr(drop, "_editor_grid_pos", None)
            if gp is None:
                gp = (
                    drop.rect.x // self.tile_size - int(self.pos.x),
                    drop.rect.y // self.tile_size - int(self.pos.y),
                )
            item_drop_data.append({
                'x': int(gp[0]),
                'y': int(gp[1]),
                'item_key': getattr(drop, 'item_key', 'crystal'),
            })
        if item_drop_data:
            layers.append({
                'type': 'item_drops',
                'name': 'ItemDrops',
                'data': item_drop_data,
            })

        data = {
            'width': self.width,
            'height': self.height,
            'tile_size': self.tile_size,
            'environment': getattr(self, '_environment', 'cave'),
            'layers': layers
        }

        if self.spawnpoint is not None:
            data['spawnpoint'] = [int(self.spawnpoint[0]), int(self.spawnpoint[1])]

        for tile in self.tile_map.values():
            if 'environment' in tile:
                data['environment'] = tile['environment']
                break

        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def update(self, dt):
        self.chests.update(dt)
        self.breakables.update(dt)

        player = getattr(self.game, 'player', None)
        rd = getattr(self.game, 'render_distance', None)

        if player is None or rd is None:
            self.items.update(dt)
            self.crystals.update(dt)
            self.crystal_pickups.update(dt)
            self.interact_boxes.update(dt)
        else:
            px, py = player.rect.centerx, player.rect.centery
            rd2 = rd * rd

            for sprite in list(self.items.sprite_dict.values()):
                sx, sy = sprite.rect.centerx, sprite.rect.centery
                if (sx - px) ** 2 + (sy - py) ** 2 <= rd2:
                    sprite.update(dt)

            for sprite in list(self.crystals.sprite_dict.values()):
                sx, sy = sprite.rect.centerx, sprite.rect.centery
                if (sx - px) ** 2 + (sy - py) ** 2 <= rd2:
                    sprite.update(dt)

            for sprite in list(self.crystal_pickups.sprite_dict.values()):
                sx, sy = sprite.rect.centerx, sprite.rect.centery
                if (sx - px) ** 2 + (sy - py) ** 2 <= rd2:
                    sprite.update(dt)

            for sprite in list(self.interact_boxes.sprite_dict.values()):
                sx, sy = sprite.rect.centerx, sprite.rect.centery
                if (sx - px) ** 2 + (sy - py) ** 2 <= rd2:
                    sprite.update(dt)

        for sensor in self.sensors.values():
            if sensor["type"] == "render":
                rect = pygame.Rect(sensor["x"] * self.tile_size,
                                   sensor["y"] * self.tile_size,
                                   sensor["w"] * self.tile_size,
                                   sensor["h"] * self.tile_size)

                player_in_sensor = rect.colliderect(self.game.player.rect)

                for prop in sensor["properties"]:
                    if "render" in prop and not sensor["triggered"] and "derender" not in prop and "toggle_render" not in prop:
                        map_name = prop.split(":")[1]
                        if player_in_sensor:
                            self.game.tilemap_current = map_name
                            self.game.tilemap = self.game.tilemaps[self.game.tilemap_current]
                            self.game.tilemaps[map_name].rendered = True
                            sensor["triggered"] = True

                    if "derender" in prop and not sensor["triggered"]:
                        map_name = prop.split(":")[1]
                        if player_in_sensor:
                            self.game.tilemap_current = map_name
                            self.game.tilemap = self.game.tilemaps[self.game.tilemap_current]
                            self.game.tilemaps[map_name].rendered = False
                            sensor["triggered"] = True

                    if "toggle_render" in prop and not sensor["triggered"]:
                        map_name = prop.split(":")[1]
                        if player_in_sensor:
                            self.game.tilemaps[map_name].rendered = not self.game.tilemaps[map_name].rendered

                            current_found = False
                            for name, tilemap in self.game.tilemaps.items():
                                if tilemap.rendered:
                                    self.game.tilemap_current = name
                                    self.game.tilemap = tilemap
                                    current_found = True
                                    break

                            if not current_found:
                                pass

                            sensor["triggered"] = True

                if sensor["triggered"] and not player_in_sensor:
                    sensor["triggered"] = False
