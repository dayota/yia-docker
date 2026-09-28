import os
import socket

port = int(os.environ["YIA_PYTHON_PORT"])
with socket.create_connection(("127.0.0.1", port), timeout=3):
    pass
