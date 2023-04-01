try:
    import honkypy

    AVAILABLE = True
except ImportError:
    AVAILABLE = False


def available():
    global AVAILABLE
    return AVAILABLE


def decrypt_file(basename: str, dest: str, data: bytes):
    dctx = honkypy.decrypt_setup_probe(basename, data[:16])[0]
    decrypted_data = dctx.decrypt_block(data[dctx.HEADER_SIZE :])
    with open(dest, "wb") as f:
        f.write(decrypted_data)
