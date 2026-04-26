import discord
from discord.ext import commands
import os
import logging
import traceback
import shutil
import sys

# ── Firebase Sync ────────────────────────────────────────────────────────────
import threading
try:
    import firebase_sync as _firebase_sync
    _FIREBASE_SYNC_AVAILABLE = True
except ImportError:
    _FIREBASE_SYNC_AVAILABLE = False
    logging.warning("⚠️  firebase_sync.py nicht gefunden — Dashboard-Sync deaktiviert.")

# Cache löschen
if os.path.exists("./features/__pycache__"):
    shutil.rmtree("./features/__pycache__")

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

# ══════════════════════════════════════════════════════════════════════════════
#  MODUS
# ══════════════════════════════════════════════════════════════════════════════
BOT_MODE = "public"

# ══════════════════════════════════════════════════════════════════════════════
#  SERVER-IDs
# ══════════════════════════════════════════════════════════════════════════════
GUILD_IDS = [
    1477774300508590332,
    1493276175429013735,
]

# ══════════════════════════════════════════════════════════════════════════════
#  BOT-VERSION
# ══════════════════════════════════════════════════════════════════════════════
BOT_VERSION = "9.9"

# ══════════════════════════════════════════════════════════════════════════════
#  API-KEYS
# ══════════════════════════════════════════════════════════════════════════════
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY  = os.getenv("GROQ_API_KEY")

# ══════════════════════════════════════════════════════════════════════════════
#  INTENTS
# ══════════════════════════════════════════════════════════════════════════════
intents = discord.Intents.default()
intents.message_content = True
intents.members         = True
intents.presences       = True


# ══════════════════════════════════════════════════════════════════════════════
#  BOT-KLASSE
# ══════════════════════════════════════════════════════════════════════════════
class MyBot(commands.Bot):
    async def setup_hook(self):
        logging.info("🔧 setup_hook gestartet...")
        logging.info(f"🌐 BOT_MODE: {BOT_MODE}")

        features_dir = "./features"
        if not os.path.exists(features_dir):
            logging.error(f"❌ Features-Verzeichnis '{features_dir}' nicht gefunden.")
            return

        for filename in sorted(os.listdir(features_dir)):
            if filename.endswith(".py"):
                ext = f"features.{filename[:-3]}"
                try:
                    await self.load_extension(ext)
                    logging.info(f"✅ Feature '{filename}' geladen.")
                except Exception:
                    logging.error(f"❌ Fehler beim Laden von '{filename}':")
                    traceback.print_exc()

        if BOT_MODE == "dev":
            for gid in GUILD_IDS:
                guild = discord.Object(id=gid)
                try:
                    synced = await self.tree.sync(guild=guild)
                    logging.info(
                        f"🔄 [DEV] Guild {gid}: {len(synced)} Command(s) gesynct: "
                        f"{[c.name for c in synced]}"
                    )
                except Exception:
                    logging.error(f"❌ Sync-Fehler für Guild {gid}:")
                    traceback.print_exc()

        elif BOT_MODE == "public":
            try:
                synced = await self.tree.sync()
                logging.info(
                    f"🌍 [PUBLIC] Global gesynct: {len(synced)} Command(s): "
                    f"{[c.name for c in synced]}"
                )
            except Exception:
                logging.error("❌ Globaler Sync-Fehler:")
                traceback.print_exc()

            for gid in GUILD_IDS:
                guild = discord.Object(id=gid)
                try:
                    synced_guild = await self.tree.sync(guild=guild)
                    logging.info(
                        f"🔄 [PUBLIC] Guild {gid}: {len(synced_guild)} guild-spez. "
                        f"Command(s) gesynct: {[c.name for c in synced_guild]}"
                    )
                except Exception:
                    logging.error(f"❌ Guild-Sync-Fehler für {gid}:")
                    traceback.print_exc()

        else:
            logging.error(f"❌ Unbekannter BOT_MODE: '{BOT_MODE}'")


# ══════════════════════════════════════════════════════════════════════════════
#  BOT INITIALISIEREN
# ══════════════════════════════════════════════════════════════════════════════
bot = MyBot(command_prefix="!", intents=intents)


# ══════════════════════════════════════════════════════════════════════════════
#  SYNC COMMAND
# ══════════════════════════════════════════════════════════════════════════════
@bot.command(name="sync")
@commands.is_owner()
async def sync(ctx: commands.Context):
    """Synct alle Slash-Commands sofort für diesen Server."""
    msg = await ctx.send("🔄 Synce Commands...")
    try:
        synced = await bot.tree.sync(guild=ctx.guild)
        names  = ", ".join(f"`{c.name}`" for c in synced)
        await msg.edit(content=f"✅ **{len(synced)} Command(s) gesynct:**\n{names}")
        logging.info(f"[SYNC] {len(synced)} Commands gesynct (Guild {ctx.guild.id})")
    except Exception as e:
        await msg.edit(content=f"❌ Sync fehlgeschlagen: `{e}`")
        logging.error(f"[SYNC] Fehler: {e}")


# ══════════════════════════════════════════════════════════════════════════════
#  ON READY
# ══════════════════════════════════════════════════════════════════════════════
@bot.event
async def on_ready():
    logging.info(f"✅ {bot.user} ist online! (v{BOT_VERSION} | Modus: {BOT_MODE})")

    # ── Firebase Sync starten ────────────────────────────────────────────────
    if _FIREBASE_SYNC_AVAILABLE:
        threading.Thread(
            target=_firebase_sync.start_sync,
            daemon=True,
            name="firebase-sync",
        ).start()
        logging.info("🔥 Firebase Sync-Thread gestartet.")
    else:
        logging.warning("⚠️  Firebase Sync nicht verfügbar.")

    logging.info(f"📋 Registrierte Commands: {[c.name for c in bot.tree.get_commands()]}")
    logging.info(f"🏠 Aktive Server: {len(bot.guilds)}")
    logging.info(f"🔍 Intents — members: {bot.intents.members} | presences: {bot.intents.presences}")

    post_changelog = getattr(bot, "_helperx_post_changelog", None)
    if post_changelog:
        for gid in GUILD_IDS:
            guild = bot.get_guild(gid)
            if guild:
                try:
                    await post_changelog(guild)
                    logging.info(f"✅ Changelog gepostet (Guild {gid}).")
                except Exception:
                    traceback.print_exc()
            else:
                logging.warning(f"⚠️  Guild {gid} nicht gefunden – Changelog übersprungen.")
    else:
        logging.warning("⚠️  _helperx_post_changelog nicht registriert.")


# ══════════════════════════════════════════════════════════════════════════════
#  START
# ══════════════════════════════════════════════════════════════════════════════
def main():
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()
