import json

path = 'Game/config.json'

def get_config():
    with open(path, 'r') as f:
        config = json.load(f)
    return config