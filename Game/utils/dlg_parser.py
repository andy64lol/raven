"""Parser for the .dlg dialogue script format.

.dlg files use a theater-play syntax:


    PERSONAJE: Primera línea de diálogo.
    PERSONAJE: Segunda línea del mismo personaje.

    OTRO: Respuesta del otro personaje.


Rules
-----
- Each non-blank, non-comment line must follow the form  ``NAME: text``
- The speaker name is everything before the first ``:``, stripped of whitespace
- Speaker names are stored as-is (case preserved)
- An empty text portion is silently skipped
- ``#`` anywhere at the start of a line (after optional whitespace) marks a comment

Returns
-------
``parse(path)``  →  list of ``(speaker: str, text: str)`` tuples in script order
"""

from __future__ import annotations
import os


def parse(path: str) -> list[tuple[str, str]]:
    """Read a ``.dlg`` file and return ordered ``(speaker, text)`` pairs."""
    lines: list[tuple[str, str]] = []
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if ":" not in line:
                continue
            speaker, _, text = line.partition(":")
            speaker = speaker.strip()
            text = text.strip()
            if speaker and text:
                lines.append((speaker, text))
    return lines


def load_sequence(path: str) -> tuple[list[str], list[str | None]]:
    """Return ``(texts, speakers)`` parallel lists suitable for
    ``DialogueBox.start_multi(texts, speakers)``.

    If all lines share the same speaker the caller can still pass them to the
    regular ``DialogueBox.start(texts, speaker=...)`` call by checking that
    ``len(set(speakers)) == 1``.
    """
    pairs = parse(path)
    texts: list[str] = [p[1] for p in pairs]
    speakers: list[str | None] = [p[0] for p in pairs]
    return texts, speakers
