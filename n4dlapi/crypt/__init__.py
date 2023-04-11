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
    def decrypt(basename: str, data: bytes) -> bytes:
        return b""


DECRYPTER_BACKENDS: list[_SupportsDecryptBackend] = [libhonoka, honkypy]

try:
    SELECTED_BACKEND = list(filter(lambda x: x.available(), DECRYPTER_BACKENDS))[0]
except IndexError:
    raise Exception("No available decrypter backends available") from None

print("Decrypter backend:", SELECTED_BACKEND)


def decrypt(filename: str, data: bytes):
    return SELECTED_BACKEND.decrypt(os.path.basename(filename), data)
