"""
HelperX Bot — Premium Ticket System v2.3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Einzigartige Features:
  • Unbegrenzte Kategorien mit eigenem KI-Kontext & Staff-Rolle
  • ✨ NEU: Jede Ticket-Kategorie kann in einen eigenen Discord-Ordner
  • Groq KI — antwortet automatisch & passend zur Kategorie
  • KI kennt den konfigurierten Roblox-Server genau
  • KI erkennt Komplexität → eskaliert selbst → deaktiviert sich
  • KI global aktivierbar/deaktivierbar über Config-Menü
  • Transkript per DM nach Schließen (als .txt Anhang)
  • 1–5 Sterne Bewertungssystem per DM nach Ticket-Schließung
  • Ticket-Claiming, Prioritäten (4 Stufen), User hinzufügen
  • Ticket-Sichtbarkeit: separate Lese-Rollen konfigurierbar
  • Vollständiges Logging, Ticket-Stats
  • /ticket-config  — Alles per Dropdown konfigurieren (Menü bleibt offen!)
  • /ticket-stats   — Statistiken & Bewertungsübersicht
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import discord
import asyncio
import aiohttp
import json
import os
import io
import uuid
import traceback
from typing import Optional
from datetime import datetime, timezone
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Modal, TextInput, Select

# ══════════════════════════════════════════════════════════════════════════════
#  IMPORTS AUS bot.py
# ══════════════════════════════════════════════════════════════════════════════

try:
    from bot import (
        BOT_VERSION, GUILD_ID,
        _load, _save, _embed, _ok, _err, _info,
        _resolve_channel,
    )
except ImportError:
    BOT_VERSION = "9.0"
    GUILD_ID    = 0

    def _load(path, default):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return default

    def _save(path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _embed(title, description="", color=0x5865F2):
        e = discord.Embed(title=title, description=description, color=color)
        e.timestamp = datetime.now(timezone.utc)
        return e

    def _ok(t):  return _embed("✅ Erledigt", t, 0x57F287)
    def _err(t): return _embed("❌ Fehler",   t, 0xED4245)
    def _info(t, h="ℹ️ Info"): return _embed(h, t, 0x5865F2)

    def _resolve_channel(guild, value):
        value = str(value).strip()
        if value.startswith("<#") and value.endswith(">"):
            cid = value[2:-1]
            if cid.isdigit(): return guild.get_channel(int(cid))
        if value.isdigit(): return guild.get_channel(int(value))
        return discord.utils.find(
            lambda c: c.name.lower() == value.lstrip("#").lower(),
            guild.channels,
        )


_GROQ_API_KEY_FALLBACK = ""

def _get_groq_key() -> str:
    try:
        import bot as _bot_mod
        return _bot_mod.GROQ_API_KEY
    except Exception:
        return os.environ.get("GROQ_API_KEY", _GROQ_API_KEY_FALLBACK)


# ══════════════════════════════════════════════════════════════════════════════
#  PERSISTENZ
# ══════════════════════════════════════════════════════════════════════════════

TICKET_CONFIG_FILE  = "ticket_config.json"
TICKET_DATA_FILE    = "ticket_data.json"
TICKET_RATINGS_FILE = "ticket_ratings.json"

_cfg_data:    dict = {}
_ticket_data: dict = {}
_rating_data: dict = {}


def _load_all():
    global _cfg_data, _ticket_data, _rating_data
    _cfg_data    = _load(TICKET_CONFIG_FILE,  {})
    _ticket_data = _load(TICKET_DATA_FILE,    {})
    _rating_data = _load(TICKET_RATINGS_FILE, {})

def _save_cfg():     _save(TICKET_CONFIG_FILE,  _cfg_data)
def _save_tickets(): _save(TICKET_DATA_FILE,    _ticket_data)
def _save_ratings(): _save(TICKET_RATINGS_FILE, _rating_data)


# ── Bekannte Roblox-Spiele ────────────────────────────────────────────────────
_ROBLOX_GAMES = {
    "erlc": {
        "label":       "Emergency Response Liberty County (ERLC)",
        "short":       "ERLC",
        "description": (
            "Emergency Response Liberty County (kurz ERLC) ist ein Roblox-Spiel, "
            "in dem Spieler Polizei, Feuerwehr, Sanitäter oder Zivilisten spielen. "
            "Es gibt verschiedene Abteilungen (z.B. LSPD, LSFD, EMS). "
            "Spieler können Fahrzeuge fahren, Einsätze abarbeiten und miteinander interagieren. "
            "Es gibt Server-Regeln, Whitelist-Systeme und oft eine eigene Community-Struktur. "
            "Typische Themen: Regelbrüche melden, Whitelist-Anfragen, Rang-Anfragen, "
            "technische Probleme im Spiel, Ban-Einsprüche, Bewerbungen."
        ),
    },
    "notruf_hh": {
        "label":       "Notruf Hamburg",
        "short":       "Notruf Hamburg",
        "description": (
            "Notruf Hamburg ist ein deutsches Roblox-Roleplay-Spiel, das in Hamburg spielt. "
            "Spieler übernehmen Rollen als Polizei (z.B. Hamburger Polizei), Feuerwehr, "
            "Rettungsdienst oder Zivilisten. Das Spiel legt Wert auf realistische deutsche "
            "Einsatzszenarien. Es gibt Abteilungen, Dienstgrade, Whitelists und "
            "Community-Regeln. Typische Themen: Regelbrüche, Bewerbungen, Whitelisting, "
            "Rang-Fragen, In-Game-Probleme, Teamkonflikte, Ban-Einsprüche."
        ),
    },
    "notruf_em": {
        "label":       "Notruf Emden",
        "short":       "Notruf Emden",
        "description": (
            "Notruf Emden ist ein deutsches Roblox-Roleplay-Spiel, das in der Stadt Emden spielt. "
            "Spieler spielen Polizei, Feuerwehr, Rettungsdienst oder Zivilisten in einem "
            "realistischen deutschen Umfeld. Das Spiel hat eigene Abteilungen, Dienstgrade "
            "und Community-Regeln. Typische Themen: Regelbrüche melden, Bewerbungen, "
            "Whitelisting, Dienstgrad-Anfragen, technische In-Game-Probleme, Ban-Einsprüche."
        ),
    },
    "custom": {
        "label":       "Anderes / Manuell konfiguriert",
        "short":       "Unbekanntes Spiel",
        "description": (
            "Es wurde kein spezifisches Spiel ausgewählt. "
            "Bitte hilf dem User so gut du kannst mit allgemeinen Roblox-Roleplay-Informationen."
        ),
    },
}


def _guild_cfg(guild_id: int) -> dict:
    gid = str(guild_id)
    if gid not in _cfg_data:
        _cfg_data[gid] = {
            "panel_channel":      None,
            "panel_msg_id":       None,
            "log_channel":        None,
            "staff_roles":        [],
            "ticket_category":    None,
            "ticket_counter":     0,
            "banner_url":         "",
            "thumbnail_url":      "",
            "ai_globally_enabled": True,
            "viewer_roles":        [],
            "roblox_game":         "custom",
            "roblox_game_custom":  "",
            "categories": [
                {
                    "id":                  "cat_support",
                    "name":                "Allgemeiner Support",
                    "emoji":               "🆘",
                    "description":         "Hilfe bei allgemeinen Fragen oder Problemen",
                    "color":               0x5865F2,
                    "staff_role":          None,
                    "ai_hint":             "Helfe dem User freundlich mit allgemeinen Fragen zum Server.",
                    "discord_category_id": None,  # ✨ NEU: eigener Discord-Ordner
                },
                {
                    "id":                  "cat_beschwerde",
                    "name":                "Beschwerde",
                    "emoji":               "📢",
                    "description":         "Melde Regelbrüche oder unangemessenes Verhalten",
                    "color":               0xED4245,
                    "staff_role":          None,
                    "ai_hint":             "Nimm die Beschwerde ernst, bitte um Details (Name, Zeitpunkt, Beweise). Eskaliere zu Staff.",
                    "discord_category_id": None,
                },
                {
                    "id":                  "cat_sonstiges",
                    "name":                "Sonstiges",
                    "emoji":               "💬",
                    "description":         "Alle anderen Anliegen",
                    "color":               0xFEE75C,
                    "staff_role":          None,
                    "ai_hint":             "Versuche zu helfen. Bei Unklarheit eskaliere zum Team.",
                    "discord_category_id": None,
                },
            ],
        }
        _save_cfg()

    # Fehlende Felder in bestehenden Einträgen nachrüsten (Migration)
    cfg     = _cfg_data[gid]
    changed = False
    for key, default in [
        ("ai_globally_enabled", True),
        ("viewer_roles",        []),
        ("roblox_game",         "custom"),
        ("roblox_game_custom",  ""),
    ]:
        if key not in cfg:
            cfg[key] = default
            changed  = True

    # ✨ NEU: Migration — discord_category_id in bestehende Kategorien einfügen
    for cat in cfg.get("categories", []):
        if "discord_category_id" not in cat:
            cat["discord_category_id"] = None
            changed = True

    if changed:
        _save_cfg()

    return _cfg_data[gid]


# ══════════════════════════════════════════════════════════════════════════════
#  HILFSFUNKTION: Discord-Ordner für eine Ticket-Kategorie ermitteln
# ══════════════════════════════════════════════════════════════════════════════

def _resolve_discord_category(
    guild: discord.Guild,
    cat: dict,
    cfg: dict,
) -> Optional[discord.CategoryChannel]:
    """
    Gibt den Discord-Kategorie-Kanal zurück, in den ein Ticket soll.
    Priorität:
      1. discord_category_id der Ticket-Kategorie (kategorie-spezifisch)
      2. ticket_category aus der globalen Config (globaler Fallback)
      3. None (kein Ordner)
    """
    # 1. Kategorie-spezifischer Ordner
    cat_specific = cat.get("discord_category_id")
    if cat_specific:
        ch = guild.get_channel(int(cat_specific))
        if isinstance(ch, discord.CategoryChannel):
            return ch

    # 2. Globaler Fallback
    global_cat = cfg.get("ticket_category")
    if global_cat:
        ch = guild.get_channel(int(global_cat))
        if isinstance(ch, discord.CategoryChannel):
            return ch

    return None


# ══════════════════════════════════════════════════════════════════════════════
#  KI — GROQ INTEGRATION  (nur Deutsch)
# ══════════════════════════════════════════════════════════════════════════════

def _build_ai_system(cfg: dict, category_name: str, category_hint: str, user_name: str) -> str:
    game_key  = cfg.get("roblox_game", "custom")
    game_info = _ROBLOX_GAMES.get(game_key, _ROBLOX_GAMES["custom"])
    game_name = game_info["short"]

    if game_key == "custom" and cfg.get("roblox_game_custom", "").strip():
        game_name        = cfg["roblox_game_custom"].strip()
        game_description = (
            f"Es handelt sich um einen Roblox-Roleplay-Server namens '{game_name}'. "
            f"Bitte hilf dem User mit Fragen zu diesem Server."
        )
    else:
        game_description = game_info["description"]

    system = f"""Du bist HelperX, der offizielle KI-Support-Assistent für den Discord-Server von **{game_name}**.

