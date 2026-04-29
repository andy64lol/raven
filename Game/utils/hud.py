import pygame
import random

from Game.utils.transisitions import Fadeout
from Game.utils.utils import load_image


class Hud:
    def __init__(self, game):
        self.game = game
        self.player = self.game.player
        self.assets = self.game.assets["hud"]

        self.hearts_assets = self.assets["heart"]
        self.heart_size = 24
        self.health = 0

        self.shine_interval = 3.0
        self.shine_duration = 1.0

        self.fadeout = Fadeout(duration=3, color=(0, 0, 0))

        self.crystal_icon = pygame.Surface((16, 16))
        self.crystal_icon.fill((0, 255, 255))  # Cyan color as placeholder
        pygame.draw.circle(self.crystal_icon, (255, 255, 255), (8, 8), 6, 2)  # White outline

        self._panel_origin = (14, 10)
        self._panel_padding_x = 12
        self._panel_padding_y = 10
        self._heart_spacing = self.heart_size + 4   # tight, no overlap

        self._toast_text = ""
        self._toast_until_ms = 0

        self.hearts = {}
        self._heart_count = 0
        self._rebuild_hearts(self.player.attributes["maxhealth"])

    def _rebuild_hearts(self, max_health):
        if max_health == self._heart_count and self.hearts:
            return
        self._heart_count = max_health
        self.hearts = {}
        current_health = self.player.attributes.get("health", max_health)
        for i in range(1, max_health + 1):
            key = str(i)
            x = self._panel_origin[0] + self._panel_padding_x + (i - 1) * self._heart_spacing
            y = self._panel_origin[1] + self._panel_padding_y
            state = "full" if i <= current_health else "empty"
            self.hearts[key] = {
                "pos": (x, y),
                "state": state,
                "animation_state": ("full", 0),
                "rect": pygame.Rect(x, y, self.heart_size, self.heart_size),
                "shine_timer": random.uniform(0, self.shine_interval),
            }

    def show_toast(self, text, duration_ms=1800):
        """Briefly display a message in the top-right of the HUD."""
        self._toast_text = text
        self._toast_until_ms = pygame.time.get_ticks() + duration_ms

    def update(self, dt):
        max_health = self.player.attributes["maxhealth"]
        current_health = self.player.attributes["health"]
        self._rebuild_hearts(max_health)

        for i in range(1, max_health + 1):
            heart_key = str(i)
            if i <= current_health:
                if self.hearts[heart_key]["state"] != "full":
                    self.hearts[heart_key]["state"] = "full"
                    self.hearts[heart_key]["animation_state"] = ("blink", 0)
            else:
                self.hearts[heart_key]["state"] = "empty"
                self.hearts[heart_key]["animation_state"] = ("full", 0)

        for heart_data in self.hearts.values():
            if heart_data["state"] == "full":
                heart_data["shine_timer"] -= dt

                if heart_data["shine_timer"] <= 0 and heart_data["animation_state"][0] == "full":
                    heart_data["animation_state"] = ("shine", 0)
                    heart_data["shine_timer"] = self.shine_interval + random.uniform(-0.5, 0.5)

                elif heart_data["animation_state"][0] == "shine":
                    frame_count = len(self.hearts_assets["shine"].images)
                    total_shine_frames = frame_count * 5
                    if heart_data["animation_state"][1] >= total_shine_frames - 1:
                        heart_data["animation_state"] = ("full", 0)

        self._tick_heart_animations(dt)

    def _tick_heart_animations(self, dt):
        step = dt * 60  # 1.0 per frame at 60fps -> matches legacy timing
        for heart_data in self.hearts.values():
            if heart_data["state"] != "full":
                continue
            anim_name, counter = heart_data["animation_state"]
            counter = counter + step

            if anim_name == "blink":
                frame_count = len(self.hearts_assets["blink"].images)
                if counter // 5 >= frame_count:
                    heart_data["animation_state"] = ("full", 0)
                else:
                    heart_data["animation_state"] = ("blink", counter)

            elif anim_name == "shine":
                frame_count = len(self.hearts_assets["shine"].images)
                total_shine_frames = frame_count * 5
                if counter >= total_shine_frames - 1:
                    heart_data["animation_state"] = ("full", 0)
                else:
                    heart_data["animation_state"] = ("shine", counter)

    def update_heart_animations(self):
        pass

    def _find_active_boss(self):
        """Return the first living UndeadExecutionerBoss near the player, or None."""
        tilemap = getattr(self.game, "tilemap", None)
        if tilemap is None:
            return None
        try:
            from Game.Sprites.Enemies.boss import UndeadExecutionerBoss
        except Exception:
            return None
        player = getattr(self.game, "player", None)
        for enemy in getattr(tilemap, "enemies", ()):
            if not (isinstance(enemy, UndeadExecutionerBoss) and getattr(enemy, "health", 0) > 0):
                continue
            if player is not None:
                dx = player.rect.centerx - enemy.rect.centerx
                dy = player.rect.centery - enemy.rect.centery
                dist = (dx * dx + dy * dy) ** 0.5
                if dist > getattr(enemy, "sight_range", 700):
                    continue
            return enemy
        return None

    def draw_boss_bar(self, screen, boss):
        """Simple hand-drawn boss bar: panel + name + health bar."""
        sw = screen.get_width()

        bar_w = min(420, sw - 40)
        bar_h = 14
        x = (sw - bar_w) // 2

        label = self.game.fonts["workbench"].render(
            "Verdugo No-Muerto", True, (230, 210, 180)
        )
        label_y = 10
        bar_y = label_y + label.get_height() + 4

        pad = 8
        panel = pygame.Surface(
            (bar_w + pad * 2, label.get_height() + bar_h + pad * 2 + 4),
            pygame.SRCALPHA,
        )
        panel.fill((0, 0, 0, 160))
        screen.blit(panel, (x - pad, label_y - pad))

        screen.blit(label, (x + (bar_w - label.get_width()) // 2, label_y))

        max_hp = max(1, getattr(boss, "max_health", 1))
        ratio = max(0.0, min(1.0, boss.health / max_hp))

        pygame.draw.rect(screen, (60, 20, 20), (x, bar_y, bar_w, bar_h))
        if ratio > 0:
            r = int(180 + 75 * (1 - ratio))
            g = int(30 + 80 * ratio)
            fill_color = (min(255, r), g, 20)
            pygame.draw.rect(screen, fill_color, (x, bar_y, int(bar_w * ratio), bar_h))
        pygame.draw.rect(screen, (160, 130, 90), (x, bar_y, bar_w, bar_h), 2)

    def draw(self, screen):
        if self.player.attributes["health"] > 0:
            self.draw_hud(screen)
            boss = self._find_active_boss()
            if boss is not None:
                self.draw_boss_bar(screen, boss)
        else:
            self.fadeout.draw(screen)
            if self.fadeout.opacity >= 255:
                text_surface = self.game.fonts["workbench"].render("Has Muerto", True, (255, 255, 255))
                text_surface = pygame.transform.scale(text_surface, (text_surface.get_width() * 4, text_surface.get_height() * 4))
                text_rect = text_surface.get_rect(center=(self.game.screen.get_width() // 2, self.game.screen.get_height() // 2))
                screen.blit(text_surface, text_rect)

    def draw_hud(self, screen):
        if self.health > self.player.attributes["health"]:
            self.health = self.player.attributes["health"]
            for key, heart_data in enumerate(self.hearts.values()):
                if heart_data["state"] == "full":
                    heart_data["animation_state"] = ("blink", 0)
                if self.player.attributes["health"] == key + 1:
                    heart_data["animation_state"] = ("blink", 0)
        self.health = self.player.attributes["health"]

        max_health = self.player.attributes["maxhealth"]

        panel_w = self._panel_padding_x * 2 + max_health * self._heart_spacing - 4
        panel_h = self._panel_padding_y * 2 + self.heart_size
        panel_rect = pygame.Rect(self._panel_origin[0], self._panel_origin[1], panel_w, panel_h)
        panel_surf = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(panel_surf, (0, 0, 0, 170), panel_surf.get_rect(), border_radius=10)
        pygame.draw.rect(panel_surf, (90, 130, 170, 180), panel_surf.get_rect(), width=1, border_radius=10)
        screen.blit(panel_surf, panel_rect.topleft)

        for heart in self.hearts:
            heart_data = self.hearts[heart]

            if heart_data["state"] == "full":
                anim = heart_data["animation_state"][0]

                if anim == "full":
                    image = pygame.transform.scale(self.hearts_assets["full"], (self.heart_size, self.heart_size))
                    screen.blit(image, heart_data["pos"])

                elif anim == "shine":
                    frame = int(heart_data["animation_state"][1] // 5)
                    frame_count = len(self.hearts_assets["shine"].images)
                    if 0 <= frame < frame_count:
                        image = pygame.transform.scale(self.hearts_assets["shine"].images[list(self.hearts_assets["shine"].images.keys())[frame]], (self.heart_size, self.heart_size))
                        screen.blit(image, heart_data["pos"])
                    else:
                        image = pygame.transform.scale(self.hearts_assets["full"], (self.heart_size, self.heart_size))
                        screen.blit(image, heart_data["pos"])

                elif anim == "blink":
                    frame = int(heart_data["animation_state"][1] // 5)
                    frame_count = len(self.hearts_assets["blink"].images)
                    if 0 <= frame < frame_count:
                        image = pygame.transform.scale(self.hearts_assets["blink"].images[list(self.hearts_assets["blink"].images.keys())[frame]], (self.heart_size, self.heart_size))
                        screen.blit(image, heart_data["pos"])
                    else:
                        image = pygame.transform.scale(self.hearts_assets["full"], (self.heart_size, self.heart_size))
                        screen.blit(image, heart_data["pos"])

                else:
                    image = pygame.transform.scale(self.hearts_assets["full"], (self.heart_size, self.heart_size))
                    screen.blit(image, heart_data["pos"])

            elif heart_data["state"] == "empty":
                image = pygame.transform.scale(self.hearts_assets["empty"], (self.heart_size, self.heart_size))
                screen.blit(image, heart_data["pos"])

        crystal_y = panel_rect.bottom + 6
        crystal_x = panel_rect.left
        count_text = str(self.player.crystals)
        count_surf = self.game.fonts["workbench_small"].render(count_text, True, (255, 255, 255))
        pill_w = 16 + 6 + count_surf.get_width() + 16
        pill_h = 22
        pill_surf = pygame.Surface((pill_w, pill_h), pygame.SRCALPHA)
        pygame.draw.rect(pill_surf, (0, 0, 0, 170), pill_surf.get_rect(), border_radius=11)
        pygame.draw.rect(pill_surf, (90, 130, 170, 180), pill_surf.get_rect(), width=1, border_radius=11)
        screen.blit(pill_surf, (crystal_x, crystal_y))
        screen.blit(load_image("miscellaneous/crystal.png", size=(14, 14)),
                    (crystal_x + 8, crystal_y + (pill_h - 14) // 2))
        screen.blit(count_surf, (crystal_x + 8 + 14 + 6, crystal_y + (pill_h - count_surf.get_height()) // 2))

        armor_assets = self.assets.get("armor")
        if armor_assets:
            icon_size = 16
            icon_gap = 4
            order = ["general", "silver", "golden"]
            ax = crystal_x + pill_w + 8
            ay = crystal_y + (pill_h - icon_size) // 2
            for key in order:
                icon = armor_assets.get(key)
                if icon is None:
                    continue
                scaled = pygame.transform.scale(icon, (icon_size, icon_size))
                screen.blit(scaled, (ax, ay))
                ax += icon_size + icon_gap

        if self._toast_text and pygame.time.get_ticks() < self._toast_until_ms:
            toast_surf = self.game.fonts["workbench_small"].render(
                self._toast_text, True, (220, 240, 255)
            )
            pad_x, pad_y = 14, 8
            tw = toast_surf.get_width() + pad_x * 2
            th = toast_surf.get_height() + pad_y * 2
            tx = screen.get_width() - tw - 16
            ty = 16
            bg = pygame.Surface((tw, th), pygame.SRCALPHA)
            pygame.draw.rect(bg, (0, 0, 0, 180), bg.get_rect(), border_radius=10)
            pygame.draw.rect(bg, (90, 180, 255, 200), bg.get_rect(), width=1, border_radius=10)
            screen.blit(bg, (tx, ty))
            screen.blit(toast_surf, (tx + pad_x, ty + pad_y))
