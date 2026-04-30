"""Inventory overlay for Raven.

Items follow the schema in items_db.py.  Click a weapon slot to equip/unequip it.
Press C or click the CRAFT button to open the crafting screen.
"""

from __future__ import annotations
import pygame

_SLOT_SIZE = 56
_SLOT_PAD = 8
_COLS = 6
_ROWS = 4

class InventoryOverlay:
    """Draws a full-screen inventory panel over the game world."""

    def __init__(self, game):
        self.game = game
        self._font: pygame.font.Font = None
        self._small_font: pygame.font.Font = None
        self._clicked_slot: int | None = None

    def _ensure_fonts(self):
        if self._font is None:
            try:
                self._font = pygame.font.Font("Game/assets/fonts/workbench.ttf", 20)
            except Exception:
                self._font = pygame.font.SysFont("Arial", 20)
        if self._small_font is None:
            try:
                self._small_font = pygame.font.Font("Game/assets/fonts/workbench.ttf", 13)
            except Exception:
                self._small_font = pygame.font.SysFont("Arial", 13)

    def handle_click(self, mx: int, my: int):
        """Call from the game event loop when a left-click happens and inventory is open."""
        self._ensure_fonts()
        sw, sh = self.game.screen.get_size()
        panel_w = _COLS * (_SLOT_SIZE + _SLOT_PAD) + _SLOT_PAD + 240
        panel_h = _ROWS * (_SLOT_SIZE + _SLOT_PAD) + _SLOT_PAD + 100
        panel_x = (sw - panel_w) // 2
        panel_y = (sh - panel_h) // 2
        grid_x = panel_x + _SLOT_PAD
        grid_y = panel_y + 56

        items = self.game.player.inventory

        for idx in range(_COLS * _ROWS):
            col = idx % _COLS
            row = idx // _COLS
            sx = grid_x + col * (_SLOT_SIZE + _SLOT_PAD)
            sy = grid_y + row * (_SLOT_SIZE + _SLOT_PAD)
            slot_rect = pygame.Rect(sx, sy, _SLOT_SIZE, _SLOT_SIZE)
            if slot_rect.collidepoint(mx, my) and idx < len(items):
                item = items[idx]
                if item.get("type") == "weapon":
                    player = self.game.player
                    key = item.get("id")
                    if player.equipped_weapon == key:
                        player.equipped_weapon = None
                    else:
                        player.equipped_weapon = key
                return

        craft_rect = self._craft_button_rect(panel_x, panel_y, panel_w, panel_h)
        if craft_rect.collidepoint(mx, my):
            self.game.inventory_open = False
            self.game.crafting_open = True
            return

    def _craft_button_rect(self, px, py, pw, ph):
        return pygame.Rect(px + pw - 110, py + ph - 42, 100, 30)

    def _plate_button(self, surface, rect, label, hovered, plate_key="plate_small_long"):
        """Draw a button using one of the dark UI plate sprites as background."""
        plate = self.game.assets.get("hud", {}).get(plate_key)
        if plate is not None:
            scaled = pygame.transform.scale(plate, rect.size)
            if hovered:
                overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
                overlay.fill((255, 255, 255, 38))
                scaled = scaled.copy()
                scaled.blit(overlay, (0, 0))
            surface.blit(scaled, rect.topleft)
        else:
            color = (60, 75, 100) if hovered else (40, 50, 65)
            pygame.draw.rect(surface, color, rect, border_radius=6)
            pygame.draw.rect(surface, (180, 160, 100), rect, 2, border_radius=6)
        text = self._small_font.render(label, True, (240, 230, 200))
        surface.blit(text, text.get_rect(center=rect.center))

    def draw(self, surface: pygame.Surface, items: list[dict]):
        self._ensure_fonts()
        sw, sh = surface.get_size()

        dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 200))
        surface.blit(dim, (0, 0))

        panel_w = _COLS * (_SLOT_SIZE + _SLOT_PAD) + _SLOT_PAD + 240
        panel_h = _ROWS * (_SLOT_SIZE + _SLOT_PAD) + _SLOT_PAD + 100
        panel_x = (sw - panel_w) // 2
        panel_y = (sh - panel_h) // 2
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        pygame.draw.rect(surface, (14, 18, 28), panel_rect, border_radius=8)
        pygame.draw.rect(surface, (180, 160, 100), panel_rect, 2, border_radius=8)

        title = self._font.render("INVENTARIO", True, (220, 200, 140))
        surface.blit(title, (panel_x + 16, panel_y + 14))

        hint = self._small_font.render("[I] Cerrar", True, (130, 130, 140))
        surface.blit(hint, (panel_rect.right - hint.get_width() - 14, panel_y + 18))

        grid_x = panel_x + _SLOT_PAD
        grid_y = panel_y + 56

        hover_item: dict | None = None
        mx, my = pygame.mouse.get_pos()

        equipped = getattr(self.game.player, "equipped_weapon", None)

        for idx in range(_COLS * _ROWS):
            col = idx % _COLS
            row = idx // _COLS
            sx = grid_x + col * (_SLOT_SIZE + _SLOT_PAD)
            sy = grid_y + row * (_SLOT_SIZE + _SLOT_PAD)
            slot_rect = pygame.Rect(sx, sy, _SLOT_SIZE, _SLOT_SIZE)
            hovered = slot_rect.collidepoint(mx, my)

            bg_col = (40, 50, 65) if not hovered else (60, 75, 100)
            pygame.draw.rect(surface, bg_col, slot_rect, border_radius=5)
            pygame.draw.rect(surface, (80, 90, 110), slot_rect, 1, border_radius=5)

            if idx < len(items):
                item = items[idx]
                if hovered:
                    hover_item = item

                is_equipped = (item.get("id") == equipped and item.get("type") == "weapon")
                if is_equipped:
                    pygame.draw.rect(surface, (200, 160, 60), slot_rect, 3, border_radius=5)

                icon = item.get("icon")
                color = item.get("color", (160, 160, 160))
                if icon is not None:
                    scaled = pygame.transform.scale(icon, (_SLOT_SIZE - 8, _SLOT_SIZE - 8))
                    surface.blit(scaled, (sx + 4, sy + 4))
                else:
                    placeholder = pygame.Rect(sx + 10, sy + 10, _SLOT_SIZE - 20, _SLOT_SIZE - 20)
                    pygame.draw.rect(surface, color, placeholder, border_radius=4)
                    letter = self._small_font.render(item["name"][0].upper(), True, (240, 240, 240))
                    surface.blit(letter, letter.get_rect(center=placeholder.center))

                qty = item.get("qty", 1)
                if qty > 1:
                    qty_surf = self._small_font.render(str(qty), True, (220, 220, 80))
                    surface.blit(qty_surf, (slot_rect.right - qty_surf.get_width() - 3,
                                            slot_rect.bottom - qty_surf.get_height() - 2))

                if is_equipped:
                    eq_surf = self._small_font.render("EQ", True, (255, 220, 80))
                    surface.blit(eq_surf, (sx + 2, sy + 2))

        tooltip_x = grid_x + _COLS * (_SLOT_SIZE + _SLOT_PAD) + _SLOT_PAD
        tooltip_w = panel_w - _COLS * (_SLOT_SIZE + _SLOT_PAD) - _SLOT_PAD * 3
        tooltip_rect = pygame.Rect(tooltip_x, grid_y, tooltip_w,
                                   _ROWS * (_SLOT_SIZE + _SLOT_PAD) - _SLOT_PAD)
        pygame.draw.rect(surface, (20, 26, 38), tooltip_rect, border_radius=6)
        pygame.draw.rect(surface, (70, 80, 100), tooltip_rect, 1, border_radius=6)

        if hover_item:
            name_surf = self._font.render(hover_item["name"], True, (230, 210, 150))
            surface.blit(name_surf, (tooltip_rect.x + 8, tooltip_rect.y + 8))
            desc = hover_item.get("desc", "")
            if desc:
                self._draw_wrapped(surface, desc, tooltip_rect.inflate(-16, -40),
                                   (180, 180, 180), self._small_font,
                                   top_offset=name_surf.get_height() + 14)
            if hover_item.get("type") == "weapon":
                dmg_txt = self._small_font.render(
                    f"DAÑO: {hover_item.get('damage', 1)}", True, (255, 180, 80))
                surface.blit(dmg_txt, (tooltip_rect.x + 8, tooltip_rect.bottom - 32))
                action = "Click para desequipar" if hover_item.get("id") == equipped else "Click para equipar"
                act_surf = self._small_font.render(action, True, (160, 220, 160))
                surface.blit(act_surf, (tooltip_rect.x + 8, tooltip_rect.bottom - 16))
        else:
            placeholder_txt = self._small_font.render("Pasa el ratón sobre", True, (80, 90, 110))
            placeholder_txt2 = self._small_font.render("un objeto para verlo.", True, (80, 90, 110))
            surface.blit(placeholder_txt, (tooltip_rect.x + 8, tooltip_rect.y + 16))
            surface.blit(placeholder_txt2, (tooltip_rect.x + 8, tooltip_rect.y + 32))

        crystals = getattr(self.game.player, "crystals", 0)
        crystal_txt = self._font.render(f"Cristales: {crystals}", True, (120, 200, 255))
        surface.blit(crystal_txt, (panel_x + 16, panel_rect.bottom - crystal_txt.get_height() - 46))

        if equipped:
            from Game.utils.items_db import ITEMS
            w_name = ITEMS.get(equipped, {}).get("name", equipped)
            w_surf = self._small_font.render(f"Equipado: {w_name}", True, (255, 200, 80))
            surface.blit(w_surf, (panel_x + 16, panel_rect.bottom - w_surf.get_height() - 26))

        craft_rect = self._craft_button_rect(panel_x, panel_y, panel_w, panel_h)
        self._plate_button(surface, craft_rect, "FABRICAR [C]", craft_rect.collidepoint(mx, my))

    def _draw_wrapped(self, surface, text, rect, color, font, top_offset=0):
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            trial = word if not current else current + " " + word
            if font.size(trial)[0] <= rect.width:
                current = trial
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        y = rect.top + top_offset
        for line in lines:
            surf = font.render(line, True, color)
            surface.blit(surf, (rect.left, y))
            y += surf.get_height() + 2
            if y > rect.bottom:
                break
