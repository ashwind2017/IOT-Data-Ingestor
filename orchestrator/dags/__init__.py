"""DAG modules registered at import time."""

import importlib
import pkgutil


_loaded = False


def load_all_dags() -> None:
    """Import every DAG module so registration side-effects fire."""
    global _loaded
    if _loaded:
        return
    for mod_info in pkgutil.iter_modules(__path__):
        if mod_info.name.startswith('_'):
            continue
        importlib.import_module(f'{__name__}.{mod_info.name}')
    _loaded = True
