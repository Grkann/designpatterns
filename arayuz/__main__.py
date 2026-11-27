"""Arayüzü başlatır:  python -m arayuz   (isteğe bağlı port: python -m arayuz 8080)"""

import sys
import webbrowser

from .server import DemoServer


def main() -> None:
    ports = [a for a in sys.argv[1:] if a.isdigit()]
    port = int(ports[0]) if ports else 8000
    server = DemoServer(("127.0.0.1", port))
    url = f"http://127.0.0.1:{port}"
    print(f"Arayüz açık: {url}  (kapatmak için Ctrl+C)")
    if "--no-browser" not in sys.argv:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nKapatıldı.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
