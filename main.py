# ==================== ИМПОРТЫ ====================
import os
import re
import io
import sys
import json
import time
import wave
import random
import string
import shutil
import zipfile
import tarfile
import hashlib
import difflib
import logging
import asyncio
import platform
import subprocess
import tempfile
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import aiohttp

try:
    import psutil
    PSUTIL = True
except ImportError:
    PSUTIL = False

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_OK = True
except ImportError:
    PIL_OK = False

try:
    import qrcode
    QR_OK = True
except ImportError:
    QR_OK = False

try:
    import mss
    import mss.tools
    MSS_OK = True
except ImportError:
    MSS_OK = False

try:
    import cv2
    CV2_OK = True
except ImportError:
    CV2_OK = False

try:
    import sounddevice as sd
    import numpy as np
    AUDIO_OK = True
except ImportError:
    AUDIO_OK = False

try:
    import dbus
    import dbus.mainloop.glib
    from gi.repository import GLib
    DBUS_OK = True
except ImportError:
    DBUS_OK = False

from aiogram import Bot, Dispatcher, types, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder


# ==================== КОНФИГ ====================
BOT_TOKEN = "8744154604:AAF-m0aIbe_ncvPpI8riVbbX9U573wLyONY"
ADMIN_ID = 8500748147
ALLOWED_USERS = [ADMIN_ID]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WELCOME_IMAGE = os.path.join(SCRIPT_DIR, "rat.png")
UPLOAD_DIR = os.path.join(SCRIPT_DIR, "uploads")
TRASH_DIR = os.path.join(SCRIPT_DIR, ".trash")
BOOKMARKS_FILE = os.path.join(SCRIPT_DIR, "bookmarks.json")
HISTORY_FILE = os.path.join(SCRIPT_DIR, "history.json")

for d in (UPLOAD_DIR, TRASH_DIR):
    os.makedirs(d, exist_ok=True)

MAX_FILE_MB = 50
TEXT_PREVIEW_LINES = 50
SEARCH_MAX_DEPTH = 5
SEARCH_MAX_RESULTS = 50
HISTORY_LIMIT = 30

SHELL_WHITELIST = {
    "ls", "cat", "pwd", "df", "du", "free", "uptime", "date",
    "whoami", "uname", "hostname", "ip", "ifconfig", "ps", "top",
    "find", "grep", "wc", "head", "tail", "echo", "file", "stat",
    "which", "whereis", "env",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)


# ==================== УСТРОЙСТВО ====================
def detect_device() -> str:
    if len(sys.argv) > 1:
        a = sys.argv[1].lower()
        if a in ("android", "windows", "linux", "mac"):
            return a
    s = platform.system().lower()
    if s == "windows":
        return "windows"
    if s == "darwin":
        return "mac"
    return "linux"


DEVICE_TYPE = detect_device()
ROOT_DIRECTORIES = {
    "android": "/storage/emulated/0/",
    "windows": os.path.expanduser("C:/"),
    "linux": os.path.expanduser("~"),
    "mac": os.path.expanduser("~"),
}
ROOT_DIRECTORY = ROOT_DIRECTORIES[DEVICE_TYPE]


# ==================== БОТ ====================
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=storage)


# ==================== MIDDLEWARE ====================
class AccessMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        u = getattr(event, "from_user", None)
        if u and u.id not in ALLOWED_USERS:
            try:
                await event.answer("🚫 Нет доступа.")
            except Exception:
                pass
            return
        return await handler(event, data)


dp.message.middleware(AccessMiddleware())
dp.callback_query.middleware(AccessMiddleware())


# ==================== СОСТОЯНИЯ ====================
class S(StatesGroup):
    DELETE = State()
    RENAME = State()
    RENAME_NEW_NAME = State()
    CREATE_FOLDER = State()
    MOVE = State()
    MOVE_DEST = State()
    COPY = State()
    COPY_DEST = State()
    ZIP = State()
    SEARCH_EXT = State()
    SEARCH_NAME = State()
    SEARCH_REGEX = State()
    SEARCH_GREP = State()
    UPLOAD = State()
    EDIT_FILE_NEW = State()
    KILL_PID = State()
    SCHEDULE_MIN = State()
    SCHEDULE_TEXT = State()
    SHELL_CMD = State()
    URL_DOWNLOAD = State()
    MASS_RENAME = State()
    DIFF_A = State()
    DIFF_B = State()
    PING = State()
    QR_TEXT = State()
    PASS_LEN = State()
    AUDIO_DURATION = State()


# ==================== ЛОКАЛИЗАЦИЯ ====================
L = {
    "ru": {
        "welcome": "🎉 <b>Бот-ратник PRO</b>\nВыбери действие:",
        "view_files": "📂 Файлы", "folders": "📁 Действия",
        "system": "💻 Система", "location": "🌍 Гео",
        "bookmarks": "⭐ Закладки", "settings": "⚙️ Настройки",
        "tools": "🛠 Утилиты",
        "back": "⬅️ Назад", "up": "⬆️ Вверх", "menu": "🔙 Меню",
        "prev": "⬅️", "next": "➡️",
        "delete": "🗑️ Удалить", "rename": "✏️ Переименовать",
        "create_folder": "📁 Создать", "move": "🚚 Переместить",
        "copy": "📄 Копировать", "zip": "📦 ZIP",
        "unzip": "📂 Распаковать", "search_ext": "🔍 Расширение",
        "search_name": "🔎 Имя", "search_regex": "🧬 Regex",
        "search_grep": "🔦 Внутри файлов",
        "duplicates": "🧬 Дубликаты", "analyze": "📊 Анализ",
        "upload": "📤 Загрузить", "edit": "📝 Правка",
        "trash": "♻️ Корзина", "send": "📤 Отправить",
        "view": "👁 Просмотр", "meta": "🔬 Метаданные",
        "hash": "🧾 Хеш", "as_text": "📝 Как текст",
        "diff": "⚖️ Diff", "mass_rename": "🔢 Шаблон",
        "url_download": "📥 URL→скачать",
        "history": "🕘 История", "undo": "↩️ Undo",
        "enter_path": "Введите путь:\n{ex}",
        "enter_new_name": "✏️ Новое имя:",
        "enter_dest": "📥 Назначение:",
        "invalid_path": "❌ Путь не существует.",
        "file_not_found": "❌ Не найдено.",
        "ok_delete": "✅ В корзину: {p}",
        "confirm_delete": "⚠️ Удалить?\n<code>{p}</code>",
        "yes": "✅ Да", "no": "❌ Нет",
        "ok_rename": "✅ → {n}",
        "ok_create": "✅ Создано: {p}",
        "ok_move": "✅ → {d}", "ok_copy": "✅ → {d}",
        "ok_zip": "✅ Архив: {p}", "ok_unzip": "✅ Распаковано: {d}",
        "ok_upload": "✅ Сохранено: {p}",
        "err": "❌ {e}",
        "lang": "🌐 Язык", "select_lang": "Язык:",
        "lang_set": "✅ {lang}",
        "search_started": "🔍 Ищу...",
        "search_found": "✅ Найдено: {n}",
        "file_too_big": "❌ Файл > {mb} МБ.",
        "no_text": "❌ Не текст.",
        "upload_prompt": "📤 Отправь файл — сохраню в: <code>{d}</code>",
        "edit_prompt": "📝 Текущее:\n<pre>{c}</pre>\n\nНовый текст:",
        "edit_done": "✅ Обновлено.",
        "bookmark_name": "Имя закладки:",
        "bookmark_added": "⭐ {n}",
        "bookmarks_empty": "⭐ Пусто.",
        "trash_empty": "♻️ Пусто.",
        "trash_restored": "✅ Восстановлено: {p}",
        "trash_cleared": "✅ Очищено.",
        "kill_prompt": "PID:",
        "kill_ok": "✅ Убит: {pid}",
        "kill_err": "❌ {e}",
        "schedule_prompt": "Через сколько минут?",
        "schedule_text": "Что напомнить?",
        "schedule_ok": "⏰ Через {m} мин.",
        "schedule_done": "⏰ {t}",
        "shell_prompt": "Введи команду (whitelist):",
        "shell_denied": "🚫 Команда не разрешена.",
        "url_prompt": "Пришли URL — скачаю в текущую папку:",
        "downloading": "📥 Скачиваю… {p}% ({s}/{t})",
        "download_done": "✅ Скачано: {p}",
        "mass_selected": "Отмечено: {n}",
        "mass_actions": "Что сделать с выбранными?",
        "mass_zip": "📦 В архив", "mass_delete": "🗑️ Удалить",
        "mass_clear": "❌ Снять",
        "rename_pattern": "Шаблон ({n} — номер, {name} — имя):",
        "ping_prompt": "Хост для ping:",
        "qr_prompt": "Текст для QR:",
        "pass_prompt": "Длина пароля (8–128):",
        "pass_result": "🔑 Пароль: <code>{p}</code>",
        "diff_prompt_a": "Путь к первому файлу:",
        "diff_prompt_b": "Путь ко второму файлу:",
        "regex_prompt": "Regex (например ^IMG_\\d+\\.jpg$):",
        "grep_prompt": "Что искать в файлах:",
        "meta_title": "🔬 <b>{n}</b>",
        "hash_title": "🧾 <b>Хеши {n}</b>",
        "undo_none": "↩️ Нечего отменять.",
        "undo_ok": "↩️ Отменено: {a}",
        "history_empty": "🕘 История пуста.",
        "history_title": "🕘 <b>Последние {n} действий</b>",
        "url_invalid": "❌ Неверная ссылка.",
    },
    "en": {
        "welcome": "🎉 <b>Warrior bot PRO</b>\nChoose:",
        "view_files": "📂 Files", "folders": "📁 Actions",
        "system": "💻 System", "location": "🌍 Geo",
        "bookmarks": "⭐ Bookmarks", "settings": "⚙️ Settings",
        "tools": "🛠 Tools",
        "back": "⬅️ Back", "up": "⬆️ Up", "menu": "🔙 Menu",
        "prev": "⬅️", "next": "➡️",
        "delete": "🗑️ Delete", "rename": "✏️ Rename",
        "create_folder": "📁 Create", "move": "🚚 Move",
        "copy": "📄 Copy", "zip": "📦 ZIP",
        "unzip": "📂 Unzip", "search_ext": "🔍 Ext",
        "search_name": "🔎 Name", "search_regex": "🧬 Regex",
        "search_grep": "🔦 Inside",
        "duplicates": "🧬 Dups", "analyze": "📊 Analyze",
        "upload": "📤 Upload", "edit": "📝 Edit",
        "trash": "♻️ Trash", "send": "📤 Send",
        "view": "👁 View", "meta": "🔬 Meta",
        "hash": "🧾 Hash", "as_text": "📝 As text",
        "diff": "⚖️ Diff", "mass_rename": "🔢 Pattern",
        "url_download": "📥 URL→file",
        "history": "🕘 History", "undo": "↩️ Undo",
        "enter_path": "Enter path:\n{ex}",
        "enter_new_name": "✏️ New name:",
        "enter_dest": "📥 Dest:",
        "invalid_path": "❌ Path missing.",
        "file_not_found": "❌ Not found.",
        "ok_delete": "✅ Trash: {p}",
        "confirm_delete": "⚠️ Delete?\n<code>{p}</code>",
        "yes": "✅ Yes", "no": "❌ No",
        "ok_rename": "✅ → {n}",
        "ok_create": "✅ {p}", "ok_move": "✅ → {d}",
        "ok_copy": "✅ → {d}",
        "ok_zip": "✅ {p}", "ok_unzip": "✅ {d}",
        "ok_upload": "✅ {p}",
        "err": "❌ {e}",
        "lang": "🌐 Lang", "select_lang": "Language:",
        "lang_set": "✅ {lang}",
        "search_started": "🔍 Searching…",
        "search_found": "✅ Found: {n}",
        "file_too_big": "❌ File > {mb} MB.",
        "no_text": "❌ Not text.",
        "upload_prompt": "📤 Send file — save to: <code>{d}</code>",
        "edit_prompt": "📝 Current:\n<pre>{c}</pre>\n\nNew text:",
        "edit_done": "✅ Updated.",
        "bookmark_name": "Bookmark name:",
        "bookmark_added": "⭐ {n}",
        "bookmarks_empty": "⭐ Empty.",
        "trash_empty": "♻️ Empty.",
        "trash_restored": "✅ Restored: {p}",
        "trash_cleared": "✅ Cleared.",
        "kill_prompt": "PID:",
        "kill_ok": "✅ Killed: {pid}",
        "kill_err": "❌ {e}",
        "schedule_prompt": "In how many minutes?",
        "schedule_text": "What to remind?",
        "schedule_ok": "⏰ In {m} min.",
        "schedule_done": "⏰ {t}",
        "shell_prompt": "Command (whitelist):",
        "shell_denied": "🚫 Not allowed.",
        "url_prompt": "Send URL:",
        "downloading": "📥 Downloading… {p}% ({s}/{t})",
        "download_done": "✅ Downloaded: {p}",
        "mass_selected": "Selected: {n}",
        "mass_actions": "What to do?",
        "mass_zip": "📦 Zip", "mass_delete": "🗑️ Delete",
        "mass_clear": "❌ Clear",
        "rename_pattern": "Pattern ({n}, {name}):",
        "ping_prompt": "Host for ping:",
        "qr_prompt": "QR text:",
        "pass_prompt": "Password length (8–128):",
        "pass_result": "🔑 <code>{p}</code>",
        "diff_prompt_a": "First file path:",
        "diff_prompt_b": "Second file path:",
        "regex_prompt": "Regex:",
        "grep_prompt": "Search inside files:",
        "meta_title": "🔬 <b>{n}</b>",
        "hash_title": "🧾 <b>Hashes {n}</b>",
        "undo_none": "↩️ Nothing.",
        "undo_ok": "↩️ Undone: {a}",
        "history_empty": "🕘 Empty.",
        "history_title": "🕘 <b>Last {n} actions</b>",
        "url_invalid": "❌ Invalid URL.",
    },
    "ua": {
        "welcome": "🎉 <b>Бот-воїн PRO</b>\nОбери:",
        "view_files": "📂 Файли", "folders": "📁 Дії",
        "system": "💻 Система", "location": "🌍 Гео",
        "bookmarks": "⭐ Закладки", "settings": "⚙️ Налаштування",
        "tools": "🛠 Утиліти",
        "back": "⬅️ Назад", "up": "⬆️ Вгору", "menu": "🔙 Меню",
        "prev": "⬅️", "next": "➡️",
        "delete": "🗑️ Видалити", "rename": "✏️ Перейменувати",
        "create_folder": "📁 Створити", "move": "🚚 Перемістити",
        "copy": "📄 Копіювати", "zip": "📦 ZIP",
        "unzip": "📂 Розпакувати", "search_ext": "🔍 Розширення",
        "search_name": "🔎 Ім'я", "search_regex": "🧬 Regex",
        "search_grep": "🔦 Всередині",
        "duplicates": "🧬 Дублі", "analyze": "📊 Аналіз",
        "upload": "📤 Завантажити", "edit": "📝 Правка",
        "trash": "♻️ Кошик", "send": "📤 Надіслати",
        "view": "👁 Перегляд", "meta": "🔬 Мета",
        "hash": "🧾 Хеш", "as_text": "📝 Як текст",
        "diff": "⚖️ Diff", "mass_rename": "🔢 Шаблон",
        "url_download": "📥 URL→файл",
        "history": "🕘 Історія", "undo": "↩️ Undo",
        "enter_path": "Шлях:\n{ex}",
        "enter_new_name": "✏️ Нова назва:",
        "enter_dest": "📥 Призначення:",
        "invalid_path": "❌ Шлях відсутній.",
        "file_not_found": "❌ Не знайдено.",
        "ok_delete": "✅ У кошик: {p}",
        "confirm_delete": "⚠️ Видалити?\n<code>{p}</code>",
        "yes": "✅ Так", "no": "❌ Ні",
        "ok_rename": "✅ → {n}",
        "ok_create": "✅ {p}", "ok_move": "✅ → {d}",
        "ok_copy": "✅ → {d}",
        "ok_zip": "✅ {p}", "ok_unzip": "✅ {d}",
        "ok_upload": "✅ {p}",
        "err": "❌ {e}",
        "lang": "🌐 Мова", "select_lang": "Мова:",
        "lang_set": "✅ {lang}",
        "search_started": "🔍 Шукаю…",
        "search_found": "✅ Знайдено: {n}",
        "file_too_big": "❌ > {mb} МБ.",
        "no_text": "❌ Не текст.",
        "upload_prompt": "📤 Надішли файл — збережу в: <code>{d}</code>",
        "edit_prompt": "📝 Зараз:\n<pre>{c}</pre>\n\nНовий текст:",
        "edit_done": "✅ Оновлено.",
        "bookmark_name": "Назва закладки:",
        "bookmark_added": "⭐ {n}",
        "bookmarks_empty": "⭐ Порожньо.",
        "trash_empty": "♻️ Порожньо.",
        "trash_restored": "✅ Відновлено: {p}",
        "trash_cleared": "✅ Очищено.",
        "kill_prompt": "PID:",
        "kill_ok": "✅ Вбито: {pid}",
        "kill_err": "❌ {e}",
        "schedule_prompt": "Через скільки хвилин?",
        "schedule_text": "Що нагадати?",
        "schedule_ok": "⏰ Через {m} хв.",
        "schedule_done": "⏰ {t}",
        "shell_prompt": "Команда (whitelist):",
        "shell_denied": "🚫 Не дозволено.",
        "url_prompt": "Надішли URL:",
        "downloading": "📥 Завантажую… {p}% ({s}/{t})",
        "download_done": "✅ Завантажено: {p}",
        "mass_selected": "Обрано: {n}",
        "mass_actions": "Що зробити?",
        "mass_zip": "📦 В архів", "mass_delete": "🗑️ Видалити",
        "mass_clear": "❌ Зняти",
        "rename_pattern": "Шаблон ({n}, {name}):",
        "ping_prompt": "Хост:",
        "qr_prompt": "Текст для QR:",
        "pass_prompt": "Довжина (8–128):",
        "pass_result": "🔑 <code>{p}</code>",
        "diff_prompt_a": "Перший файл:",
        "diff_prompt_b": "Другий файл:",
        "regex_prompt": "Regex:",
        "grep_prompt": "Що шукати:",
        "meta_title": "🔬 <b>{n}</b>",
        "hash_title": "🧾 <b>Хеші {n}</b>",
        "undo_none": "↩️ Нічого.",
        "undo_ok": "↩️ Скасовано: {a}",
        "history_empty": "🕘 Порожньо.",
        "history_title": "🕘 <b>Останні {n}</b>",
        "url_invalid": "❌ Невірне посилання.",
    },
}