ÜBER DEN SERVER / DAS SPIEL:
{game_description}

Du antwortest ausschließlich auf Deutsch, warmherzig und professionell.
Du hilfst dem User passend zu seiner Ticket-Kategorie: **{category_name}**
Aktueller User: {user_name}
"""

    if category_hint:
        system += f"\nKategorie-Hinweis vom Server-Team: {category_hint}\n"

    system += """
DEINE REGELN:
• Antworte immer auf Deutsch — egal in welcher Sprache der User schreibt
• Antworte präzise, empathisch und hilfreich
• Nutze Discord-Formatierung: **fett**, *kursiv*, passende Emojis
• Halte Antworten kompakt (max. 250 Wörter)
• Stelle Rückfragen wenn der User sein Anliegen noch nicht klar beschrieben hat
• Versuche IMMER zuerst selbst zu helfen — mindestens 3–4 Nachrichten lang
• Bei Small-Talk oder unklaren Nachrichten: freundlich antworten und nach dem eigentlichen Anliegen fragen — KEIN [ESKALIERE]
• [ESKALIERE] NUR wenn ALLE folgenden Bedingungen erfüllt sind:
  1. Das Problem ist eindeutig zu komplex/sensibel für eine KI (z.B. aktiver Ban-Einspruch, technischer Bug mit Beweisen, Teamkonflikt)
  2. Du hast bereits mindestens 2 Antworten gegeben und kannst definitiv nicht weiterhelfen
  3. Menschliches Eingreifen ist zwingend notwendig
