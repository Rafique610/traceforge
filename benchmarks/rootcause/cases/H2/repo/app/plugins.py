import importlib


def run(name, value):
    module = importlib.import_module(f"app.plugin_{name}")
    return module.apply(value)