USER_LANGUAGE = {}


def t(chat_id, key, **kw):
    lang = USER_LANGUAGE.get(chat_id, "ru")
    txt = L.get(lang, L["ru"]).get(key, key)
    if kw:
        try:
            return txt.format(**kw)
        except Exception:
            return txt
    return txt


def set_language(chat_id, lang):
    if lang in L:
        USER_LANGUAGE[chat_id] = lang


# ==================== ГЛОБАЛЬНОЕ СОСТОЯНИЕ ====================
navigation_history = {}
last_message_id = {}
file_paths = {}
current_action = {}
upload_context = {}
mass_selection = {}
undo_stack = {}
op_history = {}


def load_json(path, default=None):
    if default is None:
        default = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def save_json(path, data):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"save {path}: {e}")


BOOKMARKS = load_json(BOOKMARKS_FILE)
HISTORY = load_json(HISTORY_FILE, default=[])


# ==================== ХЕЛПЕРЫ ФАЙЛОВ ====================
def get_examples():
    if DEVICE_TYPE == "windows":
        return "<code>C:/Users/YourName/Documents</code>\n<code>C:/Users/YourName/Downloads</code>"
    if DEVICE_TYPE == "mac":
        return "<code>/Users/YourName/Documents</code>\n<code>/Applications</code>"
    return "<code>/home/user/Documents</code>\n<code>/home/user/Downloads</code>"