• Bei einfachen Fragen, Small-Talk, Grüßen oder unklaren Anfragen: NIEMALS [ESKALIERE] verwenden
• Erfinde KEINE Regeln oder Informationen — wenn du etwas nicht weißt, sage es ehrlich und bitte den User zu warten, bis Staff antwortet"""

    return system


async def _ki_antwort(
    cfg: dict,
    category_name: str,
    category_hint: str,
    user_name: str,
    conversation: list,
) -> tuple:
    groq_key = _get_groq_key()
    if not groq_key:
        return (
            "⚠️ Der KI-Assistent ist momentan nicht erreichbar. "
            "Das Support-Team wird sich gleich um dein Anliegen kümmern!",
            True,
        )

    system   = _build_ai_system(cfg, category_name, category_hint, user_name)
    messages = [{"role": "system", "content": system}] + conversation

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type":  "application/json",
                },
                json={
                    "model":       "llama-3.3-70b-versatile",
                    "max_tokens":  600,
                    "temperature": 0.72,
                    "messages":    messages,
                },
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                if resp.status != 200:
                    return (
                        f"⚠️ KI antwortet gerade nicht (HTTP {resp.status}). "
                        f"Das Team übernimmt!",
                        True,
                    )
                data       = await resp.json()
                text       = data["choices"][0]["message"]["content"].strip()
                eskalieren = "[ESKALIERE]" in text
                text       = text.replace("[ESKALIERE]", "").strip()
                return text, eskalieren

    except asyncio.TimeoutError:
        return "⚠️ KI-Timeout. Das Team übernimmt dein Ticket!", True
    except Exception as ex:
        return f"⚠️ KI-Fehler: `{ex}`\nDas Team wird benachrichtigt.", True


# ══════════════════════════════════════════════════════════════════════════════
#  TICKET PANEL
# ══════════════════════════════════════════════════════════════════════════════

def _sanitize_categories(cats: list) -> list:
    clean = []
    for c in cats:
        if not c.get("name"):
            continue
        clean.append({
            "id":                  c.get("id", str(uuid.uuid4())[:8]),
            "name":                c["name"],
            "emoji":               c.get("emoji") or "🎫",
            "description":         c.get("description") or "",
            "color":               c.get("color", 0x5865F2),
            "staff_role":          c.get("staff_role"),
            "ai_hint":             c.get("ai_hint") or "",
            "discord_category_id": c.get("discord_category_id"),  # ✨ NEU
        })
    return clean


def _build_panel_embed(cfg: dict) -> discord.Embed:
    e = discord.Embed(color=0x2B2D31)
    e.title = "🎫  T I C K E T  S U P P O R T"

    cats = _sanitize_categories(cfg.get("categories", []))
    if cats:
        lines = "\n".join(
            f"{c['emoji']} **{c['name']}** — {c['description']}"
            for c in cats
        )
        e.description = (
            f"{lines}\n\n"
            f"─────────────────────────────────\n"
            f"**Hinweis:**\n"
            f"Bitte eröffne Tickets nur für ernsthafte Anliegen und wähle "
            f"die passende Kategorie, damit wir dir schneller helfen können."
        )
    else:
        e.description = "Wähle unten eine Kategorie, um ein Ticket zu öffnen."

    if cfg.get("banner_url"):
        e.set_image(url=cfg["banner_url"])
    if cfg.get("thumbnail_url"):
        e.set_thumbnail(url=cfg["thumbnail_url"])

    e.set_footer(text=f"HelperX v{BOT_VERSION}  •  Wähle eine Kategorie im Menü unten")
    e.timestamp = datetime.now(timezone.utc)
    return e


class TicketPanelView(View):
    def __init__(self, cfg: dict):
        super().__init__(timeout=None)
        cats = _sanitize_categories(cfg.get("categories", []))
        if not cats:
            return
        options = []
        for cat in cats[:25]:
            options.append(discord.SelectOption(
                label       = cat["name"][:100],
                value       = cat["id"],
                description = cat["description"][:100] or None,
                emoji       = cat["emoji"],
            ))
        self.add_item(_CategorySelect(options))


class _CategorySelect(Select):
    def __init__(self, options: list):
        super().__init__(
            placeholder = "📂  Wähle eine Kategorie ...",
            options     = options,
            custom_id   = "helperx_ticket_cat_select",
            min_values  = 1,
            max_values  = 1,
            row         = 0,
        )

    async def callback(self, interaction: discord.Interaction):
        cat_id = self.values[0]
        cfg    = _guild_cfg(interaction.guild_id)
        cat    = next((c for c in cfg.get("categories", []) if c["id"] == cat_id), None)

        if not cat:
            await interaction.response.send_message(
                embed=_err("Diese Kategorie existiert nicht mehr. Bitte Panel aktualisieren."),
                ephemeral=True,
            )
            return

        uid = str(interaction.user.id)
        gid = str(interaction.guild_id)
        for t in _ticket_data.values():
            if (t.get("user_id") == uid
                    and t.get("guild_id") == gid
                    and t.get("status") in ("open", "claimed", "escalated")):
                ch_exists = interaction.guild.get_channel(int(t["channel_id"])) is not None
                if not ch_exists:
                    t["status"]      = "closed"
                    t["closed_at"]   = datetime.now(timezone.utc).isoformat()
                    t["close_grund"] = "Kanal manuell gelöscht (automatisch geschlossen)"
                    _save_tickets()
                    continue
                await interaction.response.send_message(
                    embed=_err(
                        f"Du hast bereits ein offenes Ticket!\n"
                        f"Bitte schließe es zuerst: <#{t['channel_id']}>"
                    ),
                    ephemeral=True,
                )
                return

        await interaction.response.send_modal(_TicketOpenModal(cat))


class _TicketOpenModal(Modal):
    betreff = TextInput(
        label       = "Betreff",
        placeholder = "Kurze Zusammenfassung deines Anliegens",
        max_length  = 100,
        required    = True,
    )
    beschreibung = TextInput(
        label       = "Beschreibung",
        placeholder = "Beschreibe dein Anliegen so genau wie möglich ...",
        style       = discord.TextStyle.paragraph,
        max_length  = 1000,
        required    = True,
    )

    def __init__(self, cat: dict):
        super().__init__(title=f"{cat.get('emoji', '🎫')} {cat.get('name', 'Ticket')}")
        self._cat = cat

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await _erstelle_ticket(
            interaction,
            self._cat,
            self.betreff.value.strip(),
            self.beschreibung.value.strip(),
        )


# ══════════════════════════════════════════════════════════════════════════════
#  TICKET ERSTELLEN
# ══════════════════════════════════════════════════════════════════════════════

async def _erstelle_ticket(
    interaction: discord.Interaction,
    cat: dict,
    betreff: str,
    beschreibung: str,
):
    guild = interaction.guild
    user  = interaction.user
    cfg   = _guild_cfg(guild.id)

    cfg["ticket_counter"] = cfg.get("ticket_counter", 0) + 1
    num = cfg["ticket_counter"]
    _save_cfg()

    # ✨ NEU: Kategorie-spezifischen Discord-Ordner ermitteln (mit globalem Fallback)
    discord_cat = _resolve_discord_category(guild, cat, cfg)

    overwrites = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        user: discord.PermissionOverwrite(
            view_channel=True, send_messages=True,
            read_message_history=True, attach_files=True,
        ),
        guild.me: discord.PermissionOverwrite(
            view_channel=True, send_messages=True, manage_messages=True,
            manage_channels=True, read_message_history=True,
        ),
    }

    for role_id in cfg.get("staff_roles", []):
        role = guild.get_role(int(role_id))
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                read_message_history=True, manage_messages=True,
            )

    if cat.get("staff_role"):
        role = guild.get_role(int(cat["staff_role"]))
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel=True, send_messages=True,
                read_message_history=True, manage_messages=True,
            )

    for role_id in cfg.get("viewer_roles", []):
        role = guild.get_role(int(role_id))
        if role:
            overwrites[role] = discord.PermissionOverwrite(
                view_channel         = True,
                read_message_history = True,
                send_messages        = False,
                attach_files         = False,
            )

    safe_name = user.name[:18].lower().replace(" ", "-")
    chan_name  = f"ticket-{num:04d}-{safe_name}"
    try:
        channel = await guild.create_text_channel(
            name       = chan_name,
            overwrites = overwrites,
            category   = discord_cat,
            topic      = (
                f"Ticket #{num:04d} | {cat.get('emoji', '🎫')} {cat.get('name', '?')} | "
                f"{user.display_name} | {betreff}"
            ),
        )
    except discord.Forbidden:
        await interaction.followup.send(
            embed=_err("Keine Berechtigung zum Erstellen von Kanälen!"), ephemeral=True
        )
        return
    except Exception as ex:
        await interaction.followup.send(embed=_err(f"Fehler: {ex}"), ephemeral=True)
        return

    ai_active = cfg.get("ai_globally_enabled", True)

    now    = datetime.now(timezone.utc).isoformat()
    ticket = {
        "guild_id":          str(guild.id),
        "channel_id":        str(channel.id),
        "user_id":           str(user.id),
        "user_name":         user.display_name,
        "category_id":       cat["id"],
        "category":          cat.get("name", "?"),
        "betreff":           betreff,
        "beschreibung":      beschreibung,
        "ticket_num":        num,
        "status":            "open",
        "ai_active":         ai_active,
        "ai_response_count": 0,
        "ai_escalate_count": 0,
        "claimed_by":        None,
        "priority":          "normal",
        "created_at":        now,
        "closed_at":         None,
        "close_grund":       "",
        "rating":            None,
        "conversation":      [],
    }
    _ticket_data[str(channel.id)] = ticket
    _save_tickets()

    color    = cat.get("color", 0x5865F2)
    ai_label = "✅ Aktiv" if ai_active else "⛔ Deaktiviert"

    game_key   = cfg.get("roblox_game", "custom")
    game_info  = _ROBLOX_GAMES.get(game_key, _ROBLOX_GAMES["custom"])
    game_label = cfg.get("roblox_game_custom", "").strip() if game_key == "custom" else game_info["short"]
    if not game_label:
        game_label = game_info["short"]

    # ✨ NEU: Ordner-Info für Embed
    ordner_label = discord_cat.name if discord_cat else "Kein Ordner"

    embed = discord.Embed(
        title = f"{cat.get('emoji', '🎫')} Ticket #{num:04d} — {betreff}",
        color = color,
    )
    embed.add_field(name="👤 Erstellt von", value=user.mention,                                         inline=True)
    embed.add_field(name="📂 Kategorie",    value=f"{cat.get('emoji', '🎫')} {cat.get('name', '?')}",  inline=True)
    embed.add_field(name="📁 Ordner",       value=ordner_label,                                         inline=True)
    embed.add_field(name="🎮 Server",       value=game_label,                                           inline=True)
    embed.add_field(name="🤖 KI-Status",    value=ai_label,                                             inline=True)
    embed.add_field(name="📋 Beschreibung",
                    value=f"```{beschreibung[:900]}```", inline=False)
    embed.set_footer(text=f"HelperX v{BOT_VERSION} · Ticket #{num:04d}")
    embed.timestamp = datetime.now(timezone.utc)

    ctrl_view = _TicketControlView(str(channel.id))
    await channel.send(content=user.mention, embed=embed, view=ctrl_view)

    await interaction.followup.send(
        embed=_ok(
            f"Dein Ticket wurde erstellt: {channel.mention}\n"
            f"{'Unser KI-Assistent meldet sich gleich! 🤖' if ai_active else 'Das Team meldet sich bald! 👋'}"
            + ("" if ai_active else "\n*(KI-Support ist auf diesem Server deaktiviert. Das Team meldet sich bald!)*")
        ),
        ephemeral=True,
    )

    await _log_event(guild, cfg, "opened", ticket, user)

    if ai_active:
        await asyncio.sleep(1.8)
        await _ki_antworten(channel, ticket, beschreibung, guild, cfg)


# ══════════════════════════════════════════════════════════════════════════════
#  TICKET CONTROL PANEL
# ══════════════════════════════════════════════════════════════════════════════

_PRIO_COLORS = {
    "low":    0x57F287,
    "normal": 0x5865F2,
    "high":   0xFEE75C,
    "urgent": 0xED4245,
}
_PRIO_LABELS = {
    "low":    "🟢 Niedrig",
    "normal": "🔵 Normal",
    "high":   "🟡 Hoch",
    "urgent": "🔴 Dringend",
}


class _TicketControlView(View):
    def __init__(self, channel_id: str):
        super().__init__(timeout=None)
        self._ch = channel_id
        self.add_item(_ClaimButton(channel_id))
        self.add_item(_ToggleAIButton(channel_id))
        self.add_item(_AddUserButton(channel_id))
        self.add_item(_CloseButton(channel_id))
        self.add_item(_PrioritySelect(channel_id))


class _ClaimButton(discord.ui.Button):
    def __init__(self, ch: str):
        super().__init__(
            label     = "Übernehmen",
            emoji     = "🙋",
            style     = discord.ButtonStyle.primary,
            custom_id = f"tk_claim_{ch}",
            row       = 0,
        )
        self._ch = ch

   # ══════════════════════════════════════════════════════════════════════════════
#  ERSETZE in ticket.py die callback-Methode von _PrioritySelect
#  (die async def callback Methode innerhalb der _PrioritySelect Klasse)
#
#  VORHER steht dort:
#      async def callback(self, interaction: discord.Interaction):
#          cfg = _guild_cfg(interaction.guild_id)
#          if not _is_staff(interaction.user, cfg):
#          ...
#          await interaction.response.defer()
#
#  ERSETZE den kompletten callback-Block mit diesem hier:
# ══════════════════════════════════════════════════════════════════════════════

    async def callback(self, interaction: discord.Interaction):
        cfg = _guild_cfg(interaction.guild_id)
        if not _is_staff(interaction.user, cfg):
            return await interaction.response.send_message(
                embed=_err("Nur Staff kann die Priorität setzen."), ephemeral=True
            )

        t = _ticket_data.get(self._ch)
        if not t:
            return await interaction.response.send_message(
                embed=_err("Ticket nicht gefunden."), ephemeral=True
            )

        prio      = self.values[0]
        t["priority"] = prio
        _save_tickets()

        label = _PRIO_LABELS[prio]

        # ── Kanal umbenennen je nach Priorität ────────────────────────────
        # Präfix-Mapping
        _PRIO_PREFIX = {
            "low":    "🟢",
            "normal": "🔵",
            "high":   "🟡",
            "urgent": "🔴",
        }

        channel = interaction.channel
        if channel:
            try:
                # Altes Präfix entfernen (falls vorhanden) und neues setzen
                old_name = channel.name
                # Bestehende Prioritäts-Emojis aus dem Namen entfernen
                for emoji in _PRIO_PREFIX.values():
                    if old_name.startswith(emoji + "-"):
                        old_name = old_name[len(emoji) + 1:]
                        break
                    elif old_name.startswith(emoji):
                        old_name = old_name[len(emoji):]
                        break

                # Neuer Name: Emoji-Präfix + alter Name (ohne altes Präfix)
                # Bei "normal" kein Präfix (Standard)
                if prio == "normal":
                    new_name = old_name
                else:
                    new_name = f"{_PRIO_PREFIX[prio]}-{old_name}"

                # Discord erlaubt max 100 Zeichen für Kanalnamen
                new_name = new_name[:100]

                await channel.edit(
                    name   = new_name,
                    reason = f"HelperX Ticket — Priorität gesetzt auf {label}",
                )
            except discord.Forbidden:
                pass  # Keine Berechtigung → trotzdem weitermachen
            except Exception:
                pass

        await interaction.channel.send(embed=discord.Embed(
            description = f"⚡ Priorität gesetzt auf **{label}** von {interaction.user.mention}",
            color       = _PRIO_COLORS[prio],
        ))
        await interaction.response.defer()

        t["claimed_by"] = str(interaction.user.id)
        if t["status"] == "open":
            t["status"] = "claimed"
        _save_tickets()

        await interaction.channel.send(embed=discord.Embed(
            description=f"✋ **{interaction.user.display_name}** hat dieses Ticket übernommen.",
            color=0x57F287,
        ))
        await interaction.response.defer()


class _ToggleAIButton(discord.ui.Button):
    def __init__(self, ch: str):
        t      = _ticket_data.get(ch, {})
        active = t.get("ai_active", True)
        super().__init__(
            label     = "KI aus" if active else "KI an",
            emoji     = "🤖",
            style     = discord.ButtonStyle.secondary,
            custom_id = f"tk_ai_{ch}",
            row       = 0,
        )
        self._ch = ch

    async def callback(self, interaction: discord.Interaction):
        cfg = _guild_cfg(interaction.guild_id)
        if not _is_staff(interaction.user, cfg):
            return await interaction.response.send_message(embed=_err("Nur Staff kann die KI steuern."), ephemeral=True)

        t = _ticket_data.get(self._ch)
        if not t:
            return await interaction.response.send_message(embed=_err("Ticket nicht gefunden."), ephemeral=True)

        t["ai_active"] = not t.get("ai_active", True)
        _save_tickets()

        state = "**aktiviert ✅**" if t["ai_active"] else "**deaktiviert ⛔**"
        await interaction.channel.send(embed=discord.Embed(
            description=f"🤖 KI-Assistent wurde {state} von {interaction.user.mention}",
            color=0x57F287 if t["ai_active"] else 0x808080,
        ))
        await interaction.response.defer()


class _AddUserButton(discord.ui.Button):
    def __init__(self, ch: str):
        super().__init__(
            label     = "User hinzufügen",
            emoji     = "➕",
            style     = discord.ButtonStyle.secondary,
            custom_id = f"tk_add_{ch}",
            row       = 0,
        )
        self._ch = ch

    async def callback(self, interaction: discord.Interaction):
        cfg = _guild_cfg(interaction.guild_id)
        if not _is_staff(interaction.user, cfg):
            return await interaction.response.send_message(embed=_err("Nur Staff kann User hinzufügen."), ephemeral=True)
        await interaction.response.send_modal(_AddUserModal(self._ch))


class _CloseButton(discord.ui.Button):
    def __init__(self, ch: str):
        super().__init__(
            label     = "Schließen",
            emoji     = "🔒",
            style     = discord.ButtonStyle.danger,
            custom_id = f"tk_close_{ch}",
            row       = 0,
        )
        self._ch = ch

    async def callback(self, interaction: discord.Interaction):
        t   = _ticket_data.get(self._ch)
        cfg = _guild_cfg(interaction.guild_id)
        if not t:
            return await interaction.response.send_message(embed=_err("Ticket nicht gefunden."), ephemeral=True)

        is_owner = str(interaction.user.id) == t.get("user_id")
        if not (is_owner or _is_staff(interaction.user, cfg)):
            return await interaction.response.send_message(
                embed=_err("Nur der Ticket-Ersteller oder Staff kann schließen."),
                ephemeral=True,
            )
        await interaction.response.send_modal(_CloseModal(self._ch))


class _PrioritySelect(Select):
    def __init__(self, ch: str):
        super().__init__(
            placeholder = "⚡  Priorität setzen (Staff)",
            custom_id   = f"tk_prio_{ch}",
            options     = [
                discord.SelectOption(label="🟢 Niedrig",  value="low",    description="Keine Eile"),
                discord.SelectOption(label="🔵 Normal",   value="normal", description="Standard"),
                discord.SelectOption(label="🟡 Hoch",     value="high",   description="Zeitnah bearbeiten"),
                discord.SelectOption(label="🔴 Dringend", value="urgent", description="Sofort bearbeiten!"),
            ],
            row=1,
        )
        self._ch = ch

    async def callback(self, interaction: discord.Interaction):
        cfg = _guild_cfg(interaction.guild_id)
        if not _is_staff(interaction.user, cfg):
            return await interaction.response.send_message(embed=_err("Nur Staff kann die Priorität setzen."), ephemeral=True)

        t = _ticket_data.get(self._ch)
        if not t:
            return await interaction.response.send_message(embed=_err("Ticket nicht gefunden."), ephemeral=True)

        prio = self.values[0]
        t["priority"] = prio
        _save_tickets()

        label = _PRIO_LABELS[prio]
        await interaction.channel.send(embed=discord.Embed(
            description=f"⚡ Priorität gesetzt auf **{label}** von {interaction.user.mention}",
            color=_PRIO_COLORS[prio],
        ))
        await interaction.response.defer()


# ══════════════════════════════════════════════════════════════════════════════
#  MODALS (Close / AddUser)
# ══════════════════════════════════════════════════════════════════════════════

class _CloseModal(Modal, title="🔒 Ticket schließen"):
    grund = TextInput(
        label       = "Abschlussgrund (optional)",
        placeholder = "z.B. Problem gelöst · Keine Antwort · Duplikat",
        required    = False,
        max_length  = 200,
    )

    def __init__(self, ch: str):
        super().__init__()
        self._ch = ch

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        await _schliesse_ticket(interaction, self._ch, self.grund.value.strip())


class _AddUserModal(Modal, title="➕ User zum Ticket hinzufügen"):
    user_input = TextInput(
        label       = "User (Mention, ID oder Name)",
        placeholder = "@username  oder  123456789",
        required    = True,
        max_length  = 100,
    )

    def __init__(self, ch: str):
        super().__init__()
        self._ch = ch

    async def on_submit(self, interaction: discord.Interaction):
        val    = self.user_input.value.strip()
        member = _resolve_member(interaction.guild, val)

        if not member:
            return await interaction.response.send_message(
                embed=_err(f"User `{val}` nicht gefunden."), ephemeral=True
            )

        await interaction.channel.set_permissions(
            member,
            view_channel=True, send_messages=True, read_message_history=True,
        )
        await interaction.response.send_message(
            embed=_ok(f"{member.mention} wurde zum Ticket hinzugefügt."), ephemeral=True
        )
        await interaction.channel.send(embed=discord.Embed(
            description=f"➕ {member.mention} wurde von {interaction.user.mention} hinzugefügt.",
            color=0x57F287,
        ))


# ══════════════════════════════════════════════════════════════════════════════
#  KI IM TICKET
# ══════════════════════════════════════════════════════════════════════════════

_MIN_AI_RESPONSES_BEFORE_ESCALATION = 2
_ESCALATE_SIGNALS_NEEDED            = 2


async def _ki_antworten(
    channel: discord.TextChannel,
    ticket: dict,
    user_msg: str,
    guild: discord.Guild,
    cfg: dict,
):
    if not ticket.get("ai_active"):
        return

    conversation = ticket.get("conversation", [])
    conversation.append({"role": "user", "content": user_msg})

    cat_id   = ticket.get("category_id", "")
    cat      = next((c for c in cfg.get("categories", []) if c["id"] == cat_id), None)
    cat_name = ticket.get("category", "Support")
    cat_hint = (cat.get("ai_hint") or "") if cat else ""

    async with channel.typing():
        text, eskalieren = await _ki_antwort(
            cfg, cat_name, cat_hint, ticket.get("user_name", "User"), conversation
        )

    if not text or not text.strip():
        text       = "Ich leite dein Anliegen an einen Mitarbeiter weiter, der dir gleich hilft! 🙋"
        eskalieren = True

    conversation.append({"role": "assistant", "content": text})
    ticket["conversation"]      = conversation[-24:]
    ticket["ai_response_count"] = ticket.get("ai_response_count", 0) + 1

    if eskalieren:
        ticket["ai_escalate_count"] = ticket.get("ai_escalate_count", 0) + 1
    else:
        ticket["ai_escalate_count"] = 0

    _save_tickets()

    ki_embed = discord.Embed(description=text[:4096], color=0x5865F2)
    ki_embed.set_author(name="HelperX KI-Assistent  •  🤖")
    ki_embed.set_footer(
        text="Automatische KI-Antwort  •  Nicht zufrieden? Tippe einfach weiter, das Team hilft dir!"
    )
    await channel.send(embed=ki_embed)

    ai_count       = ticket.get("ai_response_count", 0)
    escalate_count = ticket.get("ai_escalate_count", 0)

    should_escalate = (
        eskalieren
        and ai_count       >= _MIN_AI_RESPONSES_BEFORE_ESCALATION
        and escalate_count >= _ESCALATE_SIGNALS_NEEDED
    )

    if should_escalate:
        await _eskaliere(channel, ticket, guild, cfg)


async def _eskaliere(
    channel: discord.TextChannel,
    ticket: dict,
    guild: discord.Guild,
    cfg: dict,
):
    ticket["ai_active"]         = False
    ticket["status"]            = "escalated"
    ticket["ai_escalate_count"] = 0
    _save_tickets()

    pings = [f"<@&{r}>" for r in cfg.get("staff_roles", [])]
    cat   = next(
        (c for c in cfg.get("categories", []) if c["id"] == ticket.get("category_id")),
        None,
    )
    if cat and cat.get("staff_role"):
        pings.append(f"<@&{cat['staff_role']}>")
    ping_str = " ".join(dict.fromkeys(pings)) or "@here"

    e = discord.Embed(
        title       = "🚨 Eskalation — Menschliche Unterstützung benötigt",
        description = (
            "Die KI hat dieses Anliegen zur Bearbeitung an das Team weitergeleitet.\n\n"
            "**Das Team wurde benachrichtigt und meldet sich gleich.**\n"
            "🤖 KI-Assistent ist jetzt deaktiviert."
        ),
        color=0xED4245,
    )
    e.timestamp = datetime.now(timezone.utc)
    await channel.send(content=ping_str, embed=e)


# ══════════════════════════════════════════════════════════════════════════════
#  TICKET SCHLIESSEN
# ══════════════════════════════════════════════════════════════════════════════

async def _schliesse_ticket(
    interaction: discord.Interaction,
    channel_id: str,
    grund: str,
):
    t = _ticket_data.get(channel_id)
    if not t:
        return await interaction.followup.send(embed=_err("Ticket nicht gefunden."), ephemeral=True)

    channel = interaction.guild.get_channel(int(channel_id))
    if not channel:
        return await interaction.followup.send(embed=_err("Kanal nicht gefunden."), ephemeral=True)

    cfg = _guild_cfg(interaction.guild_id)
    t["status"]      = "closed"
    t["closed_at"]   = datetime.now(timezone.utc).isoformat()
    t["close_grund"] = grund
    _save_tickets()

    close_e = discord.Embed(
        title       = f"🔒 Ticket #{t['ticket_num']:04d} geschlossen",
        description = (
            f"**Geschlossen von:** {interaction.user.mention}\n"
            f"**Grund:** {grund or 'Kein Grund angegeben'}\n\n"
            f"Der Kanal wird in **5 Sekunden** gelöscht.\n"
            f"Du erhältst das Transkript & eine Bewertungsanfrage per DM."
        ),
        color=0xED4245,
    )
    close_e.timestamp = datetime.now(timezone.utc)
    await channel.send(embed=close_e)

    transcript = await _erstelle_transkript(channel, t)

    user = interaction.guild.get_member(int(t["user_id"]))
    if user:
        await _dm_senden(user, t, transcript)

    await _log_event(interaction.guild, cfg, "closed", t, interaction.user, grund)

    await asyncio.sleep(5)
    try:
        await channel.delete(reason=f"Ticket #{t['ticket_num']:04d} geschlossen")
    except Exception:
        pass


async def _erstelle_transkript(channel: discord.TextChannel, ticket: dict) -> discord.File:
    lines = [
        "═══════════════════════════════════════════════════",
        "  HelperX Bot — Ticket Transkript",
        "═══════════════════════════════════════════════════",
        f"  Ticket:      #{ticket['ticket_num']:04d}",
        f"  Betreff:     {ticket.get('betreff', '—')}",
        f"  Kategorie:   {ticket.get('category', '—')}",
        f"  Ersteller:   {ticket.get('user_name', '—')}",
        f"  Erstellt:    {ticket.get('created_at', '—')}",
        f"  Geschlossen: {ticket.get('closed_at', '—')}",
        f"  Grund:       {ticket.get('close_grund') or 'Kein Grund angegeben'}",
        "═══════════════════════════════════════════════════",
        "",
    ]

    try:
        async for msg in channel.history(limit=500, oldest_first=True):
            ts     = msg.created_at.strftime("%d.%m.%Y %H:%M")
            author = msg.author.display_name

            if msg.embeds:
                for emb in msg.embeds:
                    header = f"[{ts}] 🤖 {author}"
                    if emb.title:
                        header += f"  [{emb.title}]"
                    lines.append(header)
                    if emb.description:
                        for ln in emb.description.split("\n"):
                            lines.append(f"  {ln}")
                    lines.append("")
            elif msg.content and not msg.author.bot:
                lines.append(f"[{ts}] {author}:")
                lines.append(f"  {msg.content}")
                lines.append("")
    except Exception as ex:
        lines.append(f"[Fehler beim Lesen der Nachrichten: {ex}]")

    content = "\n".join(lines)
    buf     = io.BytesIO(content.encode("utf-8"))
    buf.seek(0)
    return discord.File(buf, filename=f"ticket-{ticket['ticket_num']:04d}-transkript.txt")


# ══════════════════════════════════════════════════════════════════════════════
#  DM: TRANSKRIPT + BEWERTUNG
# ══════════════════════════════════════════════════════════════════════════════

async def _dm_senden(user: discord.Member, ticket: dict, transcript: discord.File):
    try:
        dm_e = discord.Embed(
            title       = f"🎫 Dein Ticket #{ticket['ticket_num']:04d} wurde geschlossen",
            description = (
                f"**Betreff:** {ticket.get('betreff', '—')}\n"
                f"**Kategorie:** {ticket.get('category', '—')}\n\n"
                f"Das vollständige Transkript findest du im Anhang.\n\n"
                f"Wir würden uns über eine kurze Bewertung freuen — "
                f"sie hilft uns, unseren Support stetig zu verbessern! ⭐"
            ),
            color=0x5865F2,
        )
        dm_e.set_footer(text="HelperX Support · Danke für deine Geduld!")
        dm_e.timestamp = datetime.now(timezone.utc)

        await user.send(embed=dm_e, file=transcript)

        rating_e = discord.Embed(
            title       = "⭐ Wie war unser Support?",
            description = (
                "Bitte bewerte unseren Support für dieses Ticket.\n"
                "Dein Feedback ist uns wichtig und hilft uns, besser zu werden!"
            ),
            color=0xFEE75C,
        )
        rating_e.set_footer(text=f"Bewertung für Ticket #{ticket['ticket_num']:04d}")

        await user.send(
            embed=rating_e,
            view=_RatingView(str(ticket["ticket_num"]), str(user.id)),
        )

    except discord.Forbidden:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  BEWERTUNGSSYSTEM (1–5 Sterne)
# ══════════════════════════════════════════════════════════════════════════════

class _RatingView(View):
    def __init__(self, ticket_num: str, user_id: str):
        super().__init__(timeout=86400)
        for s in range(1, 6):
            self.add_item(_StarButton(s, ticket_num, user_id))


class _StarButton(discord.ui.Button):
    _LABELS    = {1: "1 ★", 2: "2 ★", 3: "3 ★", 4: "4 ★", 5: "5 ★"}
    _STYLES    = {1: discord.ButtonStyle.danger, 2: discord.ButtonStyle.danger,
                  3: discord.ButtonStyle.secondary, 4: discord.ButtonStyle.success, 5: discord.ButtonStyle.success}
    _REACTIONS = {1: "😞", 2: "😕", 3: "😐", 4: "😊", 5: "🤩"}

    def __init__(self, stars: int, ticket_num: str, user_id: str):
        super().__init__(
            label     = self._LABELS[stars],
            style     = self._STYLES[stars],
            custom_id = f"tk_rate_{ticket_num}_{user_id}_{stars}",
            row       = 0,
        )
        self._stars = stars
        self._tnum  = ticket_num
        self._uid   = user_id

    async def callback(self, interaction: discord.Interaction):
        key = f"{self._tnum}_{self._uid}"
        if key in _rating_data:
            return await interaction.response.send_message(
                "Du hast dieses Ticket bereits bewertet!", ephemeral=True
            )

        _rating_data[key] = {
            "ticket_num": self._tnum,
            "user_id":    self._uid,
            "stars":      self._stars,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
        }
        _save_ratings()

        stars_bar = "⭐" * self._stars + "☆" * (5 - self._stars)
        mood      = self._REACTIONS[self._stars]

        await interaction.response.edit_message(
            embed=discord.Embed(
                title       = "✅ Bewertung gespeichert!",
                description = (
                    f"{mood} Du hast **{self._stars}/5 Sterne** vergeben.\n"
                    f"{stars_bar}\n\n"
                    f"Vielen Dank für dein Feedback! 💙"
                ),
                color=0x57F287,
            ),
            view=None,
        )


# ══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════════════════

async def _log_event(
    guild: discord.Guild,
    cfg: dict,
    event: str,
    ticket: dict,
    actor: discord.Member,
    reason: str = "",
):
    ch_id = cfg.get("log_channel")
    if not ch_id:
        return
    ch = guild.get_channel(int(ch_id))
    if not ch:
        return

    colors = {"opened": 0x57F287, "closed": 0xED4245, "escalated": 0xFEE75C}
    titles = {
        "opened":    "🎫 Ticket eröffnet",
        "closed":    "🔒 Ticket geschlossen",
        "escalated": "🚨 Ticket eskaliert",
    }

    e = discord.Embed(title=titles.get(event, event), color=colors.get(event, 0x5865F2))
    e.add_field(name="Ticket",    value=f"#{ticket.get('ticket_num', 0):04d}", inline=True)
    e.add_field(name="Kategorie", value=ticket.get("category", "—"),           inline=True)
    e.add_field(name="Ersteller", value=f"<@{ticket.get('user_id', 0)}>",      inline=True)
    e.add_field(name="Betreff",   value=ticket.get("betreff", "—"),            inline=True)
    e.add_field(name="Staff",     value=actor.mention,                          inline=True)
    if reason:
        e.add_field(name="Grund", value=reason, inline=False)
    e.timestamp = datetime.now(timezone.utc)

    try:
        await ch.send(embed=e)
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  HILFSFUNKTIONEN
# ══════════════════════════════════════════════════════════════════════════════

def _is_staff(member: discord.Member, cfg: dict) -> bool:
    if member.guild_permissions.administrator:
        return True
    staff = cfg.get("staff_roles", [])
    return any(str(r.id) in staff for r in member.roles)


def _resolve_member(guild: discord.Guild, value: str) -> Optional[discord.Member]:
    value = value.strip()
    if value.startswith("<@") and value.endswith(">"):
        uid = value[2:-1].lstrip("!")
        if uid.isdigit():
            return guild.get_member(int(uid))
    if value.isdigit():
        return guild.get_member(int(value))
    return discord.utils.find(
        lambda m: m.name.lower() == value.lower()
               or m.display_name.lower() == value.lower(),
        guild.members,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG — HILFSFUNKTIONEN
# ══════════════════════════════════════════════════════════════════════════════

def _config_embed(cfg: dict) -> discord.Embed:
    cats    = cfg.get("categories", [])
    ai_on   = cfg.get("ai_globally_enabled", True)
    viewers = cfg.get("viewer_roles", [])

    game_key  = cfg.get("roblox_game", "custom")
    game_info = _ROBLOX_GAMES.get(game_key, _ROBLOX_GAMES["custom"])
    if game_key == "custom" and cfg.get("roblox_game_custom", "").strip():
        game_display = cfg["roblox_game_custom"].strip()
    else:
        game_display = game_info["label"]

    # Zähle Kategorien mit eigenem Discord-Ordner
    cats_with_folder = sum(1 for c in cats if c.get("discord_category_id"))

    s1 = "✅" if cfg.get("panel_channel") and cfg.get("log_channel") else "1️⃣"
    s2 = "✅" if cats    else "2️⃣"
    s3 = "✅" if cfg.get("banner_url") else "3️⃣"
    s4 = "✅" if cfg.get("panel_msg_id") else "4️⃣"
    s5 = "✅" if ai_on   else "⛔"
    s6 = "✅" if viewers else "6️⃣"
    s7 = "✅" if game_key != "custom" or cfg.get("roblox_game_custom", "").strip() else "7️⃣"

    folder_info = (
        f"{cats_with_folder}/{len(cats)} mit eigenem Ordner"
        if cats_with_folder else
        f"Globaler Ordner: {'gesetzt' if cfg.get('ticket_category') else 'keiner'}"
    )

    return _embed(
        "⚙️ Ticket-System Konfiguration",
        f"{s1} **Grundeinstellungen** — Panel-Kanal, Log-Kanal, Staff-Rollen\n"
        f"{s2} **Kategorien** — Erstellen, Bearbeiten, Löschen *(unbegrenzt)*\n"
        f"      └ 📁 **Ordner-Zuweisung:** {folder_info}\n"
        f"{s3} **Banner & Thumbnail** — Panel-Bilder setzen\n"
        f"{s4} **Panel posten** — Ticket-Panel veröffentlichen\n"
        f"{s5} **KI-Support** — Aktuell: {'**Aktiviert 🤖**' if ai_on else '**Deaktiviert ⛔**'}\n"
        f"{s6} **Ticket-Sichtbarkeit** — "
        f"{f'{len(viewers)} Lese-Rolle(n) konfiguriert' if viewers else 'Nur Staff & Ersteller'}\n"
        f"{s7} **🎮 Roblox-Spiel / Server** — Aktuell: **{game_display}**\n\n"
        f"Aktive Kategorien: **{len(cats)}**\n\n"
        f"Wähle unten eine Option:",
        0x5865F2,
    )


async def _refresh_config_menu(interaction: discord.Interaction):
    cfg = _guild_cfg(interaction.guild_id)
    try:
        await interaction.edit_original_response(
            embed=_config_embed(cfg),
            view=_ConfigView(),
        )
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG — DROPDOWN SYSTEM
# ══════════════════════════════════════════════════════════════════════════════

class _ConfigView(View):
    def __init__(self):
        super().__init__(timeout=300)
        self.add_item(_ConfigSelect())


class _ConfigSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder = "⚙️  Was möchtest du konfigurieren?",
            options     = [
                discord.SelectOption(label="📋 Grundeinstellungen",    value="grund",        description="Log-Kanal, Panel-Kanal, Staff-Rollen, Ticket-Ordner",    emoji="📋"),
                discord.SelectOption(label="➕ Kategorie hinzufügen",  value="kat_add",      description="Neue Ticket-Kategorie erstellen",                         emoji="➕"),
                discord.SelectOption(label="📝 Kategorie bearbeiten",  value="kat_edit",     description="Bestehende Kategorie anpassen",                           emoji="📝"),
                discord.SelectOption(label="🗑️ Kategorie löschen",    value="kat_delete",   description="Kategorie entfernen",                                     emoji="🗑️"),
                discord.SelectOption(label="📁 Ordner zuweisen",       value="kat_folder",   description="Jeder Kategorie einen eigenen Discord-Ordner zuweisen",   emoji="📁"),
                discord.SelectOption(label="🖼️ Banner & Thumbnail",   value="bilder",       description="Panel-Bilder setzen",                                     emoji="🖼️"),
                discord.SelectOption(label="📤 Panel posten",          value="panel_post",   description="Ticket-Panel veröffentlichen",                            emoji="📤"),
                discord.SelectOption(label="🔄 Panel aktualisieren",   value="panel_update", description="Bestehendes Panel neu laden",                             emoji="🔄"),
                discord.SelectOption(label="📊 Status anzeigen",       value="status",       description="Konfiguration & Kategorien anzeigen",                     emoji="📊"),
                discord.SelectOption(label="🤖 KI-Support",            value="ki_toggle",    description="KI-Assistent global aktivieren / deaktivieren",           emoji="🤖"),
                discord.SelectOption(label="👁️ Ticket-Sichtbarkeit",  value="sichtbarkeit", description="Rollen einstellen, die Tickets lesen dürfen",              emoji="👁️"),
                discord.SelectOption(label="🎮 Roblox-Spiel / Server", value="spiel_select", description="Welches Spiel nutzt dein Server? (Wichtig für die KI!)",  emoji="🎮"),
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        v   = self.values[0]
        cfg = _guild_cfg(interaction.guild_id)

        # ── Modal-Aktionen ─────────────────────────────────────────────────
        if v == "grund":
            await interaction.response.send_modal(_GrundModal())
            return
        if v == "kat_add":
            await interaction.response.send_modal(_KatAddModal())
            return
        if v == "bilder":
            await interaction.response.send_modal(_BilderModal())
            return
        if v == "sichtbarkeit":
            await interaction.response.send_modal(_SichtbarkeitModal())
            return

        # ── Select-Aktionen ────────────────────────────────────────────────
        if v == "kat_edit":
            await _zeige_kat_select(interaction, cfg, mode="edit")
            return
        if v == "kat_delete":
            await _zeige_kat_select(interaction, cfg, mode="delete")
            return

        # ✨ NEU: Ordner-Zuweisung
        if v == "kat_folder":
            await _zeige_kat_select(interaction, cfg, mode="folder")
            return

        # ── Spiel-Auswahl ─────────────────────────────────────────────────
        if v == "spiel_select":
            await _zeige_spiel_select(interaction)
            return

        # ── KI-Toggle ─────────────────────────────────────────────────────
        if v == "ki_toggle":
            cfg["ai_globally_enabled"] = not cfg.get("ai_globally_enabled", True)
            _save_cfg()
            state  = "**aktiviert ✅**" if cfg["ai_globally_enabled"] else "**deaktiviert ⛔**"
            hinweis = (
                "Neue Tickets erhalten automatisch KI-Unterstützung."
                if cfg["ai_globally_enabled"] else
                "Neue Tickets starten ohne KI. Bereits offene Tickets sind unberührt."
            )
            await interaction.response.send_message(
                embed=_ok(f"🤖 KI-Support wurde global {state}\n\n{hinweis}"),
                ephemeral=True,
            )
            await _refresh_config_menu(interaction)
            return

        await interaction.response.defer(ephemeral=True)

        if v == "panel_post":
            await _panel_posten(interaction, cfg)
        elif v == "panel_update":
            await _panel_update(interaction, cfg)
        elif v == "status":
            await _status_anzeigen(interaction, cfg)

        await _refresh_config_menu(interaction)


# ══════════════════════════════════════════════════════════════════════════════
#  ✨ NEU: ORDNER-ZUWEISUNG PRO KATEGORIE
# ══════════════════════════════════════════════════════════════════════════════

async def _zeige_ordner_zuweisung(interaction: discord.Interaction, cat: dict):
    """
    Zeigt ein zweistufiges Menü:
    1. Alle Discord-Kategorien (Ordner) des Servers als Dropdown
    2. Option "Keinen Ordner (globaler Fallback)"
    """
    guild = interaction.guild

    # Alle CategoryChannels sammeln
    discord_cats = [
        ch for ch in guild.channels
        if isinstance(ch, discord.CategoryChannel)
    ]

    if not discord_cats:
        return await interaction.response.send_message(
            embed=_err(
                "❌ Dieser Server hat keine Discord-Ordner (Kategorien)!\n\n"
                "Erstelle zuerst Ordner in deinem Server (Rechtsklick → Kategorie erstellen), "
                "dann weise sie hier zu."
            ),
            ephemeral=True,
        )

    # Optionen bauen (max 24 Ordner + 1 Reset-Option = 25)
    options = [
        discord.SelectOption(
            label       = "🚫 Kein eigener Ordner (globaler Fallback)",
            value       = "NONE",
            description = "Nutzt den globalen Ticket-Ordner aus den Grundeinstellungen",
        )
    ]
    for dc in discord_cats[:24]:
        # Aktuell zugewiesenen Ordner markieren
        is_current = str(dc.id) == str(cat.get("discord_category_id") or "")
        options.append(discord.SelectOption(
            label       = f"📁 {dc.name}"[:100],
            value       = str(dc.id),
            description = f"{'✅ Aktuell zugewiesen  •  ' if is_current else ''}{len(dc.channels)} Kanäle",
            default     = is_current,
        ))

    cat_id   = cat["id"]
    cat_name = cat["name"]
    cat_emoji = cat.get("emoji", "🎫")

    class _OrdnerSelect(Select):
        def __init__(s):
            super().__init__(
                placeholder = f"📁  Ordner für '{cat_name}' wählen ...",
                options     = options,
            )

        async def callback(s, inter: discord.Interaction):
            cfg_inner = _guild_cfg(inter.guild_id)
            # Kategorie in der Config finden und aktualisieren
            target_cat = next(
                (c for c in cfg_inner.get("categories", []) if c["id"] == cat_id),
                None,
            )
            if not target_cat:
                return await inter.response.send_message(
                    embed=_err("Kategorie nicht mehr vorhanden."), ephemeral=True
                )

            val = s.values[0]
            if val == "NONE":
                target_cat["discord_category_id"] = None
                msg = (
                    f"📁 Ordner-Zuweisung für **{cat_emoji} {cat_name}** entfernt.\n\n"
                    f"Tickets landen jetzt im globalen Ordner (falls gesetzt) "
                    f"oder ohne Ordner."
                )
            else:
                target_cat["discord_category_id"] = val
                # Ordnernamen für die Bestätigung ermitteln
                dc = inter.guild.get_channel(int(val))
                ordner_name = dc.name if dc else val
                msg = (
                    f"✅ Tickets der Kategorie **{cat_emoji} {cat_name}** "
                    f"landen jetzt im Ordner **📁 {ordner_name}**!"
                )

            _save_cfg()
            await inter.response.send_message(embed=_ok(msg), ephemeral=True)
            await _refresh_config_menu(inter)

    v = View(timeout=60)
    v.add_item(_OrdnerSelect())

    current_folder_id = cat.get("discord_category_id")
    if current_folder_id:
        dc = guild.get_channel(int(current_folder_id))
        current_info = f"Aktuell: **📁 {dc.name}**" if dc else "Aktuell: *(Ordner nicht gefunden)*"
    else:
        current_info = "Aktuell: *Kein eigener Ordner (globaler Fallback)*"

    await interaction.response.send_message(
        embed=_info(
            f"**Kategorie:** {cat_emoji} {cat_name}\n"
            f"{current_info}\n\n"
            f"Wähle unten den Discord-Ordner, in den neue Tickets dieser Kategorie "
            f"automatisch einsortiert werden sollen.\n\n"
            f"💡 **Tipp:** Du kannst für jede Kategorie einen anderen Ordner nutzen, "
            f"z.B. `📁 Beschwerden`, `📁 Support`, `📁 Bewerbungen`."
        ),
        view=v,
        ephemeral=True,
    )


# ── Spiel-Auswahl View ────────────────────────────────────────────────────────

async def _zeige_spiel_select(interaction: discord.Interaction):
    options = [
        discord.SelectOption(
            label       = "🚨 Emergency Response Liberty County (ERLC)",
            value       = "erlc",
            description = "Roblox — Polizei, Feuerwehr, EMS in Liberty County",
        ),
        discord.SelectOption(
            label       = "🚒 Notruf Hamburg",
            value       = "notruf_hh",
            description = "Roblox — Deutsches Roleplay in Hamburg",
        ),
        discord.SelectOption(
            label       = "🚑 Notruf Emden",
            value       = "notruf_em",
            description = "Roblox — Deutsches Roleplay in Emden",
        ),
        discord.SelectOption(
            label       = "✏️ Anderes Spiel / Manuell eintragen",
            value       = "custom",
            description = "Eigenen Spielnamen per Text eingeben",
        ),
    ]

    class _SpielSelect(Select):
        def __init__(s):
            super().__init__(
                placeholder = "🎮  Welches Spiel nutzt dein Server?",
                options     = options,
            )

        async def callback(s, inter: discord.Interaction):
            val = s.values[0]
            if val == "custom":
                await inter.response.send_modal(_CustomSpielModal())
            else:
                cfg_inner = _guild_cfg(inter.guild_id)
                cfg_inner["roblox_game"]        = val
                cfg_inner["roblox_game_custom"] = ""
                _save_cfg()
                game_label = _ROBLOX_GAMES[val]["label"]
                await inter.response.send_message(
                    embed=_ok(
                        f"🎮 Spiel gesetzt auf:\n**{game_label}**\n\n"
                        f"Die KI kennt dieses Spiel jetzt und antwortet entsprechend!"
                    ),
                    ephemeral=True,
                )
                await _refresh_config_menu(inter)

    v = View(timeout=60)
    v.add_item(_SpielSelect())
    await interaction.response.send_message(
        embed=_info(
            "Wähle das Roblox-Spiel, für das dieser Discord-Server zuständig ist.\n"
            "Die KI verwendet diese Information, um Tickets **korrekt und spezifisch** zu beantworten.\n\n"
            "⚠️ Ohne korrekte Auswahl kann die KI keine genauen Antworten geben!"
        ),
        view=v,
        ephemeral=True,
    )


class _CustomSpielModal(Modal, title="🎮 Eigenes Spiel eintragen"):
    spiel_name = TextInput(
        label       = "Name des Roblox-Spiels / Servers",
        placeholder = "z.B. Mein Roblox RP Server",
        required    = True,
        max_length  = 100,
    )
    spiel_info = TextInput(
        label       = "Kurzbeschreibung für die KI",
        placeholder = "z.B. Deutsches Roleplay-Spiel mit Polizei und Feuerwehr ...",
        style       = discord.TextStyle.paragraph,
        required    = True,
        max_length  = 500,
    )

    async def on_submit(self, interaction: discord.Interaction):
        cfg = _guild_cfg(interaction.guild_id)
        cfg["roblox_game"]        = "custom"
        cfg["roblox_game_custom"] = self.spiel_name.value.strip()
        _ROBLOX_GAMES["custom"]["description"] = self.spiel_info.value.strip()
        _save_cfg()

        await interaction.response.send_message(
            embed=_ok(
                f"🎮 Spiel eingetragen:\n**{self.spiel_name.value.strip()}**\n\n"
                f"Die KI wird ab sofort auf Basis deiner Beschreibung antworten!"
            ),
            ephemeral=True,
        )
        await _refresh_config_menu(interaction)


# ─── Modals für Config ────────────────────────────────────────────────────────

class _GrundModal(Modal, title="📋 Grundeinstellungen"):
    panel_ch   = TextInput(label="Panel-Kanal",                      placeholder="#support",     required=False, max_length=100)
    log_ch     = TextInput(label="Log-Kanal",                        placeholder="#ticket-logs", required=False, max_length=100)
    staff      = TextInput(label="Staff-Rollen (kommagetrennt)",     placeholder="@Mod, @Admin", required=False, max_length=300)
    ticket_cat = TextInput(label="Globaler Ticket-Ordner (Fallback)", placeholder="Tickets",     required=False, max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        cfg   = _guild_cfg(interaction.guild_id)
        guild = interaction.guild
        ok    = []
        err   = []

        def _try_ch(val, key, label):
            if not val.strip(): return
            ch = _resolve_channel(guild, val)
            if ch:
                cfg[key] = str(ch.id)
                ok.append(f"{label}: {ch.mention}")
            else:
                err.append(f"{label}: `{val}` nicht gefunden")

        _try_ch(self.panel_ch.value, "panel_channel", "Panel-Kanal")
        _try_ch(self.log_ch.value,   "log_channel",   "Log-Kanal")

        if self.ticket_cat.value.strip():
            cat_ch = discord.utils.find(
                lambda c: isinstance(c, discord.CategoryChannel)
                and c.name.lower() == self.ticket_cat.value.strip().lower(),
                guild.channels,
            )
            if cat_ch:
                cfg["ticket_category"] = str(cat_ch.id)
                ok.append(f"Globaler Ticket-Ordner: **{cat_ch.name}** *(Fallback für Kategorien ohne eigenen Ordner)*")
            else:
                err.append(f"Discord-Ordner `{self.ticket_cat.value}` nicht gefunden")

        if self.staff.value.strip():
            ids = []
            for part in self.staff.value.split(","):
                part = part.strip()
                role = None
                if part.startswith("<@&") and part.endswith(">"):
                    rid = part[3:-1]
                    if rid.isdigit(): role = guild.get_role(int(rid))
                elif part.isdigit():
                    role = guild.get_role(int(part))
                else:
                    role = discord.utils.find(
                        lambda r: r.name.lower() == part.lstrip("@").lower(), guild.roles
                    )
                if role:
                    ids.append(str(role.id))
                    ok.append(f"Staff-Rolle: {role.mention}")
                else:
                    err.append(f"Rolle `{part}` nicht gefunden")
            if ids:
                cfg["staff_roles"] = ids

        _save_cfg()

        lines = []
        if ok:  lines.append("**Gespeichert:**\n" + "\n".join(f"✅ {o}" for o in ok))
        if err: lines.append("**Fehler:**\n"      + "\n".join(f"❌ {e}" for e in err))
        msg = "\n\n".join(lines) or "Keine Änderungen."

        await interaction.response.send_message(
            embed=(_ok if not err else _err)(msg), ephemeral=True
        )
        await _refresh_config_menu(interaction)


class _KatAddModal(Modal, title="➕ Neue Kategorie erstellen"):
    name    = TextInput(label="Name",                       placeholder="Allgemeiner Support",           required=True,  max_length=50)
    emoji   = TextInput(label="Emoji",                      placeholder="🆘",                           required=True,  max_length=10)
    desc    = TextInput(label="Beschreibung",               placeholder="Hilfe bei allgemeinen Fragen",  required=True,  max_length=100)
    hint    = TextInput(label="KI-Hinweis",                 placeholder="Kontext für die KI (optional)", required=False, max_length=250, style=discord.TextStyle.paragraph)
    role    = TextInput(label="Staff-Rolle (optional)",     placeholder="@Support-Team",                 required=False, max_length=100)

    async def on_submit(self, interaction: discord.Interaction):
        cfg   = _guild_cfg(interaction.guild_id)
        guild = interaction.guild

        role_id = None
        if self.role.value.strip():
            part = self.role.value.strip()
            r    = None
            if part.startswith("<@&") and part.endswith(">"):
                rid = part[3:-1]
                if rid.isdigit(): r = guild.get_role(int(rid))
            elif part.isdigit():
                r = guild.get_role(int(part))
            else:
                r = discord.utils.find(
                    lambda x: x.name.lower() == part.lstrip("@").lower(), guild.roles
                )
            if r: role_id = str(r.id)

        new_cat = {
            "id":                  str(uuid.uuid4())[:8],
            "name":                self.name.value.strip(),
            "emoji":               self.emoji.value.strip(),
            "description":         self.desc.value.strip(),
            "color":               0x5865F2,
            "staff_role":          role_id,
            "ai_hint":             self.hint.value.strip(),
            "discord_category_id": None,  # ✨ NEU: Standardmäßig kein eigener Ordner
        }
        cfg.setdefault("categories", []).append(new_cat)
        _save_cfg()

        await interaction.response.send_message(
            embed=_ok(
                f"Kategorie **{new_cat['emoji']} {new_cat['name']}** hinzugefügt!\n\n"
                f"› **📁 Ordner zuweisen** — eigenen Discord-Ordner festlegen\n"
                f"› **Panel aktualisieren** — nicht vergessen!"
            ),
            ephemeral=True,
        )
        await _refresh_config_menu(interaction)


async def _zeige_kat_select(interaction: discord.Interaction, cfg: dict, mode: str):
    cats = cfg.get("categories", [])
    if not cats:
        return await interaction.response.send_message(
            embed=_err("Keine Kategorien vorhanden."), ephemeral=True
        )

    options = []
    for c in cats[:25]:
        # Bei Ordner-Modus: aktuellen Ordner in der Beschreibung anzeigen
        if mode == "folder":
            folder_id = c.get("discord_category_id")
            if folder_id and interaction.guild:
                dc = interaction.guild.get_channel(int(folder_id))
                folder_hint = f"📁 {dc.name}" if dc else "📁 ?"
            else:
                folder_hint = "Kein eigener Ordner"
            desc = folder_hint
        else:
            desc = (c.get("description") or "")[:100] or None

        options.append(discord.SelectOption(
            label       = f"{c.get('emoji', '🎫')} {c.get('name', '?')}"[:100],
            value       = c["id"],
            description = desc,
        ))

    if mode == "edit":
        class _EditSel(Select):
            def __init__(s):
                super().__init__(placeholder="Kategorie zum Bearbeiten wählen", options=options)
            async def callback(s, inter):
                cat = next((c for c in cfg["categories"] if c["id"] == s.values[0]), None)
                if not cat:
                    return await inter.response.send_message(embed=_err("Nicht gefunden."), ephemeral=True)
                await inter.response.send_modal(_KatEditModal(cat))
        v = View(timeout=60); v.add_item(_EditSel())

    elif mode == "delete":
        class _DelSel(Select):
            def __init__(s):
                super().__init__(placeholder="Kategorie zum Löschen wählen", options=options)
            async def callback(s, inter):
                cfg2 = _guild_cfg(inter.guild_id)
                before = len(cfg2["categories"])
                cfg2["categories"] = [c for c in cfg2["categories"] if c["id"] != s.values[0]]
                _save_cfg()
                if len(cfg2["categories"]) < before:
                    await inter.response.send_message(embed=_ok("Kategorie gelöscht!"), ephemeral=True)
                else:
                    await inter.response.send_message(embed=_err("Kategorie nicht gefunden."), ephemeral=True)
        v = View(timeout=60); v.add_item(_DelSel())

    # ✨ NEU: Ordner-Modus
    elif mode == "folder":
        class _FolderSel(Select):
            def __init__(s):
                super().__init__(
                    placeholder = "📁  Für welche Kategorie Ordner zuweisen?",
                    options     = options,
                )
            async def callback(s, inter: discord.Interaction):
                cfg2 = _guild_cfg(inter.guild_id)
                cat  = next((c for c in cfg2.get("categories", []) if c["id"] == s.values[0]), None)
                if not cat:
                    return await inter.response.send_message(embed=_err("Nicht gefunden."), ephemeral=True)
                # Zweites Dropdown: Ordner-Auswahl für diese Kategorie
                await _zeige_ordner_zuweisung(inter, cat)
        v = View(timeout=60); v.add_item(_FolderSel())

    await interaction.response.send_message(view=v, ephemeral=True)


class _KatEditModal(Modal, title="📝 Kategorie bearbeiten"):
    name  = TextInput(label="Name",         required=True,  max_length=50)
    emoji = TextInput(label="Emoji",        required=True,  max_length=10)
    desc  = TextInput(label="Beschreibung", required=True,  max_length=100)
    hint  = TextInput(label="KI-Hinweis",   required=False, max_length=250, style=discord.TextStyle.paragraph)

    def __init__(self, cat: dict):
        super().__init__()
        self._id           = cat["id"]
        self.name.default  = cat.get("name", "")
        self.emoji.default = cat.get("emoji", "")
        self.desc.default  = cat.get("description", "")
        self.hint.default  = cat.get("ai_hint", "")

    async def on_submit(self, interaction: discord.Interaction):
        cfg = _guild_cfg(interaction.guild_id)
        cat = next((c for c in cfg["categories"] if c["id"] == self._id), None)
        if not cat:
            return await interaction.response.send_message(
                embed=_err("Kategorie nicht mehr vorhanden."), ephemeral=True
            )

        cat["name"]        = self.name.value.strip()
        cat["emoji"]       = self.emoji.value.strip()
        cat["description"] = self.desc.value.strip()
        cat["ai_hint"]     = self.hint.value.strip()
        _save_cfg()

        await interaction.response.send_message(
            embed=_ok(f"Kategorie **{cat['emoji']} {cat['name']}** aktualisiert!"),
            ephemeral=True,
        )
        await _refresh_config_menu(interaction)


class _BilderModal(Modal, title="🖼️ Banner & Thumbnail"):
    banner = TextInput(label="Banner-URL (großes Bild)",     placeholder="https://i.imgur.com/...", required=False, max_length=300)
    thumb  = TextInput(label="Thumbnail-URL (kleines Bild)", placeholder="https://i.imgur.com/...", required=False, max_length=300)

    async def on_submit(self, interaction: discord.Interaction):
        cfg = _guild_cfg(interaction.guild_id)
        cfg["banner_url"]    = self.banner.value.strip()
        cfg["thumbnail_url"] = self.thumb.value.strip()
        _save_cfg()

        await interaction.response.send_message(
            embed=_ok("Bilder gespeichert!\n\n› Panel aktualisieren nicht vergessen."),
            ephemeral=True,
        )
        await _refresh_config_menu(interaction)


class _SichtbarkeitModal(Modal, title="👁️ Ticket-Sichtbarkeit"):
    viewer_roles = TextInput(
        label       = "Lese-Rollen (kommagetrennt, leer = zurücksetzen)",
        placeholder = "@Beobachter, @QM  — leer lassen = nur Staff & Ersteller",
        required    = False,
        max_length  = 400,
    )
    hinweis = TextInput(
        label       = "ℹ️ Info (nicht ausfüllen)",
        placeholder = (
            "Diese Rollen können Tickets nur LESEN (kein Schreiben). "
            "Staff-Rollen aus Grundeinstellungen können weiterhin schreiben. "
            "Normale Mitglieder sehen Tickets grundsätzlich NICHT."
        ),
        required    = False,
        max_length  = 1,
    )

    async def on_submit(self, interaction: discord.Interaction):
        cfg   = _guild_cfg(interaction.guild_id)
        guild = interaction.guild
        ok    = []
        err   = []

        raw = self.viewer_roles.value.strip()
        if raw:
            ids = []
            for part in raw.split(","):
                part = part.strip()
                if not part:
                    continue
                role = None
                if part.startswith("<@&") and part.endswith(">"):
                    rid = part[3:-1]
                    if rid.isdigit():
                        role = guild.get_role(int(rid))
                elif part.isdigit():
                    role = guild.get_role(int(part))
                else:
                    role = discord.utils.find(
                        lambda r: r.name.lower() == part.lstrip("@").lower(),
                        guild.roles,
                    )
                if role:
                    ids.append(str(role.id))
                    ok.append(f"Lese-Rolle: {role.mention}")
                else:
                    err.append(f"Rolle `{part}` nicht gefunden")
            cfg["viewer_roles"] = ids
        else:
            cfg["viewer_roles"] = []
            ok.append("Lese-Rollen zurückgesetzt — Tickets nur für Staff & Ersteller sichtbar")

        _save_cfg()

        lines = []
        if ok:  lines.append("**Gespeichert:**\n"  + "\n".join(f"✅ {o}" for o in ok))
        if err: lines.append("**Fehler:**\n"       + "\n".join(f"❌ {e}" for e in err))
        msg = "\n\n".join(lines) or "Keine Änderungen."

        await interaction.response.send_message(
            embed=(_ok if not err else _err)(msg),
            ephemeral=True,
        )
        await _refresh_config_menu(interaction)


# ─── Panel-Aktionen ───────────────────────────────────────────────────────────

async def _panel_posten(interaction: discord.Interaction, cfg: dict):
    try:
        ch_id = cfg.get("panel_channel")
        if not ch_id:
            return await interaction.followup.send(
                embed=_err(
                    "❌ Kein Panel-Kanal gesetzt!\n\n"
                    "→ **Grundeinstellungen** auswählen und Panel-Kanal eintragen."
                ),
                ephemeral=True,
            )

        ch = interaction.guild.get_channel(int(ch_id))
        if not ch:
            return await interaction.followup.send(
                embed=_err(
                    f"❌ Panel-Kanal (ID `{ch_id}`) nicht gefunden!\n\n"
                    "Der Kanal wurde möglicherweise gelöscht. "
                    "Bitte in **Grundeinstellungen** neu setzen."
                ),
                ephemeral=True,
            )

        if cfg.get("panel_msg_id"):
            try:
                old = await ch.fetch_message(int(cfg["panel_msg_id"]))
                await old.delete()
            except Exception:
                pass

        embed = _build_panel_embed(cfg)
        view  = TicketPanelView(cfg)
        msg   = await ch.send(embed=embed, view=view)

        cfg["panel_msg_id"] = str(msg.id)
        _save_cfg()

        await interaction.followup.send(
            embed=_ok(f"✅ Panel in {ch.mention} gepostet!"),
            ephemeral=True,
        )

    except discord.Forbidden:
        await interaction.followup.send(
            embed=_err(
                "❌ Keine Berechtigung im Panel-Kanal!\n\n"
                "Der Bot braucht folgende Rechte dort:\n"
                "• `Nachrichten senden`\n"
                "• `Eingebettete Links`\n"
                "• `Kanal lesen`"
            ),
            ephemeral=True,
        )
    except Exception as ex:
        tb = traceback.format_exc()[-600:]
        await interaction.followup.send(
            embed=_err(f"❌ Unbekannter Fehler:\n```\n{tb}\n```"),
            ephemeral=True,
        )


async def _panel_update(interaction: discord.Interaction, cfg: dict):
    try:
        ch_id  = cfg.get("panel_channel")
        msg_id = cfg.get("panel_msg_id")

        if not ch_id or not msg_id:
            return await interaction.followup.send(
                embed=_err("Kein aktives Panel gefunden. Bitte erst **📤 Panel posten**."),
                ephemeral=True,
            )

        ch = interaction.guild.get_channel(int(ch_id))
        if not ch:
            return await interaction.followup.send(
                embed=_err("Panel-Kanal nicht gefunden."), ephemeral=True
            )

        try:
            msg   = await ch.fetch_message(int(msg_id))
            embed = _build_panel_embed(cfg)
            view  = TicketPanelView(cfg)
            await msg.edit(embed=embed, view=view)
            await interaction.followup.send(embed=_ok("✅ Panel aktualisiert!"), ephemeral=True)
        except discord.NotFound:
            await interaction.followup.send(
                embed=_err(
                    "Panel-Nachricht nicht mehr gefunden.\n"
                    "Bitte **📤 Panel posten** verwenden."
                ),
                ephemeral=True,
            )

    except discord.Forbidden:
        await interaction.followup.send(
            embed=_err("❌ Keine Berechtigung zum Bearbeiten der Panel-Nachricht!"),
            ephemeral=True,
        )
    except Exception as ex:
        tb = traceback.format_exc()[-600:]
        await interaction.followup.send(
            embed=_err(f"❌ Fehler:\n```\n{tb}\n```"),
            ephemeral=True,
        )


async def _status_anzeigen(interaction: discord.Interaction, cfg: dict):
    cats    = cfg.get("categories", [])
    roles   = cfg.get("staff_roles", [])
    viewers = cfg.get("viewer_roles", [])
    ai_on   = cfg.get("ai_globally_enabled", True)

    game_key  = cfg.get("roblox_game", "custom")
    game_info = _ROBLOX_GAMES.get(game_key, _ROBLOX_GAMES["custom"])
    if game_key == "custom" and cfg.get("roblox_game_custom", "").strip():
        game_display = cfg["roblox_game_custom"].strip()
    else:
        game_display = game_info["label"]

    e = discord.Embed(title="📊 Ticket-System Status", color=0x5865F2)
    e.add_field(name="Panel-Kanal",    value=f"<#{cfg['panel_channel']}>" if cfg.get("panel_channel") else "❌", inline=True)
    e.add_field(name="Log-Kanal",      value=f"<#{cfg['log_channel']}>"   if cfg.get("log_channel")   else "❌", inline=True)
    e.add_field(name="Tickets gesamt", value=str(cfg.get("ticket_counter", 0)), inline=True)
    e.add_field(name="🤖 KI-Support",  value="✅ Aktiviert" if ai_on else "⛔ Deaktiviert", inline=True)
    e.add_field(name="🎮 Roblox-Spiel", value=game_display, inline=True)

    # ✨ NEU: Globaler Ordner im Status
    global_cat_id = cfg.get("ticket_category")
    if global_cat_id and interaction.guild:
        dc = interaction.guild.get_channel(int(global_cat_id))
        global_folder = f"📁 {dc.name}" if dc else "❓ Nicht gefunden"
    else:
        global_folder = "❌ Keiner"
    e.add_field(name="📁 Globaler Ordner", value=global_folder, inline=True)

    e.add_field(
        name  = "Staff-Rollen",
        value = ", ".join(f"<@&{r}>" for r in roles) if roles else "❌ Keine",
        inline=False,
    )
    e.add_field(
        name  = "👁️ Lese-Rollen",
        value = ", ".join(f"<@&{r}>" for r in viewers) if viewers else "Keine (nur Staff & Ersteller)",
        inline=False,
    )

    if cats:
        cat_lines = []
        for c in cats:
            line = f"{c.get('emoji', '🎫')} **{c.get('name', '?')}** — {c.get('description', '')}"
            # ✨ NEU: Ordner-Info pro Kategorie
            cat_folder_id = c.get("discord_category_id")
            if cat_folder_id and interaction.guild:
                dc = interaction.guild.get_channel(int(cat_folder_id))
                line += f"\n  └ 📁 Ordner: **{dc.name if dc else '?'}**"
            else:
                line += f"\n  └ 📁 Ordner: *globaler Fallback*"
            if c.get("ai_hint"):
                line += f"\n  └ 🤖 KI-Hinweis: *{c['ai_hint'][:50]}*"
            cat_lines.append(line)
        e.add_field(name=f"Kategorien ({len(cats)})", value="\n".join(cat_lines)[:1024], inline=False)
    else:
        e.add_field(name="Kategorien", value="❌ Keine Kategorien konfiguriert", inline=False)

    e.timestamp = datetime.now(timezone.utc)
    await interaction.followup.send(embed=e, ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════
#  SLASH COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

async def _cmd_ticket_config(interaction: discord.Interaction):
    """⚙️ Ticket-System konfigurieren."""
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            embed=_err("Du benötigst Administrator-Rechte."), ephemeral=True
        )

    cfg = _guild_cfg(interaction.guild_id)
    await interaction.response.send_message(
        embed=_config_embed(cfg),
        view=_ConfigView(),
        ephemeral=True,
    )


async def _cmd_ticket_stats(interaction: discord.Interaction):
    """📊 Ticket-Statistiken anzeigen."""
    if not interaction.user.guild_permissions.manage_guild:
        return await interaction.response.send_message(
            embed=_err("Du benötigst die Berechtigung 'Server verwalten'."), ephemeral=True
        )

    gid    = str(interaction.guild_id)
    alle   = [t for t in _ticket_data.values() if t.get("guild_id") == gid]
    offen  = [t for t in alle if t.get("status") in ("open", "claimed", "escalated")]
    geschl = [t for t in alle if t.get("status") == "closed"]
    esk    = [t for t in alle if t.get("status") == "escalated"]

    rat = [r["stars"] for r in _rating_data.values()]
    avg = sum(rat) / len(rat) if rat else 0
    stars = "⭐" * round(avg) + "☆" * (5 - round(avg))

    cat_count = {}
    for t in alle:
        k = t.get("category", "Unbekannt")
        cat_count[k] = cat_count.get(k, 0) + 1

    e = discord.Embed(title="📊 Ticket-Statistiken", color=0x5865F2)
    e.add_field(name="📬 Gesamt",      value=str(len(alle)),   inline=True)
    e.add_field(name="🟢 Offen",       value=str(len(offen)),  inline=True)
    e.add_field(name="🔒 Geschlossen", value=str(len(geschl)), inline=True)
    e.add_field(name="🚨 Eskaliert",   value=str(len(esk)),    inline=True)
    e.add_field(
        name  = "⭐ Ø Bewertung",
        value = f"{avg:.1f} / 5  {stars}\n`{len(rat)} Bewertungen`",
        inline=True,
    )
    e.add_field(name="\u200b", value="\u200b", inline=True)

    if cat_count:
        dist = "\n".join(
            f"**{cat}** — {cnt} Tickets"
            for cat, cnt in sorted(cat_count.items(), key=lambda x: -x[1])
        )
        e.add_field(name="📂 Kategorie-Verteilung", value=dist[:1024], inline=False)

    e.timestamp = datetime.now(timezone.utc)
    await interaction.response.send_message(embed=e, ephemeral=True)


# ══════════════════════════════════════════════════════════════════════════════
#  COG — on_message Listener für KI
# ══════════════════════════════════════════════════════════════════════════════

class TicketCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot      = bot
        self._ai_busy = set()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if not message.guild:
            return

        ch_id  = str(message.channel.id)
        ticket = _ticket_data.get(ch_id)

        if not ticket:
            return
        if ticket.get("status") == "closed":
            return
        if not ticket.get("ai_active"):
            return
        if str(message.author.id) != ticket.get("user_id"):
            return

        if ch_id in self._ai_busy:
            return

        self._ai_busy.add(ch_id)
        try:
            cfg = _guild_cfg(message.guild.id)
            await _ki_antworten(message.channel, ticket, message.content, message.guild, cfg)
        finally:
            self._ai_busy.discard(ch_id)


# ══════════════════════════════════════════════════════════════════════════════
#  SETUP
# ══════════════════════════════════════════════════════════════════════════════

async def setup(bot: commands.Bot):
    _load_all()

    cog = TicketCog(bot)
    await bot.add_cog(cog)

    for gid, cfg in _cfg_data.items():
        try:
            bot.add_view(TicketPanelView(cfg))
        except Exception:
            pass

    for ch_id, t in _ticket_data.items():
        if t.get("status") not in ("closed",):
            try:
                bot.add_view(_TicketControlView(ch_id))
            except Exception:
                pass

    bot.tree.add_command(app_commands.Command(
        name        = "ticket-config",
        description = "⚙️ Ticket-System konfigurieren (Admin)",
        callback    = _cmd_ticket_config,
    ))
    bot.tree.add_command(app_commands.Command(
        name        = "ticket-stats",
        description = "📊 Ticket-Statistiken & Bewertungen anzeigen",
        callback    = _cmd_ticket_stats,
    ))

