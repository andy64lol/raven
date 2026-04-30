from typing import Any
import pygame
from Game.Sprites.sprite import Sprite
from Game.Sprites.crystals import Crystal
from Game.utils.utils import SpriteSheet
from Game.utils.timer import Timer

class Player(Sprite):
    game: Any
    tilemap: Any

    def __init__(self, img=pygame.surface.Surface((32, 32)), pos=(0, 0), identifier=None, game=None, tilemap=None):
        super().__init__(img, pos, identifier)
        self.base_max_speed = 240
        self.max_speed = self.base_max_speed
        self.acceleration = 1800
        self.friction = 2400
        self.air_acceleration = 1200
        self.velocity = pygame.math.Vector2(0, 0)

        self.sprint_multiplier = 1.6
        self.dash_speed = 520
        self.dash_duration = 0.18
        self.dash_cooldown_time = 0.6
        self._dash_timer = 0.0
        self._dash_cooldown = 0.0
        self._dash_dir = 0
        self._prev_shift_held = False

        self.coyote_time = 0.10
        self.jump_buffer_time = 0.12
        self._coyote_timer = 0.0
        self._jump_buffer_timer = 0.0
        self._prev_jump_held = False

        self.tilemap = tilemap
        self.game = game

        idle_sheet = SpriteSheet("raven/sprite_1.webp", tile_size=64)
        run_sheet = SpriteSheet("raven/hoja_sprite.webp", tile_size=64)
        attack_sheet = SpriteSheet("raven/hoja_sprite_ataque_xd.webp", tile_size=64)

        self.animations = {
            "idle": (idle_sheet, 8, True),
            "death": (idle_sheet, 8, False),
            "double_slash": (attack_sheet, 18, False),
            "fall": (idle_sheet, 8, True),
            "hurt": (idle_sheet, 8, False),
            "idle_break": (idle_sheet, 8, False),
            "jump": (idle_sheet, 8, True),
            "run": (run_sheet, 14, True),
            "slash": (attack_sheet, 18, False),
            "smoke_in": (idle_sheet, 8, False),
            "smoke_out": (idle_sheet, 8, False),
            "special_skill": (idle_sheet, 8, False),
        }

        self.crystals = 0

        self.inventory: list[dict] = []

        self.equipped_weapon: str | None = None

        self.animation = "idle"
        self.frame = 0

        self.visual_scale = 2
        self.scaled_sprite_size = 64 * self.visual_scale

        char_bounds = self.calculate_character_bounds()
        char_width = char_bounds['width']
        char_height = char_bounds['height']

        self.char_offset_x = char_bounds['offset_x']
        self.char_offset_y = char_bounds['offset_y']

        self.rect = pygame.Rect(pos[0], pos[1], char_width, char_height)
        self.visual_rect = pygame.Rect(0, 0, self.scaled_sprite_size, self.scaled_sprite_size)

        self.attributes = {
            "max_jumps": 1,
            "jumps": 1,
            "falling": False,
            "damaged": False,
            "attacking": False,
            "cutscene": False,
            "idle_timer": 0,
            "jumping": False,
            "can_move": True,
            "flipped": False,
            "jump_strength": 500,

            "health": 10,
            "maxhealth": 10,

            "stun": False,
            "stun_cooldown": 200,
            "dead": False,
            "death_animation_complete": False,
            "visible": True,
        }

        self.timers = {
            "damage": 0,
            "invulnerability": 0,
            "attack_cooldown": Timer(1),
        }

        self.collisions = {
            "top": False,
            "bottom": False,
            "left": False,
            "right": False,
        }

        self.gravity = 15
        self.max_fall_speed = 400
        self.double_slash_hold_ms = 250

        self.attributes.update({
            "slashing": False,
            "double_slashing": False,
            "attack_press_time": 0,
            "slash_damage_frames": 0,
            "max_slash_damage_frames": 1,
            "max_double_slash_damage_frames": 2,
            "last_x_press_time": 0,
            "double_tap_window": 500,
        })
        self.attacking_hitboxes = {
            "slash_right": pygame.Rect(0, 0, 70, 15),
            "slash_left": pygame.Rect(0, 0, 70, 15),
        }
        self._update_attacking_hitboxes()
        self.attacking_boolean = {
            "slash": False,
            "double_slash": False,
        }

    def _update_attacking_hitboxes(self):
        """Recompute screen-space slash hitboxes; call when window size changes."""
        sw = self.game.screen.get_width()
        sh = self.game.screen.get_height()
        self.attacking_hitboxes["slash_right"] = pygame.Rect(sw // 2, sh // 2 + 10, 70, 15)
        self.attacking_hitboxes["slash_left"] = pygame.Rect(sw // 2 - 70, sh // 2 + 10, 70, 15)

    @property
    def weapon_damage(self) -> int:
        """Damage dealt per slash hit, based on the equipped weapon."""
        if self.equipped_weapon is None:
            return 1
        from Game.utils.items_db import ITEMS
        return ITEMS.get(self.equipped_weapon, {}).get("damage", 1)

    def controls(self):
        keys = pygame.key.get_pressed()

        if getattr(self.game, "debug_fly", False):
            speed = getattr(self.game, "debug_fly_speed", 350)
            x_dir = int(keys[pygame.K_d]) - int(keys[pygame.K_a])
            y_dir = int(keys[pygame.K_s]) - int(keys[pygame.K_w])
            self.velocity.x = x_dir * speed
            self.velocity.y = y_dir * speed
            if self.velocity.x > 0:
                self.attributes["flipped"] = False
            elif self.velocity.x < 0:
                self.attributes["flipped"] = True
            return

        on_ground = self.is_on_ground()

        if on_ground:
            self._coyote_timer = self.coyote_time
            self.attributes["jumps"] = self.attributes["max_jumps"]

        jump_held = bool(keys[pygame.K_w])
        if jump_held and not self._prev_jump_held:
            self._jump_buffer_timer = self.jump_buffer_time
        self._prev_jump_held = jump_held

        shift_held = bool(keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT])
        input_direction = int(keys[pygame.K_d]) - int(keys[pygame.K_a])
        if (
            shift_held
            and not self._prev_shift_held
            and self._dash_cooldown <= 0
            and self._dash_timer <= 0
            and self.attributes["can_move"]
            and not (self.attributes.get("slashing") or self.attributes.get("double_slashing"))
        ):
            if input_direction != 0:
                self._dash_dir = input_direction
            else:
                self._dash_dir = -1 if self.attributes["flipped"] else 1
            self._dash_timer = self.dash_duration
            self._dash_cooldown = self.dash_cooldown_time
        self._prev_shift_held = shift_held

        sprinting = shift_held and self._dash_timer <= 0
        self.max_speed = int(self.base_max_speed * self.sprint_multiplier) if sprinting else self.base_max_speed

        if self._dash_timer > 0:
            self.velocity.x = self._dash_dir * self.dash_speed
            if self._dash_dir > 0:
                self.attributes["flipped"] = False
            elif self._dash_dir < 0:
                self.attributes["flipped"] = True
        elif self.attributes["can_move"] and not (self.attributes.get("slashing") or self.attributes.get("double_slashing")):
            accel = self.acceleration if on_ground else self.air_acceleration
            if input_direction != 0:
                self.velocity.x += input_direction * accel * (1 / 60)
                self.velocity.x = max(-self.max_speed, min(self.max_speed, int(self.velocity.x)))
            else:
                fric = self.friction if on_ground else self.friction * 0.25
                if abs(self.velocity.x) > fric * (1 / 60):
                    friction_direction = -1 if self.velocity.x > 0 else 1
                    self.velocity.x += friction_direction * fric * (1 / 60)
                else:
                    self.velocity.x = 0

        can_ground_jump = on_ground or self._coyote_timer > 0
        if (
            self._jump_buffer_timer > 0
            and self.attributes["can_move"]
            and (can_ground_jump or self.attributes["jumps"] >= 1)
        ):
            self.velocity.y = -self.attributes["jump_strength"]
            self.attributes["jumping"] = True
            self._jump_buffer_timer = 0.0
            self._coyote_timer = 0.0
            if not can_ground_jump:
                self.attributes["jumps"] -= 1

        if not jump_held and self.velocity.y < 0:
            self.velocity.y *= 0.5

        if self.velocity.x > 0:
            self.attributes["flipped"] = False
        elif self.velocity.x < 0:
            self.attributes["flipped"] = True

        if self.attributes["jumping"] and self.velocity.y < 0:
            self.attributes["jumping"] = False

    def handle_x_key_press(self):
        current_time = pygame.time.get_ticks()

        on_ground = self.is_on_ground()

        if not self.attributes.get("slashing") and not self.attributes.get("double_slashing"):
            time_since_last_press = current_time - self.attributes["last_x_press_time"]

            if time_since_last_press <= self.attributes["double_tap_window"] and self.attributes["last_x_press_time"] > 0:
                if not self.timers["attack_cooldown"].active:
                    self.attributes["double_slashing"] = True
                    self.attributes["slashing"] = False
                    self.attributes["slash_damage_frames"] = 0
                    self.frame = 0
                    if on_ground:
                        self.velocity.x = 0
                    self.animation = "double_slash"
                    self.timers["attack_cooldown"].activate()
                else:
                    pass
            else:
                if not self.timers["attack_cooldown"].active:
                    self.attributes["slashing"] = True
                    self.attributes["double_slashing"] = False
                    self.attributes["attack_press_time"] = current_time
                    self.attributes["slash_damage_frames"] = 0
                    self.frame = 0
                    if on_ground:
                        self.velocity.x = 0
                    self.animation = "slash"
                    self.timers["attack_cooldown"].activate()
                else:
                    pass

            self.attributes["last_x_press_time"] = current_time

    def update(self, dt, events=None):
        self.timers["attack_cooldown"].update()

        if self._coyote_timer > 0:
            self._coyote_timer = max(0.0, self._coyote_timer - dt)
        if self._jump_buffer_timer > 0:
            self._jump_buffer_timer = max(0.0, self._jump_buffer_timer - dt)
        if self._dash_timer > 0:
            self._dash_timer = max(0.0, self._dash_timer - dt)
        if self._dash_cooldown > 0:
            self._dash_cooldown = max(0.0, self._dash_cooldown - dt)

        if self.timers["damage"] > 0:
            self.timers["damage"] -= dt * 1000
        if self.timers["invulnerability"] > 0:
            self.timers["invulnerability"] -= dt * 1000

        if self.timers["invulnerability"] <= 0 and self.attributes["damaged"]:
            self.attributes["damaged"] = False

        if self.animation == "hurt":
            sprite_sheet, frame_duration, is_looping = self.animations["hurt"]
            images = sprite_sheet.get_images_list()
            if int(self.frame) >= len(images) - 1:
                self.attributes["can_move"] = True
                self.attributes["stun"] = False
                self.animation = "idle"
                self.frame = 0
                if self.timers["invulnerability"] <= 0:
                    self.timers["invulnerability"] = 500

        if self.animation == "smoke_out" and self.attributes["dead"]:
            sprite_sheet, frame_duration, is_looping = self.animations["smoke_out"]
            images = sprite_sheet.get_images_list()
            if int(self.frame) >= len(images) - 1:
                self.attributes["death_animation_complete"] = True
                self.attributes["visible"] = False
                return

        if self.attributes["stun"] and isinstance(self.attributes["stun"], (int, float)):
            if pygame.time.get_ticks() - self.attributes["stun"] >= self.attributes["stun_cooldown"]:
                self.attributes["stun"] = False
                self.attributes["can_move"] = True

        self.controls()

        if self.timers["invulnerability"] <= 0 and not self.attributes["damaged"] and not getattr(self.game, "debug_fly", False):
            hazard_hit = False
            hazard_center_x = self.rect.centerx
            hazard_probe = self.rect.copy()
            hazard_probe.height += 2
            for tilemap in self.game.tilemaps.values():
                if not tilemap.rendered:
                    continue
                ts = tilemap.tile_size
                if not ts:
                    continue
                cx_min = hazard_probe.left // ts
                cy_min = hazard_probe.top // ts
                cx_max = hazard_probe.right // ts
                cy_max = hazard_probe.bottom // ts
                for cy in range(cy_min, cy_max + 1):
                    for cx in range(cx_min, cx_max + 1):
                        for tile_data in tilemap.get_tiles_at(cx, cy):
                            if 'hazard' not in tile_data.get('properties', []):
                                continue
                            tile_rect = pygame.Rect(cx * ts, cy * ts, ts, ts)
                            if hazard_probe.colliderect(tile_rect):
                                hazard_hit = True
                                hazard_center_x = tile_rect.centerx
                                break
                        if hazard_hit:
                            break
                    if hazard_hit:
                        break
                if hazard_hit:
                    break

            if hazard_hit:
                self.attributes["health"] -= 1
                self.attributes["damaged"] = True
                self.timers["damage"] = 500
                self.timers["invulnerability"] = 2000
                if self.attributes["health"] <= 0:
                    self.attributes["dead"] = True
                    self.animation = "smoke_out"
                    self.frame = 0
                    self.velocity.x = 0
                    self.velocity.y = 0
                    self.attributes["can_move"] = False
                else:
                    self.animation = "hurt"
                    self.frame = 0
                    knockback_direction = -1 if self.rect.centerx > hazard_center_x else 1
                    self.velocity.x = knockback_direction * 150
                    self.velocity.y = -200
                    self.attributes["can_move"] = False
                    self.attributes["stun"] = pygame.time.get_ticks()

            if not getattr(self.game, "debug_mode", False):
                for tilemap in self.game.tilemaps.values():
                    if not tilemap.rendered:
                        continue
                    for enemy in tilemap.enemies.sprite_dict.values():
                        if self.rect.colliderect(enemy.rect):
                            self.attributes["health"] -= 1
                            self.attributes["damaged"] = True
                            self.timers["damage"] = 500

                            self.timers["invulnerability"] = 2000

                            if self.attributes["health"] <= 0:
                                self.attributes["dead"] = True
                                self.animation = "smoke_out"
                                self.frame = 0
                                self.velocity.x = 0
                                self.velocity.y = 0
                                self.attributes["can_move"] = False
                            else:
                                self.animation = "hurt"
                                self.frame = 0
                                enemy_center_x = enemy.rect.centerx
                                player_center_x = self.rect.centerx
                                knockback_direction = -1 if player_center_x > enemy_center_x else 1
                                self.velocity.x = knockback_direction * 150
                                self.velocity.y = -200
                                self.attributes["can_move"] = False
                                self.attributes["stun"] = pygame.time.get_ticks()
                            break

        if self.attributes.get("slashing") or self.attributes.get("double_slashing"):
            max_damage_frames = self.attributes["max_double_slash_damage_frames"] if self.attributes.get("double_slashing") else self.attributes["max_slash_damage_frames"]

            if self.attributes["slash_damage_frames"] == 0:
                pass

            if self.attributes["slash_damage_frames"] < max_damage_frames:
                dmg = self.weapon_damage
                if self.attributes["flipped"]:
                    for tilemap in self.game.tilemaps.values():
                        if tilemap.rendered:
                            for enemy in tilemap.enemies.sprite_dict.values():
                                rect = enemy.rect.copy()
                                rect.topleft -= self.game.camera.offset
                                if self.attacking_hitboxes["slash_left"].colliderect(rect):
                                    enemy.take_damage(dmg)
                                    if enemy.health <= 0:
                                        self.crystals += 1
                                        crystal = Crystal((enemy.rect.x, enemy.rect.y), enemy.drop, self.game)
                                        crystal.tilemap = enemy.tilemap
                                        enemy.tilemap.crystals.append(crystal)
                                        tilemap.enemies.remove(enemy)
                                        break

                            for breakable in tilemap.breakables.sprite_dict.values():
                                rect = breakable.rect.copy()
                                rect.topleft -= self.game.camera.offset
                                if self.attacking_hitboxes["slash_left"].colliderect(rect):
                                    breakable.take_damage(dmg)
                                    break
                else:
                    for tilemap in self.game.tilemaps.values():
                        if tilemap.rendered:
                            for enemy in tilemap.enemies.sprite_dict.values():
                                rect = enemy.rect.copy()
                                rect.topleft -= self.game.camera.offset
                                if self.attacking_hitboxes["slash_right"].colliderect(rect):
                                    enemy.take_damage(dmg)
                                    if enemy.health <= 0:
                                        self.crystals += 1
                                        crystal = Crystal((enemy.rect.x, enemy.rect.y), enemy.drop, self.game)
                                        crystal.tilemap = enemy.tilemap
                                        enemy.tilemap.crystals.append(crystal)
                                        tilemap.enemies.remove(enemy)
                                        break

                            for breakable in tilemap.breakables.sprite_dict.values():
                                rect = breakable.rect.copy()
                                rect.topleft -= self.game.camera.offset
                                if self.attacking_hitboxes["slash_right"].colliderect(rect):
                                    breakable.take_damage(dmg)
                                    break

                self.attributes["slash_damage_frames"] += 1

        if events:
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_x:
                        self.handle_x_key_press()

        if self.attributes.get("slashing") or self.attributes.get("double_slashing"):
            current_anim_key = "double_slash" if self.attributes.get("double_slashing") else "slash"
            sprite_sheet, frame_duration, is_looping = self.animations[current_anim_key]
            images = sprite_sheet.get_images_list()
            slash_finished = False
            if images:
                if int(self.frame) < len(images):
                    self.image = images[int(self.frame)]
                else:
                    if self.attributes.get("double_slashing"):
                        self.attributes["double_slashing"] = False
                        self.attributes["slashing"] = False
                    else:
                        self.attributes["slashing"] = False
                    self.animation = "idle"
                    self.frame = 0
                    slash_finished = True
            if not slash_finished:
                self.frame += frame_duration * dt
            if self.image:
                self.image = pygame.transform.scale(self.image, (self.scaled_sprite_size, self.scaled_sprite_size))
                self.update_visual_rect()
            if not slash_finished and not self.collisions["bottom"] and not getattr(self.game, "debug_fly", False):
                self.velocity.y += self.gravity * dt * 60
                self.velocity.y = min(self.velocity.y, self.max_fall_speed)
                self.move(dt)
            return

        if not self.collisions["bottom"] and not getattr(self.game, "debug_fly", False):
            self.velocity.y += self.gravity * dt * 60
            self.velocity.y = min(self.velocity.y, self.max_fall_speed)

        old_x = self.rect.x
        self.move(dt)
        actually_moved_x = abs(self.rect.x - old_x) > 0.1

        if self.collisions["bottom"]:
            self.attributes["jumps"] = self.attributes["max_jumps"]
            self.attributes["falling"] = False
            if self.attributes["can_move"]:
                if actually_moved_x:
                    if self.animation != "run":
                        self.animation = "run"
                        self.frame = 0
                    self.attributes["idle_timer"] = 0
                else:
                    if self.animation not in ["idle_break"] and self.animation != "idle":
                        self.animation = "idle"
                        self.frame = 0
        else:
            if self.velocity.y > 0 and self.animation != "fall":
                self.animation = "fall"
                self.frame = 0
                self.attributes["idle_timer"] = 0
            elif self.velocity.y < 0 and self.animation != "jump":
                self.animation = "jump"
                self.frame = 0

        sprite_sheet, frame_duration, is_looping = self.animations[self.animation]
        images = sprite_sheet.get_images_list()
        if images:
            if is_looping:
                self.image = images[int(self.frame) % len(images)]
            elif int(self.frame) < len(images):
                self.image = images[int(self.frame)]
            else:
                self.animation = "idle"
                self.frame = 0
                return

        if self.image:
            self.image = pygame.transform.scale(self.image, (self.scaled_sprite_size, self.scaled_sprite_size))
            self.update_visual_rect()

        self.frame += frame_duration * dt

        if (self.animation == "idle" and self.collisions["bottom"] and
            self.velocity.x == 0 and self.attributes["can_move"]):
            if self.attributes["idle_timer"] >= 180:
                self.animation = "idle_break"
                self.frame = 0
                self.attributes["idle_timer"] = 0
            else:
                self.attributes["idle_timer"] += dt * 60

    def calculate_character_bounds(self):
        idle_spritesheet = self.animations["idle"][0]
        idle_images = idle_spritesheet.get_images_list()

        if not idle_images:
            return {
                'width': 40,
                'height': 60,
                'offset_x': 72,
                'offset_y': 100
            }

        sprite = idle_images[0]

        scaled_sprite = pygame.transform.scale(sprite, (self.scaled_sprite_size, self.scaled_sprite_size))

        bounds = self.get_sprite_bounds(scaled_sprite)

        char_width = 40
        char_height = 70

        center_x = (bounds['left'] + bounds['width'] // 2)
        bottom_y = bounds['top'] + bounds['height']

        offset_x = center_x - (char_width // 2)
        offset_y = bottom_y - char_height - 3

        return {
            'width': char_width,
            'height': char_height,
            'offset_x': offset_x,
            'offset_y': offset_y
        }

    @staticmethod
    def get_sprite_bounds(surface):
        width, height = surface.get_size()

        left = width
        right = 0
        top = height
        bottom = 0

        found_pixel = False

        try:
            surface.lock()

            for y in range(height):
                for x in range(width):
                    pixel = surface.get_at((x, y))

                    if pixel[3] > 0:
                        found_pixel = True
                        left = min(left, x)
                        right = max(right, x)
                        top = min(top, y)
                        bottom = max(bottom, y)
        finally:
            surface.unlock()

        if not found_pixel:
            return {
                'left': width // 4,
                'top': height // 4,
                'width': width // 2,
                'height': height // 2
            }

        return {
            'left': left,
            'top': top,
            'width': right - left + 1,
            'height': bottom - top + 1
        }

    def update_visual_rect(self):
        self.visual_rect.x = self.rect.x - self.char_offset_x
        self.visual_rect.y = self.rect.y - self.char_offset_y

    def move(self, dt):
        old_x, old_y = self.rect.x, self.rect.y
        self._last_dt = dt

        if getattr(self.game, "debug_fly", False):
            self.rect.x += self.velocity.x * dt
            self.rect.y += self.velocity.y * dt
            self.collisions["top"] = False
            self.collisions["bottom"] = False
            self.collisions["left"] = False
            self.collisions["right"] = False
            if hasattr(self.game, 'camera'):
                self.game.camera.update(self)
            return

        if abs(self.velocity.x) > 0.1:
            direction = 1 if self.velocity.x > 0 else -1
            side_key = "right" if direction > 0 else "left"
            intended_x = self.rect.x + self.velocity.x * dt
            self.rect.x = intended_x
            if self._push_out_horizontal(direction):
                if self._try_autojump(direction, intended_x):
                    self.collisions["bottom"] = True
                    if self.velocity.y > 0:
                        self.velocity.y = 0
                    self.collisions[side_key] = False
                else:
                    self.collisions[side_key] = True
                    self.velocity.x = 0
            else:
                self.collisions[side_key] = False
                if self._snap_onto_floor_slopes():
                    self.collisions["bottom"] = True
                    if self.velocity.y > 0:
                        self.velocity.y = 0

        if abs(self.velocity.y) > 0.1:
            self.rect.y += self.velocity.y * dt
            collision_result = self.check_ground_collisions()
            if collision_result:
                if self.velocity.y > 0:
                    self.collisions["bottom"] = True
                    self.velocity.y = 0
                elif self.velocity.y < 0:
                    self.collisions["top"] = True
                    self.velocity.y = 0
            else:
                self.collisions["top"] = False

            if self.velocity.y >= 0 and self._snap_onto_floor_slopes():
                self.collisions["bottom"] = True
                self.velocity.y = 0

        if not self.is_on_ground():
            self.collisions["bottom"] = False

        if hasattr(self.game, 'camera'):
            self.game.camera.update(self)

    def _iter_solid_subrects_near(self, tilemap):
        """Iterate (sub_rect, tile_data) for tiles whose grid cell is in the 3x3 neighborhood of
        the player's bounding box. Sub-rects are world-space pygame.Rect objects respecting tile shape.

        Floor slopes (slope_bl/slope_br) are intentionally skipped — they are
        handled separately as a smooth surface (see _iter_floor_slope_tiles_near)
        so the player can climb over them instead of bumping the stair-step
        approximation."""
        from Game.utils.tilemaps import FLOOR_SLOPE_SHAPES
        ts = tilemap.tile_size
        left_tile = int(self.rect.left - tilemap.pos.x * ts) // ts
        right_tile = int(self.rect.right - 1 - tilemap.pos.x * ts) // ts
        top_tile = int(self.rect.top - tilemap.pos.y * ts) // ts
        bottom_tile = int(self.rect.bottom - tilemap.pos.y * ts) // ts
        for gx in range(left_tile - 1, right_tile + 2):
            for gy in range(top_tile - 1, bottom_tile + 2):
                cell_tiles = tilemap.get_tiles_at(int(gx + tilemap.pos.x), int(gy + tilemap.pos.y))
                if not cell_tiles:
                    continue
                for td in cell_tiles:
                    props = td.get('properties', [])
                    if 'solid' not in props and 'hazard' not in props:
                        continue
                    if td.get('shape', 'full') in FLOOR_SLOPE_SHAPES:
                        continue
                    for sub in tilemap.get_solid_subrects(td):
                        yield sub, td

    def _iter_floor_slope_tiles_near(self, tilemap):
        """Iterate floor-slope tile dicts in the 3x3 neighborhood of the player."""
        from Game.utils.tilemaps import FLOOR_SLOPE_SHAPES
        ts = tilemap.tile_size
        left_tile = int(self.rect.left - tilemap.pos.x * ts) // ts
        right_tile = int(self.rect.right - 1 - tilemap.pos.x * ts) // ts
        top_tile = int(self.rect.top - tilemap.pos.y * ts) // ts
        bottom_tile = int(self.rect.bottom - tilemap.pos.y * ts) // ts
        for gx in range(left_tile - 1, right_tile + 2):
            for gy in range(top_tile - 1, bottom_tile + 2):
                cell_tiles = tilemap.get_tiles_at(int(gx + tilemap.pos.x), int(gy + tilemap.pos.y))
                if not cell_tiles:
                    continue
                for td in cell_tiles:
                    if 'solid' not in td.get('properties', []):
                        continue
                    if td.get('shape', 'full') in FLOOR_SLOPE_SHAPES:
                        yield td

    def _snap_onto_floor_slopes(self):
        """If the player's bottom is below the smooth surface of any nearby
        floor slope, snap rect.bottom up to the slope. Returns True if snapped."""
        from Game.utils.tilemaps import slope_floor_y
        snapped = False
        best_y = None
        for tilemap in self.game.tilemaps.values():
            if not tilemap.rendered:
                continue
            ts = tilemap.tile_size
            sample_x = self.rect.centerx
            for td in self._iter_floor_slope_tiles_near(tilemap):
                surface_y = slope_floor_y(td, sample_x, ts)
                if surface_y is None:
                    continue
                tile_top = td['y'] * ts
                tile_bottom = tile_top + ts
                if self.rect.bottom < tile_top or self.rect.top > tile_bottom:
                    continue
                if self.rect.bottom < surface_y:
                    continue
                if best_y is None or surface_y < best_y:
                    best_y = surface_y
        if best_y is not None and self.rect.bottom != best_y:
            self.rect.bottom = best_y
            snapped = True
        return snapped

    def _is_on_floor_slope(self):
        """True when the player's foot is at (or just above) any floor slope surface."""
        from Game.utils.tilemaps import slope_floor_y
        for tilemap in self.game.tilemaps.values():
            if not tilemap.rendered:
                continue
            ts = tilemap.tile_size
            sample_x = self.rect.centerx
            for td in self._iter_floor_slope_tiles_near(tilemap):
                surface_y = slope_floor_y(td, sample_x, ts)
                if surface_y is None:
                    continue
                if abs(self.rect.bottom - surface_y) <= 2:
                    return True
        return False

    def is_on_ground(self):
        if self._is_on_floor_slope():
            return True

        for tilemap in self.game.tilemaps.values():
            if not tilemap.rendered:
                continue

            for sub, td in self._iter_solid_subrects_near(tilemap):
                props = td.get('properties', [])
                if not ('solid' in props or 'platform' in props):
                    continue
                if abs(self.rect.bottom - sub.top) <= 2:
                    if self.rect.right > sub.left and self.rect.left < sub.right:
                        return True

            for breakable in tilemap.breakables.sprite_dict.values():
                if breakable.is_solid():
                    if abs(self.rect.bottom - breakable.rect.top) <= 2:
                        if (self.rect.right > breakable.rect.left and
                            self.rect.left < breakable.rect.right):
                            return True
        return False

    def check_wall_collisions(self):
        """Returns True if the player overlaps any solid wall."""
        for tilemap in self.game.tilemaps.values():
            if not tilemap.rendered:
                continue

            for sub, td in self._iter_solid_subrects_near(tilemap):
                if 'solid' not in td.get('properties', []):
                    continue
                if self.rect.colliderect(sub):
                    return True

            for breakable in tilemap.breakables.sprite_dict.values():
                if breakable.is_solid() and self.rect.colliderect(breakable.rect):
                    return True
        return False

    def _push_out_horizontal(self, direction):
        """Push the player out of any walls in the direction of horizontal motion.

        `direction`: +1 for moving right, -1 for moving left.
        Returns True if at least one wall was hit (and the player was pushed
        flush against it). The player ends up exactly touching the wall edge."""
        hit = False
        for tilemap in self.game.tilemaps.values():
            if not tilemap.rendered:
                continue

            for sub, td in self._iter_solid_subrects_near(tilemap):
                if 'solid' not in td.get('properties', []):
                    continue
                if not self.rect.colliderect(sub):
                    continue
                if direction > 0 and self.rect.right > sub.left:
                    self.rect.right = sub.left
                    hit = True
                elif direction < 0 and self.rect.left < sub.right:
                    self.rect.left = sub.right
                    hit = True

            for breakable in tilemap.breakables.sprite_dict.values():
                if not breakable.is_solid():
                    continue
                if not self.rect.colliderect(breakable.rect):
                    continue
                if direction > 0 and self.rect.right > breakable.rect.left:
                    self.rect.right = breakable.rect.left
                    hit = True
                elif direction < 0 and self.rect.left < breakable.rect.right:
                    self.rect.left = breakable.rect.right
                    hit = True
        return hit

    def _autojump_max_step(self):
        """Maximum vertical distance the auto-step will climb.

        Capped at HALF a tile so that half-height shapes (slab_bottom,
        quarter_bl/quarter_br) can be walked over, but full-height shapes
        (slab_left, slab_right, full tiles, vertical columns) act as proper
        walls and require a manual jump."""
        for tilemap in self.game.tilemaps.values():
            if tilemap.rendered:
                return max(8, tilemap.tile_size // 2)
        return 24

    def _try_autojump(self, direction, intended_x):
        """When horizontal motion is blocked by a short ledge, lift the player
        up onto it instead of stopping.

        `direction`: +1 / -1 horizontal direction.
        `intended_x`: the x-position the player wanted to reach this frame.

        Returns True if the player was successfully stepped up (rect updated),
        False if the obstacle is too tall, has no clearance, or the player
        wasn't on the ground to begin with."""
        if not self.is_on_ground():
            return False

        step_height = self._autojump_max_step()

        saved_x = self.rect.x
        saved_y = self.rect.y

        self.rect.x = intended_x
        candidate_top = None
        for tilemap in self.game.tilemaps.values():
            if not tilemap.rendered:
                continue
            for sub, td in self._iter_solid_subrects_near(tilemap):
                if 'solid' not in td.get('properties', []):
                    continue
                if not self.rect.colliderect(sub):
                    continue
                if direction > 0 and sub.right <= self.rect.left:
                    continue
                if direction < 0 and sub.left >= self.rect.right:
                    continue
                step = self.rect.bottom - sub.top
                if step <= 0 or step > step_height:
                    continue
                if candidate_top is None or sub.top < candidate_top:
                    candidate_top = sub.top

        if candidate_top is None:
            self.rect.x = saved_x
            self.rect.y = saved_y
            return False

        self.rect.bottom = candidate_top
        if self._push_out_horizontal(direction):
            pass
        if self.check_wall_collisions():
            self.rect.x = saved_x
            self.rect.y = saved_y
            return False
        return True

    def check_ground_collisions(self):
        """Resolve vertical collisions after a y-axis move.

        Snaps the player's foot to a ledge top when landing, or their head to
        a ceiling when jumping. Verifies the overlap is genuinely a vertical
        landing (not a side clip) by checking the previous frame's bottom."""
        last_dt = getattr(self, "_last_dt", 1 / 60)
        prev_bottom = self.rect.bottom - self.velocity.y * last_dt
        prev_top = self.rect.top - self.velocity.y * last_dt

        for tilemap in self.game.tilemaps.values():
            if not tilemap.rendered:
                continue

            for sub, td in self._iter_solid_subrects_near(tilemap):
                props = td.get('properties', [])
                is_solid = 'solid' in props
                is_platform = 'platform' in props
                if not (is_solid or is_platform):
                    continue
                if not self.rect.colliderect(sub):
                    continue

                if self.velocity.y >= 0:
                    if prev_bottom > sub.top + 1:
                        continue
                    self.rect.bottom = sub.top
                    return True
                elif self.velocity.y < 0 and is_solid:
                    if prev_top < sub.bottom - 1:
                        continue
                    self.rect.top = sub.bottom
                    return True

            for breakable in tilemap.breakables.sprite_dict.values():
                if not breakable.is_solid():
                    continue
                if not self.rect.colliderect(breakable.rect):
                    continue
                if self.velocity.y > 0 and prev_bottom <= breakable.rect.top + 1:
                    self.rect.bottom = breakable.rect.top
                    return True
                elif self.velocity.y < 0 and prev_top >= breakable.rect.bottom - 1:
                    self.rect.top = breakable.rect.bottom
                    return True
        return False

    def check_collisions(self):
        wall_collision = self.check_wall_collisions()
        ground_collision = self.check_ground_collisions()
        return wall_collision or ground_collision

    def draw(self, surf, offset=(0, 0)):
        if not self.attributes["visible"]:
            return

        if hasattr(self, 'image') and self.image:
            display_image = self.image

            if self.attributes["flipped"]:
                display_image = pygame.transform.flip(self.image, True, False)

            screen_pos = (self.visual_rect.x - self.game.camera.offset.x,
                         self.visual_rect.y - self.game.camera.offset.y)
            surf.blit(display_image, screen_pos)

            from Game.utils.config import get_config
            config = get_config()
            if config.get("debug", {}).get("show_collision_boxes", False):
                screen_collision_rect = (self.rect.x - self.game.camera.offset.x,
                                       self.rect.y - self.game.camera.offset.y,
                                       self.rect.width, self.rect.height)
                screen_visual_rect = (self.visual_rect.x - self.game.camera.offset.x,
                                    self.visual_rect.y - self.game.camera.offset.y,
                                    self.visual_rect.width, self.visual_rect.height)
                pygame.draw.rect(surf, (255, 0, 0), screen_collision_rect, 2)
                pygame.draw.rect(surf, (0, 0, 255), screen_visual_rect, 1)