def file_emoji(name: str) -> str:
    n = name.lower()
    for exts, e in [
        ((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"), "🖼️"),
        ((".mp3", ".wav", ".ogg", ".flac", ".m4a"), "🎵"),
        ((".mp4", ".mov", ".avi", ".mkv", ".flv", ".webm"), "🎥"),
        ((".txt", ".md", ".log", ".json", ".xml", ".csv", ".conf", ".ini", ".py", ".sh"), "📝"),
        ((".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"), "📄"),
        ((".zip", ".rar", ".tar", ".gz", ".7z", ".bz2", ".xz", ".tgz"), "📦"),
        ((".exe", ".msi", ".bat", ".apk", ".deb", ".rpm"), "⚙️"),
    ]:
        if n.endswith(exts):
            return e
    return "📄"


def human_size(size: float) -> str:
    for u in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.1f} {u}"
        size /= 1024
    return f"{size:.1f} PB"


def is_safe_path(p: str) -> bool:
    try:
        r = os.path.realpath(p)
        root = os.path.realpath(ROOT_DIRECTORY)
        return r == root or r.startswith(root + os.sep)
    except Exception:
        return False


def size_ok(p: str, mb: int = MAX_FILE_MB) -> bool:
    try:
        return os.path.getsize(p) <= mb * 1024 * 1024
    except Exception:
        return False


def is_text(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    ext = os.path.splitext(path)[1].lower()
    if ext in {".txt", ".md", ".log", ".json", ".xml", ".csv", ".conf", ".ini",
               ".py", ".sh", ".js", ".ts", ".html", ".css", ".yml", ".yaml", ".toml"}:
        return True
    try:
        with open(path, "rb") as f:
            chunk = f.read(1024)
        if b"\x00" in chunk:
            return False
        chunk.decode("utf-8")
        return True
    except Exception:
        return False


def trash_move(path: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.basename(path.rstrip(os.sep)) or "root"
    dest = os.path.join(TRASH_DIR, f"{ts}_{base}")
    shutil.move(path, dest)
    return dest


def push_history(chat_id, action: str, info: dict):
    if chat_id not in op_history:
        op_history[chat_id] = []
    op_history[chat_id].append({"t": time.time(), "a": action, "i": info})
    op_history[chat_id] = op_history[chat_id][-HISTORY_LIMIT:]
    HISTORY.append({"chat_id": chat_id, "t": time.time(), "a": action, "i": info})
    save_json(HISTORY_FILE, HISTORY[-200:])


def push_undo(chat_id, item: dict):
    if chat_id not in undo_stack:
        undo_stack[chat_id] = []
    undo_stack[chat_id].append(item)
    undo_stack[chat_id] = undo_stack[chat_id][-10:]


def find_dups(directory: str, max_files: int = 2000) -> dict:
    h = {}
    cnt = 0
    for root, dirs, files in os.walk(directory, onerror=lambda e: None):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            cnt += 1
            if cnt > max_files:
                return {k: v for k, v in h.items() if len(v) > 1}
            full = os.path.join(root, f)
            try:
                if os.path.getsize(full) < 1024:
                    continue
                md5 = hashlib.md5()
                with open(full, "rb") as fh:
                    for c in iter(lambda: fh.read(65536), b""):
                        md5.update(c)
                h.setdefault(md5.hexdigest(), []).append(full)
            except Exception:
                continue
    return {k: v for k, v in h.items() if len(v) > 1}


def analyze(directory: str, max_files: int = 5000) -> dict:
    total, count = 0, 0
    by_ext, files = {}, []
    for root, dirs, fs in os.walk(directory, onerror=lambda e: None):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in fs:
            count += 1
            if count > max_files:
                break
            full = os.path.join(root, f)
            try:
                sz = os.path.getsize(full)
            except Exception:
                continue
            total += sz
            ext = os.path.splitext(f)[1].lower() or "(no-ext)"
            by_ext[ext] = by_ext.get(ext, 0) + sz
            files.append((full, sz))
    files.sort(key=lambda x: x[1], reverse=True)
    top_ext = sorted(by_ext.items(), key=lambda x: x[1], reverse=True)[:8]
    return {"total": total, "count": count, "top": files[:10], "by_ext": top_ext}


def search_files(directory, ext=None, name_sub=None, regex=None,
                 max_depth=SEARCH_MAX_DEPTH, max_results=SEARCH_MAX_RESULTS):
    found = []
    base = os.path.realpath(directory)
    bd = base.rstrip(os.sep).count(os.sep)
    rx = re.compile(regex, re.IGNORECASE) if regex else None
    for root, dirs, files in os.walk(base, onerror=lambda e: None):
        depth = root.count(os.sep) - bd
        if depth >= max_depth:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            if f.startswith("."):
                continue
            if ext and not f.lower().endswith(ext):
                continue
            if name_sub and name_sub.lower() not in f.lower():
                continue
            if rx and not rx.search(f):
                continue
            found.append(os.path.join(root, f))
            if len(found) >= max_results:
                return found
    return found


def grep_files(directory, needle, max_files=500, max_depth=4, max_hits=30):
    hits = []
    base = os.path.realpath(directory)
    bd = base.rstrip(os.sep).count(os.sep)
    cnt = 0
    for root, dirs, files in os.walk(base, onerror=lambda e: None):
        depth = root.count(os.sep) - bd
        if depth >= max_depth:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            cnt += 1
            if cnt > max_files:
                return hits
            full = os.path.join(root, f)
            if not is_text(full) or not size_ok(full, 5):
                continue
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                    for i, line in enumerate(fh, 1):
                        if needle.lower() in line.lower():
                            hits.append((full, i, line.strip()[:120]))
                            if len(hits) >= max_hits:
                                return hits
                            break
            except Exception:
                continue
    return hits


def get_meta(path: str) -> str:
    try:
        st = os.stat(path)
        text = (
            f"{t(0, 'meta_title', n=os.path.basename(path))}\n"
            f"📂 <code>{path}</code>\n"
            f"📏 Размер: {human_size(st.st_size)}\n"
            f"📅 Создан: {datetime.fromtimestamp(st.st_ctime).strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"📅 Изменён: {datetime.fromtimestamp(st.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"🔐 Права: {oct(st.st_mode)[-3:]}\n"
        )
        if hasattr(st, "st_uid"):
            text += f"👤 UID/GID: {st.st_uid}/{st.st_gid}\n"
        if PIL_OK and path.lower().endswith((".jpg", ".jpeg", ".png", ".tiff", ".heic")):
            try:
                img = Image.open(path)
                text += f"\n🖼 {img.size[0]}×{img.size[1]}\n"
                exif = img.getexif()
                if exif:
                    for tid, val in list(exif.items())[:15]:
                        tag = TAGS.get(tid, tid)
                        text += f"  • {tag}: {str(val)[:80]}\n"
            except Exception:
                pass
        return text
    except Exception as e:
        return f"❌ {e}"


def calc_hashes(path: str) -> str:
    try:
        md5 = hashlib.md5()
        sha1 = hashlib.sha1()
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                md5.update(chunk)
                sha1.update(chunk)
                sha256.update(chunk)
        return (
            f"{t(0, 'hash_title', n=os.path.basename(path))}\n"
            f"MD5: <code>{md5.hexdigest()}</code>\n"
            f"SHA1: <code>{sha1.hexdigest()}</code>\n"
            f"SHA256: <code>{sha256.hexdigest()}</code>"
        )
    except Exception as e:
        return f"❌ {e}"


def diff_files(a: str, b: str) -> str:
    try:
        with open(a, "r", encoding="utf-8", errors="ignore") as f:
            la = f.readlines()[:500]
        with open(b, "r", encoding="utf-8", errors="ignore") as f:
            lb = f.readlines()[:500]
        d = difflib.unified_diff(la, lb, fromfile=os.path.basename(a), tofile=os.path.basename(b))
        text = "".join(d)
        if not text:
            return "✅ Файлы идентичны."
        return f"<pre>{text[:3500]}</pre>"
    except Exception as e:
        return f"❌ {e}"


def gen_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"
    return "".join(random.choice(alphabet) for _ in range(length))


def make_qr(text: str) -> Optional[bytes]:
    if not QR_OK:
        return None
    try:
        img = qrcode.make(text)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


# ==================== УНИВЕРСАЛЬНЫЕ СКРИНШОТ / ВЕБКА / ЗВУК ====================
def _has(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _run_capture(cmd, timeout=15) -> tuple:
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except Exception as e:
        return -1, b"", str(e).encode()


def _is_black_png(data: bytes) -> bool:
    """Проверяет, что PNG — однотонный (все пиксели одинаковые)."""
    if not PIL_OK or not data:
        return False
    try:
        img = Image.open(io.BytesIO(data)).convert("L")
        extrema = img.getextrema()
        return extrema[0] == extrema[1]
    except Exception:
        return False


def _portal_screenshot() -> Optional[bytes]:
    """Скриншот через XDG Desktop Portal (GNOME/KDE Wayland)."""
    if not DBUS_OK:
        return None
    try:
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        bus = dbus.SessionBus()
        result = {}
        loop = GLib.MainLoop()

        def cb(response, results):
            if response == 0:
                uri = str(results.get("uri", ""))
                if uri.startswith("file://"):
                    uri = uri[7:]
                result["path"] = uri
            loop.quit()
            return False

        bus.add_signal_receiver(
            cb,
            signal_name="Response",
            dbus_interface="org.freedesktop.portal.Request",
        )
        portal = bus.get_object(
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
        )
        screenshot = dbus.Interface(portal, "org.freedesktop.portal.Screenshot")
        screenshot.Screenshot(
            "",
            {"interactive": dbus.Boolean(False), "modal": dbus.Boolean(False)},
        )
        GLib.timeout_add_seconds(25, loop.quit)
        loop.run()

        path = result.get("path")
        if path and os.path.exists(path):
            data = open(path, "rb").read()
            try:
                os.remove(path)
            except Exception:
                pass
            logging.info("screenshot via XDG portal")
            return data
    except Exception as e:
        logging.error(f"portal: {e}")
    return None


def take_screenshot() -> Optional[bytes]:
    """Универсальный скриншот. Пробует всё, что есть в системе."""
    system = platform.system().lower()
    is_wayland = bool(os.environ.get("WAYLAND_DISPLAY")) or \
                 os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"

    # === XDG Portal (GNOME/KDE Wayland) — пробуем первым ===
    if system == "linux" and is_wayland and DBUS_OK:
        data = _portal_screenshot()
        if data and not _is_black_png(data):
            return data

    # ========== WINDOWS ==========
    if system == "windows":
        if MSS_OK:
            try:
                with mss.mss() as sct:
                    monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                    shot = sct.grab(monitor)
                    data = mss.tools.to_png(shot.rgb, shot.size)
                    if data and not _is_black_png(data):
                        logging.info("screenshot via mss (win)")
                        return data
            except Exception as e:
                logging.error(f"win mss: {e}")
        try:
            tmp = tempfile.mktemp(suffix=".png")
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms,System.Drawing;"
                "$b=[System.Windows.Forms.Screen]::PrimaryScreen.Bounds;"
                "$bmp=New-Object System.Drawing.Bitmap $b.Width,$b.Height;"
                "$g=[System.Drawing.Graphics]::FromImage($bmp);"
                "$g.CopyFromScreen($b.Location,[System.Drawing.Point]::Empty,$b.Size);"
                f"$bmp.Save('{tmp}','Png')"
            )
            subprocess.run(["powershell", "-Command", ps], capture_output=True, timeout=15)
            if os.path.exists(tmp):
                data = open(tmp, "rb").read()
                os.remove(tmp)
                if data:
                    logging.info("screenshot via powershell")
                    return data
        except Exception as e:
            logging.error(f"win ps: {e}")
        return None

    # ========== macOS ==========
    if system == "darwin":
        try:
            tmp = tempfile.mktemp(suffix=".png")
            subprocess.run(["screencapture", "-x", tmp], capture_output=True, timeout=15)
            if os.path.exists(tmp):
                data = open(tmp, "rb").read()
                os.remove(tmp)
                if data and not _is_black_png(data):
                    logging.info("screenshot via screencapture")
                    return data
        except Exception as e:
            logging.error(f"mac screencapture: {e}")
        if MSS_OK:
            try:
                with mss.mss() as sct:
                    shot = sct.grab(sct.monitors[1])
                    return mss.tools.to_png(shot.rgb, shot.size)
            except Exception:
                pass
        return None

    # ========== LINUX ==========
    if is_wayland:
        # grim (wlroots: Sway, Hyprland)
        if _has("grim"):
            try:
                tmp = tempfile.mktemp(suffix=".png")
                _run_capture(["grim", tmp], timeout=10)
                if os.path.exists(tmp):
                    data = open(tmp, "rb").read()
                    os.remove(tmp)
                    if data and not _is_black_png(data):
                        logging.info("screenshot via grim")
                        return data
            except Exception as e:
                logging.error(f"grim: {e}")

        # gnome-screenshot (fallback, может не сработать)
        if _has("gnome-screenshot"):
            try:
                tmp = tempfile.mktemp(suffix=".png")
                _run_capture(["gnome-screenshot", "-f", tmp], timeout=15)
                if os.path.exists(tmp):
                    data = open(tmp, "rb").read()
                    os.remove(tmp)
                    if data and not _is_black_png(data) and len(data) > 1000:
                        logging.info("screenshot via gnome-screenshot")
                        return data
            except Exception as e:
                logging.error(f"gnome-screenshot: {e}")

        # spectacle (KDE Wayland)
        if _has("spectacle"):
            try:
                tmp = tempfile.mktemp(suffix=".png")
                _run_capture(["spectacle", "-b", "-n", "-o", tmp], timeout=10)
                if os.path.exists(tmp):
                    data = open(tmp, "rb").read()
                    os.remove(tmp)
                    if data and not _is_black_png(data):
                        logging.info("screenshot via spectacle")
                        return data
            except Exception as e:
                logging.error(f"spectacle: {e}")

        # flameshot
        if _has("flameshot"):
            try:
                tmpdir = tempfile.mkdtemp()
                _run_capture(["flameshot", "full", "-p", tmpdir], timeout=10)
                for f in os.listdir(tmpdir):
                    if f.lower().endswith(".png"):
                        data = open(os.path.join(tmpdir, f), "rb").read()
                        if data and not _is_black_png(data):
                            logging.info("screenshot via flameshot")
                            return data
            except Exception as e:
                logging.error(f"flameshot: {e}")

    # X11 и общее
    if _has("scrot"):
        try:
            tmp = tempfile.mktemp(suffix=".png")
            _run_capture(["scrot", "-o", tmp], timeout=10)
            if os.path.exists(tmp):
                data = open(tmp, "rb").read()
                os.remove(tmp)
                if data and not _is_black_png(data):
                    logging.info("screenshot via scrot")
                    return data
        except Exception as e:
            logging.error(f"scrot: {e}")

    if _has("import"):
        try:
            tmp = tempfile.mktemp(suffix=".png")
            _run_capture(["import", "-window", "root", tmp], timeout=10)
            if os.path.exists(tmp):
                data = open(tmp, "rb").read()
                os.remove(tmp)
                if data and not _is_black_png(data):
                    logging.info("screenshot via import")
                    return data
        except Exception as e:
            logging.error(f"import: {e}")

    if _has("ffmpeg") and not is_wayland:
        try:
            tmp = tempfile.mktemp(suffix=".png")
            display = os.environ.get("DISPLAY", ":0")
            _run_capture(
                ["ffmpeg", "-y", "-f", "x11grab", "-i", display, "-frames:v", "1", tmp],
                timeout=15
            )
            if os.path.exists(tmp):
                data = open(tmp, "rb").read()
                os.remove(tmp)
                if data and not _is_black_png(data):
                    logging.info("screenshot via ffmpeg x11grab")
                    return data
        except Exception as e:
            logging.error(f"ffmpeg x11grab: {e}")

    if MSS_OK:
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                shot = sct.grab(monitor)
                data = mss.tools.to_png(shot.rgb, shot.size)
                if data and not _is_black_png(data):
                    logging.info("screenshot via mss")
                    return data
                logging.warning("mss вернул чёрный/пустой скриншот")
        except Exception as e:
            logging.error(f"mss: {e}")

    return None


def capture_webcam(index: int = 0) -> Optional[bytes]:
    """Универсальный снимок с веб-камеры."""
    if CV2_OK:
        for idx in [index, 0, 1, 2, 3]:
            cap = None
            try:
                cap = cv2.VideoCapture(idx)
                if cap.isOpened():
                    for _ in range(5):
                        cap.read()
                        time.sleep(0.05)
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                        if ok:
                            logging.info(f"webcam via cv2 idx={idx}")
                            return buf.tobytes()
            except Exception as e:
                logging.error(f"cv2 cam {idx}: {e}")
            finally:
                if cap:
                    cap.release()

    if _has("ffmpeg"):
        system = platform.system().lower()
        input_args = None
        if system == "linux":
            for i in range(4):
                if os.path.exists(f"/dev/video{i}"):
                    input_args = ["-f", "v4l2", "-i", f"/dev/video{i}"]
                    break
        elif system == "darwin":
            input_args = ["-f", "avfoundation", "-i", "0"]
        elif system == "windows":
            input_args = ["-f", "dshow", "-i", "video=default"]

        if input_args:
            try:
                tmp = tempfile.mktemp(suffix=".jpg")
                _run_capture(["ffmpeg", "-y"] + input_args + ["-frames:v", "1", tmp], timeout=15)
                if os.path.exists(tmp):
                    data = open(tmp, "rb").read()
                    os.remove(tmp)
                    if data:
                        logging.info("webcam via ffmpeg")
                        return data
            except Exception as e:
                logging.error(f"ffmpeg cam: {e}")

    if platform.system().lower() == "linux" and _has("fswebcam"):
        try:
            tmp = tempfile.mktemp(suffix=".jpg")
            _run_capture(["fswebcam", "-r", "1280x720", "--no-banner", tmp], timeout=15)
            if os.path.exists(tmp):
                data = open(tmp, "rb").read()
                os.remove(tmp)
                if data:
                    logging.info("webcam via fswebcam")
                    return data
        except Exception as e:
            logging.error(f"fswebcam: {e}")

    return None


def record_audio(duration: int = 30, samplerate: int = 44100) -> Optional[bytes]:
    """Универсальная запись с микрофона."""
    duration = max(1, min(duration, 300))

    if AUDIO_OK:
        try:
            rec = sd.rec(int(duration * samplerate), samplerate=samplerate,
                         channels=1, dtype="int16")
            sd.wait()
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(samplerate)
                wf.writeframes(rec.tobytes())
            buf.seek(0)
            logging.info("audio via sounddevice")
            return buf.read()
        except Exception as e:
            logging.error(f"sounddevice: {e}")

    if _has("ffmpeg"):
        system = platform.system().lower()
        candidates = []
        if system == "linux":
            candidates = [
                ["-f", "pulse", "-i", "default"],
                ["-f", "alsa", "-i", "default"],
            ]
        elif system == "darwin":
            candidates = [["-f", "avfoundation", "-i", ":0"]]
        elif system == "windows":
            candidates = [["-f", "dshow", "-i", "audio=default"]]

        for input_spec in candidates:
            try:
                tmp = tempfile.mktemp(suffix=".wav")
                _run_capture(
                    ["ffmpeg", "-y"] + input_spec + ["-t", str(duration), "-ac", "1", tmp],
                    timeout=duration + 10
                )
                if os.path.exists(tmp):
                    data = open(tmp, "rb").read()
                    os.remove(tmp)
                    if data and len(data) > 100:
                        logging.info("audio via ffmpeg")
                        return data
            except Exception:
                continue

    if platform.system().lower() == "linux" and _has("arecord"):
        try:
            tmp = tempfile.mktemp(suffix=".wav")
            _run_capture(
                ["arecord", "-d", str(duration), "-f", "S16_LE",
                 "-r", str(samplerate), "-c", "1", tmp],
                timeout=duration + 10
            )
            if os.path.exists(tmp):
                data = open(tmp, "rb").read()
                os.remove(tmp)
                if data:
                    logging.info("audio via arecord")
                    return data
        except Exception as e:
            logging.error(f"arecord: {e}")

    return None


async def do_power_action(action: str) -> tuple:
    try:
        if DEVICE_TYPE == "linux":
            if action == "shutdown":
                cmd = ["systemctl", "poweroff"]
            elif action == "suspend":
                cmd = ["systemctl", "suspend"]
            elif action == "reboot":
                cmd = ["systemctl", "reboot"]
            elif action == "lock":
                for lc in (["loginctl", "lock-session"],
                           ["xdg-screensaver", "lock"],
                           ["gnome-screensaver-command", "-l"]):
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            *lc, stdout=asyncio.subprocess.DEVNULL,
                            stderr=asyncio.subprocess.DEVNULL,
                        )
                        rc = await asyncio.wait_for(proc.wait(), timeout=3)
                        if rc == 0:
                            return True, f"✅ {action}"
                    except Exception:
                        continue
                return False, "❌ Не удалось заблокировать."
            else:
                return False, "❌ Неизвестно."
        elif DEVICE_TYPE == "windows":
            if action == "shutdown":
                cmd = ["shutdown", "/s", "/t", "0"]
            elif action == "reboot":
                cmd = ["shutdown", "/r", "/t", "0"]
            elif action == "suspend":
                cmd = ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]
            elif action == "lock":
                cmd = ["rundll32.exe", "user32.dll,LockWorkStation"]
            else:
                return False, "❌"
        elif DEVICE_TYPE == "mac":
            if action == "shutdown":
                cmd = ["osascript", "-e", 'tell app "System Events" to shut down']
            elif action == "reboot":
                cmd = ["osascript", "-e", 'tell app "System Events" to restart']
            elif action == "suspend":
                cmd = ["pmset", "sleepnow"]
            elif action == "lock":
                cmd = ["pmset", "displaysleepnow"]
            else:
                return False, "❌"
        else:
            return False, "❌ Платформа не поддерживается."

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=10)
        if proc.returncode == 0:
            return True, f"✅ {action} выполнено"
        return False, f"❌ {(err or out).decode(errors='ignore')[:200]}"
    except asyncio.TimeoutError:
        return True, f"✅ {action} запущено"
    except Exception as e:
        return False, f"❌ {e}"


# ==================== URL DOWNLOAD ====================
async def url_download(chat_id, url: str, dest_dir: str):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            await bot.send_message(chat_id, t(chat_id, "url_invalid"))
            return
        name = os.path.basename(parsed.path) or f"download_{int(time.time())}"
        dest = os.path.join(dest_dir, name)
        base, ext = os.path.splitext(dest)
        i = 1
        while os.path.exists(dest):
            dest = f"{base}_{i}{ext}"
            i += 1
        msg = await bot.send_message(chat_id, t(chat_id, "downloading", p=0, s="0 B", t="?"))
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=600)) as r:
                if r.status != 200:
                    await msg.edit_text(f"❌ HTTP {r.status}")
                    return
                total = int(r.headers.get("Content-Length", 0))
                downloaded = 0
                last_pct = -1
                with open(dest, "wb") as f:
                    async for chunk in r.content.iter_chunked(65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = downloaded * 100 // total
                            if pct - last_pct >= 10:
                                last_pct = pct
                                try:
                                    await msg.edit_text(t(
                                        chat_id, "downloading",
                                        p=pct, s=human_size(downloaded), t=human_size(total),
                                    ))
                                except Exception:
                                    pass
        await msg.edit_text(t(chat_id, "download_done", p=dest))
        push_history(chat_id, "download", {"path": dest, "url": url})
        push_undo(chat_id, {"action": "delete", "path": dest})
    except Exception as e:
        await bot.send_message(chat_id, t(chat_id, "err", e=e))


# ==================== РЕДАКТИРОВАНИЕ ====================
async def edit_msg(message, text, reply_markup=None):
    try:
        if message.caption is not None:
            await message.edit_caption(caption=text, reply_markup=reply_markup, parse_mode="HTML")
            return
        await message.edit_text(text=text, reply_markup=reply_markup, parse_mode="HTML")
        return
    except TelegramBadRequest:
        pass
    except Exception:
        pass
    try:
        await message.answer(text, reply_markup=reply_markup, parse_mode="HTML")
    except Exception:
        pass


# ==================== МЕНЮ ====================
def main_menu(chat_id):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(chat_id, "view_files"), callback_data="view_files")
    kb.button(text=t(chat_id, "folders"), callback_data="folders_menu")
    kb.button(text=t(chat_id, "system"), callback_data="system")
    kb.button(text=t(chat_id, "tools"), callback_data="tools")
    kb.button(text="📸 Скриншот", callback_data="sys_shot")
    kb.button(text="📷 Камера", callback_data="sys_cam")
    kb.button(text="🎤 Микрофон", callback_data="sys_audio")
    kb.button(text="⚡ Питание", callback_data="sys_power")
    kb.button(text=t(chat_id, "location"), callback_data="location")
    kb.button(text=t(chat_id, "bookmarks"), callback_data="bookmarks")
    kb.button(text=t(chat_id, "history"), callback_data="history_show")
    kb.button(text=t(chat_id, "undo"), callback_data="undo")
    kb.button(text=t(chat_id, "settings"), callback_data="settings")
    kb.adjust(2)
    return kb.as_markup()


