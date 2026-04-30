"""Lightweight JSON save/load for player progress.

Supports multiple save slots stored in a dedicated directory. The game
saves everything that meaningfully changes during play: the active level,
player position, health, crystal count, full inventory, and equipped weapon.
Tiles themselves are not snapshotted — levels are rebuilt from their JSON
definitions on load.
"""

import json
import os
from pathlib import Path

SAVE_DIR = "saves"
NUM_SLOTS = 5

Path(SAVE_DIR).mkdir(exist_ok=True)

def _get_slot_path(slot: int) -> str:
    """Get the file path for a given save slot."""
    return os.path.join(SAVE_DIR, f"save_slot_{slot}.json")

def has_save(slot: int = 0) -> bool:
    """Check if a save exists in the given slot."""
    return os.path.isfile(_get_slot_path(slot))

def get_all_saves() -> dict[int, dict | None]:
    """Get metadata for all save slots."""
    saves = {}
    for slot in range(NUM_SLOTS):
        path = _get_slot_path(slot)
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                    saves[slot] = data
            except (OSError, json.JSONDecodeError):
                saves[slot] = None
        else:
            saves[slot] = None
    return saves

def get_save_metadata(slot: int) -> dict | None:
    """Get metadata about a save slot (level, position, health, etc)."""
    if not has_save(slot):
        return None
    try:
        with open(_get_slot_path(slot), encoding="utf-8") as f:
            data = json.load(f)
            return {
                "level": data.get("tilemap_current", "unknown"),
                "health": data.get("player", {}).get("health", 0),
                "maxhealth": data.get("player", {}).get("maxhealth", 10),
                "crystals": data.get("player", {}).get("crystals", 0),
            }
    except (OSError, json.JSONDecodeError):
        return None

_INVENTORY_PERSIST_KEYS = ("id", "qty")

def _serialize_inventory(inventory) -> list[dict]:
    """Strip transient fields (icon Surface, etc.) for JSON storage."""
    out: list[dict] = []
    for item in inventory or ():
        if not isinstance(item, dict):
            continue
        slim = {k: item[k] for k in _INVENTORY_PERSIST_KEYS if k in item}
        if "id" not in slim:
            continue
        slim.setdefault("qty", 1)
        out.append(slim)
    return out

def save_game(game, slot: int = 0) -> bool:
    """Save game to the specified slot."""
    if slot < 0 or slot >= NUM_SLOTS:
        print(f"[save] invalid slot: {slot}")
        return False

    player = game.player
    data = {
        "version": 1,
        "tilemap_current": getattr(game, "tilemap_current", "church"),
        "player": {
            "x": int(player.rect.x),
            "y": int(player.rect.y),
            "health": int(player.attributes.get("health", 10)),
            "maxhealth": int(player.attributes.get("maxhealth", 10)),
            "crystals": int(getattr(player, "crystals", 0)),
            "inventory": _serialize_inventory(getattr(player, "inventory", [])),
            "equipped_weapon": getattr(player, "equipped_weapon", None),
        },
    }
    try:
        save_path = _get_slot_path(slot)
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"[save] wrote slot {slot} to {save_path}")
        return True
    except (OSError, TypeError, ValueError) as e:
        print(f"[save] failed: {e}")
        return False

def load_save(slot: int = 0) -> dict | None:
    """Load a save from the specified slot."""
    if slot < 0 or slot >= NUM_SLOTS:
        return None

    if not has_save(slot):
        return None
    try:
        with open(_get_slot_path(slot), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[save] load slot {slot} failed: {e}")
        return None

def _rehydrate_inventory(saved_items) -> list[dict]:
    """Rebuild full inventory dicts (with icon Surfaces) from slim saved entries."""
    from Game.utils.items_db import make_inv_item, _draw_item_icon

    rebuilt: list[dict] = []
    for entry in saved_items or ():
        if not isinstance(entry, dict):
            continue
        item_id = entry.get("id")
        if not item_id:
            continue
        qty = int(entry.get("qty", 1))
        inv_item = make_inv_item(item_id, qty)
        try:
            inv_item["icon"] = _draw_item_icon(item_id, 32)
        except Exception:
            inv_item["icon"] = None
        rebuilt.append(inv_item)
    return rebuilt

def apply_save(game, data: dict | None) -> bool:
    """Apply loaded save state to an already-initialized Game/Player.

    Returns True if a save was applied, False otherwise.
    """
    if not data:
        return False

    p = data.get("player", {})

    target_map = data.get("tilemap_current", "church")
    if target_map in game.tilemaps:
        game.tilemap_current = target_map
        game.tilemap = game.tilemaps[target_map]

    player = game.player
    player.rect.x = int(p.get("x", player.rect.x))
    player.rect.y = int(p.get("y", player.rect.y))

    maxhealth = int(p.get("maxhealth", player.attributes.get("maxhealth", 10)))
    health = int(p.get("health", maxhealth))
    player.attributes["maxhealth"] = max(1, maxhealth)
    player.attributes["health"] = max(0, min(maxhealth, health))

    if hasattr(player, "crystals"):
        player.crystals = int(p.get("crystals", 0))
    player.inventory = _rehydrate_inventory(p.get("inventory", []))
    player.equipped_weapon = p.get("equipped_weapon")

    print(f"[save] save applied to game")
    return True
