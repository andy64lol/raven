import os
import pygame.font

from Game.Sprites.player import Player

from Game.utils.camera import Camera
from Game.utils.config import get_config
from Game.utils.utils import *
from Game.utils.spritegroup import SpriteGroup
from Game.utils.tilemaps import TileMap, SHAPE_NAMES, get_shape_mask
from Game.Sprites.Enemies.enemy import Enemy
from Game.utils.hud import Hud
from Game.utils.title_screen import TitleScreen
from Game.utils.save_game import save_game as _save_game_to_disk
from Game.utils.save_game import load_save as _load_save_from_disk
from Game.utils.save_game import apply_save as _apply_save_to_game
from Game.utils.dialogue import DialogueBox
from Game.utils.dlg_parser import load_sequence as load_dlg
from Game.utils.inventory import InventoryOverlay
from Game.utils.crafting import CraftingOverlay

from Game.world import World
from Game.entity import Entity
from Game.components.position import Position
from Game.components.sprite import Sprite as ECSSprite
from Game.components.animation import Animation as ECSAnimation
from Game.systems.animation_system import AnimationSystem
from Game.systems.input_system import InputSystem
from Game.systems.physics_system import PhysicsSystem
from Game.systems.render_system import RenderSystem

_HEART_THEMES = ["normal"]

def _load_heart_theme(name):
    """Build the dict shape Hud expects for a given Heart Container variant."""
    folder_map = {
        "silver": ("Heart Container Silver", "heart_silver"),
        "normal": ("Heart Container Normal", "heart_normal"),
        "golden": ("Heart Container Golden", "heart_golden"),
        "poison": ("Heart Container Poison", "heart_poison"),
    }
    folder, prefix = folder_map[name]
    theme = {
        "full": load_image(f"hud/{folder}/{prefix}_full.png"),
        "half": load_image(f"hud/{folder}/{prefix}_half.png"),
        "blink": SpriteSheet(f"hud/{folder}/{prefix}_blink_full.png", tile_size=16),
        "empty": load_image("hud/Heart Container General/heart_empty.png"),
    }
    shine_candidates = [
        f"hud/{folder}/{prefix}_shine_full.png",
        f"hud/{folder}/{prefix}_dripping_full.png",
        f"hud/{folder}/{prefix}_transform_full.png",
    ]
    for candidate in shine_candidates:
        if os.path.exists("Game/assets/" + candidate):
            theme["shine"] = SpriteSheet(candidate, tile_size=16)
            break
    else:
        theme["shine"] = theme["blink"]
    return theme

def _load_armor_icons():
    """Return small armor-container icons for the HUD: golden / silver / general."""
    icons = {}
    icons["golden"] = load_image("hud/Armor Container Golden/armor_golden_full.png")
    icons["silver"] = load_image("hud/Armor Container Silver/armor_silver_full.png")
    icons["general"] = load_image(
        "hud/Armor Container General/armor_container_highlight.png"
    )
    return icons

