"""
HelperX Bot — Firebase Sync v1.1
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Bidirektionaler Sync zwischen lokalen JSON-Dateien und Firebase.
  Dashboard schreibt → Firebase → dieser Sync → lokale JSON → Bot liest
  Bot schreibt → lokale JSON → dieser Sync → Firebase → Dashboard liest
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os
import json
import time
import threading
import logging

FIREBASE_DB_URL    = "https://helperx-dashboard-default-rtdb.firebaseio.com"
TICKET_CONFIG_FILE = "ticket_config.json"
SYNC_INTERVAL      = 4

log = logging.getLogger("firebase_sync")

_suppress_push = threading.Event()
_firebase_ready = False


def _load_json(path: str) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.error(f"Fehler beim Lesen von {path}: {e}")
    return {}


def _save_json(path: str, data: dict):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        log.error(f"Fehler beim Schreiben von {path}: {e}")


def _init_firebase() -> bool:
    global _firebase_ready
    try:
        import firebase_admin
        from firebase_admin import credentials, db as rtdb
    except ImportError:
        log.error("❌ firebase-admin nicht installiert!")
        return False

    cred_json = os.environ.get("FIREBASE_CREDENTIALS")
    if not cred_json:
        log.error("❌ FIREBASE_CREDENTIALS nicht gesetzt!")
        return False

    try:
        cred_dict = json.loads(cred_json)

        pk = cred_dict.get("private_key", "")

        # Alle Escape-Varianten abfangen
        pk = pk.replace("\\\\n", "\n").replace("\\n", "\n").replace("\r\n", "\n").replace("\r", "\n")

        # PEM sauber rekonstruieren
        lines = [l.strip() for l in pk.split("\n") if l.strip()]
        pk = "\n".join(lines) + "\n"

        cred_dict["private_key"] = pk

        log.info(
            f"🔑 Key: Länge={len(pk)}, Newlines={pk.count(chr(10))}, "
            f"Start='{pk[:27]}', Ende='{pk[-26:].strip()}'"
        )

        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})
        log.info("✅ Firebase Admin SDK erfolgreich initialisiert.")
        _firebase_ready = True
        return True

    except Exception as e:
        log.error(f"❌ Firebase Initialisierungs-Fehler: {e}")
        return False


def push_config_to_firebase(data: dict = None):
    if not _firebase_ready:
        return
    if _suppress_push.is_set():
        return
    if data is None:
        data = _load_json(TICKET_CONFIG_FILE)
    if not data:
        return
    try:
        from firebase_admin import db as rtdb
        rtdb.reference("/ticket_config").set(data)
        log.info("📤 ticket_config → Firebase gesynct.")
    except Exception as e:
        log.error(f"Firebase Push-Fehler: {e}")


def _on_firebase_change(event):
    if event.data is None:
        return
    log.info("📥 Dashboard-Änderung erkannt → lokale Config wird aktualisiert...")
    _suppress_push.set()
    try:
        _save_json(TICKET_CONFIG_FILE, event.data)
        log.info("✅ ticket_config.json erfolgreich aktualisiert.")
    except Exception as e:
        log.error(f"Fehler beim Schreiben der lokalen Config: {e}")
    finally:
        time.sleep(2)
        _suppress_push.clear()


def _file_watcher():
    last_mtime = 0
    if os.path.exists(TICKET_CONFIG_FILE):
        last_mtime = os.path.getmtime(TICKET_CONFIG_FILE)
    log.info("👁️  File-Watcher für ticket_config.json aktiv.")
    while True:
        try:
            if os.path.exists(TICKET_CONFIG_FILE):
                mtime = os.path.getmtime(TICKET_CONFIG_FILE)
                if mtime != last_mtime:
                    log.info("📂 Lokale Config geändert → Firebase wird aktualisiert...")
                    data = _load_json(TICKET_CONFIG_FILE)
                    push_config_to_firebase(data)
                    last_mtime = mtime
        except Exception as e:
            log.error(f"File-Watcher-Fehler: {e}")
        time.sleep(SYNC_INTERVAL)


def start_sync():
    log.info("🔄 Firebase Sync wird gestartet...")

    if not _init_firebase():
        log.warning("⚠️  Firebase-Sync deaktiviert — Bot läuft ohne Dashboard-Sync.")
        return

    initial_data = _load_json(TICKET_CONFIG_FILE)
    if initial_data:
        push_config_to_firebase(initial_data)
        log.info("📤 Initiale Config zu Firebase gesendet.")
    else:
        log.info("ℹ️  Keine lokale Config gefunden.")

    try:
        from firebase_admin import db as rtdb
        rtdb.reference("/ticket_config").listen(_on_firebase_change)
        log.info("👂 Firebase-Listener aktiv.")
    except Exception as e:
        log.error(f"Firebase-Listener Fehler: {e}")

    watcher_thread = threading.Thread(target=_file_watcher, daemon=True, name="firebase-file-watcher")
    watcher_thread.start()

    log.info("✅ Firebase Sync vollständig gestartet.")
