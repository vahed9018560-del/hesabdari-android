import os
import threading
import time

_server_thread = None

def start_server(db_path):
    global _server_thread
    os.environ["HESABDARI_DB"] = db_path
    os.environ["HESABDARI_SECRET"] = os.environ.get(
        "HESABDARI_SECRET", "local-hesabdari-app-session-key"
    )

    import app as accounting_app

    if _server_thread is None or not _server_thread.is_alive():
        _server_thread = threading.Thread(
            target=lambda: accounting_app.app.run(
                host="127.0.0.1", port=5000, debug=False, threaded=True,
                use_reloader=False
            ),
            daemon=True
        )
        _server_thread.start()
        time.sleep(0.3)
