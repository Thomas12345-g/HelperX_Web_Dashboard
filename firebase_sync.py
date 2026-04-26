"""
HelperX Bot — Firebase Sync v1.4
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
import tempfile

# ══════════════════════════════════════════════════════════════════════════════
#  KONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════
FIREBASE_DB_URL    = "https://helperx-dashboard-default-rtdb.firebaseio.com"
TICKET_CONFIG_FILE = "ticket_config.json"
SYNC_INTERVAL      = 4

# ══════════════════════════════════════════════════════════════════════════════

log = logging.getLogger("firebase_sync")

_suppress_push = threading.Event()
_firebase_ready = False


# ──────────────────────────────────────────────────────────────────────────────
#  JSON HELFER
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
#  FIREBASE INITIALISIERUNG
# ──────────────────────────────────────────────────────────────────────────────

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

    tmp_path = None
    try:
        # 1. JSON parsen → \n werden zu echten Newlines
        cred_dict = json.loads(cred_json)

        # 2. Sauber als Datei schreiben via json.dump (nicht raw string!)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            json.dump(cred_dict, f)
            tmp_path = f.name

        # 3. Firebase mit Datei initialisieren
        cred = credentials.Certificate(tmp_path)
        firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DB_URL})
        log.info("✅ Firebase Admin SDK erfolgreich initialisiert.")
        _firebase_ready = True
        return True

    except Exception as e:
        log.error(f"❌ Firebase Initialisierungs-Fehler: {e}")
        return False

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ──────────────────────────────────────────────────────────────────────────────
#  PUSH: Lokale Config → Firebase
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
#  LISTENER: Firebase → Lokale Config
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
#  FILE WATCHER: Lokale Config → Firebase
# ──────────────────────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────────────────────
#  EINSTIEGSPUNKT
# ──────────────────────────────────────────────────────────────────────────────

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
        log.info("ℹ️  Keine lokale Config gefunden — warte auf erste Konfiguration.")

    try:
        from firebase_admin import db as rtdb
        rtdb.reference("/ticket_config").listen(_on_firebase_change)
        log.info("👂 Firebase-Listener aktiv (Dashboard → Bot).")
    except Exception as e:
        log.error(f"Firebase-Listener konnte nicht gestartet werden: {e}")

    watcher_thread = threading.Thread(target=_file_watcher, daemon=True, name="firebase-file-watcher")
    watcher_thread.start()

    log.info("✅ Firebase Sync vollständig gestartet.")
