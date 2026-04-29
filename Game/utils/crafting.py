"""Crafting overlay for Raven.

Open with C key.  Shows all RECIPES and lets the player craft when they have
the required ingredients.
"""

from __future__ import annotations
import pygame
from Game.utils.items_db import RECIPES, ITEMS, make_inv_item, _draw_item_icon


class CraftingOverlay:
    def __init__(self, game):
        self.game = game
        self._font: pygame.font.Font = None  # type: ignore[assignment]
        self._small_font: pygame.font.Font = None  # type: ignore[assignment]
        self._big_font: pygame.font.Font = None  # type: ignore[assignment]
        self._result_msg: str = ""
        self._msg_timer: float = 0.0
        self._recipe_rects: list[tuple[dict, pygame.Rect]] = []

    def _ensure_fonts(self):
        if self._font is not None:
            return
        try:
            self._font = pygame.font.Font("Game/assets/fonts/workbench.ttf", 20)
            self._small_font = pygame.font.Font("Game/assets/fonts/workbench.ttf", 13)
            self._big_font = pygame.font.Font("Game/assets/fonts/workbench.ttf", 26)
        except Exception:
            self._font = pygame.font.SysFont("Arial", 20)
            self._small_font = pygame.font.SysFont("Arial", 13)
            self._big_font = pygame.font.SysFont("Arial", 26)

    def _count_ingredient(self, player, key: str) -> int:
        """How many of ``key`` the player currently has."""
        if key == "crystal":
            return player.crystals
        for it in player.inventory:
            if it.get("id") == key:
                return it.get("qty", 1)
        return 0

    def _can_craft(self, player, recipe: dict) -> bool:
        for key, needed in recipe["ingredients"].items():
            if self._count_ingredient(player, key) < needed:
                return False
        return True

    def _consume_ingredients(self, player, recipe: dict):
        for key, needed in recipe["ingredients"].items():
            if key == "crystal":
                player.crystals -= needed
            else:
                for it in player.inventory:
                    if it.get("id") == key:
                        it["qty"] = it.get("qty", 1) - needed
                        if it["qty"] <= 0:
                            player.inventory.remove(it)
                        break

    def _give_result(self, player, recipe: dict):
        result_key = recipe["result"]
        qty = recipe.get("qty", 1)
        data = ITEMS.get(result_key, {})

        existing = next(
            (it for it in player.inventory if it.get("id") == result_key), None
        )
        if existing and data.get("stackable"):
            existing["qty"] = existing.get("qty", 1) + qty
        else:
            inv_item = make_inv_item(result_key, qty)
            inv_item["icon"] = _draw_item_icon(result_key, 32)
            player.inventory.append(inv_item)

    def handle_click(self, mx: int, my: int):
        player = self.game.player
        for recipe, rect in self._recipe_rects:
            if rect.collidepoint(mx, my):
                if self._can_craft(player, recipe):
                    self._consume_ingredients(player, recipe)
                    self._give_result(player, recipe)
                    result_name = ITEMS.get(recipe["result"], {}).get(
                        "name", recipe["result"]
                    )
                    self._result_msg = f"¡Fabricado: {result_name}!"
                else:
                    self._result_msg = "No tienes suficientes ingredientes."
                self._msg_timer = 2.5
                return

    def update(self, dt: float):
        if self._msg_timer > 0:
            self._msg_timer -= dt

    def draw(self, surface: pygame.Surface):
        self._ensure_fonts()
        sw, sh = surface.get_size()
        player = self.game.player

        dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 210))
        surface.blit(dim, (0, 0))

        panel_w = min(560, sw - 60)
        row_h = 100
        panel_h = 80 + len(RECIPES) * (row_h + 12) + 50
        panel_x = (sw - panel_w) // 2
        panel_y = (sh - panel_h) // 2
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

        pygame.draw.rect(surface, (12, 16, 26), panel_rect, border_radius=10)
        pygame.draw.rect(surface, (120, 160, 100), panel_rect, 2, border_radius=10)

        title = self._big_font.render("FABRICAR", True, (180, 230, 160))
        surface.blit(title, (panel_x + 20, panel_y + 16))

        hint = self._small_font.render("[I] Cerrar", True, (120, 130, 120))
        surface.blit(hint, (panel_rect.right - hint.get_width() - 14, panel_y + 20))

        self._recipe_rects = []
        mx, my = pygame.mouse.get_pos()

        y = panel_y + 60
        for recipe in RECIPES:
            can = self._can_craft(player, recipe)
            row_rect = pygame.Rect(panel_x + 12, y, panel_w - 24, row_h)
            hov = row_rect.collidepoint(mx, my)

            row_bg = (25, 45, 30) if can else (30, 28, 28)
            if hov and can:
                row_bg = (35, 65, 40)
            pygame.draw.rect(surface, row_bg, row_rect, border_radius=8)
            border_col = (100, 180, 100) if can else (80, 70, 70)
            pygame.draw.rect(surface, border_col, row_rect, 2, border_radius=8)

            icon_x = row_rect.x + 10
            icon_size = 36

            for key, needed in recipe["ingredients"].items():
                icon = _draw_item_icon(key, icon_size)
                surface.blit(icon, (icon_x, row_rect.y + row_h // 2 - icon_size // 2))
                have = self._count_ingredient(player, key)
                color = (100, 220, 100) if have >= needed else (220, 80, 80)
                qty_surf = self._small_font.render(f"{have}/{needed}", True, color)
                surface.blit(
                    qty_surf, (icon_x, row_rect.bottom - qty_surf.get_height() - 4)
                )
                icon_x += icon_size + 28

            arrow_surf = self._font.render("→", True, (200, 200, 140))
            surface.blit(
                arrow_surf, (icon_x, row_rect.centery - arrow_surf.get_height() // 2)
            )
            icon_x += arrow_surf.get_width() + 14

            result_key = recipe["result"]
            result_icon = _draw_item_icon(result_key, icon_size)
            surface.blit(
                result_icon, (icon_x, row_rect.y + row_h // 2 - icon_size // 2)
            )
            result_name = ITEMS.get(result_key, {}).get("name", result_key)
            rname_surf = self._small_font.render(result_name, True, (220, 200, 140))
            surface.blit(
                rname_surf, (icon_x, row_rect.bottom - rname_surf.get_height() - 4)
            )

            btn_w, btn_h = 90, 30
            btn_rect = pygame.Rect(
                row_rect.right - btn_w - 8, row_rect.centery - btn_h // 2, btn_w, btn_h
            )
            if can:
                btn_col = (50, 130, 60) if not hov else (70, 170, 80)
                pygame.draw.rect(surface, btn_col, btn_rect, border_radius=6)
                pygame.draw.rect(surface, (130, 220, 140), btn_rect, 2, border_radius=6)
                lbl = self._small_font.render("FABRICAR", True, (220, 255, 220))
            else:
                btn_col = (50, 40, 40)
                pygame.draw.rect(surface, btn_col, btn_rect, border_radius=6)
                pygame.draw.rect(surface, (90, 80, 80), btn_rect, 2, border_radius=6)
                lbl = self._small_font.render("FABRICAR", True, (130, 120, 120))
            surface.blit(lbl, lbl.get_rect(center=btn_rect.center))

            self._recipe_rects.append((recipe, btn_rect))
            y += row_h + 12

        if self._msg_timer > 0:
            alpha = min(255, int(self._msg_timer * 200))
            msg_surf = self._font.render(self._result_msg, True, (180, 255, 160))
            msg_surf.set_alpha(alpha)
            surface.blit(
                msg_surf, (panel_x + 20, panel_rect.bottom - msg_surf.get_height() - 12)
            )