# ==================== ЛИСТИНГ ПАПКИ ====================
async def show_dir(chat_id, directory, page=0):
    if not os.path.isdir(directory):
        await bot.send_message(chat_id, t(chat_id, "invalid_path"))
        return
    if not is_safe_path(directory):
        await bot.send_message(chat_id, "🚫 Вне зоны.")
        return

    if chat_id not in navigation_history:
        navigation_history[chat_id] = []
    if not navigation_history[chat_id] or navigation_history[chat_id][-1] != directory:
        navigation_history[chat_id].append(directory)

    try:
        entries = sorted(
            os.listdir(directory),
            key=lambda x: (not os.path.isdir(os.path.join(directory, x)), x.lower()),
        )
    except PermissionError:
        await bot.send_message(chat_id, "🚫 Нет доступа.")
        return
    except Exception as e:
        await bot.send_message(chat_id, t(chat_id, "err", e=e))
        return

    per = 8
    total_pages = max(1, (len(entries) + per - 1) // per)
    page = max(0, min(page, total_pages - 1))
    current = entries[page * per:(page + 1) * per]

    file_paths[chat_id] = {}
    if chat_id not in mass_selection:
        mass_selection[chat_id] = set()

    kb = InlineKeyboardBuilder()
    for idx, item in enumerate(current):
        full = os.path.join(directory, item)
        file_paths[chat_id][str(idx)] = full
        disp = item if len(item) <= 32 else item[:29] + "…"
        check = "✅" if full in mass_selection[chat_id] else (
            "📁" if os.path.isdir(full) else file_emoji(item)
        )
        kb.button(text=f"{check} {disp}", callback_data=f"sel_{idx}")
    kb.adjust(1)

    nav = []
    if directory.rstrip(os.sep) != os.path.realpath(ROOT_DIRECTORY).rstrip(os.sep):
        nav.append(types.InlineKeyboardButton(text=t(chat_id, "up"), callback_data="up"))
    nav.append(types.InlineKeyboardButton(text=t(chat_id, "menu"), callback_data="return_to_menu"))
    kb.row(*nav)

    kb.row(
        types.InlineKeyboardButton(text=t(chat_id, "prev"), callback_data=f"pg_{page - 1}"),
        types.InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="ignore"),
        types.InlineKeyboardButton(text=t(chat_id, "next"), callback_data=f"pg_{page + 1}"),
    )

    sel_n = len(mass_selection[chat_id])
    kb.row(types.InlineKeyboardButton(text=t(chat_id, "upload"), callback_data="upload_here"))
    kb.row(types.InlineKeyboardButton(
        text=f"☑️ {t(chat_id, 'mass_selected', n=sel_n)}",
        callback_data="mass_menu",
    ))
    kb.row(types.InlineKeyboardButton(text=t(chat_id, "url_download"), callback_data="url_dl"))

    disp_dir = directory if len(directory) <= 55 else "…" + directory[-52:]
    text = f"📂 <code>{disp_dir}</code>"

    if chat_id in last_message_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=last_message_id[chat_id],
                text=text,
                reply_markup=kb.as_markup(),
            )
            return
        except TelegramBadRequest:
            pass

    msg = await bot.send_message(chat_id, text, reply_markup=kb.as_markup())
    last_message_id[chat_id] = msg.message_id


# ==================== СИСТЕМА ====================
def sys_info() -> str:
    if not PSUTIL:
        return "❌ <code>pip install psutil</code>"
    try:
        cpu = psutil.cpu_percent(interval=0.3)
        cores = psutil.cpu_count(logical=True)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage(ROOT_DIRECTORY if os.path.exists(ROOT_DIRECTORY) else "/")
        up = datetime.now() - datetime.fromtimestamp(psutil.boot_time())
        session = os.environ.get("XDG_SESSION_TYPE", "?")
        return (
            f"💻 <b>Система</b>\n"
            f"🖥 {platform.system()} {platform.release()}\n"
            f"🌐 Session: <code>{session}</code>\n"
            f"🧠 CPU: <b>{cpu}%</b> ({cores} ядер)\n"
            f"💾 RAM: <b>{human_size(ram.used)}</b> / {human_size(ram.total)} ({ram.percent}%)\n"
            f"💿 Диск: <b>{human_size(disk.used)}</b> / {human_size(disk.total)} ({disk.percent}%)\n"
            f"⏱ Uptime: {up.days}д {up.seconds // 3600}ч {(up.seconds // 60) % 60}м"
        )
    except Exception as e:
        return f"❌ {e}"


def top_procs(by="cpu", limit=10) -> str:
    if not PSUTIL:
        return "❌ psutil нет."
    try:
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
            try:
                procs.append(p.info)
            except Exception:
                continue
        key = "cpu_percent" if by == "cpu" else "memory_percent"
        procs.sort(key=lambda x: x.get(key) or 0, reverse=True)
        lines = [f"📊 <b>Топ-{limit} {by.upper()}</b>\n"]
        for p in procs[:limit]:
            lines.append(f"<code>{p['pid']:>6}</code> | {p.get(key, 0):.1f}% | {p['name'][:40]}")
        return "\n".join(lines)
    except Exception as e:
        return f"❌ {e}"


def get_ports() -> str:
    if not PSUTIL:
        return "❌ psutil нет."
    try:
        lines = ["🔌 <b>Слушающие порты</b>\n"]
        for c in psutil.net_connections(kind="inet"):
            if c.status == psutil.CONN_LISTEN:
                laddr = f"{c.laddr.ip}:{c.laddr.port}"
                pid = c.pid or "-"
                name = "?"
                if c.pid:
                    try:
                        name = psutil.Process(c.pid).name()
                    except Exception:
                        pass
                lines.append(f"<code>{laddr}</code> | PID {pid} | {name}")
                if len(lines) > 30:
                    break
        return "\n".join(lines) if len(lines) > 1 else "🔌 Нет портов."
    except Exception as e:
        return f"❌ {e}"


def get_connections() -> str:
    if not PSUTIL:
        return "❌ psutil нет."
    try:
        lines = ["🌐 <b>Соединения (est.)</b>\n"]
        for c in psutil.net_connections(kind="inet"):
            if c.status == "ESTABLISHED" and c.raddr:
                lines.append(f"<code>{c.laddr.ip}:{c.laddr.port} → {c.raddr.ip}:{c.raddr.port}</code>")
                if len(lines) > 25:
                    break
        return "\n".join(lines) if len(lines) > 1 else "Нет соединений."
    except Exception as e:
        return f"❌ {e}"


async def do_ping(chat_id, host):
    try:
        param = "-n" if DEVICE_TYPE == "windows" else "-c"
        proc = await asyncio.create_subprocess_exec(
            "ping", param, "4", host,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=15)
        text = (out or err).decode(errors="ignore")
        await bot.send_message(chat_id, f"<pre>{text[:3500]}</pre>")
    except asyncio.TimeoutError:
        await bot.send_message(chat_id, "⏱ Таймаут")
    except Exception as e:
        await bot.send_message(chat_id, f"❌ {e}")


