class Entity:
    def __init__(self, entity_id):
        self.id = entity_id
        self.components = {}

    def add_component(self, component):
        self.components[type(component).__name__] = component
        component.entity = self

    def get_component(self, component_type):
        return self.components.get(component_type.__name__)

    def has_component(self, component_type):
        return component_type.__name__ in self.components

    def remove_component(self, component_type):
        if component_type.__name__ in self.components:
            del self.components[component_type.__name__]
