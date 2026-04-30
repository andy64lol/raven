import pygame
import random
import math
import webbrowser

from Game.utils.utils import load_image, SpriteSheet

PLAY_BUTTON_URL = "https://music.youtube.com/watch?v=dQw4w9WgXcQ"

class Particle:
    """Floating crystal/dust particle with glow effect."""

    def __init__(self, screen_width, screen_height):
        self.x = random.uniform(0, screen_width)
        self.y = random.uniform(0, screen_height)
        self.size = random.uniform(1, 4)
        self.speed_y = random.uniform(-10, -30)
        self.speed_x = random.uniform(-5, 5)
        self.life = random.uniform(2, 5)
        self.max_life = self.life
        self.color = random.choice(
            [
                (100, 200, 255),
                (150, 220, 255),
                (200, 240, 255),
                (80, 180, 220),
                (120, 255, 200),
            ]
        )
        self.pulse = random.uniform(0, math.pi * 2)
        self.pulse_speed = random.uniform(1, 3)

    def update(self, dt):
        self.y += self.speed_y * dt
        self.x += self.speed_x * dt
        self.life -= dt
        self.pulse += self.pulse_speed * dt

    def draw(self, surf):
        alpha = max(0, min(255, int(255 * (self.life / self.max_life))))
        pulse_size = self.size + math.sin(self.pulse) * 1
        glow_surf = pygame.Surface(
            (int(pulse_size * 6), int(pulse_size * 6)), pygame.SRCALPHA
        )
        center = int(pulse_size * 3)

        pygame.draw.circle(
            glow_surf, (*self.color, alpha // 4), (center, center), int(pulse_size * 3)
        )

        pygame.draw.circle(
            glow_surf,
            (*self.color, alpha // 2),
            (center, center),
            int(pulse_size * 1.5),
        )

        pygame.draw.circle(
            glow_surf, (255, 255, 255, alpha), (center, center), max(1, int(pulse_size))
        )
        surf.blit(glow_surf, (int(self.x - center), int(self.y - center)))

    def is_dead(self, screen_height):
        return self.life <= 0 or self.y < -20

class TitleScreen:
    def __init__(self, game):
        self.game = game
        self.screen = game.screen
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()
        self.fonts = game.fonts

        self.fade_in_opacity = 255
        self.fade_in_speed = 255 / (1.5 * 60)
        self.fading_out = False
        self.fade_out_opacity = 0
        self.fade_out_speed = 255 / (1.0 * 60)
        self.next_state = None

        self.parallax_layers = self._build_parallax_layers()
        self.parallax_offsets = [0.0] * len(self.parallax_layers)

        self.particles = []
        self.particle_spawn_timer = 0
        self.max_particles = 60

        self.idle_sheet = SpriteSheet(
            "raven/sprite_1.webp", tile_size=64
        )
        self.idle_images = self.idle_sheet.get_images_list()
        self.idle_frame = 0
        self.idle_frame_duration = 8
        self.idle_scale = 3
        self.idle_pos = (self.screen_width // 2, self.screen_height // 2 + 40)
        self._character_rect: pygame.Rect | None = None

        self.title_text = "RAVEN"
        self.title_font_size = 36
        self.title_font = pygame.font.Font(
            "Game/assets/fonts/workbench.ttf", self.title_font_size
        )
        self.demo_tag_font = pygame.font.Font(
            "Game/assets/fonts/workbench.ttf", 14
        )
        self.title_pulse = 0
        self.title_base_y = 80

        self.button_width = 240
        self.button_height = 52
        self.button_gap = 18
        buttons_y_start = self.screen_height // 2 + 120

        button_specs = [
            ("JUGAR", "play"),
            ("SALIR", "quit"),
        ]
        self.buttons = []
        for idx, (text, action) in enumerate(button_specs):
            self.buttons.append({
                "text": text,
                "action": action,
                "y": buttons_y_start + idx * (self.button_height + self.button_gap),
            })
        self.hovered_button = None
        self.selected_index = 0
        self.button_glow = 0

        self._button_font = pygame.font.Font("Game/assets/fonts/workbench.ttf", 14)

        try:
            self._button_plate = load_image("UI/dark ui large-long plate.png")
        except Exception:
            self._button_plate = None

        self._footer_font = pygame.font.Font("Game/assets/fonts/workbench.ttf", 10)
        self._version_label = "v0.1"

        self._vignette = self._build_vignette()

        self.decor_crystals = self._build_decor_crystals()

    def _build_parallax_layers(self):
        """Background parallax disabled — the main menu now has no scenic
        backdrop, just the solid base fill, particles, character, and title."""
        return []

    def _build_vignette(self):
        """Pre-render a soft radial darkening overlay applied on top of the screen."""
        sw, sh = self.screen_width, self.screen_height
        vignette = pygame.Surface((sw, sh), pygame.SRCALPHA)

        steps = 28
        max_alpha = 140
        for i in range(steps):
            t = i / (steps - 1)
            alpha = int(max_alpha * (t**2.2))
            pad_x = int(sw * 0.04 * (1 - t))
            pad_y = int(sh * 0.04 * (1 - t))
            shrink = int(min(sw, sh) * 0.5 * (1 - t))
            rect = pygame.Rect(
                pad_x + shrink,
                pad_y + shrink,
                sw - 2 * (pad_x + shrink),
                sh - 2 * (pad_y + shrink),
            )
            if rect.width <= 0 or rect.height <= 0:
                continue
            ring = pygame.Surface((sw, sh), pygame.SRCALPHA)
            pygame.draw.ellipse(ring, (0, 0, 0, alpha), rect)
            vignette.blit(ring, (0, 0), special_flags=pygame.BLEND_RGBA_MAX)

        final = pygame.Surface((sw, sh), pygame.SRCALPHA)
        final.fill((0, 0, 0, max_alpha))

        final.blit(vignette, (0, 0), special_flags=pygame.BLEND_RGBA_SUB)
        return final

    def _build_decor_crystals(self):
        """Place decorative crystals around the title screen."""
        crystals = []
        try:
            crystal_img = load_image("miscellaneous/crystal.png")
            positions = [
                (60, self.screen_height - 80),
                (self.screen_width - 60, self.screen_height - 100),
                (120, self.screen_height - 60),
                (self.screen_width - 120, self.screen_height - 70),
                (self.screen_width // 2 - 150, self.screen_height - 50),
                (self.screen_width // 2 + 150, self.screen_height - 50),
            ]
            for pos in positions:
                scale = random.uniform(0.8, 1.5)
                img = pygame.transform.scale(
                    crystal_img, (int(24 * scale), int(24 * scale))
                )
                crystals.append(
                    {
                        "img": img,
                        "pos": pos,
                        "bob": random.uniform(0, math.pi * 2),
                        "bob_speed": random.uniform(1, 2),
                        "glow": random.uniform(0, math.pi * 2),
                    }
                )
        except Exception:
            pass
        return crystals

    def update(self, dt):

        if self.fade_in_opacity > 0:
            self.fade_in_opacity -= self.fade_in_speed
            if self.fade_in_opacity < 0:
                self.fade_in_opacity = 0

        if self.fading_out:
            self.fade_out_opacity += self.fade_out_speed
            if self.fade_out_opacity >= 255:
                self.fade_out_opacity = 255
                return self.next_state

        for i, layer in enumerate(self.parallax_layers):
            self.parallax_offsets[i] += layer["speed"] * dt
            tile_w = layer["tile"].get_width()
            if self.parallax_offsets[i] >= tile_w:
                self.parallax_offsets[i] %= tile_w

        self.particle_spawn_timer -= dt
        if self.particle_spawn_timer <= 0 and len(self.particles) < self.max_particles:
            self.particles.append(Particle(self.screen_width, self.screen_height))
            self.particle_spawn_timer = random.uniform(0.05, 0.2)

        for p in self.particles:
            p.update(dt)
        self.particles = [
            p for p in self.particles if not p.is_dead(self.screen_height)
        ]

        self.idle_frame += self.idle_frame_duration * dt
        if self.idle_images:
            total_frames = len(self.idle_images)
            if int(self.idle_frame) >= total_frames:
                self.idle_frame = 0

        self.title_pulse += dt * 2

        self.button_glow += dt * 4

        for c in self.decor_crystals:
            c["bob"] += c["bob_speed"] * dt
            c["glow"] += dt * 3

        return None

    def draw(self):

        self.screen.fill((5, 5, 15))

        for i, layer in enumerate(self.parallax_layers):
            tile = layer["tile"].copy()
            tile.set_alpha(layer["alpha"])
            tile_w = tile.get_width()
            y = layer["y_offset"]
            offset = self.parallax_offsets[i] % tile_w
            x = -offset
            while x < self.screen_width + tile_w:
                self.screen.blit(tile, (int(x), int(y)))
                x += tile_w

        for p in self.particles:
            p.draw(self.screen)

        for c in self.decor_crystals:
            bob_y = math.sin(c["bob"]) * 4
            pos = (c["pos"][0], c["pos"][1] + bob_y)

            glow_size = 40 + math.sin(c["glow"]) * 10
            glow_surf = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
            pygame.draw.circle(
                glow_surf,
                (0, 200, 255, 30),
                (glow_size // 2, glow_size // 2),
                glow_size // 2,
            )
            self.screen.blit(
                glow_surf,
                (
                    pos[0] - glow_size // 2 + c["img"].get_width() // 2,
                    pos[1] - glow_size // 2 + c["img"].get_height() // 2,
                ),
            )
            self.screen.blit(c["img"], pos)

        if self.idle_images:
            frame_idx = int(self.idle_frame) % len(self.idle_images)
            sprite = self.idle_images[frame_idx]
            scaled = pygame.transform.scale(
                sprite, (144 * self.idle_scale, 144 * self.idle_scale)
            )
            scaled.set_colorkey((0, 0, 0))
            rect = scaled.get_rect(center=self.idle_pos)
            self.screen.blit(scaled, rect)
            self._character_rect = rect

        pulse_scale = 1.0 + math.sin(self.title_pulse) * 0.03
        title_surf = self.title_font.render(self.title_text, True, (220, 240, 255))
        scaled_title = pygame.transform.scale(
            title_surf,
            (
                int(title_surf.get_width() * pulse_scale),
                int(title_surf.get_height() * pulse_scale),
            ),
        )
        title_rect = scaled_title.get_rect(
            center=(self.screen_width // 2, self.title_base_y)
        )

        shadow_surf = self.title_font.render(self.title_text, True, (0, 30, 60))
        shadow_scaled = pygame.transform.scale(
            shadow_surf,
            (
                int(shadow_surf.get_width() * pulse_scale),
                int(shadow_surf.get_height() * pulse_scale),
            ),
        )
        shadow_rect = shadow_scaled.get_rect(
            center=(self.screen_width // 2 + 4, self.title_base_y + 4)
        )
        self.screen.blit(shadow_scaled, shadow_rect)

        glow_pad = 20
        glow_surf = pygame.Surface(
            (
                scaled_title.get_width() + glow_pad * 2,
                scaled_title.get_height() + glow_pad * 2,
            ),
            pygame.SRCALPHA,
        )
        glow_alpha = int(40 + math.sin(self.title_pulse) * 20)
        pygame.draw.ellipse(glow_surf, (0, 100, 180, glow_alpha), glow_surf.get_rect())
        self.screen.blit(glow_surf, (title_rect.x - glow_pad, title_rect.y - glow_pad))

        self.screen.blit(scaled_title, title_rect)

        demo_tag = self.demo_tag_font.render("¡Demo!", True, (255, 200, 100))
        demo_pulse = 1.0 + math.sin(self.title_pulse * 1.5) * 0.1
        demo_scaled = pygame.transform.scale(
            demo_tag,
            (
                int(demo_tag.get_width() * demo_pulse),
                int(demo_tag.get_height() * demo_pulse),
            ),
        )
        demo_rect = demo_scaled.get_rect(
            topleft=(title_rect.right + 12, title_rect.top + 8)
        )

        demo_shadow = self.demo_tag_font.render("¡Demo!", True, (80, 60, 0))
        demo_shadow_scaled = pygame.transform.scale(
            demo_shadow,
            (
                int(demo_shadow.get_width() * demo_pulse),
                int(demo_shadow.get_height() * demo_pulse),
            ),
        )
        demo_shadow_rect = demo_shadow_scaled.get_rect(
            topleft=(demo_rect.left + 2, demo_rect.top + 2)
        )
        self.screen.blit(demo_shadow_scaled, demo_shadow_rect)

        demo_glow_alpha = int(30 + math.sin(self.title_pulse * 1.5) * 15)
        demo_glow_surf = pygame.Surface(
            (demo_scaled.get_width() + 12, demo_scaled.get_height() + 12),
            pygame.SRCALPHA,
        )
        pygame.draw.ellipse(
            demo_glow_surf,
            (255, 150, 50, demo_glow_alpha),
            demo_glow_surf.get_rect(),
        )
        self.screen.blit(
            demo_glow_surf,
            (demo_rect.x - 6, demo_rect.y - 6),
        )

        self.screen.blit(demo_scaled, demo_rect)

        subtitle_font = pygame.font.Font("Game/assets/fonts/workbench.ttf", 11)
        subtitle = subtitle_font.render(
            "Aventura en las Profundidades", True, (150, 170, 190)
        )
        subtitle_rect = subtitle.get_rect(
            center=(self.screen_width // 2, self.title_base_y + 50)
        )

        subtitle_glow = pygame.Surface(
            (subtitle_rect.width + 20, subtitle_rect.height + 8),
            pygame.SRCALPHA,
        )
        pygame.draw.rect(
            subtitle_glow,
            (100, 150, 200, 20),
            subtitle_glow.get_rect(),
            border_radius=4,
        )
        self.screen.blit(
            subtitle_glow,
            (subtitle_rect.x - 10, subtitle_rect.y - 4),
        )

        self.screen.blit(subtitle, subtitle_rect)

        mx, my = pygame.mouse.get_pos()
        self.hovered_button = None
        for idx, btn in enumerate(self.buttons):
            rect = pygame.Rect(0, 0, self.button_width, self.button_height)
            rect.center = (self.screen_width // 2, btn["y"])
            hovered = rect.collidepoint(mx, my)
            if hovered:
                self.hovered_button = btn["action"]
                self.selected_index = idx
            selected = idx == self.selected_index
            self._draw_button(rect, btn["text"], hovered, selected)

        self._draw_footer()

        if self._vignette is not None:
            self.screen.blit(self._vignette, (0, 0))

        if self.fade_in_opacity > 0:
            overlay = pygame.Surface((self.screen_width, self.screen_height))
            overlay.fill((0, 0, 0))
            overlay.set_alpha(int(self.fade_in_opacity))
            self.screen.blit(overlay, (0, 0))
        if self.fading_out and self.fade_out_opacity > 0:
            overlay = pygame.Surface((self.screen_width, self.screen_height))
            overlay.fill((0, 0, 0))
            overlay.set_alpha(int(self.fade_out_opacity))
            self.screen.blit(overlay, (0, 0))

    def _draw_button(self, rect, text, hovered, selected):
        """Draw a stylized button. `hovered` = mouse over; `selected` = keyboard focus."""
        active = hovered or selected

        scale = 1.04 if active else 1.0
        scaled_rect = pygame.Rect(
            rect.x - (rect.width * (scale - 1)) / 2,
            rect.y - (rect.height * (scale - 1)) / 2,
            rect.width * scale,
            rect.height * scale,
        )

        if active:
            bg_color = (28, 60, 90)
            border_color = (120, 200, 255)
            glow_alpha = int(90 + math.sin(self.button_glow) * 40)
        else:
            bg_color = (15, 30, 45)
            border_color = (60, 100, 140)
            glow_alpha = 20

        if glow_alpha > 0:
            glow_surf = pygame.Surface(
                (scaled_rect.width + 28, scaled_rect.height + 28), pygame.SRCALPHA
            )
            pygame.draw.rect(
                glow_surf,
                (0, 150, 255, glow_alpha // 2),
                glow_surf.get_rect(),
                border_radius=14,
            )
            self.screen.blit(glow_surf, (scaled_rect.x - 14, scaled_rect.y - 14))

        if self._button_plate is not None:
            plate_scaled = pygame.transform.scale(
                self._button_plate, (int(scaled_rect.width), int(scaled_rect.height))
            )
            self.screen.blit(plate_scaled, (scaled_rect.x, scaled_rect.y))
            if active:

                tint = pygame.Surface(plate_scaled.get_size(), pygame.SRCALPHA)
                tint.fill((100, 200, 255, 70))
                self.screen.blit(tint, (scaled_rect.x, scaled_rect.y))
                pygame.draw.rect(
                    self.screen, border_color, scaled_rect, width=3, border_radius=8
                )
            else:

                pygame.draw.rect(
                    self.screen, (border_color[0]//2, border_color[1]//2, border_color[2]//2),
                    scaled_rect, width=1, border_radius=8
                )
        else:
            pygame.draw.rect(self.screen, bg_color, scaled_rect, border_radius=10)
            pygame.draw.rect(
                self.screen, border_color, scaled_rect, width=2 if active else 1, border_radius=10
            )

        if selected:
            caret_pulse = 0.6 + 0.4 * abs(math.sin(self.button_glow * 1.2))
            caret_color = (
                int(100 + 155 * caret_pulse),
                int(200 + 55 * caret_pulse),
                255,
            )
            cx = scaled_rect.left + 18
            cy = scaled_rect.centery
            pygame.draw.polygon(
                self.screen,
                caret_color,
                [(cx, cy - 7), (cx + 9, cy), (cx, cy + 7)],
            )

        text_color = (220, 245, 255) if active else (160, 185, 210)
        txt_surf = self._button_font.render(text, True, text_color)
        txt_rect = txt_surf.get_rect(center=scaled_rect.center)
        self.screen.blit(txt_surf, txt_rect)

    def _draw_footer(self):
        """Bottom-of-screen control hint + version tag."""
        hint = "W/S  navegar    Enter  seleccionar    Esc  salir"
        hint_surf = self._footer_font.render(hint, True, (150, 170, 200))
        hint_rect = hint_surf.get_rect(
            center=(self.screen_width // 2, self.screen_height - 18)
        )

        pad_x, pad_y = 20, 8
        pill = pygame.Rect(
            hint_rect.left - pad_x,
            hint_rect.top - pad_y,
            hint_rect.width + pad_x * 2,
            hint_rect.height + pad_y * 2,
        )
        pill_surf = pygame.Surface(pill.size, pygame.SRCALPHA)

        pygame.draw.rect(
            pill_surf, (0, 0, 0, 140), pill_surf.get_rect(), border_radius=10
        )
        pygame.draw.rect(
            pill_surf, (80, 120, 160, 60), pill_surf.get_rect(), border_radius=10, width=1
        )
        self.screen.blit(pill_surf, pill.topleft)
        self.screen.blit(hint_surf, hint_rect)

        ver_surf = self._footer_font.render(self._version_label, True, (130, 160, 200))
        ver_rect = ver_surf.get_rect(topleft=(self.screen_width - ver_surf.get_width() - 16, 14))

        ver_bg = pygame.Surface((ver_rect.width + 8, ver_rect.height + 4), pygame.SRCALPHA)
        pygame.draw.rect(ver_bg, (0, 0, 0, 80), ver_bg.get_rect(), border_radius=4)
        self.screen.blit(ver_bg, (ver_rect.x - 4, ver_rect.y - 2))
        self.screen.blit(ver_surf, ver_rect)

    def move_selection(self, delta):
        """Keyboard navigation between buttons."""
        if not self.buttons:
            return
        self.selected_index = (self.selected_index + delta) % len(self.buttons)

    def activate_selected(self):
        """Trigger the keyboard-focused button (Enter / Space)."""
        if self.fading_out:
            return
        if 0 <= self.selected_index < len(self.buttons):
            action = self.buttons[self.selected_index]["action"]
            self.fading_out = True
            self.next_state = action

    def handle_click(self):
        """Handle mouse click, returns action if a button was clicked."""
        if self.fading_out:
            return None
        mx, my = pygame.mouse.get_pos()
        for btn in self.buttons:
            rect = pygame.Rect(0, 0, self.button_width, self.button_height)
            rect.center = (self.screen_width // 2, btn["y"])
            if rect.collidepoint(mx, my):
                self.fading_out = True
                self.next_state = btn["action"]
                return None
        if self._character_rect and self._character_rect.collidepoint(mx, my):
            webbrowser.open(PLAY_BUTTON_URL)
            return None
        return None

    def handle_escape(self):
        """ESC on title screen does nothing (no slot picker). Returns False."""
        return False

    def start_fade_out(self, state):
        """Start fade out to a specific state."""
        self.fading_out = True
        self.next_state = state
