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

try:
    import honkypy

    AVAILABLE = True
except ImportError:
    AVAILABLE = False


def available():
    global AVAILABLE
    return AVAILABLE


def decrypt(basename: str, data: bytes):
    dctx = honkypy.decrypt_setup_probe(basename, data[:16])[0]
    return dctx.decrypt_block(data[dctx.HEADER_SIZE :])
