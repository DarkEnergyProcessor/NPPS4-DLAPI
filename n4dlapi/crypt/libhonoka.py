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
