import os
import sys

from . import libhonoka
from . import honkypy

from typing import Protocol


class _SupportsDecryptBackend(Protocol):
    @staticmethod
    def available() -> bool:
        return False

    @staticmethod
    def decrypt_file(basename: str, dest: str, data: bytes):
        pass


if sys.platform in ("win32", "msys", "cygwin"):
    # Windows process creation is slow. Prioritize HonkyPy
    DECRYPTER_BACKENDS: list[_SupportsDecryptBackend] = [honkypy, libhonoka]
else:
    # Process creation is fast.
    DECRYPTER_BACKENDS: list[_SupportsDecryptBackend] = [libhonoka, honkypy]

SELECTED_BACKEND: _SupportsDecryptBackend | None = None
for backend in DECRYPTER_BACKENDS:
    if backend.available():
        SELECTED_BACKEND = backend
        break

if SELECTED_BACKEND is None:
    raise Exception("No available decrypter backends available")


def decrypt_file(filename: str, dest: str, data: bytes):
    SELECTED_BACKEND.decrypt_file(os.path.basename(filename), dest, data)
