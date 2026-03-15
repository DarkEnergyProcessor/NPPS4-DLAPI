# Copyright (c) 2023 Dark Energy Processor
#
# This software is provided 'as-is', without any express or implied
# warranty. In no event will the authors be held liable for any damages
# arising from the use of this software.
#
# Permission is granted to anyone to use this software for any purpose,
# including commercial applications, and to alter it and redistribute it
# freely, subject to the following restrictions:
#
# 1. The origin of this software must not be misrepresented; you must not
#    claim that you wrote the original software. If you use this software
#    in a product, an acknowledgment in the product documentation would be
#    appreciated but is not required.
# 2. Altered source versions must be plainly marked as such, and must not be
#    misrepresented as being the original software.
# 3. This notice may not be removed or altered from any source distribution.

import os

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
