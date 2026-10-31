"""Compatibility registry for persisted bundled types; new types come from Git."""
from . import legacy_echo

TYPES = {'echo': legacy_echo}
CATALOG = []
