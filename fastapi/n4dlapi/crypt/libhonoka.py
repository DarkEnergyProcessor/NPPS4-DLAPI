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

import shutil
import subprocess

# HonokaMiku accepts same options as libhonoka.
LIBHONOKA_EXECUTABLE = shutil.which("honoka2") or shutil.which("libhonoka") or shutil.which("HonokaMiku")


def available():
    global LIBHONOKA_EXECUTABLE
    return LIBHONOKA_EXECUTABLE is not None


def decrypt(basename: str, data: bytes):
    global LIBHONOKA_EXECUTABLE
    if LIBHONOKA_EXECUTABLE is None:
        raise RuntimeError("libhonoka is not available")
    process = subprocess.Popen(
        [LIBHONOKA_EXECUTABLE, "-b", basename, "-", "-"], stdin=subprocess.PIPE, stdout=subprocess.PIPE
    )
    result = process.communicate(data)[0]
    if process.wait() != 0:
        raise ValueError("libhonoka failed to decrypt")
    return result
