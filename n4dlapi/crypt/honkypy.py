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
