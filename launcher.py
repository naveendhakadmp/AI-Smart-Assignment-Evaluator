import logging
import os
import socket
import threading
import webbrowser

from waitress import serve

from app import APP_DATA_DIR, app, init_db


def available_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def open_browser(url):
    if os.environ.get("GRADEPILOT_NO_BROWSER") == "1":
        return
    try:
        if not webbrowser.open_new_tab(url):
            logging.error("Could not open the default browser for %s", url)
    except Exception:
        logging.exception("Could not open the default browser for %s", url)


def main():
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=APP_DATA_DIR / "gradepilot.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    init_db()
    port = int(os.environ.get("GRADEPILOT_PORT", "0")) or available_port()
    url = f"http://127.0.0.1:{port}/"
    browser_timer = threading.Timer(1, open_browser, args=(url,))
    browser_timer.daemon = True
    browser_timer.start()
    logging.info("GradePilot starting at %s", url)
    serve(app, host="127.0.0.1", port=port, threads=8)


if __name__ == "__main__":
    main()
