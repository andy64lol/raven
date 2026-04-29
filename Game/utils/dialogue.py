"""Lightweight dialogue engine.

A `DialogueBox` displays a queue of text lines at the bottom of the screen
with a typewriter effect. While it is `active`, the game loop freezes all
world updates (enemies, player movement, etc.) so the player can read
without being harmed.

Usage (single speaker):
    self.dialogue.start(["Line 1", "Line 2"], speaker="Box")

Usage (per-line speakers, from .dlg parser):
    texts, speakers = dlg_parser.load_sequence("path/to/file.dlg")
    self.dialogue.start_multi(texts, speakers)

Controls:
    Z / SPACE / ENTER  - advance / skip typewriter / next line
"""
import pygame


class DialogueBox:
    CHARS_PER_SECOND = 38

    def __init__(self, game):
        self.game = game
        self._queue: list[tuple[str | None, str]] = []
        self.current = ""
        self.speaker: str | None = None
        self.revealed = 0.0
        self.active = False
        self._font: pygame.font.Font = None  # type: ignore[assignment]
        self._title_font: pygame.font.Font = None  # type: ignore[assignment]
        self._advance_cooldown = 0.0


    def start(self, messages: list[str], speaker: str | None = None):
        """Begin a single-speaker dialogue sequence."""
        if not messages:
            return
        self._queue = [(speaker, m) for m in messages]
        self._pop_next()
        self.active = True
        self._advance_cooldown = 0.15

    def start_multi(self, texts: list[str], speakers: list[str | None]):
        """Begin a multi-speaker dialogue sequence (one speaker per line)."""
        if not texts:
            return
        self._queue = list(zip(speakers, texts))
        self._pop_next()
        self.active = True
        self._advance_cooldown = 0.15

    def _pop_next(self):
        if self._queue:
            self.speaker, self.current = self._queue.pop(0)
            self.revealed = 0.0
        else:
            self.current = ""
            self.speaker = None
            self.active = False

    def advance(self):
        """Skip typewriter on current line, or advance to the next."""
        if not self.active:
            return
        if int(self.revealed) < len(self.current):
            self.revealed = float(len(self.current))
        else:
            self._pop_next()


    def update(self, dt: float, events=None):
        if not self.active:
            return
        if self._advance_cooldown > 0.0:
            self._advance_cooldown = max(0.0, self._advance_cooldown - dt)
        if int(self.revealed) < len(self.current):
            self.revealed += self.CHARS_PER_SECOND * dt
            if self.revealed > len(self.current):
                self.revealed = float(len(self.current))
        if events:
            for ev in events:
                if ev.type == pygame.KEYDOWN and ev.key in (
                    pygame.K_z, pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER
                ):
                    if self._advance_cooldown <= 0.0:
                        self.advance()


    def _ensure_fonts(self):
        if self._font is None:
            try:
                self._font = pygame.font.Font("Game/assets/fonts/workbench.ttf", 20)
            except Exception:
                self._font = pygame.font.SysFont("Arial", 20)
        if self._title_font is None:
            try:
                self._title_font = pygame.font.Font("Game/assets/fonts/workbench.ttf", 18)
            except Exception:
                self._title_font = pygame.font.SysFont("Arial", 18)

    def _wrap(self, text: str, max_width: int) -> list[str]:
        words = text.split(" ")
        lines: list[str] = []
        cur = ""
        for w in words:
            trial = w if not cur else cur + " " + w
            if self._font.size(trial)[0] <= max_width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def draw(self, surface: pygame.Surface):
        if not self.active:
            return
        self._ensure_fonts()
        sw, sh = surface.get_size()

        dim = pygame.Surface((sw, sh), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 90))
        surface.blit(dim, (0, 0))

        margin_x = 40
        box_h = 130
        box_y = sh - box_h - 24
        box_rect = pygame.Rect(margin_x, box_y, sw - margin_x * 2, box_h)

        panel = pygame.Surface(box_rect.size, pygame.SRCALPHA)
        panel.fill((10, 14, 20, 220))
        surface.blit(panel, box_rect.topleft)
        pygame.draw.rect(surface, (220, 200, 140), box_rect, 2, border_radius=4)
        inner = box_rect.inflate(-8, -8)
        pygame.draw.rect(surface, (60, 70, 90), inner, 1, border_radius=3)

        text_top = inner.top + 8
        if self.speaker:
            label = self._title_font.render(str(self.speaker), True, (240, 220, 160))
            surface.blit(label, (inner.left + 10, inner.top + 4))
            text_top = inner.top + 4 + label.get_height() + 4

        shown = self.current[: int(self.revealed)]
        max_text_w = inner.width - 20
        lines = self._wrap(shown, max_text_w)
        for i, line in enumerate(lines):
            surf = self._font.render(line, True, (235, 235, 235))
            surface.blit(surf, (inner.left + 10, text_top + i * (surf.get_height() + 2)))

        if int(self.revealed) >= len(self.current):
            prompt = self._title_font.render("[Z] continuar", True, (200, 180, 110))
            surface.blit(
                prompt,
                (inner.right - prompt.get_width() - 10,
                 inner.bottom - prompt.get_height() - 4),
            )
