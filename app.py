"""Main entry point to run the Task 3 Full-Stack Web Application."""
import socket
import uvicorn
from backend.config import APP_HOST, APP_PORT
from backend.main import app


def find_available_port(host: str, preferred_port: int, max_tries: int = 20) -> int:
    """Return preferred_port if free; otherwise return the next free port."""
    for offset in range(max_tries):
        port = preferred_port + offset
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    return preferred_port


if __name__ == "__main__":
    port = find_available_port(APP_HOST, APP_PORT)
    print(f"\n============================================================")
    print(f" Task 3 Web Dashboard Ready: http://{APP_HOST}:{port}")
    print(f"============================================================\n")
    uvicorn.run("backend.main:app", host=APP_HOST, port=port, reload=False)