async def do_shell(chat_id, command: str):
    parts = command.strip().split()
    if not parts:
        return
    if parts[0] not in SHELL_WHITELIST:
        await bot.send_message(chat_id, t(chat_id, "shell_denied"))
        return
    try:
        proc = await asyncio.create_subprocess_shell(
            command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await asyncio.wait_for(proc.communicate(), timeout=20)
        text = (out or err).decode(errors="ignore") or "(пусто)"
        await bot.send_message(chat_id, f"<pre>{text[:3500]}</pre>")
        push_history(chat_id, "shell", {"cmd": command})
    except asyncio.TimeoutError:
        await bot.send_message(chat_id, "⏱ Таймаут")
    except Exception as e:
        await bot.send_message(chat_id, t(chat_id, "err", e=e))


# ==================== КОМАНДЫ ====================
@dp.message(Command("start"))
async def cmd_start(m: types.Message, state: FSMContext):
    await state.clear()
    cid = m.chat.id
    if cid in last_message_id:
        try:
            await bot.delete_message(cid, last_message_id[cid])
        except Exception:
            pass
    text = t(cid, "welcome")
    kb = main_menu(cid)
    if os.path.exists(WELCOME_IMAGE):
        try:
            await bot.send_photo(cid, FSInputFile(WELCOME_IMAGE), caption=text, reply_markup=kb)
            return
        except Exception:
            pass
    await m.answer(text, reply_markup=kb)


@dp.message(Command("help"))
async def cmd_help(m: types.Message):
    await m.answer(
        "📖 <b>Команды</b>\n"
        "/start /help /cancel\n"
        "/system — система\n"
        "/trash — корзина\n"
        "/bookmarks — закладки\n"
        "/history — история\n"
        "/undo — отменить\n"
        "/sh &lt;cmd&gt; — shell (whitelist)\n"
        "/pass [N] — пароль\n"
        "/qr &lt;text&gt; — QR\n"
        "/ping &lt;host&gt; — ping\n"
        "/screenshot — скриншот\n"
        "/webcam — снимок с камеры\n"
        "/listen [N] — запись звука (по умолч. 30 сек)"
    )


@dp.message(Command("cancel"))
async def cmd_cancel(m: types.Message, state: FSMContext):
    await state.clear()
    await m.answer("❌ Отменено.")


@dp.message(Command("system"))
async def cmd_system(m: types.Message):
    await m.answer(sys_info())


@dp.message(Command("trash"))
async def cmd_trash(m: types.Message):
    await show_trash(m.chat.id, m)


@dp.message(Command("bookmarks"))
async def cmd_bm(m: types.Message):
    await show_bookmarks(m.chat.id, m)


@dp.message(Command("history"))
async def cmd_hist(m: types.Message):
    await show_history(m.chat.id, m)


@dp.message(Command("undo"))
async def cmd_undo(m: types.Message):
    await do_undo(m.chat.id, m)


@dp.message(Command("pass"))
async def cmd_pass(m: types.Message):
    try:
        n = int((m.text.split() + ["16"])[1])
    except Exception:
        n = 16
    n = max(8, min(n, 128))
    await m.answer(t(m.chat.id, "pass_result", p=gen_password(n)))


@dp.message(Command("qr"))
async def cmd_qr(m: types.Message):
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        await m.answer(t(m.chat.id, "qr_prompt"))
        return
    data = make_qr(parts[1])
    if not data:
        await m.answer("❌ <code>pip install qrcode[pil]</code>")
        return
    await m.answer_photo(BufferedInputFile(data, filename="qr.png"))


@dp.message(Command("ping"))
async def cmd_ping(m: types.Message):
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        await m.answer(t(m.chat.id, "ping_prompt"))
        return
    await do_ping(m.chat.id, parts[1].strip())


@dp.message(Command("sh"))
async def cmd_sh(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        await m.answer("🚫 Только админ.")
        return
    parts = m.text.split(maxsplit=1)
    if len(parts) < 2:
        await m.answer(t(m.chat.id, "shell_prompt"))
        return
    await do_shell(m.chat.id, parts[1])


@dp.message(Command("screenshot"))
async def cmd_screenshot(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        await m.answer("🚫")
        return
    await m.answer("📸 Делаю скриншот…")
    data = take_screenshot()
    if not data:
        await m.answer(
            "❌ Не удалось.\n"
            "Для Wayland GNOME установите: <code>sudo apt install xdg-desktop-portal-gnome python3-dbus python3-gi</code>\n"
            "Для X11: <code>sudo apt install scrot imagemagick</code>"
        )
        return
    await m.answer_photo(BufferedInputFile(data, filename="screen.png"))


@dp.message(Command("webcam"))
async def cmd_webcam(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        await m.answer("🚫")
        return
    await m.answer("📷 Снимаю…")
    data = capture_webcam()
    if not data:
        await m.answer("❌ Камера недоступна. Установите: <code>sudo apt install ffmpeg fswebcam</code>")
        return
    await m.answer_photo(BufferedInputFile(data, filename="webcam.jpg"))


@dp.message(Command("listen"))
async def cmd_listen(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        await m.answer("🚫")
        return
    parts = m.text.split()
    dur = 30
    if len(parts) > 1:
        try:
            dur = int(parts[1])
        except ValueError:
            pass
    dur = max(1, min(dur, 300))
    await m.answer(f"🎤 Записываю {dur} сек…")
    data = record_audio(dur)
    if not data:
        await m.answer("❌ Микрофон недоступен. Установите: <code>sudo apt install ffmpeg alsa-utils</code>")
        return
    await m.answer_voice(BufferedInputFile(data, filename="rec.wav"))


# ==================== CALLBACK: НАВИГАЦИЯ ====================
@dp.callback_query(F.data == "return_to_menu")
async def cb_menu(c: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await edit_msg(c.message, t(c.message.chat.id, "welcome"),
                   reply_markup=main_menu(c.message.chat.id))


@dp.callback_query(F.data == "ignore")
async def cb_ignore(c: types.CallbackQuery):
    await c.answer()


@dp.callback_query(F.data == "up")
async def cb_up(c: types.CallbackQuery):
    cid = c.message.chat.id
    if cid in navigation_history and len(navigation_history[cid]) > 1:
        navigation_history[cid].pop()
        await show_dir(cid, navigation_history[cid][-1])


@dp.callback_query(F.data == "back")
async def cb_back(c: types.CallbackQuery):
    await cb_up(c)


@dp.callback_query(F.data.startswith("pg_"))
async def cb_pg(c: types.CallbackQuery):
    try:
        p = int(c.data.split("_", 1)[1])
    except ValueError:
        return
    cid = c.message.chat.id
    if cid in navigation_history:
        await show_dir(cid, navigation_history[cid][-1], p)


@dp.callback_query(F.data == "view_files")
async def cb_view(c: types.CallbackQuery):
    await show_dir(c.message.chat.id, ROOT_DIRECTORY)


# ==================== ВЫБОР ФАЙЛА ====================
@dp.callback_query(F.data.startswith("sel_"))
async def cb_sel(c: types.CallbackQuery):
    cid = c.message.chat.id
    idx = c.data.split("_", 1)[1]
    path = file_paths.get(cid, {}).get(idx)
    if not path:
        await c.answer("❌")
        return
    if os.path.isdir(path):
        await show_dir(cid, path)
        return

    kb = InlineKeyboardBuilder()
    if is_text(path) and size_ok(path, 5):
        kb.button(text=t(cid, "view"), callback_data=f"f_view_{idx}")
    if path.lower().endswith((".zip", ".tar", ".gz", ".tgz", ".bz2", ".xz")):
        kb.button(text=t(cid, "unzip"), callback_data=f"f_unzip_{idx}")
    kb.button(text=t(cid, "send"), callback_data=f"f_send_{idx}")
    kb.button(text=t(cid, "as_text"), callback_data=f"f_txt_{idx}")
    kb.button(text=t(cid, "meta"), callback_data=f"f_meta_{idx}")
    kb.button(text=t(cid, "hash"), callback_data=f"f_hash_{idx}")
    kb.button(text=t(cid, "edit"), callback_data=f"f_edit_{idx}")
    kb.button(text="☑️ Выбрать", callback_data=f"f_mark_{idx}")
    kb.button(text=t(cid, "delete"), callback_data=f"f_del_{idx}")
    kb.button(text=t(cid, "back"), callback_data="back_list")
    kb.adjust(2)

    size = human_size(os.path.getsize(path)) if os.path.exists(path) else "?"
    text = f"📄 <b>{os.path.basename(path)}</b>\n<i>{size}</i>\n<code>{path}</code>"
    await edit_msg(c.message, text, reply_markup=kb.as_markup())


@dp.callback_query(F.data == "back_list")
async def cb_back_list(c: types.CallbackQuery):
    cid = c.message.chat.id
    if cid in navigation_history:
        await show_dir(cid, navigation_history[cid][-1])


@dp.callback_query(F.data.startswith("f_mark_"))
async def cb_mark(c: types.CallbackQuery):
    cid = c.message.chat.id
    idx = c.data.split("_")[2]
    path = file_paths.get(cid, {}).get(idx)
    if not path:
        return
    if cid not in mass_selection:
        mass_selection[cid] = set()
    if path in mass_selection[cid]:
        mass_selection[cid].discard(path)
        await c.answer("➖")
    else:
        mass_selection[cid].add(path)
        await c.answer("➕")
    await show_dir(cid, navigation_history[cid][-1])


@dp.callback_query(F.data.startswith("f_send_"))
async def cb_send(c: types.CallbackQuery):
    cid = c.message.chat.id
    idx = c.data.split("_")[2]
    path = file_paths.get(cid, {}).get(idx)
    if not path or not os.path.exists(path):
        await c.answer("❌", show_alert=True)
        return
    if not size_ok(path):
        await c.answer(t(cid, "file_too_big", mb=MAX_FILE_MB), show_alert=True)
        return
    try:
        f = FSInputFile(path)
        lower = path.lower()
        if lower.endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")):
            await bot.send_photo(cid, f)
        elif lower.endswith((".mp3", ".wav", ".ogg", ".flac", ".m4a")):
            await bot.send_audio(cid, f)
        elif lower.endswith((".mp4", ".mov", ".avi", ".mkv", ".flv", ".webm")):
            await bot.send_video(cid, f)
        else:
            await bot.send_document(cid, f)
    except Exception as e:
        await bot.send_message(cid, t(cid, "err", e=e))


@dp.callback_query(F.data.startswith("f_view_"))
async def cb_view_file(c: types.CallbackQuery):
    cid = c.message.chat.id
    idx = c.data.split("_")[2]
    path = file_paths.get(cid, {}).get(idx)
    if not path or not is_text(path):
        await c.answer(t(cid, "no_text"), show_alert=True)
        return
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = []
            for _ in range(TEXT_PREVIEW_LINES):
                line = f.readline()
                if not line:
                    break
                lines.append(line.rstrip())
        content = "\n".join(lines)[:3500]
        await c.message.answer(f"📄 <code>{os.path.basename(path)}</code>\n<pre>{content}</pre>")
    except Exception as e:
        await c.message.answer(t(cid, "err", e=e))


@dp.callback_query(F.data.startswith("f_txt_"))
async def cb_as_text(c: types.CallbackQuery):
    cid = c.message.chat.id
    idx = c.data.split("_")[2]
    path = file_paths.get(cid, {}).get(idx)
    if not path or not is_text(path) or not size_ok(path, 5):
        await c.answer(t(cid, "no_text"), show_alert=True)
        return
    try:
        data = open(path, "rb").read()
        await bot.send_document(
            cid,
            BufferedInputFile(data, filename=os.path.basename(path) + ".txt"),
            caption=f"📝 <code>{path}</code>",
        )
    except Exception as e:
        await bot.send_message(cid, t(cid, "err", e=e))


@dp.callback_query(F.data.startswith("f_meta_"))
async def cb_meta(c: types.CallbackQuery):
    cid = c.message.chat.id
    idx = c.data.split("_")[2]
    path = file_paths.get(cid, {}).get(idx)
    if not path:
        return
    await c.message.answer(get_meta(path))


@dp.callback_query(F.data.startswith("f_hash_"))
async def cb_hash(c: types.CallbackQuery):
    cid = c.message.chat.id
    idx = c.data.split("_")[2]
    path = file_paths.get(cid, {}).get(idx)
    if not path or not size_ok(path, 500):
        await c.answer("❌ Файл большой/нет", show_alert=True)
        return
    await c.message.answer("⏳ Считаю хеши…")
    await c.message.answer(calc_hashes(path))


@dp.callback_query(F.data.startswith("f_edit_"))
async def cb_edit(c: types.CallbackQuery, state: FSMContext):
    cid = c.message.chat.id
    idx = c.data.split("_")[2]
    path = file_paths.get(cid, {}).get(idx)
    if not path or not is_text(path) or not size_ok(path, 1):
        await c.answer(t(cid, "no_text"), show_alert=True)
        return
    try:
        content = open(path, "r", encoding="utf-8", errors="replace").read(3500)
        current_action[cid] = {"edit": path}
        await c.message.answer(t(cid, "edit_prompt", c=content))
        await state.set_state(S.EDIT_FILE_NEW)
    except Exception as e:
        await c.message.answer(t(cid, "err", e=e))


@dp.message(StateFilter(S.EDIT_FILE_NEW))
async def process_edit(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    path = current_action.get(cid, {}).get("edit")
    if not path:
        await state.clear()
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(m.text)
        await m.answer(t(cid, "edit_done"))
        push_history(cid, "edit", {"path": path})
    except Exception as e:
        await m.answer(t(cid, "err", e=e))
    await state.clear()


@dp.callback_query(F.data.startswith("f_del_"))
async def cb_del(c: types.CallbackQuery):
    cid = c.message.chat.id
    idx = c.data.split("_")[2]
    path = file_paths.get(cid, {}).get(idx)
    if not path:
        return
    current_action[cid] = {"del": path}
    kb = InlineKeyboardBuilder()
    kb.button(text=t(cid, "yes"), callback_data="del_ok")
    kb.button(text=t(cid, "no"), callback_data="back_list")
    kb.adjust(2)
    await edit_msg(c.message, t(cid, "confirm_delete", p=path), reply_markup=kb.as_markup())


@dp.callback_query(F.data == "del_ok")
async def cb_del_ok(c: types.CallbackQuery):
    cid = c.message.chat.id
    path = current_action.get(cid, {}).get("del")
    if not path or not os.path.exists(path):
        await c.message.answer(t(cid, "file_not_found"))
        return
    try:
        trashed = trash_move(path)
        push_history(cid, "delete", {"path": path, "trash": trashed})
        push_undo(cid, {"action": "restore", "path": trashed})
        await edit_msg(c.message, t(cid, "ok_delete", p=path))
    except Exception as e:
        await edit_msg(c.message, t(cid, "err", e=e))


@dp.callback_query(F.data.startswith("f_unzip_"))
async def cb_unzip(c: types.CallbackQuery):
    cid = c.message.chat.id
    idx = c.data.split("_")[2]
    path = file_paths.get(cid, {}).get(idx)
    if not path:
        return
    dest = os.path.join(os.path.dirname(path),
                        os.path.splitext(os.path.basename(path))[0] + "_unpacked")
    try:
        os.makedirs(dest, exist_ok=True)
        lower = path.lower()
        if lower.endswith(".zip"):
            with zipfile.ZipFile(path) as z:
                z.extractall(dest)
        elif lower.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")):
            with tarfile.open(path, "r:*") as tf:
                tf.extractall(dest)
        else:
            await c.message.answer("❌ Формат не поддерживается.")
            return
        await c.message.answer(t(cid, "ok_unzip", d=dest))
        push_history(cid, "unzip", {"path": path, "to": dest})
    except Exception as e:
        await c.message.answer(t(cid, "err", e=e))


# ==================== МАССОВЫЕ ДЕЙСТВИЯ ====================
@dp.callback_query(F.data == "mass_menu")
async def cb_mass(c: types.CallbackQuery):
    cid = c.message.chat.id
    n = len(mass_selection.get(cid, set()))
    kb = InlineKeyboardBuilder()
    kb.button(text=t(cid, "mass_zip"), callback_data="mass_zip")
    kb.button(text=t(cid, "mass_delete"), callback_data="mass_del")
    kb.button(text=t(cid, "mass_clear"), callback_data="mass_clear")
    kb.button(text=t(cid, "back"), callback_data="back_list")
    kb.adjust(2)
    await c.message.answer(f"☑️ {t(cid, 'mass_selected', n=n)}\n{t(cid, 'mass_actions')}",
                           reply_markup=kb.as_markup())


@dp.callback_query(F.data == "mass_clear")
async def cb_mass_clear(c: types.CallbackQuery):
    cid = c.message.chat.id
    mass_selection[cid] = set()
    await c.message.answer("✅ Снято.")
    await show_dir(cid, navigation_history[cid][-1])


@dp.callback_query(F.data == "mass_del")
async def cb_mass_del(c: types.CallbackQuery):
    cid = c.message.chat.id
    items = list(mass_selection.get(cid, set()))
    if not items:
        await c.answer("Пусто", show_alert=True)
        return
    ok = 0
    for p in items:
        try:
            trashed = trash_move(p)
            push_undo(cid, {"action": "restore", "path": trashed})
            ok += 1
        except Exception:
            pass
    mass_selection[cid] = set()
    await c.message.answer(f"✅ Удалено: {ok}/{len(items)}")
    await show_dir(cid, navigation_history[cid][-1])


@dp.callback_query(F.data == "mass_zip")
async def cb_mass_zip(c: types.CallbackQuery):
    cid = c.message.chat.id
    items = list(mass_selection.get(cid, set()))
    if not items:
        await c.answer("Пусто", show_alert=True)
        return
    out = os.path.join(SCRIPT_DIR, f"batch_{int(time.time())}.zip")
    try:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for p in items:
                if os.path.isfile(p):
                    z.write(p, arcname=os.path.basename(p))
                elif os.path.isdir(p):
                    for root, dirs, files in os.walk(p):
                        for f in files:
                            full = os.path.join(root, f)
                            z.write(full, arcname=os.path.relpath(full, os.path.dirname(p)))
        if size_ok(out):
            await bot.send_document(cid, FSInputFile(out))
        else:
            await c.message.answer(t(cid, "file_too_big", mb=MAX_FILE_MB))
        os.remove(out)
    except Exception as e:
        await c.message.answer(t(cid, "err", e=e))


# ==================== URL DOWNLOAD ====================
@dp.callback_query(F.data == "url_dl")
async def cb_url(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer(t(c.message.chat.id, "url_prompt"))
    await state.set_state(S.URL_DOWNLOAD)


@dp.message(StateFilter(S.URL_DOWNLOAD))
async def process_url(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    dest = navigation_history[cid][-1] if cid in navigation_history else ROOT_DIRECTORY
    await url_download(cid, m.text.strip(), dest)
    await state.clear()


# ==================== ДЕЙСТВИЯ ====================
@dp.callback_query(F.data == "folders_menu")
async def cb_folders(c: types.CallbackQuery):
    cid = c.message.chat.id
    kb = InlineKeyboardBuilder()
    for txt, cb in [
        ("create_folder", "a_create"), ("move", "a_move"),
        ("copy", "a_copy"), ("delete", "a_del"),
        ("rename", "a_ren"), ("zip", "a_zip"),
        ("search_ext", "a_sext"), ("search_name", "a_sname"),
        ("search_regex", "a_sre"), ("search_grep", "a_grep"),
        ("duplicates", "a_dups"), ("analyze", "a_an"),
        ("mass_rename", "a_mren"), ("diff", "a_diff"),
        ("trash", "a_trash"),
    ]:
        kb.button(text=t(cid, txt), callback_data=cb)
    kb.button(text=t(cid, "menu"), callback_data="return_to_menu")
    kb.adjust(2)
    await edit_msg(c.message, f"📁 <b>{t(cid, 'folders')}</b>", reply_markup=kb.as_markup())


@dp.callback_query(F.data == "a_del")
async def a_del(c: types.CallbackQuery, state: FSMContext):
    await bot.send_message(c.message.chat.id, t(c.message.chat.id, "enter_path", ex=get_examples()))
    await state.set_state(S.DELETE)


@dp.message(StateFilter(S.DELETE))
async def p_del(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    p = m.text.strip()
    if not os.path.exists(p):
        await m.answer(t(cid, "invalid_path"))
        await state.clear()
        return
    if not is_safe_path(p):
        await m.answer("🚫 Вне зоны.")
        await state.clear()
        return
    current_action[cid] = {"del": p}
    kb = InlineKeyboardBuilder()
    kb.button(text=t(cid, "yes"), callback_data="del_ok")
    kb.button(text=t(cid, "no"), callback_data="return_to_menu")
    kb.adjust(2)
    await m.answer(t(cid, "confirm_delete", p=p), reply_markup=kb.as_markup())
    await state.clear()


@dp.callback_query(F.data == "a_ren")
async def a_ren(c: types.CallbackQuery, state: FSMContext):
    await bot.send_message(c.message.chat.id, t(c.message.chat.id, "enter_path", ex=get_examples()))
    await state.set_state(S.RENAME)


@dp.message(StateFilter(S.RENAME))
async def p_ren1(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    p = m.text.strip()
    if not os.path.exists(p):
        await m.answer(t(cid, "invalid_path"))
        await state.clear()
        return
    current_action[cid] = {"ren": p}
    await m.answer(t(cid, "enter_new_name"))
    await state.set_state(S.RENAME_NEW_NAME)


@dp.message(StateFilter(S.RENAME_NEW_NAME))
async def p_ren2(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    new = m.text.strip()
    old = current_action.get(cid, {}).get("ren")
    if not old:
        await state.clear()
        return
    dest = os.path.join(os.path.dirname(old), new)
    try:
        os.rename(old, dest)
        await m.answer(t(cid, "ok_rename", n=dest))
        push_history(cid, "rename", {"from": old, "to": dest})
        push_undo(cid, {"action": "rename", "from": dest, "to": old})
    except Exception as e:
        await m.answer(t(cid, "err", e=e))
    await state.clear()


@dp.callback_query(F.data == "a_create")
async def a_create(c: types.CallbackQuery, state: FSMContext):
    await bot.send_message(c.message.chat.id, t(c.message.chat.id, "enter_path", ex=get_examples()))
    await state.set_state(S.CREATE_FOLDER)


@dp.message(StateFilter(S.CREATE_FOLDER))
async def p_create(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    try:
        os.makedirs(m.text.strip(), exist_ok=True)
        await m.answer(t(cid, "ok_create", p=m.text.strip()))
    except Exception as e:
        await m.answer(t(cid, "err", e=e))
    await state.clear()


@dp.callback_query(F.data == "a_move")
async def a_move(c: types.CallbackQuery, state: FSMContext):
    await bot.send_message(c.message.chat.id, t(c.message.chat.id, "enter_path", ex=get_examples()))
    await state.set_state(S.MOVE)


@dp.message(StateFilter(S.MOVE))
async def p_move1(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    p = m.text.strip()
    if not os.path.exists(p):
        await m.answer(t(cid, "invalid_path"))
        await state.clear()
        return
    current_action[cid] = {"mv": p}
    await m.answer(t(cid, "enter_dest"))
    await state.set_state(S.MOVE_DEST)


@dp.message(StateFilter(S.MOVE_DEST))
async def p_move2(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    d = m.text.strip()
    s = current_action.get(cid, {}).get("mv")
    try:
        shutil.move(s, d)
        await m.answer(t(cid, "ok_move", d=d))
        push_history(cid, "move", {"from": s, "to": d})
        push_undo(cid, {"action": "move", "from": d, "to": s})
    except Exception as e:
        await m.answer(t(cid, "err", e=e))
    await state.clear()


@dp.callback_query(F.data == "a_copy")
async def a_copy(c: types.CallbackQuery, state: FSMContext):
    await bot.send_message(c.message.chat.id, t(c.message.chat.id, "enter_path", ex=get_examples()))
    await state.set_state(S.COPY)


@dp.message(StateFilter(S.COPY))
async def p_copy1(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    p = m.text.strip()
    if not os.path.exists(p):
        await m.answer(t(cid, "invalid_path"))
        await state.clear()
        return
    current_action[cid] = {"cp": p}
    await m.answer(t(cid, "enter_dest"))
    await state.set_state(S.COPY_DEST)


@dp.message(StateFilter(S.COPY_DEST))
async def p_copy2(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    d = m.text.strip()
    s = current_action.get(cid, {}).get("cp")
    try:
        if os.path.isdir(s):
            shutil.copytree(s, os.path.join(d, os.path.basename(s.rstrip(os.sep))))
        else:
            shutil.copy2(s, d)
        await m.answer(t(cid, "ok_copy", d=d))
        push_history(cid, "copy", {"from": s, "to": d})
    except Exception as e:
        await m.answer(t(cid, "err", e=e))
    await state.clear()


@dp.callback_query(F.data == "a_zip")
async def a_zip(c: types.CallbackQuery, state: FSMContext):
    await bot.send_message(c.message.chat.id, t(c.message.chat.id, "enter_path", ex=get_examples()))
    await state.set_state(S.ZIP)


@dp.message(StateFilter(S.ZIP))
async def p_zip(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    p = m.text.strip()
    if not os.path.exists(p):
        await m.answer(t(cid, "invalid_path"))
        await state.clear()
        return
    try:
        base = os.path.basename(p.rstrip(os.sep)) or "archive"
        out = os.path.join(SCRIPT_DIR, base)
        arch = shutil.make_archive(out, "zip", p)
        if size_ok(arch):
            await bot.send_document(cid, FSInputFile(arch))
            os.remove(arch)
        else:
            await m.answer(t(cid, "file_too_big", mb=MAX_FILE_MB))
            os.remove(arch)
    except Exception as e:
        await m.answer(t(cid, "err", e=e))
    await state.clear()


@dp.callback_query(F.data == "a_sext")
async def a_sext(c: types.CallbackQuery, state: FSMContext):
    await bot.send_message(c.message.chat.id, "Расширение (.txt):")
    await state.set_state(S.SEARCH_EXT)


@dp.message(StateFilter(S.SEARCH_EXT))
async def p_sext(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    ext = m.text.strip().lower()
    if not ext.startswith("."):
        ext = "." + ext
    await m.answer(t(cid, "search_started"))
    found = search_files(ROOT_DIRECTORY, ext=ext)
    if not found:
        await m.answer(t(cid, "file_not_found"))
    else:
        await m.answer(t(cid, "search_found", n=len(found)))
        for fp in found[:15]:
            try:
                if not size_ok(fp):
                    continue
                await bot.send_document(ADMIN_ID, FSInputFile(fp), caption=f"<code>{fp}</code>")
            except Exception:
                continue
    await state.clear()


@dp.callback_query(F.data == "a_sname")
async def a_sname(c: types.CallbackQuery, state: FSMContext):
    await bot.send_message(c.message.chat.id, "Часть имени:")
    await state.set_state(S.SEARCH_NAME)


@dp.message(StateFilter(S.SEARCH_NAME))
async def p_sname(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    sub = m.text.strip()
    if len(sub) < 2:
        await m.answer("❌ Коротко.")
        await state.clear()
        return
    found = search_files(ROOT_DIRECTORY, name_sub=sub)
    if not found:
        await m.answer(t(cid, "file_not_found"))
    else:
        lines = "\n".join(f"<code>{p}</code>" for p in found[:30])
        await m.answer(t(cid, "search_found", n=len(found)) + "\n\n" + lines)
    await state.clear()


@dp.callback_query(F.data == "a_sre")
async def a_sre(c: types.CallbackQuery, state: FSMContext):
    await bot.send_message(c.message.chat.id, t(c.message.chat.id, "regex_prompt"))
    await state.set_state(S.SEARCH_REGEX)


@dp.message(StateFilter(S.SEARCH_REGEX))
async def p_sre(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    try:
        re.compile(m.text)
    except re.error as e:
        await m.answer(f"❌ Regex: {e}")
        await state.clear()
        return
    found = search_files(ROOT_DIRECTORY, regex=m.text)
    if not found:
        await m.answer(t(cid, "file_not_found"))
    else:
        lines = "\n".join(f"<code>{p}</code>" for p in found[:30])
        await m.answer(t(cid, "search_found", n=len(found)) + "\n\n" + lines)
    await state.clear()


@dp.callback_query(F.data == "a_grep")
async def a_grep(c: types.CallbackQuery, state: FSMContext):
    await bot.send_message(c.message.chat.id, t(c.message.chat.id, "grep_prompt"))
    await state.set_state(S.SEARCH_GREP)


@dp.message(StateFilter(S.SEARCH_GREP))
async def p_grep(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    needle = m.text.strip()
    if len(needle) < 2:
        await m.answer("❌ Коротко.")
        await state.clear()
        return
    await m.answer(t(cid, "search_started"))
    hits = grep_files(ROOT_DIRECTORY, needle)
    if not hits:
        await m.answer("❌ Ничего не найдено.")
    else:
        text = f"✅ Совпадений: {len(hits)}\n\n"
        for full, line, content in hits[:20]:
            text += f"<code>{full}:{line}</code>\n{content}\n\n"
        await m.answer(text[:3900])
    await state.clear()


@dp.callback_query(F.data == "a_dups")
async def a_dups(c: types.CallbackQuery):
    cid = c.message.chat.id
    await c.message.answer("🧬 Ищу дубликаты…")
    dups = find_dups(ROOT_DIRECTORY)
    if not dups:
        await c.message.answer("✅ Нет дубликатов.")
        return
    text = f"🧬 <b>{len(dups)} групп</b>\n\n"
    for i, (h, ps) in enumerate(list(dups.items())[:5]):
        text += f"<b>#{i + 1}</b> ({len(ps)}):\n"
        for p in ps[:3]:
            text += f"  • <code>{p}</code>\n"
        if len(ps) > 3:
            text += f"  …+{len(ps) - 3}\n"
        text += "\n"
    if len(dups) > 5:
        text += f"…+{len(dups) - 5} групп."
    await c.message.answer(text[:4000])


@dp.callback_query(F.data == "a_an")
async def a_an(c: types.CallbackQuery):
    cid = c.message.chat.id
    await c.message.answer("📊 Анализирую…")
    info = analyze(ROOT_DIRECTORY)
    text = (
        f"📊 <b>Анализ</b>\n"
        f"📁 Файлов: {info['count']}\n"
        f"💾 Размер: {human_size(info['total'])}\n\n"
        f"<b>Топ-10:</b>\n"
    )
    for p, s in info["top"]:
        text += f"  {human_size(s)} — <code>{p[-60:]}</code>\n"
    text += "\n<b>По расширениям:</b>\n"
    for ext, s in info["by_ext"]:
        text += f"  {ext}: {human_size(s)}\n"
    await c.message.answer(text[:4000])


@dp.callback_query(F.data == "a_mren")
async def a_mren(c: types.CallbackQuery, state: FSMContext):
    await bot.send_message(c.message.chat.id, "Путь к папке:")
    await state.set_state(S.MASS_RENAME)


@dp.message(StateFilter(S.MASS_RENAME))
async def p_mren(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    directory = m.text.strip()
    if not os.path.isdir(directory):
        await m.answer(t(cid, "invalid_path"))
        await state.clear()
        return
    try:
        files = [f for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
        files.sort()
        n = 0
        for f in files:
            ext = os.path.splitext(f)[1]
            base = os.path.splitext(f)[0]
            new_name = f"{n:03d}_{base}{ext}"
            src = os.path.join(directory, f)
            dst = os.path.join(directory, new_name)
            if src != dst:
                os.rename(src, dst)
            n += 1
        await m.answer(f"✅ Переименовано: {n}")
        push_history(cid, "mass_rename", {"dir": directory, "count": n})
    except Exception as e:
        await m.answer(t(cid, "err", e=e))
    await state.clear()


@dp.callback_query(F.data == "a_diff")
async def a_diff(c: types.CallbackQuery, state: FSMContext):
    await bot.send_message(c.message.chat.id, t(c.message.chat.id, "diff_prompt_a"))
    await state.set_state(S.DIFF_A)


@dp.message(StateFilter(S.DIFF_A))
async def p_diff_a(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    if not os.path.exists(m.text.strip()):
        await m.answer(t(cid, "invalid_path"))
        await state.clear()
        return
    current_action[cid] = {"diff_a": m.text.strip()}
    await m.answer(t(cid, "diff_prompt_b"))
    await state.set_state(S.DIFF_B)


@dp.message(StateFilter(S.DIFF_B))
async def p_diff_b(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    b = m.text.strip()
    a = current_action.get(cid, {}).get("diff_a")
    if not os.path.exists(b):
        await m.answer(t(cid, "invalid_path"))
        await state.clear()
        return
    await m.answer(diff_files(a, b))
    await state.clear()


@dp.callback_query(F.data == "a_trash")
async def a_trash(c: types.CallbackQuery):
    await show_trash(c.message.chat.id, c.message)


async def show_trash(cid, message):
    items = sorted(os.listdir(TRASH_DIR), reverse=True)
    if not items:
        await message.answer(t(cid, "trash_empty"))
        return
    kb = InlineKeyboardBuilder()
    for item in items[:15]:
        kb.button(text=item[:40], callback_data=f"tr_r_{item[:30]}")
    kb.button(text="🗑 Очистить", callback_data="tr_clear")
    kb.button(text=t(cid, "menu"), callback_data="return_to_menu")
    kb.adjust(1)
    await message.answer(f"♻️ <b>Корзина ({len(items)})</b>", reply_markup=kb.as_markup())


@dp.callback_query(F.data.startswith("tr_r_"))
async def tr_restore(c: types.CallbackQuery):
    cid = c.message.chat.id
    name = c.data[5:]
    src = None
    for item in os.listdir(TRASH_DIR):
        if item.startswith(name):
            src = os.path.join(TRASH_DIR, item)
            break
    if not src:
        await c.answer("❌", show_alert=True)
        return
    original = name.split("_", 2)[-1]
    dest = os.path.join(ROOT_DIRECTORY, original)
    try:
        shutil.move(src, dest)
        await c.message.answer(t(cid, "trash_restored", p=dest))
    except Exception as e:
        await c.message.answer(t(cid, "err", e=e))


@dp.callback_query(F.data == "tr_clear")
async def tr_clear(c: types.CallbackQuery):
    cid = c.message.chat.id
    try:
        for item in os.listdir(TRASH_DIR):
            p = os.path.join(TRASH_DIR, item)
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
        await c.message.answer(t(cid, "trash_cleared"))
    except Exception as e:
        await c.message.answer(t(cid, "err", e=e))


# ==================== UPLOAD ====================
@dp.callback_query(F.data == "upload_here")
async def up_here(c: types.CallbackQuery, state: FSMContext):
    cid = c.message.chat.id
    d = navigation_history[cid][-1] if cid in navigation_history else ROOT_DIRECTORY
    upload_context[cid] = d
    await c.message.answer(t(cid, "upload_prompt", d=d))
    await state.set_state(S.UPLOAD)


@dp.message(StateFilter(S.UPLOAD), F.document | F.photo | F.video | F.audio | F.voice)
async def proc_upload(m: types.Message, state: FSMContext):
    cid = m.chat.id
    d = upload_context.get(cid, ROOT_DIRECTORY)

    if m.document:
        fid, name = m.document.file_id, m.document.file_name or "file.bin"
    elif m.photo:
        fid, name = m.photo[-1].file_id, f"photo_{int(time.time())}.jpg"
    elif m.video:
        fid, name = m.video.file_id, m.video.file_name or f"video_{int(time.time())}.mp4"
    elif m.audio:
        fid, name = m.audio.file_id, m.audio.file_name or f"audio_{int(time.time())}.mp3"
    elif m.voice:
        fid, name = m.voice.file_id, f"voice_{int(time.time())}.ogg"
    else:
        await m.answer("❌ Тип не поддержан.")
        return

    try:
        f = await bot.get_file(fid)
        if f.file_size and f.file_size > MAX_FILE_MB * 1024 * 1024:
            await m.answer(t(cid, "file_too_big", mb=MAX_FILE_MB))
            return
        dest = os.path.join(d, name)
        base, ext = os.path.splitext(dest)
        i = 1
        while os.path.exists(dest):
            dest = f"{base}_{i}{ext}"
            i += 1
        await bot.download_file(f.file_path, dest)
        await m.answer(t(cid, "ok_upload", p=dest))
        push_history(cid, "upload", {"path": dest})
        push_undo(cid, {"action": "delete", "path": dest})
    except Exception as e:
        await m.answer(t(cid, "err", e=e))
    await state.clear()


# ==================== СИСТЕМА (callback) ====================
@dp.callback_query(F.data == "system")
async def sys_menu(c: types.CallbackQuery):
    cid = c.message.chat.id
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Инфо", callback_data="sys_info")
    kb.button(text="🔥 CPU", callback_data="sys_cpu")
    kb.button(text="🧠 RAM", callback_data="sys_ram")
    kb.button(text="🔌 Порты", callback_data="sys_ports")
    kb.button(text="🌐 Соединения", callback_data="sys_conns")
    kb.button(text="📡 Ping", callback_data="sys_ping")
    kb.button(text="🛑 Kill", callback_data="sys_kill")
    kb.button(text="🖥 Shell", callback_data="sys_shell")
    kb.button(text="📸 Скриншот", callback_data="sys_shot")
    kb.button(text="📷 Веб-камера", callback_data="sys_cam")
    kb.button(text="🎤 Микрофон", callback_data="sys_audio")
    kb.button(text="⚡ Питание", callback_data="sys_power")
    kb.button(text=t(cid, "menu"), callback_data="return_to_menu")
    kb.adjust(2)
    await edit_msg(c.message, "💻 <b>Система</b>", reply_markup=kb.as_markup())


@dp.callback_query(F.data == "sys_info")
async def cb_sys_info(c: types.CallbackQuery):
    await c.message.answer(sys_info())


@dp.callback_query(F.data == "sys_cpu")
async def cb_sys_cpu(c: types.CallbackQuery):
    await c.message.answer(top_procs("cpu"))


@dp.callback_query(F.data == "sys_ram")
async def cb_sys_ram(c: types.CallbackQuery):
    await c.message.answer(top_procs("ram"))


@dp.callback_query(F.data == "sys_ports")
async def cb_sys_ports(c: types.CallbackQuery):
    await c.message.answer(get_ports())


@dp.callback_query(F.data == "sys_conns")
async def cb_sys_conns(c: types.CallbackQuery):
    await c.message.answer(get_connections())


@dp.callback_query(F.data == "sys_ping")
async def cb_sys_ping(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer(t(c.message.chat.id, "ping_prompt"))
    await state.set_state(S.PING)


@dp.message(StateFilter(S.PING))
async def p_ping(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    await do_ping(m.chat.id, m.text.strip())
    await state.clear()


@dp.callback_query(F.data == "sys_kill")
async def cb_sys_kill(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer(t(c.message.chat.id, "kill_prompt"))
    await state.set_state(S.KILL_PID)


@dp.message(StateFilter(S.KILL_PID))
async def p_kill(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    try:
        pid = int(m.text.strip())
        if not PSUTIL:
            await m.answer("❌ psutil нет.")
            await state.clear()
            return
        p = psutil.Process(pid)
        p.terminate()
        try:
            p.wait(timeout=3)
        except psutil.TimeoutExpired:
            p.kill()
        await m.answer(t(cid, "kill_ok", pid=pid))
        push_history(cid, "kill", {"pid": pid})
    except Exception as e:
        await m.answer(t(cid, "kill_err", e=e))
    await state.clear()


@dp.callback_query(F.data == "sys_shell")
async def cb_sys_shell(c: types.CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID:
        await c.answer("🚫", show_alert=True)
        return
    await c.message.answer(t(c.message.chat.id, "shell_prompt"))
    await state.set_state(S.SHELL_CMD)


@dp.message(StateFilter(S.SHELL_CMD))
async def p_shell(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    if m.from_user.id != ADMIN_ID:
        await m.answer("🚫")
        await state.clear()
        return
    await do_shell(m.chat.id, m.text)
    await state.clear()


@dp.callback_query(F.data == "sys_shot")
async def cb_sys_shot(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await c.answer("🚫", show_alert=True)
        return
    await c.answer("📸")
    await c.message.answer("📸 Делаю скриншот…")
    data = take_screenshot()
    if not data:
        await c.message.answer(
            "❌ Не удалось.\n"
            "GNOME Wayland: <code>sudo apt install xdg-desktop-portal-gnome python3-dbus python3-gi</code>\n"
            "X11: <code>sudo apt install scrot imagemagick</code>"
        )
        return
    await bot.send_photo(c.message.chat.id, BufferedInputFile(data, filename="screen.png"))


@dp.callback_query(F.data == "sys_cam")
async def cb_sys_cam(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await c.answer("🚫", show_alert=True)
        return
    await c.answer("📷")
    await c.message.answer("📷 Снимаю…")
    data = capture_webcam()
    if not data:
        await c.message.answer("❌ Камера недоступна. Установите: <code>sudo apt install ffmpeg fswebcam</code>")
        return
    await bot.send_photo(c.message.chat.id, BufferedInputFile(data, filename="webcam.jpg"))


@dp.callback_query(F.data == "sys_audio")
async def cb_sys_audio(c: types.CallbackQuery, state: FSMContext):
    if c.from_user.id != ADMIN_ID:
        await c.answer("🚫", show_alert=True)
        return
    await c.message.answer("🎤 Сколько секунд записать? (1–300)\nОтправьте число. Или /cancel.")
    await state.set_state(S.AUDIO_DURATION)


@dp.message(StateFilter(S.AUDIO_DURATION))
async def p_audio_dur(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    if m.from_user.id != ADMIN_ID:
        await state.clear()
        return
    try:
        dur = int(m.text.strip())
        dur = max(1, min(dur, 300))
    except ValueError:
        await m.answer("❌ Число от 1 до 300.")
        await state.clear()
        return
    await m.answer(f"🎤 Записываю {dur} сек…")
    data = record_audio(dur)
    if not data:
        await m.answer("❌ Микрофон недоступен. Установите: <code>sudo apt install ffmpeg alsa-utils</code>")
        await state.clear()
        return
    await bot.send_voice(m.chat.id, BufferedInputFile(data, filename="rec.wav"))
    await state.clear()


@dp.callback_query(F.data == "sys_power")
async def cb_sys_power(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await c.answer("🚫", show_alert=True)
        return
    cid = c.message.chat.id
    kb = InlineKeyboardBuilder()
    kb.button(text="⏻ Выключить", callback_data="pw_shutdown")
    kb.button(text="🔄 Перезагрузить", callback_data="pw_reboot")
    kb.button(text="💤 Спящий режим", callback_data="pw_suspend")
    kb.button(text="🔒 Заблокировать", callback_data="pw_lock")
    kb.button(text=t(cid, "back"), callback_data="system")
    kb.adjust(2)
    await edit_msg(c.message,
                   "⚡ <b>Управление питанием</b>\n\n⚠️ Опасные действия — требуют подтверждения.",
                   reply_markup=kb.as_markup())


@dp.callback_query(F.data.startswith("pw_") & ~F.data.startswith("pw_ok_"))
async def cb_power_action(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await c.answer("🚫", show_alert=True)
        return
    action = c.data.split("_", 1)[1]
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да", callback_data=f"pw_ok_{action}")
    kb.button(text="❌ Отмена", callback_data="sys_power")
    kb.adjust(2)
    names = {
        "shutdown": "выключить ПК",
        "reboot": "перезагрузить ПК",
        "suspend": "ввести в спящий режим",
        "lock": "заблокировать экран",
    }
    await edit_msg(c.message,
                   f"⚠️ Точно <b>{names.get(action, action)}</b>?",
                   reply_markup=kb.as_markup())


@dp.callback_query(F.data.startswith("pw_ok_"))
async def cb_power_confirm(c: types.CallbackQuery):
    if c.from_user.id != ADMIN_ID:
        await c.answer("🚫", show_alert=True)
        return
    action = c.data.split("_", 2)[2]
    cid = c.message.chat.id
    await c.answer()
    await c.message.answer(f"⚡ Выполняю: <b>{action}</b>…")
    ok, msg = await do_power_action(action)
    try:
        await c.message.answer(msg)
    except Exception:
        pass
    push_history(cid, f"power_{action}", {})


# ==================== УТИЛИТЫ ====================
@dp.callback_query(F.data == "tools")
async def cb_tools(c: types.CallbackQuery):
    cid = c.message.chat.id
    kb = InlineKeyboardBuilder()
    kb.button(text="🔑 Пароль", callback_data="tool_pass")
    kb.button(text="📱 QR-код", callback_data="tool_qr")
    kb.button(text="🧾 Хеш файла", callback_data="tool_hash")
    kb.button(text="⏰ Напоминание", callback_data="tool_sched")
    kb.button(text=t(cid, "menu"), callback_data="return_to_menu")
    kb.adjust(2)
    await edit_msg(c.message, f"🛠 <b>{t(cid, 'tools')}</b>", reply_markup=kb.as_markup())


@dp.callback_query(F.data == "tool_pass")
async def cb_tool_pass(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer(t(c.message.chat.id, "pass_prompt"))
    await state.set_state(S.PASS_LEN)


@dp.message(StateFilter(S.PASS_LEN))
async def p_pass_len(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    try:
        n = int(m.text.strip())
        n = max(8, min(n, 128))
        await m.answer(t(cid, "pass_result", p=gen_password(n)))
    except ValueError:
        await m.answer("❌ Число.")
    await state.clear()


@dp.callback_query(F.data == "tool_qr")
async def cb_tool_qr(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer(t(c.message.chat.id, "qr_prompt"))
    await state.set_state(S.QR_TEXT)


@dp.message(StateFilter(S.QR_TEXT))
async def p_qr_text(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    data = make_qr(m.text)
    if not data:
        await m.answer("❌ <code>pip install qrcode[pil]</code>")
    else:
        await m.answer_photo(BufferedInputFile(data, filename="qr.png"))
    await state.clear()


@dp.callback_query(F.data == "tool_hash")
async def cb_tool_hash(c: types.CallbackQuery):
    await c.message.answer("🧾 Откройте файл и нажмите «Хеш».")


@dp.callback_query(F.data == "tool_sched")
async def cb_tool_sched(c: types.CallbackQuery, state: FSMContext):
    await c.message.answer(t(c.message.chat.id, "schedule_prompt"))
    await state.set_state(S.SCHEDULE_MIN)


@dp.message(StateFilter(S.SCHEDULE_MIN))
async def p_sched_min(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    try:
        mins = int(m.text.strip())
        if mins <= 0 or mins > 10080:
            raise ValueError
        current_action[cid] = {"sched_min": mins}
        await m.answer(t(cid, "schedule_text"))
        await state.set_state(S.SCHEDULE_TEXT)
    except ValueError:
        await m.answer("❌ 1–10080 минут.")
        await state.clear()


@dp.message(StateFilter(S.SCHEDULE_TEXT))
async def p_sched_text(m: types.Message, state: FSMContext):
    if m.text in ("/start", "/cancel"):
        await state.clear()
        return
    cid = m.chat.id
    mins = current_action.get(cid, {}).get("sched_min", 1)
    text = m.text
    await m.answer(t(cid, "schedule_ok", m=mins))

    async def reminder():
        await asyncio.sleep(mins * 60)
        try:
            await bot.send_message(cid, t(cid, "schedule_done", t=text))
        except Exception:
            pass

    asyncio.create_task(reminder())
    await state.clear()


# ==================== ГЕО ====================
async def get_ip():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get("https://api.ipify.org?format=json", timeout=10) as r:
                if r.status == 200:
                    return (await r.json())["ip"]
    except Exception:
        pass
    return None


async def get_geo(ip):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"http://ip-api.com/json/{ip}", timeout=10) as r:
                d = await r.json()
                return d if d.get("status") == "success" else None
    except Exception:
        return None


@dp.callback_query(F.data == "location")
async def cb_geo(c: types.CallbackQuery):
    cid = c.message.chat.id
    await c.answer()
    ip = await get_ip()
    if not ip:
        await c.message.answer("❌ Не удалось получить IP.")
        return
    info = await get_geo(ip)
    if not info:
        await c.message.answer("❌ Гео-сервис недоступен.")
        return
    await bot.send_location(cid, info["lat"], info["lon"])
    await c.message.answer(
        f"🌍 <b>{info.get('country')}, {info.get('city')}</b>\n"
        f"📍 IP: <code>{ip}</code>\n"
        f"📍 {info.get('regionName')}\n"
        f"📍 {info.get('isp')}"
    )


# ==================== ЗАКЛАДКИ ====================
@dp.callback_query(F.data == "bookmarks")
async def cb_bm(c: types.CallbackQuery):
    await show_bookmarks(c.message.chat.id, c.message)


async def show_bookmarks(cid, message):
    user_bms = BOOKMARKS.get(str(cid), {})
    if not user_bms:
        await message.answer(t(cid, "bookmarks_empty"))
        return
    kb = InlineKeyboardBuilder()
    for name in user_bms:
        kb.button(text=f"⭐ {name}", callback_data=f"bm_open_{name[:25]}")
    kb.button(text="🗑 Удалить все", callback_data="bm_clear")
    kb.button(text=t(cid, "menu"), callback_data="return_to_menu")
    kb.adjust(1)
    await message.answer("⭐ <b>Закладки</b>", reply_markup=kb.as_markup())


@dp.callback_query(F.data.startswith("bm_open_"))
async def cb_bm_open(c: types.CallbackQuery):
    cid = c.message.chat.id
    name = c.data[8:]
    user_bms = BOOKMARKS.get(str(cid), {})
    path = None
    for k, v in user_bms.items():
        if k.startswith(name):
            path = v
            break
    if not path or not os.path.isdir(path):
        await c.answer("❌", show_alert=True)
        return
    await show_dir(cid, path)


@dp.callback_query(F.data == "bm_clear")
async def cb_bm_clear(c: types.CallbackQuery):
    BOOKMARKS[str(c.message.chat.id)] = {}
    save_json(BOOKMARKS_FILE, BOOKMARKS)
    await c.message.answer("✅ Очищено.")


# ==================== ИСТОРИЯ / UNDO ====================
@dp.callback_query(F.data == "history_show")
async def cb_history(c: types.CallbackQuery):
    await show_history(c.message.chat.id, c.message)


async def show_history(cid, message):
    items = op_history.get(cid, [])
    if not items:
        await message.answer(t(cid, "history_empty"))
        return
    text = t(cid, "history_title", n=len(items)) + "\n\n"
    for i, item in enumerate(reversed(items[-15:]), 1):
        ts = datetime.fromtimestamp(item["t"]).strftime("%H:%M:%S")
        text += f"{i}. [{ts}] <b>{item['a']}</b>\n"
    await message.answer(text[:4000])


@dp.callback_query(F.data == "undo")
async def cb_undo(c: types.CallbackQuery):
    await do_undo(c.message.chat.id, c.message)


async def do_undo(cid, message):
    stack = undo_stack.get(cid, [])
    if not stack:
        await message.answer(t(cid, "undo_none"))
        return
    item = stack.pop()
    try:
        act = item["action"]
        if act == "delete":
            if os.path.exists(item["path"]):
                if os.path.isdir(item["path"]):
                    shutil.rmtree(item["path"])
                else:
                    os.remove(item["path"])
        elif act == "restore":
            if os.path.exists(item["path"]):
                orig = os.path.basename(item["path"]).split("_", 2)[-1]
                dest = os.path.join(ROOT_DIRECTORY, orig)
                shutil.move(item["path"], dest)
        elif act == "rename":
            if os.path.exists(item["from"]):
                os.rename(item["from"], item["to"])
        elif act == "move":
            if os.path.exists(item["from"]):
                shutil.move(item["from"], item["to"])
        await message.answer(t(cid, "undo_ok", a=act))
    except Exception as e:
        await message.answer(t(cid, "err", e=e))


# ==================== НАСТРОЙКИ ====================
@dp.callback_query(F.data == "settings")
async def cb_settings(c: types.CallbackQuery):
    cid = c.message.chat.id
    kb = InlineKeyboardBuilder()
    kb.button(text=t(cid, "lang"), callback_data="ch_lang")
    kb.button(text=t(cid, "menu"), callback_data="return_to_menu")
    kb.adjust(1)
    await edit_msg(c.message, f"⚙️ <b>{t(cid, 'settings')}</b>", reply_markup=kb.as_markup())


@dp.callback_query(F.data == "ch_lang")
async def cb_ch_lang(c: types.CallbackQuery):
    cid = c.message.chat.id
    kb = InlineKeyboardBuilder()
    kb.button(text="🇷🇺 Русский", callback_data="sl_ru")
    kb.button(text="🇺🇸 English", callback_data="sl_en")
    kb.button(text="🇺🇦 Українська", callback_data="sl_ua")
    kb.button(text=t(cid, "back"), callback_data="settings")
    kb.adjust(1)
    await edit_msg(c.message, t(cid, "select_lang"), reply_markup=kb.as_markup())


@dp.callback_query(F.data.startswith("sl_"))
async def cb_sl(c: types.CallbackQuery):
    lang = c.data.split("_", 1)[1]
    set_language(c.message.chat.id, lang)
    await edit_msg(c.message, t(c.message.chat.id, "lang_set", lang=lang),
                   reply_markup=main_menu(c.message.chat.id))


# ==================== МОНИТОРИНГ ====================
async def monitor_loop():
    if not PSUTIL:
        return
    last_alert = {}
    while True:
        await asyncio.sleep(120)
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage(ROOT_DIRECTORY if os.path.exists(ROOT_DIRECTORY) else "/")
            for key, val, threshold in [
                ("cpu", cpu, 95),
                ("ram", ram.percent, 95),
                ("disk", disk.percent, 95),
            ]:
                if val >= threshold:
                    now = time.time()
                    if now - last_alert.get(key, 0) > 3600:
                        last_alert[key] = now
                        try:
                            await bot.send_message(
                                ADMIN_ID,
                                f"⚠️ <b>Алерт системы</b>\n{key.upper()}: {val}%"
                            )
                        except Exception:
                            pass
        except Exception as e:
            logging.warning(f"monitor: {e}")


# ==================== ЗАПУСК ====================
async def main():
    if not BOT_TOKEN or ":" not in BOT_TOKEN or BOT_TOKEN.startswith("ВСТАВЬТЕ"):
        raise RuntimeError("Укажите BOT_TOKEN")

    session = os.environ.get("XDG_SESSION_TYPE", "?")
    logging.info(f"Device: {DEVICE_TYPE}, root: {ROOT_DIRECTORY}, session: {session}")
    flags = (
        f"psutil: {'✅' if PSUTIL else '❌'} | "
        f"PIL: {'✅' if PIL_OK else '❌'} | "
        f"QR: {'✅' if QR_OK else '❌'} | "
        f"mss: {'✅' if MSS_OK else '❌'} | "
        f"cv2: {'✅' if CV2_OK else '❌'} | "
        f"audio: {'✅' if AUDIO_OK else '❌'} | "
        f"dbus: {'✅' if DBUS_OK else '❌'}"
    )
    try:
        await bot.send_message(
            ADMIN_ID,
            f"🚀 <b>Бот-ратник PRO запущен</b>\n"
            f"🖥 <code>{DEVICE_TYPE}</code>\n"
            f"🌐 Session: <code>{session}</code>\n"
            f"📂 <code>{ROOT_DIRECTORY}</code>\n"
            f"🛠 {flags}"
        )
    except Exception as e:
        logging.warning(f"start msg: {e}")

    asyncio.create_task(monitor_loop())
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
