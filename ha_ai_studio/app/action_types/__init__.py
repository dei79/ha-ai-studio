"""Explicit registry of trusted, bundled action plugins."""
from . import echo
TYPES = {'echo': echo}
CATALOG = [plugin.metadata for plugin in TYPES.values()]