class Game:
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        pygame.font.init()
        try:
            pygame.mixer.init()
            self._audio_ok = True
        except pygame.error as e:
            print(
                f"[audio] primary mixer init failed: {e} — retrying with dummy driver"
            )
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
            try:
                pygame.mixer.init()
                self._audio_ok = True
            except pygame.error as e2:
                print(f"[audio] dummy mixer init also failed: {e2} — running silent")
                self._audio_ok = False
        if self._audio_ok:
            print(f"[audio] mixer ready: {pygame.mixer.get_init()}")

        self._menu_music_path = "Game/assets/music/main_menu.ogg"
        self._level_music = {
            "church": "Game/assets/music/church.mp3",
        }
        self._current_music_path = None

        self._heart_theme_index = 0

        cfg = get_config()
        self._window_flags = pygame.RESIZABLE if cfg.get("resizable", True) else 0
        self._min_resolution = tuple(cfg.get("min_resolution", [640, 480]))
        self.screen = pygame.display.set_mode(
            tuple(cfg["resolution"]), self._window_flags
        )
        pygame.display.set_caption("Raven")
        self.running = True

        self.fonts = {
            "workbench": pygame.font.Font("Game/assets/fonts/workbench.ttf", 24),
            "workbench_small": pygame.font.Font("Game/assets/fonts/workbench.ttf", 18),
            "Arial": pygame.font.SysFont("Arial", 14),
        }

        self.camera = Camera(*get_config()["resolution"])

        self.sprite_group = SpriteGroup()

        self.tilemaps = {}

        self.assets = {}
        self.setup()

        self.tilemap_current = "church"
        self.tilemap = self.tilemaps[self.tilemap_current]

        if getattr(self.tilemap, "spawnpoint", None) is not None:
            sx, sy = self.tilemap.spawnpoint
            spawn_pos = (sx * self.tilemap.tile_size, sy * self.tilemap.tile_size)
        else:
            spawn_pos = (
                get_config()["resolution"][0] / 2,
                get_config()["resolution"][1] / 2,
            )
        self.player = Player(pos=spawn_pos, game=self, tilemap=self.tilemap)
        self._snap_player_above_ground()
        self.num = 0

        self.hud = Hud(self)
        self.clock = pygame.time.Clock()

        self._title_world = self._build_title_world()

        self.title_screen_active = True
        self.title_screen = TitleScreen(self)
        self._pending_load = False
        self._pending_load_slot = 0
        self._loaded_from_save = False
        self._active_save_slot = 0

        self.dialogue = DialogueBox(self)
        self._intro_played = False
        self._intro_delay: float = 0.6

        self.inventory_open = False
        self.inv_overlay = InventoryOverlay(self)

        self.crafting_open = False
        self.craft_overlay = CraftingOverlay(self)

        self.render_distance = 1000

        self.death_screen_visible = False
        self._death_at_ms = None
        self._death_delay_ms = 1500

        self.paused = False

        self._dev_unlocked = False
        self._pwd_buf = ""
        self._pwd_asking = False
        self._pwd_pending_action = None

        self.demo_complete_visible = False
        self._demo_complete_pending = False

        self._boss_music_active = False

        self.debug_mode = False
        self.debug_fly = False
        self.debug_fly_speed = 350

        self.fog_enabled = True
        self.fog_radius = 350
        self.fog_darkness = 245
        self._fog_overlay = None
        self._fog_hole_stamp = None
        self._fog_hole_radius_built = None

        self.editor_mode = False
        self.editor_sidebar_width = 300
        self._editor_palette_cache = None
        self._editor_palette_buckets = {}
        self._editor_thumb_cache = {}
        self.editor_minimized = False
        self.selected_env = "church"
        self.selected_type = "tiles"
        self.selected_variant = 0
        self.selected_collision = "solid"
        self.collision_types = ["none", "solid", "platform", "hazard"]
        self.selected_shape = "full"
        self.shape_options = SHAPE_NAMES
        self.brush_size = 1
        self.editor_scroll = 0
        self.editor_sidebar_scroll = 0
        self.editor_mouse_held = False
        self.editor_right_held = False
        self.spawnpoint_mode = False
        self.enemy_mode = False
        self.selected_enemy_kind = "ground"
        self.editor_erase_mode = False
        self.enemy_axes = [
            ("X", (1, 0)),
            ("Y", (0, 1)),
            ("XY", (1, 1)),
            ("Static", (0, 0)),
        ]
        self.selected_enemy_axis = "X"
        self.object_mode = False
        self.object_kinds = ["crystal", "box", "sword", "tetrahaxal", "wrench", "chest", "key"]
        self.selected_object_kind = "crystal"
        self._editor_tooltips = []

        self.layers = [{"id": 1, "in_front": False}]
        self.next_layer_id = 2
        self.selected_layer = 1
        self._sync_layers_with_tilemaps()

    def _handle_resize(self, w, h):
        """Recreate the display surface at (w, h) and update derived sizes."""
        min_w, min_h = self._min_resolution
        w = max(int(w), min_w)
        h = max(int(h), min_h)
        self.screen = pygame.display.set_mode((w, h), self._window_flags)
        self.camera.width = w
        self.camera.height = h
        if hasattr(self, "player") and hasattr(
            self.player, "_update_attacking_hitboxes"
        ):
            self.player._update_attacking_hitboxes()

    def _sync_layers_with_tilemaps(self):
        """Scan all loaded tilemaps for unique tile z values and ensure each has a layer entry.
        Preserves existing layer order/in_front settings; only appends missing ones."""
        existing_ids = {l["id"] for l in self.layers}
        discovered = set()
        for tm in self.tilemaps.values():
            for tile in tm.tile_map.values():
                z = tile.get("z")
                if z is not None:
                    discovered.add(int(z))
        for z in sorted(discovered):
            if z not in existing_ids:
                self.layers.append({"id": z, "in_front": False})
                existing_ids.add(z)
                if z >= self.next_layer_id:
                    self.next_layer_id = z + 1

    def setup(self):
        heart_themes = {name: _load_heart_theme(name) for name in _HEART_THEMES}
        active_theme_name = _HEART_THEMES[self._heart_theme_index % len(_HEART_THEMES)]

        self.assets = {
            "hud": {
                "heart": heart_themes[active_theme_name],
                "heart_themes": heart_themes,
                "heart_theme_name": active_theme_name,
                "armor": _load_armor_icons(),
                "bossbar": load_image("UI/bossfight_bossbar_spritesheet.png"),
                "plate_large":      load_image("UI/dark ui large plate.png"),
                "plate_large_long": load_image("UI/dark ui large-long plate.png"),
                "plate_small":      load_image("UI/dark ui small plate.png"),
                "plate_small_long": load_image("UI/dark ui small-long plate.png"),
            },
            "cave": {
                "big_rocks": SpriteSheet(
                    "cave_tiles/Cave - BigRocks1.png",
                    cut=load_json_as_dict("cut_tiles_json/Cave-BigRocks1.json"),
                ),
                "floor": SpriteSheet(
                    "cave_tiles/Cave - Floor.png",
                    cut=load_json_as_dict("cut_tiles_json/Cave-Floor.json"),
                ),
                "platform": SpriteSheet(
                    "cave_tiles/Cave - Platforms.png",
                    cut=load_json_as_dict("cut_tiles_json/Cave-Platforms.json"),
                ),
                "small_rocks": SpriteSheet(
                    "cave_tiles/Cave - SmallRocks.png", tile_size=16
                ),
                "rock_combos": SpriteSheet(
                    "cave_tiles/Cave - RockCombinations1.png", tile_size=16
                ),
                "black_square": SpriteSheet(
                    "cave_tiles/Square - Black.jpg", tile_size=16
                ),
            },
            "mossy": {
                "platform": SpriteSheet(
                    "mossy_tiles/Mossy - FloatingPlatforms.png", tile_size=512
                ),
                "tileset": SpriteSheet("mossy_tiles/Mossy - TileSet.png", tile_size=16),
                "mossy_hills": SpriteSheet(
                    "mossy_tiles/Mossy - MossyHills.png", tile_size=16
                ),
                "background": SpriteSheet(
                    "mossy_tiles/Mossy - BackgroundDecoration.png", tile_size=16
                ),
                "decorations": SpriteSheet(
                    "mossy_tiles/Mossy - Decorations&Hazards.png", tile_size=16
                ),
            },
            "church": {
                "tiles": SpriteSheet("dungeons/church.png", tile_size=16),
            },
            "plants": {},
        }

        self._editor_palette_cache = None
        self._editor_palette_buckets = {}
        self._editor_thumb_cache = {}

        self.tilemaps["church"] = TileMap(self, tile_size=48, pos=(0, 0), rendered=True)

        maps = get_config()["tilemaps"]

        for name, tilemaps in self.tilemaps.items():
            tilemaps.load_map("Game/assets/" + maps[name])

    def _load_plant_assets(self):
        """Plant assets disabled — returns an empty mapping so the editor's
        plants palette is empty and the title-screen ambient world spawns no
        plant entities. Retained as a method so existing call sites (asset
        rebuild on settings change, etc.) keep working."""
        return {}

    def _play_music(self, path, volume=0.4, loops=-1):
        """Stream a background music track. No-op if audio isn't available
        or the requested track is already playing."""
        if not getattr(self, "_audio_ok", False) or not path:
            return
        if path == self._current_music_path and pygame.mixer.music.get_busy():
            return
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(volume)
            pygame.mixer.music.play(loops=loops)
            self._current_music_path = path
        except pygame.error:
            self._current_music_path = None

    def _stop_music(self):
        if not getattr(self, "_audio_ok", False):
            return
        try:
            pygame.mixer.music.stop()
        except pygame.error:
            pass
        self._current_music_path = None

    def _build_title_world(self):
        """Construct a tiny ECS world that drives ambient plant decorations
        on the title screen. Exists primarily to keep Game.world / Game.entity
        / Game.component / the components/ + systems/ packages active rather
        than orphaned dead code, but it does also draw nice swaying plants
        along the bottom of the menu."""
        world = World()
        world.add_system(InputSystem(world))
        world.add_system(PhysicsSystem(world, self.tilemaps))
        world.add_system(AnimationSystem(world))
        world.add_system(RenderSystem(world))

        plants = self.assets.get("plants", {})
        preferred = [
            "Plant Wind 1",
            "BlueFlower1",
            "Plant 1",
            "Grass2",
            "Group Plant",
        ]
        chosen = [name for name in preferred if name in plants]
        if not chosen:
            chosen = list(plants.keys())[:5]

        sw = self.screen.get_width()
        sh = self.screen.get_height()
        next_id = 1
        for i, name in enumerate(chosen):
            pack = plants[name]
            frame_count = max(1, len(pack.get_images_list()))
            frame_duration = max(1.0, frame_count / 3.0)
            anim = ECSAnimation({"idle": (pack, frame_duration, True)}, current="idle")

            sample = pack.get_images_list()[0]
            scale = 2
            scaled = pygame.transform.scale(
                sample,
                (
                    max(1, sample.get_width() * scale),
                    max(1, sample.get_height() * scale),
                ),
            )
            sprite = ECSSprite(scaled)

            slot_w = sw / max(1, len(chosen) + 1)
            x = int(slot_w * (i + 1) - scaled.get_width() / 2)
            y = sh - scaled.get_height() - 30
            position = Position(x, y)

            ent = Entity(next_id)
            next_id += 1
            ent.add_component(position)
            ent.add_component(sprite)
            ent.add_component(anim)
            world.add_entity(ent)

        return world

    def _draw_title_ambient(self, screen):
        """Update + draw the ECS ambient world. Called by the title screen."""
        world = getattr(self, "_title_world", None)
        if world is None:
            return
        world.draw(screen)

    def _update_title_ambient(self, dt):
        world = getattr(self, "_title_world", None)
        if world is None:
            return
        world.update(dt)

    def _rotate_heart_theme(self):
        pass

    def _draw_button(self, rect, text, color=(80, 80, 80), hover=False, font=None):
        """Helper to draw a button with hover animation and no border."""
        scale = 1.05 if hover else 1.0
        scaled_rect = pygame.Rect(
            rect.x - (rect.width * (scale - 1)) / 2,
            rect.y - (rect.height * (scale - 1)) / 2,
            rect.width * scale,
            rect.height * scale,
        )

        button_color = (60, 100, 140) if hover else color
        pygame.draw.rect(self.screen, button_color, scaled_rect, border_radius=6)

        font_to_use = font if font is not None else self.fonts["workbench"]
        txt = font_to_use.render(text, True, (255, 255, 255))
        txt_rect = txt.get_rect(center=scaled_rect.center)
        self.screen.blit(txt, txt_rect)

    def _draw_pause_button(self, rect, text, color=(80, 120, 160), hover=False, font=None, lock=False):
        """Enhanced button for pause menu with better visuals."""
        scale = 1.08 if hover else 1.0
        scaled_rect = pygame.Rect(
            rect.x - (rect.width * (scale - 1)) / 2,
            rect.y - (rect.height * (scale - 1)) / 2,
            rect.width * scale,
            rect.height * scale,
        )

        if lock:
            color = tuple(int(c * 0.6) for c in color)

        if hover and not lock:
            glow_surf = pygame.Surface(
                (scaled_rect.width + 16, scaled_rect.height + 16), pygame.SRCALPHA
            )
            pygame.draw.rect(
                glow_surf, (100, 180, 255, 40),
                glow_surf.get_rect(), border_radius=10
            )
            self.screen.blit(glow_surf, (scaled_rect.x - 8, scaled_rect.y - 8))

        if hover and not lock:
            button_color = tuple(min(255, c + 60) for c in color)
            border_color = (150, 220, 255)
            border_width = 3
        else:
            button_color = color
            border_color = tuple(max(0, c - 30) for c in color)
            border_width = 2

        pygame.draw.rect(self.screen, button_color, scaled_rect, border_radius=8)
        pygame.draw.rect(self.screen, border_color, scaled_rect, border_width, border_radius=8)

        font_to_use = font if font is not None else self.fonts["workbench"]
        text_color = (255, 255, 255) if hover and not lock else (220, 235, 255)
        txt = font_to_use.render(text, True, text_color)
        txt_rect = txt.get_rect(center=scaled_rect.center)
        self.screen.blit(txt, txt_rect)

        if lock:
            lock_text = font_to_use.render("🔒", True, (200, 150, 100))
            lock_rect = lock_text.get_rect(right=scaled_rect.right - 12, centery=scaled_rect.centery)
            self.screen.blit(lock_text, lock_rect)

    def _dbg_button_rect(self):
        """The clickable rectangle for the in-game DBG toggle (top-right corner)."""
        sw = self.screen.get_width()
        return pygame.Rect(sw - 70, 8, 60, 28)

    def _draw_dbg_button(self):
        """Always-on small DBG toggle button in the top-right corner of the HUD."""
        rect = self._dbg_button_rect()
        active = self.debug_mode
        bg = (180, 100, 40) if active else (50, 50, 60)
        border = (255, 200, 80) if active else (110, 110, 130)
        pygame.draw.rect(self.screen, bg, rect, border_radius=6)
        pygame.draw.rect(self.screen, border, rect, 2, border_radius=6)
        label = "DBG ON" if active else "DBG"
        txt = self.fonts["workbench_small"].render(label, True, (255, 255, 255))
        self.screen.blit(txt, txt.get_rect(center=rect.center))

    def _draw_debug_overlay(self):
        """Draw a small DEBUG/FLY indicator + player position in the top-right corner."""
        text = "DEBUG  FLY (WASD)" if self.debug_fly else "DEBUG"
        surf = self.fonts["workbench_small"].render(text, True, (255, 200, 80))
        y = 10
        bg = pygame.Surface(
            (surf.get_width() + 8, surf.get_height() + 4), pygame.SRCALPHA
        )
        bg.fill((0, 0, 0, 160))
        self.screen.blit(bg, (self.screen.get_width() - surf.get_width() - 12, y - 2))
        self.screen.blit(surf, (self.screen.get_width() - surf.get_width() - 8, y))

        pos_text = f"x:{int(self.player.rect.x)} y:{int(self.player.rect.y)}"
        pos_surf = self.fonts["workbench_small"].render(pos_text, True, (200, 220, 255))
        self.screen.blit(
            pos_surf,
            (
                self.screen.get_width() - pos_surf.get_width() - 8,
                y + surf.get_height() + 6,
            ),
        )
        rd_text = f"render dist: {self.render_distance}px"
        rd_surf = self.fonts["workbench_small"].render(rd_text, True, (180, 220, 160))
        self.screen.blit(
            rd_surf,
            (
                self.screen.get_width() - rd_surf.get_width() - 8,
                y + surf.get_height() + pos_surf.get_height() + 10,
            ),
        )

    def _is_hovered(self, rect):
        mx, my = pygame.mouse.get_pos()
        return rect.collidepoint(mx, my)

    def draw_pause(self):
        overlay = pygame.Surface(self.screen.get_size())
        overlay.fill((0, 0, 0))
        overlay.set_alpha(200)
        self.screen.blit(overlay, (0, 0))

        small_font = self.fonts["workbench_small"]
        cx = self.screen.get_width() // 2
        cy = self.screen.get_height() // 2

        panel_width = 300
        panel_height = 400
        panel_rect = pygame.Rect(0, 0, panel_width, panel_height)
        panel_rect.center = (cx, cy)

        pygame.draw.rect(self.screen, (15, 20, 35), panel_rect, border_radius=12)
        pygame.draw.rect(self.screen, (80, 120, 180), panel_rect, 3, border_radius=12)

        glow_surf = pygame.Surface((panel_width + 20, panel_height + 20), pygame.SRCALPHA)
        pygame.draw.rect(
            glow_surf, (50, 100, 150, 40),
            glow_surf.get_rect(), border_radius=14
        )
        self.screen.blit(glow_surf, (panel_rect.x - 10, panel_rect.y - 10))

        y_offset = panel_rect.top + 20
        title_font = self.fonts["workbench"]
        paused_text = title_font.render("PAUSA", True, (220, 240, 255))
        title_rect = paused_text.get_rect(center=(cx, y_offset))
        self.screen.blit(paused_text, title_rect)

        line_y = y_offset + 25
        pygame.draw.line(self.screen, (100, 150, 200), (cx - 60, line_y), (cx + 60, line_y), 2)

        y_offset = line_y + 20

        if self._pwd_asking:
            pwd_label = small_font.render("Código dev:", True, (150, 170, 210))
            pwd_label_rect = pwd_label.get_rect(center=(cx, y_offset))
            self.screen.blit(pwd_label, pwd_label_rect)

            box_rect = pygame.Rect(0, 0, 220, 36)
            box_rect.center = (cx, y_offset + 40)
            pygame.draw.rect(self.screen, (25, 35, 55), box_rect, border_radius=6)
            pygame.draw.rect(self.screen, (100, 140, 200), box_rect, 2, border_radius=6)

            stars = "*" * len(self._pwd_buf)
            pwd_surf = small_font.render(stars, True, (255, 255, 150))
            self.screen.blit(pwd_surf, pwd_surf.get_rect(center=box_rect.center))

            hint = self.fonts["Arial"].render("Pulsa ENTER para confirmar", True, (110, 140, 180))
            hint_rect = hint.get_rect(center=(cx, y_offset + 75))
            self.screen.blit(hint, hint_rect)

            back_rect = pygame.Rect(0, 0, 220, 40)
            back_rect.center = (cx, y_offset + 120)
            self._draw_pause_button(back_rect, "Atrás", hover=self._is_hovered(back_rect), font=small_font, color=(100, 100, 120))

            return back_rect, None, None, None, None

        resume_rect = pygame.Rect(0, 0, 220, 40)
        resume_rect.center = (cx, y_offset)
        self._draw_pause_button(resume_rect, "Continuar", hover=self._is_hovered(resume_rect), font=small_font)
        y_offset += 55

        pygame.draw.line(self.screen, (60, 100, 140), (cx - 90, y_offset - 10), (cx + 90, y_offset - 10), 1)
        y_offset += 10

        debug_rect = pygame.Rect(0, 0, 220, 40)
        debug_rect.center = (cx, y_offset)
        debug_label = "Debug: ON" if self.debug_mode else "Debug: OFF"
        debug_color = (180, 100, 50) if self.debug_mode else (100, 120, 150)
        self._draw_pause_button(debug_rect, debug_label, hover=self._is_hovered(debug_rect), font=small_font, color=debug_color, lock=not self._dev_unlocked)
        y_offset += 50

        build_rect = pygame.Rect(0, 0, 220, 40)
        build_rect.center = (cx, y_offset)
        self._draw_pause_button(build_rect, "Editar Mapa", hover=self._is_hovered(build_rect), font=small_font, color=(100, 150, 100), lock=not self._dev_unlocked)
        y_offset += 55

        pygame.draw.line(self.screen, (60, 100, 140), (cx - 90, y_offset - 10), (cx + 90, y_offset - 10), 1)
        y_offset += 10

        menu_rect = pygame.Rect(0, 0, 220, 40)
        menu_rect.center = (cx, y_offset)
        self._draw_pause_button(menu_rect, "Menú Principal", hover=self._is_hovered(menu_rect), font=small_font, color=(150, 100, 80))
        y_offset += 50

        quit_rect = pygame.Rect(0, 0, 220, 40)
        quit_rect.center = (cx, y_offset)
        self._draw_pause_button(quit_rect, "Salir", hover=self._is_hovered(quit_rect), font=small_font, color=(180, 80, 80))

        return resume_rect, debug_rect, build_rect, menu_rect, quit_rect

    def draw_death_screen(self):
        """Game-over overlay with a Main Menu button.

        Shown only after ``self.death_screen_visible`` flips on, which
        happens a short delay after the player's ``dead`` flag is set.
        Returns the button rect so the click handler can hit-test it.
        """
        overlay = pygame.Surface(self.screen.get_size())
        overlay.fill((0, 0, 0))
        overlay.set_alpha(190)
        self.screen.blit(overlay, (0, 0))

        cx = self.screen.get_width() // 2
        cy = self.screen.get_height() // 2

        title_font = self.fonts["workbench"]
        small_font = self.fonts["workbench_small"]

        title = title_font.render("HAS MUERTO", True, (220, 60, 60))
        shadow = title_font.render("HAS MUERTO", True, (0, 0, 0))
        title_rect = title.get_rect(center=(cx, cy - 70))
        self.screen.blit(shadow, shadow.get_rect(center=(cx + 2, cy - 68)))
        self.screen.blit(title, title_rect)

        menu_rect = pygame.Rect(0, 0, 220, 44)
        menu_rect.center = (cx, cy)
        self._draw_button(
            menu_rect,
            "Menú Principal",
            color=(110, 70, 50),
            hover=self._is_hovered(menu_rect),
            font=small_font,
        )

        return menu_rect

    def draw_demo_complete(self):
        """Overlay shown when the player escapes through the door."""
        overlay = pygame.Surface(self.screen.get_size())
        overlay.fill((0, 0, 0))
        overlay.set_alpha(200)
        self.screen.blit(overlay, (0, 0))

        cx = self.screen.get_width() // 2
        cy = self.screen.get_height() // 2
        title_font = self.fonts["workbench"]
        small_font = self.fonts["workbench_small"]

        title = title_font.render("DEMO COMPLETADA", True, (255, 220, 80))
        shadow = title_font.render("DEMO COMPLETADA", True, (0, 0, 0))
        self.screen.blit(shadow, shadow.get_rect(center=(cx + 2, cy - 68)))
        self.screen.blit(title, title.get_rect(center=(cx, cy - 70)))

        sub = small_font.render("Has escapado de la iglesia.", True, (210, 210, 210))
        self.screen.blit(sub, sub.get_rect(center=(cx, cy - 20)))

        menu_rect = pygame.Rect(0, 0, 220, 44)
        menu_rect.center = (cx, cy + 30)
        self._draw_button(
            menu_rect,
            "Menú Principal",
            color=(60, 100, 60),
            hover=self._is_hovered(menu_rect),
            font=small_font,
        )
        return menu_rect

    def _snap_player_above_ground(self):
        """Place the player so they rest just above the nearest solid below
        them. Defends against spawnpoints (or saved positions) that would
        otherwise leave the character clipped inside or beneath geometry.
        """
        player = getattr(self, "player", None)
        tilemap = getattr(self, "tilemap", None)
        if player is None or tilemap is None:
            return
        ts = getattr(tilemap, "tile_size", 0)
        if not ts:
            return

        offset_x_px = tilemap.pos.x * ts
        offset_y_px = tilemap.pos.y * ts
        grid_left = int((player.rect.left - offset_x_px) // ts)
        grid_right = int((player.rect.right - 1 - offset_x_px) // ts)
        grid_y_start = int((player.rect.top - offset_y_px) // ts)

        max_depth = 80
        nearest_grid_y = None
        for gy in range(grid_y_start, grid_y_start + max_depth):
            for gx in range(grid_left, grid_right + 1):
                for tile in tilemap.get_tiles_at(gx, gy):
                    if "solid" in tile.get("properties", []):
                        if nearest_grid_y is None or gy < nearest_grid_y:
                            nearest_grid_y = gy
                        break
            if nearest_grid_y is not None:
                break

        if nearest_grid_y is None:
            return

        floor_top_world_y = (nearest_grid_y + tilemap.pos.y) * ts
        player.rect.bottom = floor_top_world_y - 1
        if hasattr(player, "velocity"):
            player.velocity.y = 0
        if hasattr(player, "attributes"):
            player.attributes["falling"] = False
            player.attributes["jumping"] = False
        if hasattr(player, "update_visual_rect"):
            player.update_visual_rect()

    def _restart_game(self):
        """Tear down runtime state and rebuild the level fresh.

        Reloads every tilemap from disk (so placed enemies, breakables,
        chests, etc. respawn), recreates the player at the spawnpoint,
        rebuilds the HUD, and clears the death-screen flags. Also cycles
        the heart container theme so each fresh attempt swaps to the next
        of the four unused asset packs.
        """
        self._rotate_heart_theme()
        self.tilemaps = {}
        self.sprite_group = SpriteGroup()
        self.setup()
        self._title_world = self._build_title_world()

        self.tilemap_current = "church"
        self.tilemap = self.tilemaps[self.tilemap_current]

        if getattr(self.tilemap, "spawnpoint", None) is not None:
            sx, sy = self.tilemap.spawnpoint
            spawn_pos = (sx * self.tilemap.tile_size, sy * self.tilemap.tile_size)
        else:
            res = get_config()["resolution"]
            spawn_pos = (res[0] / 2, res[1] / 2)

        self.player = Player(pos=spawn_pos, game=self, tilemap=self.tilemap)
        self._snap_player_above_ground()
        self.hud = Hud(self)

        self.death_screen_visible = False
        self._death_at_ms = None
        self.paused = False
        self.demo_complete_visible = False
        self._demo_complete_pending = False
        self._boss_music_active = False
        self._pwd_buf = ""

        self.dialogue = DialogueBox(self)

    def _get_editor_palette(self):
        """Return a flat list of selectable tiles from self.assets.

        Cached on first call — assets don't change at runtime. Without this
        cache, opening the editor walked every spritesheet and recreated
        the same list 2-3 times *per frame* (once in draw_editor, once or
        twice in _editor_layout via the click handler). The cache is
        cleared in ``setup()`` whenever assets are rebuilt.

        Some spritesheets are very large (mossy.background and
        mossy.decorations expand to 65k variants each), so the flat list
        can be 200k+ items long. Callers that just want the variants for
        the current (env, type) selection should prefer the O(1) bucketed
        accessor :meth:`_get_editor_palette_for` instead — filtering the
        flat list every frame was the actual root cause of editor lag."""
        if self._editor_palette_cache is not None:
            return self._editor_palette_cache
        palette = []
        buckets = {}
        for env_name, env_data in self.assets.items():
            if env_name == "hud":
                continue
            for type_name, sprite_sheet in env_data.items():
                images = sprite_sheet.get_images_list()
                bucket_key = (env_name, type_name)
                bucket = buckets.setdefault(bucket_key, [])
                for i, img in enumerate(images):
                    item = {
                        "env": env_name,
                        "type": type_name,
                        "variant": i,
                        "image": img,
                    }
                    palette.append(item)
                    bucket.append(item)
        self._editor_palette_cache = palette
        self._editor_palette_buckets = buckets
        return palette

    def _get_editor_palette_for(self, env, ttype):
        """Return the cached palette items for a single (env, type) pair.
        O(1) dict lookup; previously this was a 200k-item list comprehension
        firing several times per frame in the editor draw + click paths."""
        if self._editor_palette_cache is None:
            self._get_editor_palette()
        return self._editor_palette_buckets.get((env, ttype), [])

    def _get_editor_thumb(self, item, thumb_size):
        """Return a cached pre-scaled thumbnail Surface for a palette item.
        Eliminates per-frame pygame.transform.scale calls in draw_editor."""
        key = (item["env"], item["type"], item["variant"], thumb_size)
        thumb = self._editor_thumb_cache.get(key)
        if thumb is None:
            thumb = pygame.transform.scale(item["image"], (thumb_size, thumb_size))
            self._editor_thumb_cache[key] = thumb
        return thumb

    def _editor_layout(self):
        """Compute layout rects used by both draw_editor and the click handler.
        Returns a dict of named regions so draw and hit-test stay in sync.
        Sections above the variant palette respect ``self.editor_sidebar_scroll``.
        """
        layout = {}
        sw = self.editor_sidebar_width
        layout["sidebar_w"] = sw
        layout["toggle"] = pygame.Rect(4, 4, 24, 24)

        if self.editor_minimized:
            return layout

        scroll = self.editor_sidebar_scroll
        y = 38 + scroll
        layout["sections"] = []

        env_names = [k for k in self.assets.keys() if k != "hud"]
        layout["env_names"] = env_names
        layout["sections"].append(("AMBIENTE", pygame.Rect(8, y, sw - 16, 16)))
        y += 20
        layout["env_rects"] = [
            pygame.Rect(10 + i * 60, y, 55, 24) for i in range(len(env_names))
        ]
        y += 30

        type_names = (
            list(self.assets.get(self.selected_env, {}).keys())
            if self.selected_env != "hud"
            else []
        )
        layout["type_names"] = type_names
        layout["sections"].append(("TIPO", pygame.Rect(8, y, sw - 16, 16)))
        y += 20
        layout["type_rects"] = [
            pygame.Rect(10 + i * 60, y, 55, 24) for i in range(max(1, len(type_names)))
        ]
        y += 30

        layout["sections"].append(
            ("CAPAS (arriba = frente)", pygame.Rect(8, y, sw - 16, 16))
        )
        y += 20
        row_h = 26
        layer_rects = []
        for i, layer in enumerate(self.layers):
            ry = y + i * row_h
            layer_rects.append(
                {
                    "select": pygame.Rect(10, ry, 70, 22),
                    "up": pygame.Rect(82, ry, 22, 22),
                    "down": pygame.Rect(106, ry, 22, 22),
                    "side": pygame.Rect(130, ry, 50, 22),
                    "delete": pygame.Rect(182, ry, 22, 22),
                }
            )
        layout["layer_rects"] = layer_rects
        y += len(self.layers) * row_h + 4
        layout["add_layer"] = pygame.Rect(10, y, 110, 22)
        y += 32

        layout["sections"].append(("COLISIÓN", pygame.Rect(8, y, sw - 16, 16)))
        y += 20
        layout["coll_rects"] = [
            pygame.Rect(10 + (i % 2) * 110, y + (i // 2) * 26, 100, 22)
            for i in range(len(self.collision_types))
        ]
        y += ((len(self.collision_types) + 1) // 2) * 26 + 10

        shape_rects = []
        cols = 2
        pill_w = 100
        pill_h = 22
        gap_x = 10
        gap_y = 4
        for i, sh in enumerate(self.shape_options):
            cx = 10 + (i % cols) * (pill_w + gap_x)
            cy = y + (i // cols) * (pill_h + gap_y)
            shape_rects.append((sh, pygame.Rect(cx, cy, pill_w, pill_h)))
        layout["shape_rects"] = shape_rects
        rows_used = (len(self.shape_options) + cols - 1) // cols
        y += rows_used * (pill_h + gap_y) + 8

        layout["sections"].append(("TAMAÑO PINCEL", pygame.Rect(8, y, sw - 16, 16)))
        y += 20
        layout["brush_minus"] = pygame.Rect(10, y, 36, 24)
        layout["brush_label"] = pygame.Rect(50, y, 100, 24)
        layout["brush_plus"] = pygame.Rect(154, y, 36, 24)
        y += 32

        layout["sections"].append(("APARICIÓN", pygame.Rect(8, y, sw - 16, 16)))
        y += 20
        layout["spawn_rect"] = pygame.Rect(10, y, sw - 20, 22)
        y += 32

        layout["sections"].append(("ENEMIGOS", pygame.Rect(8, y, sw - 16, 16)))
        y += 20
        layout["enemy_toggle_rect"] = pygame.Rect(10, y, sw - 20, 22)
        y += 28
        layout["erase_toggle_rect"] = pygame.Rect(10, y, sw - 20, 22)
        y += 28
        kind_w = (sw - 30) // 3
        layout["enemy_kind_ground"] = pygame.Rect(10, y, kind_w, 22)
        layout["enemy_kind_flying"] = pygame.Rect(10 + kind_w + 5, y, kind_w, 22)
        layout["enemy_kind_boss"]   = pygame.Rect(10 + (kind_w + 5) * 2, y, kind_w, 22)
        y += 28
        axis_rects = []
        for i, (label, _vec) in enumerate(self.enemy_axes):
            rx = 10 + i * 60
            axis_rects.append((label, pygame.Rect(rx, y, 55, 22)))
        layout["enemy_axis_rects"] = axis_rects
        y += 32

        layout["sections"].append(("OBJETOS", pygame.Rect(8, y, sw - 16, 16)))
        y += 20
        layout["object_toggle_rect"] = pygame.Rect(10, y, sw - 20, 22)
        y += 28
        pill_w = 85; pill_h = 22; pill_gap = 4
        obj_cols = max(1, (sw - 20) // (pill_w + pill_gap))
        kind_rects = []
        for i, kind in enumerate(self.object_kinds):
            col = i % obj_cols
            row = i // obj_cols
            rx = 10 + col * (pill_w + pill_gap)
            ry = y + row * (pill_h + pill_gap)
            kind_rects.append((kind, pygame.Rect(rx, ry, pill_w, pill_h)))
        obj_rows = (len(self.object_kinds) + obj_cols - 1) // obj_cols
        layout["object_kind_rects"] = kind_rects
        y += obj_rows * (pill_h + pill_gap) + 4

        layout["sidebar_content_bottom"] = (
            y - scroll
        )

        layout["sections"].append(("VARIANTS", pygame.Rect(8, y, sw - 16, 16)))
        y += 20
        layout["var_y"] = y

        filtered = self._get_editor_palette_for(
            self.selected_env, self.selected_type
        )
        thumb_size = 40
        palette_cols = max(1, (sw - 20) // (thumb_size + 5))
        palette_rows = (len(filtered) + palette_cols - 1) // palette_cols
        palette_height = palette_rows * (thumb_size + 5)
        layout["palette_bottom_y"] = (
            y - scroll
        ) + palette_height
        layout["sidebar_total_h"] = layout["palette_bottom_y"] + 20

        layout["save_rect"] = pygame.Rect(10, self.screen.get_height() - 50, 95, 32)
        layout["exit_rect"] = pygame.Rect(120, self.screen.get_height() - 50, 95, 32)
        layout["info_y"] = self.screen.get_height() - 78

        return layout

    def _draw_section_header(self, rect, text):
        """Draw a section header with an underline divider."""
        pygame.draw.line(
            self.screen,
            (90, 100, 120),
            (rect.left, rect.top - 4),
            (rect.right, rect.top - 4),
            1,
        )
        surf = self.fonts["workbench_small"].render(text, True, (140, 200, 250))
        self.screen.blit(surf, (rect.left + 2, rect.top - 2))

    def _draw_pill(self, rect, text, selected=False, color=(60, 60, 70), tooltip=None):
        """Draw a styled rectangular button with hover scale animation, a
        permanent border, and selected/hover color states. The clickable area
        remains the original ``rect``; we only draw a visually scaled version
        on hover so collision detection stays predictable."""
        hover = self._is_hovered(rect)

        if hover and not selected:
            inflate = max(2, int(rect.width * 0.06))
            draw_rect = rect.inflate(inflate, max(2, int(rect.height * 0.10)))
        else:
            draw_rect = rect

        if selected:
            r, g, b = color
            fill = (min(255, r + 40), min(255, g + 60), min(255, b + 80))
        else:
            fill = color
        if hover and not selected:
            r, g, b = fill
            fill = (min(255, r + 25), min(255, g + 25), min(255, b + 25))

        pygame.draw.rect(self.screen, fill, draw_rect, border_radius=4)

        if selected:
            pygame.draw.rect(self.screen, (255, 220, 90), draw_rect, 3, border_radius=4)
        elif hover:
            pygame.draw.rect(
                self.screen, (200, 220, 245), draw_rect, 2, border_radius=4
            )
        else:
            pygame.draw.rect(
                self.screen, (110, 120, 145), draw_rect, 1, border_radius=4
            )

        txt = self.fonts["workbench_small"].render(text, True, (240, 240, 240))
        self.screen.blit(txt, txt.get_rect(center=draw_rect.center))
        if tooltip and hover:
            self._editor_tooltips.append((rect, tooltip))

    def _draw_shape_button(self, rect, shape, selected, tooltip):
        """Draw a shape preview as a button (small icon showing the shape silhouette)."""
        hover = self._is_hovered(rect)
        bg = (40, 50, 65) if not selected else (70, 95, 130)
        if hover and not selected:
            bg = (55, 65, 80)
        pygame.draw.rect(self.screen, bg, rect, border_radius=4)
        inset = 6
        size = rect.width - inset * 2
        try:
            mask = get_shape_mask(shape, size)
        except Exception:
            mask = None
        if mask is not None:
            preview = pygame.Surface((size, size), pygame.SRCALPHA)
            preview.fill((220, 230, 255, 0))
            color_layer = pygame.Surface((size, size), pygame.SRCALPHA)
            color_layer.fill((230, 240, 255, 255) if selected else (180, 200, 230, 255))
            color_layer.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
            preview.blit(color_layer, (0, 0))
            self.screen.blit(preview, (rect.left + inset, rect.top + inset))
        if selected:
            pygame.draw.rect(self.screen, (255, 220, 90), rect, 3, border_radius=4)
        elif hover:
            pygame.draw.rect(self.screen, (180, 200, 230), rect, 1, border_radius=4)
        if hover and tooltip:
            self._editor_tooltips.append((rect, tooltip))

    def _draw_editor_tooltips(self):
        """Render any tooltips queued during this frame's editor draw."""
        if not self._editor_tooltips:
            return
        rect, text = self._editor_tooltips[-1]
        font = self.fonts["workbench_small"]
        surf = font.render(text, True, (255, 255, 255))
        pad = 6
        bg = pygame.Rect(0, 0, surf.get_width() + pad * 2, surf.get_height() + pad)
        bg.topleft = (rect.right + 6, rect.top)
        sw = self.screen.get_width()
        if bg.right > sw - 4:
            bg.right = sw - 4
        if bg.bottom > self.screen.get_height() - 4:
            bg.bottom = self.screen.get_height() - 4
        pygame.draw.rect(self.screen, (20, 20, 30), bg, border_radius=4)
        pygame.draw.rect(self.screen, (180, 200, 230), bg, 1, border_radius=4)
        self.screen.blit(surf, (bg.left + pad, bg.top + pad // 2))

    def draw_editor(self):
        self._editor_tooltips = []

        layout = self._editor_layout()
        sw = layout["sidebar_w"]

        if self.editor_minimized:
            mini = pygame.Rect(0, 0, 32, self.screen.get_height())
            pygame.draw.rect(self.screen, (24, 26, 36), mini)
            self._draw_pill(
                layout["toggle"], ">", color=(60, 100, 140), tooltip="Expandir panel"
            )
            self._draw_editor_tooltips()
            return [], None, None, layout

        sidebar = pygame.Rect(0, 0, sw, self.screen.get_height())
        pygame.draw.rect(self.screen, (24, 26, 36), sidebar)
        pygame.draw.line(
            self.screen, (90, 110, 150), (sw, 0), (sw, self.screen.get_height()), 2
        )

        old_clip = self.screen.get_clip()
        sticky_top = layout["save_rect"].top - 8
        self.screen.set_clip(pygame.Rect(0, 32, sw, sticky_top - 32))

        for title, hrect in layout.get("sections", []):
            self._draw_section_header(hrect, title)

        for i, env in enumerate(layout["env_names"]):
            r = layout["env_rects"][i]
            self._draw_pill(
                r,
                env[:7],
                selected=(env == self.selected_env),
                color=(45, 75, 55),
                tooltip=f"Usar ambiente: {env}",
            )

        for i, tname in enumerate(layout["type_names"]):
            r = layout["type_rects"][i]
            self._draw_pill(
                r,
                tname[:7],
                selected=(tname == self.selected_type),
                color=(45, 75, 55),
                tooltip=f"Tipo de recurso: {tname}",
            )

        for i, layer in enumerate(self.layers):
            r = layout["layer_rects"][i]
            self._draw_pill(
                r["select"],
                f"L{layer['id']}",
                selected=(layer["id"] == self.selected_layer),
                color=(45, 70, 100),
                tooltip=f"Editar capa {layer['id']}",
            )
            self._draw_pill(r["up"], "^", color=(60, 60, 70), tooltip="Subir capa")
            self._draw_pill(
                r["down"], "v", color=(60, 60, 70), tooltip="Bajar capa"
            )
            side_label = "Frente" if layer["in_front"] else "Detrás"
            side_color = (110, 80, 50) if layer["in_front"] else (45, 75, 110)
            self._draw_pill(
                r["side"],
                side_label,
                color=side_color,
                tooltip="Cambiar Frente/Detrás del jugador",
            )
            del_color = (120, 50, 50) if len(self.layers) > 1 else (40, 40, 40)
            self._draw_pill(
                r["delete"],
                "x",
                color=del_color,
                tooltip="Eliminar capa"
                if len(self.layers) > 1
                else "No se puede eliminar la última capa",
            )
        self._draw_pill(
            layout["add_layer"],
            "+ Añadir capa",
            color=(45, 95, 55),
            tooltip="Añadir nueva capa (frente)",
        )

        for i, ctype in enumerate(self.collision_types):
            r = layout["coll_rects"][i]
            self._draw_pill(
                r,
                ctype,
                selected=(ctype == self.selected_collision),
                color=(110, 50, 50),
                tooltip=f"Colocar tiles con colisión: {ctype}",
            )

        SHAPE_TOOLTIPS = {
            "full": "Tile completo",
            "slab_top": "Losa — mitad superior",
            "slab_bottom": "Losa — mitad inferior",
            "slab_left": "Losa — mitad izquierda",
            "slab_right": "Losa — mitad derecha",
            "quarter_tl": "Cuarto — arriba-izquierda",
            "quarter_tr": "Cuarto — arriba-derecha",
            "quarter_bl": "Cuarto — abajo-izquierda",
            "quarter_br": "Cuarto — abajo-derecha",
            "slope_tl": "Rampa — sólida arriba-izquierda (◤)",
            "slope_tr": "Rampa — sólida arriba-derecha (◥)",
            "slope_bl": "Rampa — sube hacia la IZQUIERDA (◣)",
            "slope_br": "Rampa — sube hacia la DERECHA (◢)",
        }
        SHAPE_LABELS = {
            "full": "full",
            "slab_top": "slab T",
            "slab_bottom": "slab B",
            "slab_left": "slab L",
            "slab_right": "slab R",
            "quarter_tl": "qtr TL",
            "quarter_tr": "qtr TR",
            "quarter_bl": "qtr BL",
            "quarter_br": "qtr BR",
            "slope_tl": "slope TL",
            "slope_tr": "slope TR",
            "slope_bl": "slope BL",
            "slope_br": "slope BR",
        }
        for shape, r in layout.get("shape_rects", []):
            self._draw_pill(
                r,
                SHAPE_LABELS.get(shape, shape),
                selected=(shape == self.selected_shape),
                color=(70, 60, 100),
                tooltip=SHAPE_TOOLTIPS.get(shape, shape),
            )

        self._draw_pill(
            layout["brush_minus"], "-", color=(70, 80, 100), tooltip="Pincel más pequeño ([)"
        )
        label = self.fonts["workbench_small"].render(
            f"{self.brush_size} x {self.brush_size}", True, (240, 240, 240)
        )
        readout = layout["brush_label"]
        pygame.draw.rect(self.screen, (40, 45, 60), readout, border_radius=4)
        pygame.draw.rect(self.screen, (110, 120, 145), readout, 1, border_radius=4)
        self.screen.blit(label, label.get_rect(center=readout.center))
        self._draw_pill(
            layout["brush_plus"], "+", color=(70, 80, 100), tooltip="Pincel más grande (])"
        )

        sp_color = (50, 130, 80) if self.spawnpoint_mode else (60, 60, 70)
        sp_label = "Aparición: ACT" if self.spawnpoint_mode else "Colocar aparición (C1)"
        self._draw_pill(
            layout["spawn_rect"],
            sp_label,
            selected=self.spawnpoint_mode,
            color=sp_color,
            tooltip="Click en el mundo para fijar la aparición (sólo capa 1)",
        )

        em_color = (130, 50, 60) if self.enemy_mode else (60, 60, 70)
        em_label = "Colocar enemigos: ACT" if self.enemy_mode else "Colocar enemigos"
        self._draw_pill(
            layout["enemy_toggle_rect"],
            em_label,
            selected=self.enemy_mode,
            color=em_color,
            tooltip="Click izq. para colocar, click der. para eliminar",
        )
        er_color = (170, 70, 70) if self.editor_erase_mode else (60, 60, 70)
        er_label = "Modo borrado: ACT (click izq. borra)" if self.editor_erase_mode else "Modo borrado (click izq. borra)"
        self._draw_pill(
            layout["erase_toggle_rect"],
            er_label,
            selected=self.editor_erase_mode,
            color=er_color,
            tooltip="Cuando está ACT, click izquierdo elimina enemigos/objetos bajo el cursor",
        )
        self._draw_pill(
            layout["enemy_kind_ground"],
            "Suelo",
            selected=(self.selected_enemy_kind == "ground"),
            color=(110, 60, 50),
            tooltip="Colocar enemigo terrestre",
        )
        self._draw_pill(
            layout["enemy_kind_flying"],
            "Volador",
            selected=(self.selected_enemy_kind == "flying"),
            color=(80, 60, 130),
            tooltip="Colocar enemigo volador",
        )
        self._draw_pill(
            layout["enemy_kind_boss"],
            "Jefe",
            selected=(self.selected_enemy_kind == "boss"),
            color=(170, 90, 40),
            tooltip="Colocar al Verdugo No-Muerto (jefe)",
        )
        for label, rect in layout["enemy_axis_rects"]:
            axis_selected = (
                self.selected_enemy_axis == label
                and self.selected_enemy_kind == "flying"
            )
            base_color = (
                (50, 60, 90) if self.selected_enemy_kind == "flying" else (40, 45, 55)
            )
            self._draw_pill(
                rect,
                label,
                selected=axis_selected,
                color=base_color,
                tooltip="Eje de patrulla (sólo para enemigos voladores)",
            )

        obj_color = (50, 110, 130) if self.object_mode else (60, 60, 70)
        obj_label = "Colocar objetos: ACT" if self.object_mode else "Colocar objetos"
        self._draw_pill(
            layout["object_toggle_rect"],
            obj_label,
            selected=self.object_mode,
            color=obj_color,
            tooltip="Click izq. para colocar, click der. para eliminar",
        )
        from Game.utils.items_db import ITEMS as _ITEMS_DB
        OBJ_LABELS = {"crystal": "Cristal", "box": "Caja (Z)"}
        OBJ_TOOLTIPS = {
            "crystal": "Cristal coleccionable — se recoge al tocarlo",
            "box": "Caja de madera — pulsa Z para abrirla",
        }
        for _k, _d in _ITEMS_DB.items():
            if _k not in OBJ_LABELS:
                OBJ_LABELS[_k] = _d.get("name", _k.capitalize())
                OBJ_TOOLTIPS[_k] = f"Objeto: {_d.get('name', _k)} — {_d.get('desc', '')}"
        for kind, rect in layout["object_kind_rects"]:
            self._draw_pill(
                rect,
                OBJ_LABELS.get(kind, kind),
                selected=(self.selected_object_kind == kind),
                color=(50, 90, 120),
                tooltip=OBJ_TOOLTIPS.get(kind, kind),
            )

        filtered = self._get_editor_palette_for(
            self.selected_env, self.selected_type
        )
        thumb_size = 40
        cols = max(1, (sw - 20) // (thumb_size + 5))
        var_top = layout["var_y"]
        for i, item in enumerate(filtered):
            col = i % cols
            row = i // cols
            x = 10 + col * (thumb_size + 5)
            y = var_top + row * (thumb_size + 5)
            thumb_rect = pygame.Rect(x, y, thumb_size, thumb_size)
            is_selected = (
                item["env"] == self.selected_env
                and item["type"] == self.selected_type
                and item["variant"] == self.selected_variant
            )
            thumb_img = self._get_editor_thumb(item, thumb_size)
            self.screen.blit(thumb_img, (x, y))
            if is_selected:
                pygame.draw.rect(self.screen, (255, 220, 90), thumb_rect, 3)
            else:
                pygame.draw.rect(self.screen, (90, 100, 120), thumb_rect, 1)
            if self._is_hovered(thumb_rect):
                self._editor_tooltips.append((thumb_rect, f"variante {item['variant']}"))

        self.screen.set_clip(old_clip)

        self._draw_pill(
            layout["toggle"], "<", color=(60, 100, 140), tooltip="Minimizar panel"
        )
        title = self.fonts["workbench"].render("EDITOR", True, (240, 240, 250))
        self.screen.blit(title, (34, 6))

        info_text = self.fonts["workbench_small"].render(
            f"L{self.selected_layer} {self.selected_collision} {self.selected_shape}",
            True,
            (220, 220, 230),
        )
        self.screen.blit(info_text, (10, layout["info_y"]))
        pygame.draw.rect(
            self.screen,
            (24, 26, 36),
            pygame.Rect(
                0,
                layout["save_rect"].top - 6,
                sw,
                self.screen.get_height() - layout["save_rect"].top + 6,
            ),
        )
        pygame.draw.line(
            self.screen,
            (60, 70, 90),
            (0, layout["save_rect"].top - 6),
            (sw, layout["save_rect"].top - 6),
            1,
        )
        self._draw_pill(
            layout["save_rect"], "Guardar", color=(45, 95, 55), tooltip="Guardar mapa a JSON"
        )
        self._draw_pill(
            layout["exit_rect"], "Salir", color=(110, 70, 50), tooltip="Cerrar editor"
        )

        self._draw_editor_tooltips()

        return filtered, layout["save_rect"], layout["exit_rect"], layout

    def _editor_active_sidebar_w(self):
        return 32 if self.editor_minimized else self.editor_sidebar_width

    def _get_mouse_grid_pos(self):
        """Get grid coordinates under the mouse in world space."""
        mx, my = pygame.mouse.get_pos()
        if self.editor_mode and mx < self._editor_active_sidebar_w():
            return None

        world_x = mx + self.camera.offset.x
        world_y = my + self.camera.offset.y

        grid_x = int(world_x // self.tilemap.tile_size)
        grid_y = int(world_y // self.tilemap.tile_size)

        return grid_x, grid_y

    def _brush_cells(self, center_x, center_y):
        """Yield (gx, gy) for every tile covered by the current NxN brush
        centered (top-left aligned for even sizes) on (center_x, center_y)."""
        n = max(1, int(self.brush_size))
        half = n // 2
        for dy in range(-half, -half + n):
            for dx in range(-half, -half + n):
                yield center_x + dx, center_y + dy

    def _current_enemy_axis(self):
        """Return the (dx, dy) tuple for the currently selected patrol axis."""
        for label, vec in self.enemy_axes:
            if label == self.selected_enemy_axis:
                return vec
        return (0, 0)

    def _brush_place(self, grid_x, grid_y):
        """Place the currently selected tile across the whole brush area."""
        props = [] if self.selected_collision == "none" else [self.selected_collision]
        for gx, gy in self._brush_cells(grid_x, grid_y):
            self.tilemap.place_tile(
                gx,
                gy,
                {
                    "environment": self.selected_env,
                    "type": self.selected_type,
                    "variant": self.selected_variant,
                    "properties": props,
                    "z": self.selected_layer,
                    "shape": self.selected_shape,
                },
            )

    def _brush_erase(self, grid_x, grid_y):
        """Erase tiles across the whole brush area."""
        for gx, gy in self._brush_cells(grid_x, grid_y):
            self.tilemap.erase_tile(gx, gy)

    def draw_editor_cursor(self):
        grid_pos = self._get_mouse_grid_pos()
        if grid_pos is None:
            return

        grid_x, grid_y = grid_pos
        ts = self.tilemap.tile_size

        if self.object_mode:
            from Game.utils.items_db import ITEMS as _ICUR
            sx = grid_x * ts - self.camera.offset.x
            sy = grid_y * ts - self.camera.offset.y
            kind = self.selected_object_kind
            if self.editor_erase_mode:
                color = (230, 60, 60)
                tag = "X"
            elif kind == "box":
                color = (180, 130, 60)
                tag = "B"
            elif kind == "crystal":
                color = (90, 200, 230)
                tag = "C"
            else:
                color = _ICUR.get(kind, {}).get("color", (160, 160, 200))
                tag = _ICUR.get(kind, {}).get("name", kind)[:2].upper()
            preview = pygame.Surface((ts, ts), pygame.SRCALPHA)
            preview.fill((color[0], color[1], color[2], 120))
            self.screen.blit(preview, (sx, sy))
            pygame.draw.rect(self.screen, color, (sx, sy, ts, ts), 2)
            tag_surf = self.fonts["workbench"].render(tag, True, (255, 255, 255))
            self.screen.blit(
                tag_surf,
                (
                    sx + ts // 2 - tag_surf.get_width() // 2,
                    sy + ts // 2 - tag_surf.get_height() // 2,
                ),
            )
            coord_text = self.fonts["workbench_small"].render(
                f"{grid_x},{grid_y}  {kind}", True, (255, 220, 120)
            )
            self.screen.blit(coord_text, (sx, sy - 18))
            return

        if self.enemy_mode:
            sx = grid_x * ts - self.camera.offset.x
            sy = grid_y * ts - self.camera.offset.y
            kind = self.selected_enemy_kind
            if self.editor_erase_mode:
                color = (230, 60, 60)
                tag = "X"
            elif kind == "boss":
                color = (220, 130, 50)
                tag = "B"
            elif kind == "flying":
                color = (140, 80, 220)
                tag = "F"
            else:
                color = (220, 80, 80)
                tag = "G"
            is_flying = kind == "flying"
            preview = pygame.Surface((ts, ts), pygame.SRCALPHA)
            preview.fill((color[0], color[1], color[2], 120))
            self.screen.blit(preview, (sx, sy))
            pygame.draw.rect(self.screen, color, (sx, sy, ts, ts), 2)
            tag_surf = self.fonts["workbench"].render(tag, True, (255, 255, 255))
            self.screen.blit(
                tag_surf,
                (
                    sx + ts // 2 - tag_surf.get_width() // 2,
                    sy + ts // 2 - tag_surf.get_height() // 2,
                ),
            )
            extra = f"  axis {self.selected_enemy_axis}" if is_flying else ""
            coord_text = self.fonts["workbench_small"].render(
                f"{grid_x},{grid_y}  {self.selected_enemy_kind}{extra}",
                True,
                (255, 220, 120),
            )
            self.screen.blit(coord_text, (sx, sy - 18))
            return

        try:
            mask = get_shape_mask(self.selected_shape, ts)
        except Exception:
            mask = None

        cells = list(self._brush_cells(grid_x, grid_y))
        for gx, gy in cells:
            sx = gx * ts - self.camera.offset.x
            sy = gy * ts - self.camera.offset.y
            if mask is not None:
                preview = pygame.Surface((ts, ts), pygame.SRCALPHA)
                colored = pygame.Surface((ts, ts), pygame.SRCALPHA)
                colored.fill((90, 220, 120, 90))
                colored.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
                preview.blit(colored, (0, 0))
                self.screen.blit(preview, (sx, sy))
            pygame.draw.rect(self.screen, (0, 200, 90), (sx, sy, ts, ts), 1)

        if cells:
            xs = [gx for gx, _ in cells]
            ys = [gy for _, gy in cells]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            outline = pygame.Rect(
                min_x * ts - self.camera.offset.x,
                min_y * ts - self.camera.offset.y,
                (max_x - min_x + 1) * ts,
                (max_y - min_y + 1) * ts,
            )
            pygame.draw.rect(self.screen, (255, 255, 0), outline, 2)

        screen_x = grid_x * ts - self.camera.offset.x
        screen_y = grid_y * ts - self.camera.offset.y
        coord_text = self.fonts["workbench_small"].render(
            f"{grid_x},{grid_y}  brush {self.brush_size}x{self.brush_size}",
            True,
            (255, 255, 0),
        )
        self.screen.blit(coord_text, (screen_x, screen_y - 18))

    def _grant_all_combo_items(self):
        """Give the player one of every craftable item plus all combo
        results, used when starting a fresh "JUGAR" run so they can try
        every recipe immediately. Crystals are bumped to 5 (the max any
        recipe needs)."""
        from Game.utils.items_db import ITEMS, _draw_item_icon, make_inv_item
        self.player.inventory = []
        self.player.equipped_weapon = None
        self.player.crystals = max(self.player.crystals, 5)
        for key in ITEMS.keys():
            if key == "crystal":
                continue
            inv_item = make_inv_item(key, 1)
            inv_item["icon"] = _draw_item_icon(key, 32)
            self.player.inventory.append(inv_item)

    def _trigger_intro_dialogue(self):
        """Queue the opening 'wake-up' lines the first time the player
        enters gameplay. Loaded from intro.dlg so it can be edited without
        touching Python code. Plays once per process run."""
        if self._intro_played:
            return
        self._intro_played = True
        try:
            texts, speakers = load_dlg("Game/assets/dialogue/intro.dlg")
            self.dialogue.start_multi(texts, speakers)
        except Exception as exc:
            print(f"[dialogue] Could not load intro.dlg: {exc}")
            self.dialogue.start(["..."], speaker="Box")

    def _ensure_fog_surfaces(self):
        """Lazily build (and rebuild on resize/radius change) the two fog
        surfaces we need: a screen-sized scratch surface to dye black each
        frame, and a small "hole stamp" with a radial alpha falloff that we
        subtract to carve a soft visibility hole around the player.

        Both are cached so the per-frame cost is just one fill, one blit
        with BLEND_RGBA_SUB, and one final blit — no surface allocations
        and no expensive transparent gradient generation."""
        sw = self.screen.get_width()
        sh = self.screen.get_height()
        need_overlay = (
            self._fog_overlay is None
            or self._fog_overlay.get_size() != (sw, sh)
        )
        if need_overlay:
            self._fog_overlay = pygame.Surface((sw, sh), pygame.SRCALPHA).convert_alpha()

        radius = int(self.fog_radius)
        if (
            self._fog_hole_stamp is None
            or self._fog_hole_radius_built != radius
        ):
            size = radius * 2
            stamp = pygame.Surface((size, size), pygame.SRCALPHA).convert_alpha()
            steps = 18
            for i in range(steps - 1, -1, -1):
                t = i / (steps - 1)
                r = int(radius * t)
                if r <= 0:
                    continue
                a = int(255 * (1.0 - t) ** 1.6)
                pygame.draw.circle(stamp, (255, 255, 255, a), (radius, radius), r)
            self._fog_hole_stamp = stamp
            self._fog_hole_radius_built = radius

    def _apply_fog(self):
        """Dim the world with a circular hole of visibility centered on the
        player. Runs only when fog is enabled and we're not in the editor."""
        if not self.fog_enabled or self.editor_mode or self.title_screen_active or self.debug_mode:
            return
        self._ensure_fog_surfaces()
        assert self._fog_overlay is not None
        assert self._fog_hole_stamp is not None

        overlay = self._fog_overlay
        overlay.fill((0, 0, 0, self.fog_darkness))

        player_screen_x = self.player.rect.centerx - int(self.camera.offset.x)
        player_screen_y = self.player.rect.centery - int(self.camera.offset.y)
        radius = self._fog_hole_radius_built or self.fog_radius
        overlay.blit(
            self._fog_hole_stamp,
            (player_screen_x - radius, player_screen_y - radius),
            special_flags=pygame.BLEND_RGBA_SUB,
        )
        self.screen.blit(overlay, (0, 0))

    def draw(self):
        self.screen.fill((0, 0, 0))

        behind_layer_ids = [l["id"] for l in self.layers if not l["in_front"]]
        front_layer_ids = [l["id"] for l in self.layers if l["in_front"]]

        for tilemap in self.tilemaps.values():
            if tilemap.rendered:
                tilemap.render_supports(self.screen, self.camera.offset)
                for lid in behind_layer_ids:
                    tilemap.render_tiles(self.screen, self.camera.offset, layer_id=lid)

        self.sprite_group.draw(self.screen, self.camera.offset)
        if not self.debug_mode:
            for tilemap in self.tilemaps.values():
                if tilemap.rendered:
                    tilemap.enemies.draw(self.screen, self.camera.offset)
        self.player.draw(self.screen, (0, 0))

        for tilemap in self.tilemaps.values():
            if tilemap.rendered:
                for lid in front_layer_ids:
                    tilemap.render_tiles(self.screen, self.camera.offset, layer_id=lid)
                tilemap.render_overlays(self.screen, self.camera.offset)

        for tilemap in self.tilemaps.values():
            if tilemap.rendered:
                tilemap.render_items(self.screen, self.camera.offset)

        self._apply_fog()

        if self.editor_mode and getattr(self.tilemap, "spawnpoint", None) is not None:
            sx, sy = self.tilemap.spawnpoint
            ts = self.tilemap.tile_size
            mx = sx * ts - self.camera.offset.x
            my = sy * ts - self.camera.offset.y
            pygame.draw.rect(self.screen, (60, 220, 90), (mx, my, ts, ts), 3)
            stxt = self.fonts["workbench"].render("S", True, (60, 220, 90))
            self.screen.blit(
                stxt,
                (
                    mx + ts // 2 - stxt.get_width() // 2,
                    my + ts // 2 - stxt.get_height() // 2,
                ),
            )

        if self.editor_mode and getattr(self, "tilemap", None) is not None:
            ts = self.tilemap.tile_size
            for enemy in list(self.tilemap.enemies.sprite_dict.values()):
                attrs = getattr(enemy, "attributes", {})
                if attrs.get("boss"):
                    color = (220, 80, 220)
                    label_ch = "B"
                elif attrs.get("flying"):
                    color = (80, 180, 255)
                    label_ch = "F"
                else:
                    color = (255, 100, 60)
                    label_ch = "E"
                cx = enemy.rect.centerx - int(self.camera.offset.x)
                cy = enemy.rect.centery - int(self.camera.offset.y)
                r = max(12, ts // 3)
                pygame.draw.circle(self.screen, color, (cx, cy), r, 3)
                etxt = self.fonts["workbench_small"].render(label_ch, True, color)
                self.screen.blit(
                    etxt,
                    (cx - etxt.get_width() // 2, cy - etxt.get_height() // 2),
                )
                gp = getattr(enemy, "_editor_grid_pos", None)
                if gp is not None:
                    spawn_cx = int((gp[0] + 0.5) * ts - self.camera.offset.x)
                    spawn_cy = int((gp[1] + 0.5) * ts - self.camera.offset.y)
                    if abs(spawn_cx - cx) > 4 or abs(spawn_cy - cy) > 4:
                        pygame.draw.circle(
                            self.screen, color, (spawn_cx, spawn_cy), 5, 2
                        )

        self.hud.draw(self.screen)

        if not self.title_screen_active and self.dialogue.active:
            self.dialogue.draw(self.screen)

        if self.debug_mode:
            self._draw_debug_overlay()

        if self.editor_mode:
            self.draw_editor_cursor()

        if self.inventory_open and not self.title_screen_active:
            self.inv_overlay.draw(self.screen, self.player.inventory)

        if self.crafting_open and not self.title_screen_active:
            self.craft_overlay.draw(self.screen)

        if self.demo_complete_visible:
            self.draw_demo_complete()
        elif self.death_screen_visible:
            self.draw_death_screen()
        elif self.paused:
            self.draw_pause()
        elif self.editor_mode:
            self.draw_editor()

        pygame.display.flip()

    def update(self, dt):
        events = []
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            events.append(event)

            if event.type == pygame.VIDEORESIZE:
                self._handle_resize(event.w, event.h)

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if self.crafting_open:
                        self.crafting_open = False
                    elif self.inventory_open:
                        self.inventory_open = False
                    elif self.death_screen_visible:
                        self.title_screen_active = True
                        self.title_screen = TitleScreen(self)
                        self._restart_game()
                    elif self.editor_mode:
                        self.editor_mode = False
                    else:
                        self.paused = not self.paused

                if self.paused and self._pwd_asking:
                    if event.key == pygame.K_RETURN or event.key == pygame.K_KP_ENTER:
                        if self._pwd_buf == "RAVEN":
                            self._dev_unlocked = True
                            self.hud.show_toast("Modo dev desbloqueado")

                            if self._pwd_pending_action == "debug":
                                self.debug_mode = not self.debug_mode
                                self.debug_fly = self.debug_mode
                                if self.debug_fly:
                                    self.player.velocity.x = 0
                                    self.player.velocity.y = 0
                            elif self._pwd_pending_action == "build":
                                self.paused = False
                                self.editor_mode = True
                        else:
                            self.hud.show_toast("Código incorrecto")

                        self._pwd_buf = ""
                        self._pwd_asking = False
                        self._pwd_pending_action = None
                    elif event.key == pygame.K_BACKSPACE:
                        self._pwd_buf = self._pwd_buf[:-1]
                    elif event.key == pygame.K_ESCAPE:
                        self._pwd_asking = False
                        self._pwd_buf = ""
                        self._pwd_pending_action = None
                    elif event.unicode and event.unicode.isprintable() and len(self._pwd_buf) < 16:
                        self._pwd_buf += event.unicode.upper()

                if (
                    self._dev_unlocked
                    and event.key == pygame.K_e
                    and not self.paused
                    and not self.death_screen_visible
                    and not self.dialogue.active
                ):
                    self.editor_mode = not self.editor_mode

                if (
                    event.key == pygame.K_z
                    and not self.paused
                    and not self.death_screen_visible
                    and not self.editor_mode
                    and not self.dialogue.active
                    and not self.demo_complete_visible
                ):
                    _door_tiles = [(33, 8), (33, 9), (34, 9)]
                    _ts = self.tilemap.tile_size
                    _player_inflated = self.player.rect.inflate(_ts, _ts)
                    _near_door = any(
                        _player_inflated.colliderect(
                            pygame.Rect(gx * _ts, gy * _ts, _ts, _ts)
                        )
                        for gx, gy in _door_tiles
                    )
                    if _near_door:
                        _has_key = any(
                            it.get("id") == "key" for it in self.player.inventory
                        )
                        if _has_key:
                            self.player.inventory = [
                                it for it in self.player.inventory
                                if it.get("id") != "key"
                            ]
                            for _gx, _gy in _door_tiles:
                                self.tilemap.erase_tile(_gx, _gy)
                            _texts, _speakers = load_dlg(
                                "Game/assets/dialogue/door_unlock.dlg"
                            )
                            self.dialogue.start_multi(_texts, _speakers)
                            self._demo_complete_pending = True
                        else:
                            self.hud.show_toast("Necesitas una llave")
                    else:
                        for tilemap in self.tilemaps.values():
                            if not tilemap.rendered:
                                continue
                            for box in list(tilemap.interact_boxes.sprite_dict.values()):
                                if box.player_overlapping():
                                    box.interact()
                                    break

                if self._dev_unlocked and event.key == pygame.K_F3:
                    self.debug_mode = not self.debug_mode
                    self.debug_fly = self.debug_mode
                    if self.debug_fly:
                        self.player.velocity.x = 0
                        self.player.velocity.y = 0

                if event.key == pygame.K_F4:
                    self.fog_enabled = not self.fog_enabled

                if (
                    event.key == pygame.K_F5
                    and not self.editor_mode
                    and not self.title_screen_active
                    and not self.death_screen_visible
                ):
                    _slot = getattr(self, "_active_save_slot", 0)
                    if _save_game_to_disk(self, _slot):
                        self.hud.show_toast(f"Partida guardada (Slot {_slot + 1})")
                    else:
                        self.hud.show_toast("Error al guardar")

                if (
                    event.key == pygame.K_i
                    and not self.death_screen_visible
                    and not self.editor_mode
                    and not self.title_screen_active
                ):
                    self.inventory_open = not self.inventory_open
                    if self.inventory_open:
                        self.crafting_open = False

                if (
                    event.key == pygame.K_c
                    and not self.death_screen_visible
                    and not self.editor_mode
                    and not self.title_screen_active
                ):
                    if self.player.crystals >= 1:
                        self.player.crystals -= 1
                        self.player.attributes["health"] = self.player.attributes["maxhealth"]
                        if hasattr(self.hud, "show_toast"):
                            self.hud.show_toast("Curado con un cristal")

                if self.editor_mode:
                    if event.key == pygame.K_LEFTBRACKET:
                        self.brush_size = max(1, self.brush_size - 1)
                    elif event.key == pygame.K_RIGHTBRACKET:
                        self.brush_size = min(10, self.brush_size + 1)

            if event.type == pygame.MOUSEWHEEL:
                if self.editor_mode:
                    mx, _ = pygame.mouse.get_pos()
                    sw_active = self._editor_active_sidebar_w()
                    if mx < sw_active and not self.editor_minimized:
                        self.editor_sidebar_scroll += event.y * 30
                        if self.editor_sidebar_scroll > 0:
                            self.editor_sidebar_scroll = 0
                        layout = self._editor_layout()
                        sticky_top = layout["save_rect"].top - 8
                        palette_bottom = layout.get(
                            "palette_bottom_y",
                            layout.get("sidebar_content_bottom", sticky_top),
                        )
                        max_negative = min(0, sticky_top - palette_bottom)
                        if self.editor_sidebar_scroll < max_negative:
                            self.editor_sidebar_scroll = max_negative

            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1 and not self.title_screen_active:
                    mx, my = pygame.mouse.get_pos()
                    if self.inventory_open:
                        self.inv_overlay.handle_click(mx, my)
                        continue
                    if self.crafting_open:
                        self.craft_overlay.handle_click(mx, my)
                        continue

                if self.demo_complete_visible and event.button == 1:
                    menu_rect = self.draw_demo_complete()
                    if self._is_hovered(menu_rect):
                        self.demo_complete_visible = False
                        self.title_screen_active = True
                        self.title_screen = TitleScreen(self)
                        self._restart_game()
                    continue

                if self.death_screen_visible and event.button == 1:
                    menu_rect = self.draw_death_screen()
                    if self._is_hovered(menu_rect):
                        self.title_screen_active = True
                        self.title_screen = TitleScreen(self)
                        self._restart_game()
                    continue

                if self.paused:
                    pause_rects = self.draw_pause()
                    resume_rect, debug_rect, build_rect, menu_rect, quit_rect = pause_rects

                    if self._pwd_asking:
                        if resume_rect and self._is_hovered(resume_rect):
                            self._pwd_asking = False
                            self._pwd_buf = ""
                            self._pwd_pending_action = None
                    else:
                        if self._is_hovered(resume_rect):
                            self.paused = False
                        elif debug_rect and self._is_hovered(debug_rect):
                            if not self._dev_unlocked:
                                self._pwd_asking = True
                                self._pwd_pending_action = "debug"
                                self._pwd_buf = ""
                            else:
                                self.debug_mode = not self.debug_mode
                                self.debug_fly = self.debug_mode
                                if self.debug_fly:
                                    self.player.velocity.x = 0
                                    self.player.velocity.y = 0
                        elif build_rect and self._is_hovered(build_rect):
                            if not self._dev_unlocked:
                                self._pwd_asking = True
                                self._pwd_pending_action = "build"
                                self._pwd_buf = ""
                            else:
                                self.paused = False
                                self.editor_mode = True
                        elif self._is_hovered(menu_rect):
                            self.paused = False
                            self.title_screen_active = True
                            self.title_screen = TitleScreen(self)
                        elif self._is_hovered(quit_rect):
                            self.running = False

                elif self.editor_mode:
                    layout = self._editor_layout()
                    mx, my = pygame.mouse.get_pos()
                    sw_active = self._editor_active_sidebar_w()

                    if layout["toggle"].collidepoint(mx, my) and event.button == 1:
                        self.editor_minimized = not self.editor_minimized
                        continue

                    if not self.editor_minimized and event.button == 1:
                        if layout["save_rect"].collidepoint(mx, my):
                            maps = get_config()["tilemaps"]
                            save_path = "Game/assets/" + maps.get(
                                self.tilemap_current,
                                f"level/{self.tilemap_current}.json",
                            )
                            self.tilemap.save_map(save_path)
                            print(f"Map saved to {save_path}")
                            continue
                        if layout["exit_rect"].collidepoint(mx, my):
                            self.editor_mode = False
                            continue

                        for i, env in enumerate(layout["env_names"]):
                            if layout["env_rects"][i].collidepoint(mx, my):
                                self.selected_env = env
                                if env in self.assets and env != "hud":
                                    self.selected_type = list(self.assets[env].keys())[
                                        0
                                    ]
                                self.selected_variant = 0
                                continue

                        for i, tname in enumerate(layout["type_names"]):
                            if layout["type_rects"][i].collidepoint(mx, my):
                                self.selected_type = tname
                                self.selected_variant = 0
                                continue

                        layer_action_taken = False
                        for i, layer in enumerate(self.layers):
                            r = layout["layer_rects"][i]
                            if r["select"].collidepoint(mx, my):
                                self.selected_layer = layer["id"]
                                layer_action_taken = True
                                break
                            if r["up"].collidepoint(mx, my) and i > 0:
                                self.layers[i - 1], self.layers[i] = (
                                    self.layers[i],
                                    self.layers[i - 1],
                                )
                                layer_action_taken = True
                                break
                            if (
                                r["down"].collidepoint(mx, my)
                                and i < len(self.layers) - 1
                            ):
                                self.layers[i + 1], self.layers[i] = (
                                    self.layers[i],
                                    self.layers[i + 1],
                                )
                                layer_action_taken = True
                                break
                            if r["side"].collidepoint(mx, my):
                                layer["in_front"] = not layer["in_front"]
                                layer_action_taken = True
                                break
                            if (
                                r["delete"].collidepoint(mx, my)
                                and len(self.layers) > 1
                            ):
                                deleted_id = layer["id"]
                                self.layers.pop(i)
                                if self.selected_layer == deleted_id:
                                    self.selected_layer = self.layers[0]["id"]
                                layer_action_taken = True
                                break
                        if layer_action_taken:
                            continue

                        if layout["add_layer"].collidepoint(mx, my):
                            new_id = self.next_layer_id
                            self.next_layer_id += 1
                            self.layers.append({"id": new_id, "in_front": True})
                            self.selected_layer = new_id
                            continue

                        coll_clicked = False
                        for i, ctype in enumerate(self.collision_types):
                            if layout["coll_rects"][i].collidepoint(mx, my):
                                self.selected_collision = ctype
                                coll_clicked = True
                                break
                        if coll_clicked:
                            continue

                        shape_clicked = False
                        for shape, srect in layout.get("shape_rects", []):
                            if srect.collidepoint(mx, my):
                                self.selected_shape = shape
                                shape_clicked = True
                                break
                        if shape_clicked:
                            continue

                        if layout["brush_minus"].collidepoint(mx, my):
                            self.brush_size = max(1, self.brush_size - 1)
                            continue
                        if layout["brush_plus"].collidepoint(mx, my):
                            self.brush_size = min(10, self.brush_size + 1)
                            continue

                        if layout["spawn_rect"].collidepoint(mx, my):
                            self.spawnpoint_mode = not self.spawnpoint_mode
                            if self.spawnpoint_mode:
                                self.enemy_mode = False
                                self.object_mode = False
                            continue

                        if layout["enemy_toggle_rect"].collidepoint(mx, my):
                            self.enemy_mode = not self.enemy_mode
                            if self.enemy_mode:
                                self.spawnpoint_mode = False
                                self.object_mode = False
                            continue

                        if layout["erase_toggle_rect"].collidepoint(mx, my):
                            self.editor_erase_mode = not self.editor_erase_mode
                            continue

                        if layout["object_toggle_rect"].collidepoint(mx, my):
                            self.object_mode = not self.object_mode
                            if self.object_mode:
                                self.spawnpoint_mode = False
                                self.enemy_mode = False
                            continue
                        obj_kind_clicked = False
                        for kind, rect in layout["object_kind_rects"]:
                            if rect.collidepoint(mx, my):
                                self.selected_object_kind = kind
                                self.object_mode = True
                                self.spawnpoint_mode = False
                                self.enemy_mode = False
                                obj_kind_clicked = True
                                break
                        if obj_kind_clicked:
                            continue
                        if layout["enemy_kind_ground"].collidepoint(mx, my):
                            self.selected_enemy_kind = "ground"
                            continue
                        if layout["enemy_kind_flying"].collidepoint(mx, my):
                            self.selected_enemy_kind = "flying"
                            continue
                        if layout["enemy_kind_boss"].collidepoint(mx, my):
                            self.selected_enemy_kind = "boss"
                            continue
                        axis_clicked = False
                        for label, rect in layout["enemy_axis_rects"]:
                            if rect.collidepoint(mx, my):
                                self.selected_enemy_axis = label
                                self.selected_enemy_kind = "flying"
                                axis_clicked = True
                                break
                        if axis_clicked:
                            continue

                        filtered = self._get_editor_palette_for(
                            self.selected_env, self.selected_type
                        )
                        thumb_size = 40
                        cols = max(1, (layout["sidebar_w"] - 20) // (thumb_size + 5))
                        var_top = layout["var_y"]
                        thumb_clicked = False
                        for i, item in enumerate(filtered):
                            col = i % cols
                            row = i // cols
                            x = 10 + col * (thumb_size + 5)
                            y = var_top + row * (thumb_size + 5)
                            if pygame.Rect(x, y, thumb_size, thumb_size).collidepoint(
                                mx, my
                            ):
                                self.selected_env = item["env"]
                                self.selected_type = item["type"]
                                self.selected_variant = item["variant"]
                                thumb_clicked = True
                                break
                        if thumb_clicked:
                            continue

                    if mx >= sw_active and event.button == 1:
                        grid_pos = self._get_mouse_grid_pos()
                        if grid_pos:
                            grid_x, grid_y = grid_pos
                            if self.spawnpoint_mode and self.selected_layer == 1:
                                self.tilemap.spawnpoint = (grid_x, grid_y)
                            elif self.enemy_mode:
                                if self.editor_erase_mode:
                                    self.tilemap.erase_enemy_near(grid_x, grid_y)
                                else:
                                    self.tilemap.place_enemy(
                                        grid_x,
                                        grid_y,
                                        kind=self.selected_enemy_kind,
                                        move_axis=self._current_enemy_axis(),
                                    )
                            elif self.object_mode:
                                if self.editor_erase_mode:
                                    self.tilemap.erase_object_near(grid_x, grid_y)
                                else:
                                    _kind = self.selected_object_kind
                                    if _kind == "crystal":
                                        self.tilemap.place_crystal_pickup(
                                            grid_x, grid_y, value=1
                                        )
                                    elif _kind == "box":
                                        self.tilemap.place_interact_box(
                                            grid_x, grid_y, reward=5
                                        )
                                    else:
                                        self.tilemap.place_item_drop(
                                            grid_x, grid_y, _kind
                                        )
                            else:
                                self.editor_mouse_held = True
                                self._brush_place(grid_x, grid_y)

                    if mx >= sw_active and event.button == 3:
                        grid_pos = self._get_mouse_grid_pos()
                        if grid_pos:
                            grid_x, grid_y = grid_pos
                            if self.enemy_mode:
                                self.tilemap.erase_enemy_near(grid_x, grid_y)
                            elif self.object_mode:
                                self.tilemap.erase_object_near(grid_x, grid_y)
                            else:
                                self.editor_right_held = True
                                self._brush_erase(grid_x, grid_y)

            if event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.editor_mouse_held = False
                if event.button == 3:
                    self.editor_right_held = False

        if self.paused or self.editor_mode:
            if self.editor_mode:
                keys = pygame.key.get_pressed()
                pan_speed = 600
                dx = 0
                dy = 0
                if keys[pygame.K_a] or keys[pygame.K_LEFT]:
                    dx -= 1
                if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
                    dx += 1
                if keys[pygame.K_w] or keys[pygame.K_UP]:
                    dy -= 1
                if keys[pygame.K_s] or keys[pygame.K_DOWN]:
                    dy += 1
                if dx or dy:
                    speed = pan_speed * (
                        2.5 if (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]) else 1.0
                    )
                    self.camera.offset.x += dx * speed * dt
                    self.camera.offset.y += dy * speed * dt

            if (
                self.editor_mode
                and self.editor_mouse_held
                and not self.spawnpoint_mode
                and not self.enemy_mode
                and not self.object_mode
            ):
                grid_pos = self._get_mouse_grid_pos()
                if grid_pos:
                    grid_x, grid_y = grid_pos
                    self._brush_place(grid_x, grid_y)

            if (
                self.editor_mode
                and self.editor_right_held
                and not self.enemy_mode
                and not self.object_mode
            ):
                grid_pos = self._get_mouse_grid_pos()
                if grid_pos:
                    grid_x, grid_y = grid_pos
                    self._brush_erase(grid_x, grid_y)

            if self.paused:
                return
            return

        if self.player.attributes.get("dead"):
            now = pygame.time.get_ticks()
            if self._death_at_ms is None:
                self._death_at_ms = now
            if (
                not self.death_screen_visible
                and now - self._death_at_ms >= self._death_delay_ms
            ):
                REVIVE_COST = 5
                if self.player.crystals >= REVIVE_COST:
                    self.player.crystals -= REVIVE_COST
                    self.player.attributes["dead"] = False
                    self.player.attributes["death_animation_complete"] = False
                    self.player.attributes["visible"] = True
                    self.player.attributes["can_move"] = True
                    self.player.attributes["damaged"] = False
                    self.player.attributes["stun"] = False
                    self.player.attributes["health"] = self.player.attributes["maxhealth"]
                    self.player.attributes["damage_cooldown"] = 0
                    self.player.timers["invulnerability"] = 1500
                    self.player.timers["damage"] = 0
                    self.player.velocity = pygame.math.Vector2(0, 0)
                    self.player.animation = "idle"
                    self.player.frame = 0
                    if getattr(self.tilemap, "spawnpoint", None) is not None:
                        sx, sy = self.tilemap.spawnpoint
                        self.player.rect.topleft = (
                            sx * self.tilemap.tile_size,
                            sy * self.tilemap.tile_size,
                        )
                        self._snap_player_above_ground()
                    self._death_at_ms = None
                    if hasattr(self.hud, "show_toast"):
                        self.hud.show_toast(f"Renacido — {REVIVE_COST} cristales perdidos")
                else:
                    self.death_screen_visible = True
        else:
            self._death_at_ms = None
            self.death_screen_visible = False

        if self.death_screen_visible:
            self.player.update(dt, events)
            return

        if not self._intro_played and hasattr(self, "_intro_delay") and self._intro_delay > 0:
            self._intro_delay -= dt
            if self._intro_delay <= 0:
                self._trigger_intro_dialogue()

        if self.inventory_open:
            self.hud.update(dt)
            return

        if self.dialogue.active:
            self.dialogue.update(dt, events)
            self.hud.update(dt)
            return

        if self._demo_complete_pending and not self.dialogue.active:
            self._demo_complete_pending = False
            self.demo_complete_visible = True

        if self.demo_complete_visible:
            self.hud.update(dt)
            return

        if not self.title_screen_active and not self.paused:
            _active_boss = self.hud._find_active_boss()
            if _active_boss is not None and not self._boss_music_active:
                self._boss_music_active = True
                self._play_music("Game/assets/music/boss.wav", volume=0.7)
            elif _active_boss is None and self._boss_music_active:
                self._boss_music_active = False
                _level_track = self._level_music.get(self.tilemap_current)
                if _level_track:
                    self._play_music(_level_track, volume=0.4)
                else:
                    self._stop_music()

        self.sprite_group.update(dt)
        self.player.update(dt, events)
        self.hud.update(dt)
        if self.crafting_open:
            self.craft_overlay.update(dt)
        for tilemap in self.tilemaps.values():
            tilemap.update(dt)
            if tilemap.rendered and not self.debug_mode:
                px = self.player.rect.centerx
                py = self.player.rect.centery
                rd2 = self.render_distance * self.render_distance
                for enemy in list(tilemap.enemies.sprite_dict.values()):
                    ex = enemy.rect.centerx
                    ey = enemy.rect.centery
                    if (ex - px) ** 2 + (ey - py) ** 2 <= rd2:
                        enemy.update(dt)

    def run(self):
        while self.running:
            self._play_music(self._menu_music_path, volume=0.5)
            while self.running and self.title_screen_active:
                dt = self.clock.tick(60) / 1000

                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self.running = False
                    if event.type == pygame.VIDEORESIZE:
                        self._handle_resize(event.w, event.h)
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button == 1:
                            self.title_screen.handle_click()
                    if event.type == pygame.KEYDOWN:
                        if event.key in (pygame.K_w, pygame.K_UP):
                            self.title_screen.move_selection(-1)
                        elif event.key in (pygame.K_s, pygame.K_DOWN):
                            self.title_screen.move_selection(1)
                        elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                            self.title_screen.activate_selected()
                        elif event.key == pygame.K_e:
                            self.title_screen.start_fade_out("editor")
                        elif event.key == pygame.K_ESCAPE:
                            if not self.title_screen.handle_escape():
                                self.running = False

                result = self.title_screen.update(dt)
                self._update_title_ambient(dt)
                self.title_screen.draw()
                pygame.display.flip()

                if result == "play":
                    self.title_screen_active = False
                    self._active_save_slot = 0
                    self._grant_all_combo_items()
                elif isinstance(result, str) and result.startswith("continue"):
                    slot = 0
                    if ":" in result:
                        try:
                            slot = int(result.split(":", 1)[1])
                        except ValueError:
                            slot = 0
                    self.title_screen_active = False
                    self._pending_load = True
                    self._pending_load_slot = slot
                    self._active_save_slot = slot
                elif result == "editor":
                    self.title_screen_active = False
                    self.editor_mode = True
                elif result == "quit":
                    self.running = False

            if not self.running:
                break

            if self._pending_load:
                _slot_to_load = self._pending_load_slot
                if _apply_save_to_game(self, _load_save_from_disk(_slot_to_load)):
                    self._loaded_from_save = True
                    self._intro_played = True
                    self._active_save_slot = _slot_to_load
                self._snap_player_above_ground()
                self._pending_load = False
                self._pending_load_slot = 0

            level_track = self._level_music.get(self.tilemap_current)
            if level_track is not None:
                self._play_music(level_track, volume=0.4)
            else:
                self._stop_music()

            if not self.editor_mode and not self._intro_played:
                self._intro_delay = 0.6

            while self.running and not self.title_screen_active:
                dt = self.clock.tick(60) / 1000
                self.draw()
                self.update(dt)

            if self.running and self.title_screen_active:
                self.title_screen = TitleScreen(self)

        self._stop_music()
