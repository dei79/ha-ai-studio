"""Atomic private persistence. All callers serialize mutations at service level."""
import json
import os
import tempfile
from pathlib import Path


class Store:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)

    def read(self, name, default=None):
        try:
            return json.loads((self.root / name).read_text())
        except FileNotFoundError:
            return default
        # Corrupt state must fail closed; never silently reset persisted action state.

    def write(self, name, value):
        self.bytes(name, (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode())

    def bytes(self, name, value):
        fd, temporary = tempfile.mkstemp(prefix='.', dir=self.root)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(value)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.root / name)
            directory = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
