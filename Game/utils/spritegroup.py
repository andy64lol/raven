class SpriteGroup:
    def __init__(self):
        self.sprite_dict = {}

    def add(self, *sprites):
        for sprite in sprites:
            if hasattr(sprite, 'id'):
                self.sprite_dict[sprite.id] = sprite

    def append(self, sprite):
        if hasattr(sprite, 'id'):
            self.sprite_dict[sprite.id] = sprite
        else:
            self.sprite_dict[len(self.sprite_dict)] = sprite

    def remove(self, *sprites):
        for sprite in sprites:
            if hasattr(sprite, 'id') and sprite.id in self.sprite_dict:
                del self.sprite_dict[sprite.id]

    def get_by_id(self, sprite_id):
        return self.sprite_dict.get(sprite_id)

    def empty(self):
        self.sprite_dict.clear()

    def draw(self, surface, offset):
        for sprite in self.sprite_dict.values():
            sprite.draw(surface, offset)

    def update(self, dt):
        for sprite in list(self.sprite_dict.values()):
            sprite.update(dt)

    def __iter__(self):
        return iter(self.sprite_dict.values())

    def __len__(self):
        return len(self.sprite_dict)

    def __contains__(self, item):
        return item in self.sprite_dict.values()
