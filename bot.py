import asyncio
import logging
import random
import json
import math
import os
from datetime import datetime, timedelta
from io import BytesIO

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    BufferedInputFile, LabeledPrice, PreCheckoutQuery, Message,
    FSInputFile, BotCommand, BotCommandScopeDefault
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

import aiosqlite
from PIL import Image, ImageDraw, ImageFont, ImageOps

BOT_TOKEN = "8949953502:AAGwrEWWVST3yXRNA57yLWl8RXDdmr9WRQs"
ADMIN_IDS = [5341904332]  # ID главных администраторов

DB_PATH = "game_database.db"

# Цвета редкостей для оформления рамок карт (RGB)
RARITY_COLORS = {
    "Basic": (128, 128, 128),       # Серый
    "Uncommon": (0, 255, 0),        # Зеленый
    "Rare": (0, 191, 255),          # Голубой
    "Epic": (128, 0, 128),          # Фиолетовый
    "Legendary": (255, 215, 0),     # Жёлтый
    "Mythic": (255, 0, 0),          # Красный
    "Super": (255, 0, 255),         # Радужный/Пурпурный
    "Secret": (20, 20, 20),         # Чёрный
    "Exclusive": (255, 105, 180),   # Розовый
    "Leaderboard": (218, 165, 32)   # Золотой
}

# Мутации карт
MUTATIONS = {
    "Normal": {"chance": 0.88, "buff": 1.0, "name": "Обычная"},
    "Gold": {"chance": 0.10, "buff": 1.15, "name": "✨ Золотая"},
    "Rainbow": {"chance": 0.02, "buff": 1.30, "name": "🌈 Радужная"}
}

# Список Донат-товаров и Геймпасов
GAMEPASSES = {
    "x2_shekels": {
        "title": "⚡️ X2 Шекели",
        "desc": "Удваивает получение шекелей во всех режимах!",
        "robux": 69,
        "stars": 29
    },
    "x2_skills": {
        "title": "🎓 X2 Очки навыков",
        "desc": "Удваивает получаемые очки навыков за бои!",
        "robux": 99,
        "stars": 49
    },
    "slot_5": {
        "title": "⚔️ 5-й Слот Юнита",
        "desc": "Открывает 5-й слот для установки юнита в боевой отряд!",
        "robux": 99,
        "stars": 49
    },
    "vip": {
        "title": "👑 VIP Статус",
        "desc": "x1.5 Шекели, x1.3 Удача карт, +5% к Очкам навыков, 4 слота в AFK режимах и VIP-значок!",
        "robux": 159,
        "stars": 79
    }
}

RANKS = {
    "Rock I": {"min": 0, "max": 150, "trophies": (60, 80), "shekels": (2, 4)},
    "Rock II": {"min": 151, "max": 350, "trophies": (55, 70), "shekels": (4, 4)},
    "Rock III": {"min": 351, "max": 600, "trophies": (50, 65), "shekels": (4, 4)},
    "Rock IV": {"min": 601, "max": 1000, "trophies": (50, 60), "shekels": (4, 6)},
    "Bronze I": {"min": 1001, "max": 1275, "trophies": (45, 60), "shekels": (4, 6)},
    "Bronze II": {"min": 1276, "max": 1600, "trophies": (45, 55), "shekels": (4, 8)},
    "Bronze III": {"min": 1601, "max": 1800, "trophies": (40, 50), "shekels": (6, 8)},
    "Bronze IV": {"min": 1801, "max": 2250, "trophies": (40, 48), "shekels": (6, 8)},
    "Iron I": {"min": 2251, "max": 2700, "trophies": (38, 45), "shekels": (6, 8)},
    "Iron II": {"min": 2701, "max": 3200, "trophies": (35, 42), "shekels": (8, 12)},
    "Iron III": {"min": 3201, "max": 3800, "trophies": (32, 38), "shekels": (10, 12)},
    "Iron IV": {"min": 3801, "max": 4500, "trophies": (28, 35), "shekels": (12, 16)},
    "Gold I": {"min": 4501, "max": 5300, "trophies": (25, 32), "shekels": (14, 16)},
    "Gold II": {"min": 5301, "max": 6200, "trophies": (22, 28), "shekels": (16, 18)},
    "Gold III": {"min": 6201, "max": 7200, "trophies": (20, 25), "shekels": (18, 22)},
    "Gold IV": {"min": 7201, "max": 8300, "trophies": (18, 22), "shekels": (20, 22)},
    "Diamond I": {"min": 8301, "max": 9500, "trophies": (16, 20), "shekels": (22, 24)},
    "Diamond II": {"min": 9501, "max": 10800, "trophies": (14, 18), "shekels": (24, 26)},
    "Diamond III": {"min": 10801, "max": 12200, "trophies": (12, 16), "shekels": (26, 28)},
    "Diamond IV": {"min": 12201, "max": 13700, "trophies": (10, 14), "shekels": (28, 32)},
    "Platina I": {"min": 13701, "max": 15300, "trophies": (9, 13), "shekels": (30, 34)},
    "Platina II": {"min": 15301, "max": 17000, "trophies": (8, 11), "shekels": (32, 34)},
    "Platina III": {"min": 17001, "max": 18800, "trophies": (7, 10), "shekels": (34, 36)},
    "Platina IV": {"min": 18801, "max": 20700, "trophies": (6, 9), "shekels": (36, 38)},
    "Modern I": {"min": 20701, "max": 22700, "trophies": (6, 8), "shekels": (38, 40)},
    "Modern II": {"min": 22701, "max": 24800, "trophies": (5, 7), "shekels": (40, 42)},
    "Modern III": {"min": 24801, "max": 27000, "trophies": (4, 6), "shekels": (42, 46)},
    "Modern IV": {"min": 27001, "max": 29300, "trophies": (4, 5), "shekels": (44, 46)},
    "Digital I": {"min": 29301, "max": 31700, "trophies": (3, 5), "shekels": (46, 48)},
    "Digital II": {"min": 31701, "max": 34200, "trophies": (3, 4), "shekels": (48, 50)},
    "Digital III": {"min": 34201, "max": 36800, "trophies": (2, 4), "shekels": (50, 52)},
    "Digital IV": {"min": 36801, "max": 39500, "trophies": (2, 3), "shekels": (52, 56)},
    "Cosmic I": {"min": 39501, "max": 42300, "trophies": (2, 3), "shekels": (54, 58)},
    "Cosmic II": {"min": 42301, "max": 45200, "trophies": (2, 2), "shekels": (56, 58)},
    "Cosmic III": {"min": 45201, "max": 48200, "trophies": (1, 2), "shekels": (58, 60)},
    "Cosmic IV": {"min": 48201, "max": 50000, "trophies": (1, 1), "shekels": (60, 64)},
    "Ultimate I": {"min": 50001, "max": 9999999, "trophies": (1, 1), "shekels": (70, 100)}
}

# Подбор подгрупп ИИ по рангам и сложности
AI_MATCHING_TABLE = {
    "easy": {
        "Rock": ["Basic", "Uncommon"],
        "Bronze": ["Uncommon", "Rare"],
        "Iron": ["Uncommon", "Rare"],
        "Gold": ["Rare", "Epic"],
        "Platina": ["Epic", "Legendary", "Mythic"],
        "Modern": ["Legendary", "Mythic", "Super"],
        "Digital": ["Mythic", "Super"],
        "Cosmic": ["Mythic", "Super"],
        "Ultimate": ["Super"]
    },
    "medium": {
        "Rock": ["Basic", "Uncommon"],
        "Bronze": ["Uncommon", "Rare"],
        "Iron": ["Rare", "Epic"],
        "Gold": ["Epic", "Legendary"],
        "Platina": ["Legendary", "Mythic"],
        "Modern": ["Legendary", "Mythic", "Super"],
        "Digital": ["Mythic", "Super"],
        "Cosmic": ["Mythic", "Super"],
        "Ultimate": ["Super"]
    },
    "hard": {
        "Rock": ["Uncommon"],
        "Bronze": ["Uncommon", "Rare", "Epic"],
        "Iron": ["Rare", "Epic", "Legendary"],
        "Gold": ["Epic", "Legendary"],
        "Platina": ["Legendary", "Mythic"],
        "Modern": ["Mythic", "Super"],
        "Cosmic": ["Mythic", "Super"],
        "Ultimate": ["Super"]
    },
    "nightmare": {
        "Rock": ["Uncommon", "Rare"],
        "Bronze": ["Rare", "Epic"],
        "Iron": ["Epic", "Legendary"],
        "Gold": ["Legendary", "Mythic"],
        "Platina": ["Mythic", "Super"],
        "Modern": ["Mythic", "Super"],
        "Cosmic": ["Super"],
        "Ultimate": ["Super"]
    }
}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            shekels INTEGER DEFAULT 10,
            robux INTEGER DEFAULT 0,
            trophies INTEGER DEFAULT 0,
            pity_mythic INTEGER DEFAULT 0,
            pity_super INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            last_quest_time TEXT DEFAULT '2000-01-01 00:00:00',
            quests_done_hour INTEGER DEFAULT 0,
            daily_streak INTEGER DEFAULT 0,
            last_daily_claim TEXT DEFAULT ''
        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS cards (
            card_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            rarity TEXT,
            card_class TEXT,
            damage INTEGER,
            hp INTEGER,
            cooldown REAL,
            photo_id TEXT,
            is_banned_ai INTEGER DEFAULT 0,
            is_hidden_index INTEGER DEFAULT 0,
            dmg_boost REAL DEFAULT 0.0,
            cld_boost REAL DEFAULT 0.0,
            hp_boost REAL DEFAULT 0.0
        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS inventory (
            item_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            card_id INTEGER,
            mutation TEXT,
            serial_number TEXT,
            hp_pts INTEGER DEFAULT 0,
            dmg_pts INTEGER DEFAULT 0,
            cld_pts INTEGER DEFAULT 0,
            is_equipped INTEGER DEFAULT 0,
            equip_slot INTEGER DEFAULT 0
        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS seed_packs (
            pack_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            pack_type TEXT,
            amount INTEGER DEFAULT 1
        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS crates (
            crate_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price INTEGER,
            photo_id TEXT,
            contents_json TEXT
        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS skills (
            user_id INTEGER PRIMARY KEY,
            points INTEGER DEFAULT 0
        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS user_gamepasses (
            user_id INTEGER,
            gamepass_id TEXT,
            PRIMARY KEY (user_id, gamepass_id)
        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS afk_expeditions (
            user_id INTEGER PRIMARY KEY,
            cards_json TEXT,
            duration_hours INTEGER,
            start_time TEXT,
            end_time TEXT,
            claimed INTEGER DEFAULT 0
        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS global_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            multiplier REAL,
            end_time TEXT
        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS top_rewards (
            tier TEXT PRIMARY KEY,
            reward_desc TEXT,
            shekels INTEGER DEFAULT 0
        )''')

        # Заполнение дефолтных карт при пустой БД
        async with db.execute("SELECT COUNT(*) FROM cards") as cursor:
            count = (await cursor.fetchone())[0]
            if count == 0:
                await db.execute("""
                    INSERT INTO cards (name, rarity, card_class, damage, hp, cooldown, photo_id)
                    VALUES ('Стартовый Шрекс', 'Basic', 'Single', 25, 100, 2.0, '')
                """)

        async with db.execute("SELECT COUNT(*) FROM crates") as cursor:
            count_crates = (await cursor.fetchone())[0]
            if count_crates == 0:
                default_crate = json.dumps({"Basic": 80.0, "Uncommon": 20.0})
                await db.execute("""
                    INSERT INTO crates (name, price, photo_id, contents_json)
                    VALUES ('Стандартный Крейт', 50, '', ?)
                """, (default_crate,))

        await db.commit()

def generate_card_frame(photo_bytes: bytes, rarity: str) -> bytes:
    """Накладывает рамку соответствующего цвета редкости на изображение карты."""
    try:
        img = Image.open(BytesIO(photo_bytes)).convert("RGBA")
        color = RARITY_COLORS.get(rarity, (255, 255, 255))
        img_with_border = ImageOps.expand(img, border=16, fill=color)
        out = BytesIO()
        img_with_border.save(out, format="PNG")
        return out.getvalue()
    except Exception as e:
        logging.error(f"Error generating card frame: {e}")
        return photo_bytes

def generate_skill_panel(hp_pts: int, dmg_pts: int, cld_pts: int, available_pts: int, card_name: str = "Карта") -> bytes:
    """Генерирует стильное изображение панели навыков."""
    width, height = 520, 360
    img = Image.new('RGB', (width, height), color=(22, 26, 35))
    draw = ImageDraw.Draw(img)

    try:
        font_title = ImageFont.truetype("arial.ttf", 26)
        font_stat = ImageFont.truetype("arial.ttf", 20)
        font_sub = ImageFont.truetype("arial.ttf", 15)
    except IOError:
        font_title = ImageFont.load_default()
        font_stat = ImageFont.load_default()
        font_sub = ImageFont.load_default()

    draw.rounded_rectangle([12, 12, width - 12, height - 12], radius=15, outline=(255, 120, 20), width=4)

    draw.text((140, 25), "ОЧКИ НАВЫКОВ", fill=(255, 140, 30), font=font_title)
    draw.text((180, 65), f"Осталось: {available_pts}", fill=(50, 230, 120), font=font_stat)
    draw.text((30, 100), f"Юнит: {card_name[:25]}", fill=(200, 200, 210), font=font_sub)

    hp_mult = 1.0 + (hp_pts * 0.05)
    dmg_mult = 1.0 + (dmg_pts * 0.05)
    cld_mult = max(0.1, 1.0 - (cld_pts * 0.05))
    ppt_mult = 1.00

    stats = [
        ("HP", f"x{hp_mult:.2f}", hp_pts, (255, 60, 60), 135),
        ("DMG", f"x{dmg_mult:.2f}", dmg_pts, (255, 170, 30), 185),
        ("CLD", f"x{cld_mult:.2f}", cld_pts, (60, 160, 255), 235),
        ("PPT", f"x{ppt_mult:.2f}", 0, (60, 220, 120), 285)
    ]

    for label, mult_str, pts, color, y in stats:
        draw.text((35, y), label, fill=color, font=font_stat)
        draw.text((120, y), mult_str, fill=(255, 255, 255), font=font_stat)

        bar_x = 220
        bar_w = 180
        draw.rounded_rectangle([bar_x, y + 4, bar_x + bar_w, y + 20], radius=5, fill=(45, 50, 65), outline=(90, 95, 110))

        fill_len = int(bar_w * (pts / 100.0))
        if fill_len > 0:
            draw.rounded_rectangle([bar_x, y + 4, bar_x + fill_len, y + 20], radius=5, fill=color)

        draw.text((415, y), f"[{pts}/100]", fill=(190, 190, 200), font=font_sub)

    out = BytesIO()
    img.save(out, format="JPEG")
    return out.getvalue()

class CardCreation(StatesGroup):
    photo = State()
    name = State()
    rarity = State()
    c_class = State()
    damage = State()
    hp = State()
    cooldown = State()

class CrateCreation(StatesGroup):
    photo = State()
    name = State()
    price = State()
    cards_json = State()

class ExchangeState(StatesGroup):
    amount = State()

class GiftState(StatesGroup):
    gamepass_id = State()
    currency_type = State()
    target_user = State()

class AFKState(StatesGroup):
    selecting_cards = State()

class AdminPlayerAction(StatesGroup):
    target_user = State()
    amount = State()
    card_select = State()
    mutation_select = State()
    serial_select = State()

class AdminEventState(StatesGroup):
    multiplier = State()
    duration_min = State()

def main_menu_kb(is_admin=False):
    kb = [
        [InlineKeyboardButton(text="📦 Крейты", callback_data="menu_crates"), InlineKeyboardButton(text="⚔️ Поиск боя", callback_data="menu_battle"), InlineKeyboardButton(text="📜 Квесты", callback_data="menu_quests")],
        [InlineKeyboardButton(text="🏆 Топ игроков", callback_data="menu_top"), InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile"), InlineKeyboardButton(text="✨ Очки навыков", callback_data="menu_skills")],
        [InlineKeyboardButton(text="🎒 Инвентарь", callback_data="menu_inventory"), InlineKeyboardButton(text="📖 Индекс", callback_data="menu_index"), InlineKeyboardButton(text="🛡 Экипировка", callback_data="menu_equip")],
        [InlineKeyboardButton(text="🌱 Сид-паки", callback_data="menu_seeds"), InlineKeyboardButton(text="🎁 Награды", callback_data="menu_daily"), InlineKeyboardButton(text="⏳ AFK Режим", callback_data="menu_afk")],
        [InlineKeyboardButton(text="💎 Донат Магазин", callback_data="menu_donate")]
    ]
    if is_admin:
        kb.append([InlineKeyboardButton(text="⚙️ Админ панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def admin_panel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🃏 Карты", callback_data="admin_cards"), InlineKeyboardButton(text="👥 Игроки", callback_data="admin_players")],
        [InlineKeyboardButton(text="🎉 Ивенты", callback_data="admin_events"), InlineKeyboardButton(text="👮‍♂️ Админы", callback_data="admin_admins")],
        [InlineKeyboardButton(text="📦 Крейты", callback_data="admin_crates"), InlineKeyboardButton(text="🏅 Награды за топ", callback_data="admin_top_rewards")],
        [InlineKeyboardButton(text="💾 Бекап БД", callback_data="admin_backup"), InlineKeyboardButton(text="🚫 Запреты", callback_data="admin_bans")],
        [InlineKeyboardButton(text="⬅️ Главное меню", callback_data="menu_main")]
    ])

def battle_difficulty_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Лёгкий (-50% трофеев)", callback_data="battle_start_easy")],
        [InlineKeyboardButton(text="🟡 Средний (Базовые награды)", callback_data="battle_start_medium")],
        [InlineKeyboardButton(text="🔴 Сложный (+30% трофеев)", callback_data="battle_start_hard")],
        [InlineKeyboardButton(text="💀 КОШМАР (+80% трофеев)", callback_data="battle_start_nightmare")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ])

def get_rank_by_trophies(trophies: int) -> str:
    for rank, data in RANKS.items():
        if data["min"] <= trophies <= data["max"]:
            return rank
    return "Ultimate I"

async def check_is_admin(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return bool(row[0]) if row else False

async def get_user_stats(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT shekels, robux, trophies, pity_mythic, pity_super, username, daily_streak, last_daily_claim FROM users WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            return await cursor.fetchone()

async def has_gamepass(user_id: int, gamepass_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT 1 FROM user_gamepasses WHERE user_id = ? AND gamepass_id = ?", (user_id, gamepass_id)) as cursor:
            res = await cursor.fetchone()
            return res is not None

async def give_gamepass(user_id: int, gamepass_id: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("INSERT OR IGNORE INTO user_gamepasses (user_id, gamepass_id) VALUES (?, ?)", (user_id, gamepass_id))
            await db.commit()
            return True
        except Exception as e:
            logging.error(f"Error giving gamepass: {e}")
            return False

async def get_next_serial(rarity: str):
    if rarity not in ["Mythic", "Super", "Exclusive", "Leaderboard"]:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM inventory i JOIN cards c ON i.card_id = c.card_id WHERE c.rarity = ?", (rarity,)) as cursor:
            count = (await cursor.fetchone())[0]
            serial = count + 1
            if serial > 9999:
                serial = 9999
            return f"#{serial:04d}"

async def add_card_to_user(user_id: int, rarity_filter: str = None) -> tuple:
    async with aiosqlite.connect(DB_PATH) as db:
        query = "SELECT card_id, name, rarity FROM cards"
        params = []
        if rarity_filter:
            query += " WHERE rarity = ?"
            params.append(rarity_filter)
        query += " ORDER BY RANDOM() LIMIT 1"

        async with db.execute(query, params) as cursor:
            card = await cursor.fetchone()

        if not card:
            async with db.execute("SELECT card_id, name, rarity FROM cards ORDER BY RANDOM() LIMIT 1") as cursor2:
                card = await cursor2.fetchone()

        if not card:
            return None, "Нет доступных карт"

        card_id, card_name, rarity = card

        rand = random.random()
        if rand < MUTATIONS["Rainbow"]["chance"]:
            mutation = "Rainbow"
        elif rand < MUTATIONS["Rainbow"]["chance"] + MUTATIONS["Gold"]["chance"]:
            mutation = "Gold"
        else:
            mutation = "Normal"

        serial = await get_next_serial(rarity)

        await db.execute(
            "INSERT INTO inventory (user_id, card_id, mutation, serial_number) VALUES (?, ?, ?, ?)",
            (user_id, card_id, mutation, serial)
        )
        await db.commit()
        return card_name, rarity, mutation, serial

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO users (user_id, username, shekels) VALUES (?, ?, 10) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username",
            (user_id, username)
        )
        await db.commit()

    is_admin = await check_is_admin(user_id)

    text = (
        f"👋 Привет, <b>{username}</b>!\n\n"
        f"Добро пожаловать в коллекционную карточную арену <b>Card Battle Bot</b>!\n"
        f"Собирайте уникальные карты, отправляйте отряды в AFK-походы, участвуйте в аренах и прокачивайте навыки!\n\n"
        f"<i>Воспользуйтесь кнопками ниже или меню команд слева.</i>"
    )
    await message.answer(text, reply_markup=main_menu_kb(is_admin))

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    help_text = (
        f"📖 <b>СПРАВКА ПО КОМАНДАМ БОТА</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• <code>/start</code> — Перезапуск бота и открытие меню\n"
        f"• <code>/afk</code> — Режим AFK-экспедиций\n"
        f"• <code>/donate</code> — Магазин доната и обмен валюты\n"
        f"• <code>/profile</code> — Мой профиль и статистика\n"
        f"• <code>/inventory</code> — Мой инвентарь карт\n"
        f"• <code>/admin</code> — Панель администратора\n"
        f"• <code>/help</code> — Показать это сообщение\n\n"
        f"Используйте кнопки под сообщениями для навигации!"
    )
    await message.answer(help_text)

@dp.message(Command("admin"))
async def cmd_admin_command(message: types.Message):
    user_id = message.from_user.id
    if not await check_is_admin(user_id):
        return await message.answer("❌ <b>Отказано в доступе!</b> У вас нет прав администратора.")
    await message.answer("⚙️ <b>АДМИНИСТРАТИВНАЯ ПАНЕЛЬ</b>\nВыберите раздел для управления:", reply_markup=admin_panel_kb())

@dp.message(Command("afk"))
async def cmd_afk(message: types.Message):
    user_id = message.from_user.id
    now = datetime.utcnow()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT cards_json, duration_hours, start_time, end_time FROM afk_expeditions WHERE user_id = ?", (user_id,)) as cursor:
            expedition = await cursor.fetchone()

    if expedition:
        cards_json, duration_h, start_str, end_str = expedition
        end_time = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")

        if now >= end_time:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎁 Забрать награду!", callback_data="afk_claim_reward")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
            ])
            await message.answer(
                f"🎉 <b>AFK Экспедиция завершена!</b>\n"
                f"Ваш отряд вернулся из похода на <b>{duration_h} ч.</b>!\nЗаберите награду!",
                reply_markup=kb
            )
        else:
            rem = end_time - now
            rem_h, rem_m = rem.seconds // 3600, (rem.seconds % 3600) // 60
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить", callback_data="afk_cancel")],
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="menu_afk")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
            ])
            await message.answer(
                f"⏳ <b>AFK Экспедиция в процессе...</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏱ Длительность: <b>{duration_h} часов</b>\n"
                f"⏳ Осталось времени: <b>{rem_h} ч. {rem_m} мин.</b>\n",
                reply_markup=kb
            )
    else:
        is_vip = await has_gamepass(user_id, "vip")
        max_afk_cards = 4 if is_vip else 3

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Собрать отряд и запустить", callback_data="afk_setup_cards")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
        ])
        await message.answer(
            f"⏳ <b>AFK ЭКСПЕДИЦИИ</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• Слотов для карт: <b>{max_afk_cards} шт.</b> {'👑 (VIP)' if is_vip else '(Купите VIP для 4 слотов)'}\n"
            f"• Варианты походов: <b>2, 4, 6, 10 или 24 часа</b>\n"
            f"• Награды: <b>1 — 500 шекелей</b> 🪙 и <b>1 — 35 очков навыков</b> ✨!",
            reply_markup=kb
        )

@dp.message(Command("donate"))
async def cmd_donate(message: types.Message):
    await message.answer("💎 <b>ДОНАТ МАГАЗИН</b>\nВыберите раздел:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обменять Шекели ➡️ Робуксы", callback_data="donate_exchange")],
        [InlineKeyboardButton(text="🛒 F2P Магазин (Робуксы R$)", callback_data="donate_f2p")],
        [InlineKeyboardButton(text="🌟 P2W Магазин (Telegram Stars)", callback_data="donate_p2w")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ]))

@dp.message(Command("profile"))
async def cmd_profile(message: types.Message):
    user_id = message.from_user.id
    stats = await get_user_stats(user_id)
    if not stats:
        return await message.answer("Ошибка профиля!")

    shekels, robux, trophies, pity_m, pity_s, username, streak, _ = stats
    rank = get_rank_by_trophies(trophies)

    is_vip = await has_gamepass(user_id, "vip")
    has_slot5 = await has_gamepass(user_id, "slot_5")
    max_slots = 5 if has_slot5 else 4
    afk_slots = 4 if is_vip else 3

    vip_badge = "👑 [VIP Игрок] " if is_vip else ""

    equipped_text = ""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT c.name, i.mutation, c.rarity, i.hp_pts, i.dmg_pts, i.cld_pts, i.equip_slot, i.serial_number
            FROM inventory i JOIN cards c ON i.card_id = c.card_id 
            WHERE i.user_id = ? AND i.is_equipped = 1 ORDER BY i.equip_slot
        """, (user_id,)) as cursor:
            equipped = await cursor.fetchall()
            for eq in equipped:
                mut = MUTATIONS.get(eq[1], MUTATIONS["Normal"])["name"]
                ser_str = f" ({eq[7]})" if eq[7] else ""
                equipped_text += f"• Слот {eq[6]}: {mut} {eq[0]}{ser_str} [{eq[2]}] (Очки: {eq[3]+eq[4]+eq[5]})\n"

            if not equipped:
                equipped_text = "<i>Нет экипированных карт</i>"

    text = (
        f"👤 <b>ПРОФИЛЬ ИГРОКА:</b> {vip_badge}{username}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>Ранг:</b> {rank} ({trophies} кубков)\n"
        f"🪙 <b>Шекели:</b> {shekels}\n"
        f"💎 <b>Робуксы (R$):</b> {robux}\n"
        f"🔥 <b>Серия входа:</b> {streak} дней\n"
        f"⚔️ <b>Слотов юнитов:</b> {max_slots} | ⏳ <b>AFK слотов:</b> {afk_slots}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔮 <b>Гарант на Мифик:</b> {pity_m}/1000\n"
        f"🌈 <b>Гарант на Супер:</b> {pity_s}/10000\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡 <b>Экипировка ({len(equipped)}/{max_slots}):</b>\n{equipped_text}"
    )
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]]))

@dp.message(Command("inventory"))
async def cmd_inventory(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT c.name, i.mutation, COUNT(*) as cnt, i.serial_number 
            FROM inventory i JOIN cards c ON i.card_id = c.card_id 
            WHERE i.user_id = ? GROUP BY c.name, i.mutation ORDER BY c.rarity DESC
        """, (user_id,)) as cursor:
            items = await cursor.fetchall()

    text = f"🎒 <b>ИНВЕНТАРЬ КАРТ</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for item in items[:25]:
        mut = MUTATIONS.get(item[1], MUTATIONS["Normal"])["name"]
        ser_str = f" ({item[3]})" if item[3] else ""
        text += f"• {mut} {item[0]}{ser_str} — {item[2]} шт.\n"

    if not items:
        text += "<i>Инвентарь пуст...</i>"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌱 Сид-паки", callback_data="menu_seeds"), InlineKeyboardButton(text="📦 Крейты", callback_data="menu_crates")],
        [InlineKeyboardButton(text="🛡 Экипировка", callback_data="menu_equip"), InlineKeyboardButton(text="⬅️ Главное меню", callback_data="menu_main")]
    ])
    await message.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "menu_main")
async def cb_menu_main(callback: CallbackQuery):
    user_id = callback.from_user.id
    is_admin = await check_is_admin(user_id)
    await callback.message.edit_text("Главное меню:", reply_markup=main_menu_kb(is_admin))

@dp.callback_query(F.data == "menu_profile")
async def cb_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    stats = await get_user_stats(user_id)
    if not stats:
        return await callback.answer("Ошибка профиля!")

    shekels, robux, trophies, pity_m, pity_s, username, streak, _ = stats
    rank = get_rank_by_trophies(trophies)

    is_vip = await has_gamepass(user_id, "vip")
    has_slot5 = await has_gamepass(user_id, "slot_5")
    max_slots = 5 if has_slot5 else 4
    afk_slots = 4 if is_vip else 3

    vip_badge = "👑 [VIP Игрок] " if is_vip else ""

    equipped_text = ""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT c.name, i.mutation, c.rarity, i.hp_pts, i.dmg_pts, i.cld_pts, i.equip_slot, i.serial_number
            FROM inventory i JOIN cards c ON i.card_id = c.card_id 
            WHERE i.user_id = ? AND i.is_equipped = 1 ORDER BY i.equip_slot
        """, (user_id,)) as cursor:
            equipped = await cursor.fetchall()
            for eq in equipped:
                mut = MUTATIONS.get(eq[1], MUTATIONS["Normal"])["name"]
                ser_str = f" ({eq[7]})" if eq[7] else ""
                equipped_text += f"• Слот {eq[6]}: {mut} {eq[0]}{ser_str} [{eq[2]}] (Очки: {eq[3]+eq[4]+eq[5]})\n"

            if not equipped:
                equipped_text = "<i>Нет экипированных карт</i>"

    text = (
        f"👤 <b>ПРОФИЛЬ ИГРОКА:</b> {vip_badge}{username}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 <b>Ранг:</b> {rank} ({trophies} кубков)\n"
        f"🪙 <b>Шекели:</b> {shekels}\n"
        f"💎 <b>Робуксы (R$):</b> {robux}\n"
        f"🔥 <b>Серия входа:</b> {streak} дней\n"
        f"⚔️ <b>Слотов юнитов:</b> {max_slots} | ⏳ <b>AFK слотов:</b> {afk_slots}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔮 <b>Гарант на Мифик:</b> {pity_m}/1000\n"
        f"🌈 <b>Гарант на Супер:</b> {pity_s}/10000\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡 <b>Экипировка ({len(equipped)}/{max_slots}):</b>\n{equipped_text}"
    )

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]]))

DAILY_REWARDS_INFO = {
    1: {"type": "shekels", "amount": 10, "desc": "10 шекелей 🪙"},
    2: {"type": "card", "rarity": "Uncommon", "desc": "Гарантированный Uncommon юнит 🟢"},
    3: {"type": "card", "rarity": "Epic", "desc": "Гарантированный Epic юнит 🟣"},
    4: {"type": "shekels", "amount": 400, "desc": "400 шекелей 🪙"},
    5: {"type": "card", "rarity": "Legendary", "desc": "Гарантированный Legendary юнит 🟡"},
    6: {"type": "shekels", "amount": 700, "desc": "700 шекелей 🪙"},
    7: {"type": "card", "rarity": "Mythic", "desc": "Гарантированный Mythic юнит 🔴"}
}

@dp.callback_query(F.data == "menu_daily")
async def cb_daily_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    stats = await get_user_stats(user_id)
    _, _, _, _, _, _, streak, last_claim_str = stats

    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    yesterday_str = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

    can_claim = True
    status_text = ""

    if last_claim_str == today_str:
        can_claim = False
        status_text = "❌ <b>Вы уже забрали награду сегодня!</b> Приходите завтра."
    elif last_claim_str == yesterday_str:
        next_day = streak + 1 if streak < 7 else 1
        status_text = f"✅ Вы можете забрать награду за <b>{next_day} день</b>!"
    else:
        status_text = "✅ Начните серию наград за <b>1 день</b>!"

    text = "🎁 <b>ЕЖЕДНЕВНЫЕ НАГРАДЫ</b>\nЗаходите каждый день и получайте призы!\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for day in range(1, 8):
        reward = DAILY_REWARDS_INFO[day]
        text += f"<b>День {day}:</b> {reward['desc']}\n"

    text += f"\n━━━━━━━━━━━━━━━━━━━━━━━━\n🔥 Ваша текущая серия: <b>{streak} дн.</b>\n{status_text}"

    kb = []
    if can_claim:
        kb.append([InlineKeyboardButton(text="🎉 Забрать награду!", callback_data="daily_claim")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "daily_claim")
async def cb_daily_claim(callback: CallbackQuery):
    user_id = callback.from_user.id
    stats = await get_user_stats(user_id)
    _, _, _, _, _, _, streak, last_claim_str = stats

    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    yesterday_str = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

    if last_claim_str == today_str:
        return await callback.answer("Вы уже забирали награду сегодня!", show_alert=True)

    new_streak = (streak + 1) if last_claim_str == yesterday_str else 1
    if new_streak > 7: new_streak = 1

    reward = DAILY_REWARDS_INFO[new_streak]
    reward_msg = ""

    is_vip = await has_gamepass(user_id, "vip")
    shekel_mult = 1.5 if is_vip else 1.0

    async with aiosqlite.connect(DB_PATH) as db:
        if reward["type"] == "shekels":
            final_amt = int(reward["amount"] * shekel_mult)
            await db.execute("UPDATE users SET shekels = shekels + ? WHERE user_id = ?", (final_amt, user_id))
            reward_msg = f"🪙 Получено <b>{final_amt} шекелей</b>!"
        elif reward["type"] == "card":
            card_res = await add_card_to_user(user_id, reward["rarity"])
            if card_res[0]:
                c_name, c_rar, c_mut, c_ser = card_res
                ser_str = f" ({c_ser})" if c_ser else ""
                reward_msg = f"🃏 Вы получили карту: <b>{c_name}</b> [{c_rar}]{ser_str}!"
            else:
                fallback_shekels = int(200 * shekel_mult)
                await db.execute("UPDATE users SET shekels = shekels + ? WHERE user_id = ?", (fallback_shekels, user_id))
                reward_msg = f"🪙 Не удалось выдать карту, компенсация: <b>{fallback_shekels} шекелей</b>!"

        await db.execute("UPDATE users SET daily_streak = ?, last_daily_claim = ? WHERE user_id = ?", (new_streak, today_str, user_id))
        await db.commit()

    await callback.message.edit_text(
        f"🎉 <b>НАГРАДА ЗА {new_streak} ДЕНЬ ПОЛУЧЕНА!</b>\n\n{reward_msg}\n\nВозвращайтесь завтра за следующей наградой!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")]])
    )

@dp.callback_query(F.data == "menu_quests")
async def cb_quests(callback: CallbackQuery):
    user_id = callback.from_user.id
    now = datetime.utcnow()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT last_quest_time, quests_done_hour FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

    last_time_str = row[0] if row else '2000-01-01 00:00:00'
    last_time = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")

    time_diff = (now - last_time).total_seconds()
    quests_done = row[1] if (row and time_diff < 3600) else 0

    remaining_time = max(0, int(3600 - time_diff))
    rem_min = remaining_time // 60

    text = (
        f"📜 <b>ЕЖЕЧАСНЫЕ КВЕСТЫ (3 в час)</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"• Выполнено квестов в этом часу: <b>{quests_done}/3</b>\n"
        f"• Награда за каждый квест: <b>125 Шекелей 🪙 + 1 Сид-пак 🌱</b>\n\n"
    )

    kb = []
    if quests_done < 3:
        text += f"🎯 <b>Доступный квест:</b> Сыграйте бой на Арене или откройте крейт!"
        kb.append([InlineKeyboardButton(text="✅ Сдать выполненный квест", callback_data="claim_quest")])
    else:
        text += f"⏳ Все квесты часа выполнены! До обновления осталось: <b>{rem_min} мин.</b>"

    kb.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "claim_quest")
async def cb_claim_quest(callback: CallbackQuery):
    user_id = callback.from_user.id
    now = datetime.utcnow()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT last_quest_time, quests_done_hour FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

        last_time_str = row[0] if row else '2000-01-01 00:00:00'
        last_time = datetime.strptime(last_time_str, "%Y-%m-%d %H:%M:%S")

        time_diff = (now - last_time).total_seconds()
        quests_done = row[1] if (row and time_diff < 3600) else 0

        if quests_done >= 3:
            return await callback.answer("Вы уже выполнили все 3 квеста за этот час!", show_alert=True)

        new_done = quests_done + 1
        await db.execute("UPDATE users SET shekels = shekels + 125, quests_done_hour = ?, last_quest_time = ? WHERE user_id = ?", (new_done, now_str, user_id))
        await db.execute("INSERT INTO seed_packs (user_id, pack_type, amount) VALUES (?, 'Базовый Сид-пак', 1) ON CONFLICT(user_id, pack_type) DO UPDATE SET amount = amount + 1", (user_id,))
        await db.commit()

    await callback.message.edit_text(
        f"🎉 <b>КВЕСТ ВЫПОЛНЕН!</b>\n\nВы получили:\n🪙 <b>+125 Шекелей</b>\n🌱 <b>+1 Базовый Сид-пак</b>!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_quests")]])
    )

@dp.callback_query(F.data == "menu_afk")
async def cb_afk_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    now = datetime.utcnow()

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT cards_json, duration_hours, start_time, end_time FROM afk_expeditions WHERE user_id = ?", (user_id,)) as cursor:
            expedition = await cursor.fetchone()

    if expedition:
        cards_json, duration_h, start_str, end_str = expedition
        end_time = datetime.strptime(end_str, "%Y-%m-%d %H:%M:%S")

        if now >= end_time:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎁 Забрать награду!", callback_data="afk_claim_reward")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
            ])
            await callback.message.edit_text(
                f"🎉 <b>AFK Экспедиция завершена!</b>\n"
                f"Ваш отряд вернулся из похода на <b>{duration_h} ч.</b>!\nЗаберите заслуженные ресурсы!",
                reply_markup=kb
            )
        else:
            rem = end_time - now
            rem_h, rem_m = rem.seconds // 3600, (rem.seconds % 3600) // 60
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отменить", callback_data="afk_cancel")],
                [InlineKeyboardButton(text="🔄 Обновить", callback_data="menu_afk")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
            ])
            await callback.message.edit_text(
                f"⏳ <b>AFK Экспедиция в процессе...</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏱ Длительность: <b>{duration_h} часов</b>\n"
                f"⏳ Осталось времени: <b>{rem_h} ч. {rem_m} мин.</b>\n",
                reply_markup=kb
            )
    else:
        is_vip = await has_gamepass(user_id, "vip")
        max_afk_cards = 4 if is_vip else 3

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Собрать отряд и запустить", callback_data="afk_setup_cards")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
        ])
        await callback.message.edit_text(
            f"⏳ <b>AFK ЭКСПЕДИЦИИ</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"• Слотов для карт: <b>{max_afk_cards} шт.</b> {'👑 (VIP)' if is_vip else '(Купите VIP для 4 слотов)'}\n"
            f"• Варианты походов: <b>2, 4, 6, 10 или 24 часа</b>\n"
            f"• Награды: <b>1 — 500 шекелей</b> 🪙 и <b>1 — 35 очков навыков</b> ✨!",
            reply_markup=kb
        )

@dp.callback_query(F.data == "afk_setup_cards")
async def cb_afk_setup_cards(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    is_vip = await has_gamepass(user_id, "vip")
    max_slots = 4 if is_vip else 3

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT i.item_id, c.name, i.mutation, c.rarity, c.damage, c.hp
            FROM inventory i JOIN cards c ON i.card_id = c.card_id
            WHERE i.user_id = ? LIMIT 20
        """, (user_id,)) as cursor:
            items = await cursor.fetchall()

    if not items:
        return await callback.answer("У вас нет карт для экспедиции!", show_alert=True)

    await state.update_data(selected_cards=[], max_slots=max_slots)
    await state.set_state(AFKState.selecting_cards)

    kb = []
    for item in items:
        mut = MUTATIONS.get(item[2], MUTATIONS["Normal"])["name"]
        kb.append([InlineKeyboardButton(text=f"▫️ {mut} {item[1]} [{item[3]}] (⚔️{item[4]} ❤️{item[5]})", callback_data=f"afk_toggle:{item[0]}")])

    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="menu_afk")])

    await callback.message.edit_text(
        f"⏳ Выберите карты в отряд (Выбрано: <b>0/{max_slots}</b>):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

@dp.callback_query(AFKState.selecting_cards, F.data.startswith("afk_toggle:"))
async def cb_afk_toggle_card(callback: CallbackQuery, state: FSMContext):
    item_id = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected = data.get("selected_cards", [])
    max_slots = data.get("max_slots", 3)

    if item_id in selected:
        selected.remove(item_id)
    else:
        if len(selected) >= max_slots:
            return await callback.answer(f"Максимум карт в отряде: {max_slots}!", show_alert=True)
        selected.append(item_id)

    await state.update_data(selected_cards=selected)

    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT i.item_id, c.name, i.mutation, c.rarity, c.damage, c.hp
            FROM inventory i JOIN cards c ON i.card_id = c.card_id
            WHERE i.user_id = ? LIMIT 20
        """, (user_id,)) as cursor:
            items = await cursor.fetchall()

    kb = []
    for item in items:
        icon = "☑️" if item[0] in selected else "▫️"
        mut = MUTATIONS.get(item[2], MUTATIONS["Normal"])["name"]
        kb.append([InlineKeyboardButton(text=f"{icon} {mut} {item[1]} [{item[3]}]", callback_data=f"afk_toggle:{item[0]}")])

    if selected:
        kb.append([InlineKeyboardButton(text="✅ Подтвердить отряд ➡️", callback_data="afk_choose_time")])
    kb.append([InlineKeyboardButton(text="❌ Отмена", callback_data="menu_afk")])

    await callback.message.edit_text(
        f"⏳ Выберите карты в отряд (Выбрано: <b>{len(selected)}/{max_slots}</b>):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

@dp.callback_query(AFKState.selecting_cards, F.data == "afk_choose_time")
async def cb_afk_choose_time(callback: CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏱ 2 Часа", callback_data="afk_start_exp:2"), InlineKeyboardButton(text="⏱ 4 Часа", callback_data="afk_start_exp:4")],
        [InlineKeyboardButton(text="⏱ 6 Часов", callback_data="afk_start_exp:6"), InlineKeyboardButton(text="⏱ 10 Часов", callback_data="afk_start_exp:10")],
        [InlineKeyboardButton(text="🌟 24 Часа", callback_data="afk_start_exp:24")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="afk_setup_cards")]
    ])
    await callback.message.edit_text("⏱ Выберите длительность экспедиции:", reply_markup=kb)

@dp.callback_query(AFKState.selecting_cards, F.data.startswith("afk_start_exp:"))
async def cb_afk_start_expedition(callback: CallbackQuery, state: FSMContext):
    hours = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected = data.get("selected_cards", [])
    user_id = callback.from_user.id

    start_time = datetime.utcnow()
    end_time = start_time + timedelta(hours=hours)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO afk_expeditions (user_id, cards_json, duration_hours, start_time, end_time, claimed)
            VALUES (?, ?, ?, ?, ?, 0) ON CONFLICT(user_id) DO UPDATE SET
            cards_json=excluded.cards_json, duration_hours=excluded.duration_hours,
            start_time=excluded.start_time, end_time=excluded.end_time, claimed=0
        """, (user_id, json.dumps(selected), hours, start_time.strftime("%Y-%m-%d %H:%M:%S"), end_time.strftime("%Y-%m-%d %H:%M:%S")))
        await db.commit()

    await state.clear()
    await callback.message.edit_text(
        f"🚀 <b>ОТРЯД ОТПРАВЛЕН В ЭКСПЕДИЦИЮ!</b>\n\n⏱ Время: <b>{hours} часов</b>\n🎴 Карты: <b>{len(selected)} шт.</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ В меню AFK", callback_data="menu_afk")]])
    )

@dp.callback_query(F.data == "afk_claim_reward")
async def cb_afk_claim_reward(callback: CallbackQuery):
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT cards_json, duration_hours FROM afk_expeditions WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

        if not row:
            return await callback.answer("Нет активной экспедиции!")

        cards_json, duration_h = row
        card_ids = json.loads(cards_json)

        total_power = 0
        if card_ids:
            placeholders = ",".join(["?"] * len(card_ids))
            async with db.execute(f"SELECT c.damage, c.hp FROM inventory i JOIN cards c ON i.card_id = c.card_id WHERE i.item_id IN ({placeholders})", card_ids) as cursor:
                for r in await cursor.fetchall():
                    total_power += r[0] + (r[1] // 5)

        factor = (min(1.0, duration_h / 24.0) * 0.6) + (min(1.0, total_power / 300.0) * 0.4)
        shekels_won = max(1, min(500, int(1 + factor * 499)))
        skills_won = max(1, min(35, int(1 + factor * 34)))

        is_vip = await has_gamepass(user_id, "vip")
        if is_vip: shekels_won = int(shekels_won * 1.5)
        if await has_gamepass(user_id, "x2_shekels"): shekels_won *= 2
        if await has_gamepass(user_id, "x2_skills"): skills_won *= 2

        await db.execute("UPDATE users SET shekels = shekels + ? WHERE user_id = ?", (shekels_won, user_id))
        await db.execute("INSERT INTO skills (user_id, points) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET points = points + ?", (user_id, skills_won, skills_won))
        await db.execute("DELETE FROM afk_expeditions WHERE user_id = ?", (user_id,))
        await db.commit()

    await callback.message.edit_text(
        f"🎉 <b>ЭКСПЕДИЦИЯ ЗАВЕРШЕНА!</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🪙 <b>+{shekels_won} Шекелей</b>\n✨ <b>+{skills_won} Очков навыков</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]])
    )

@dp.callback_query(F.data == "afk_cancel")
async def cb_afk_cancel(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM afk_expeditions WHERE user_id = ?", (user_id,))
        await db.commit()
    await callback.answer("Экспедиция отменена!")
    await cb_afk_menu(callback)

@dp.callback_query(F.data == "menu_donate")
async def cb_donate_menu(callback: CallbackQuery):
    await callback.message.edit_text("💎 <b>ДОНАТ МАГАЗИН</b>\nВыберите раздел:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обменять Шекели ➡️ Робуксы", callback_data="donate_exchange")],
        [InlineKeyboardButton(text="🛒 F2P Магазин (Робуксы R$)", callback_data="donate_f2p")],
        [InlineKeyboardButton(text="🌟 P2W Магазин (Telegram Stars)", callback_data="donate_p2w")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ]))

@dp.callback_query(F.data == "donate_exchange")
async def cb_exchange_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    stats = await get_user_stats(user_id)
    shekels, robux = stats[0], stats[1]

    await state.set_state(ExchangeState.amount)
    await callback.message.edit_text(
        f"🔄 <b>ОБМЕН ВАЛЮТЫ</b>\nКурс: <b>100 Шекелей = 1 R$</b>\n\n"
        f"💰 Шекели: <b>{shekels}</b> | 💎 Робуксы: <b>{robux}</b>\n\n"
        f"Введите количество <b>R$</b>, которое хотите купить:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="menu_donate")]])
    )

@dp.message(ExchangeState.amount)
async def process_exchange_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) <= 0:
        return await message.answer("Введите положительное число!")

    robux_wanted = int(message.text)
    shekels_cost = robux_wanted * 100
    user_id = message.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT shekels FROM users WHERE user_id = ?", (user_id,)) as cursor:
            shekels = (await cursor.fetchone())[0]

        if shekels < shekels_cost:
            await state.clear()
            return await message.answer(f"❌ Недостаточно шекелей! Нужно: {shekels_cost}, у вас: {shekels}")

        await db.execute("UPDATE users SET shekels = shekels - ?, robux = robux + ? WHERE user_id = ?", (shekels_cost, robux_wanted, user_id))
        await db.commit()

    await state.clear()
    await message.answer(f"✅ Вы успешно обменяли <b>{shekels_cost} шекелей</b> на <b>{robux_wanted} R$</b>!")

@dp.callback_query(F.data == "donate_f2p")
async def cb_donate_f2p(callback: CallbackQuery):
    user_id = callback.from_user.id
    stats = await get_user_stats(user_id)
    robux = stats[1]

    kb = []
    text = f"🛒 <b>F2P МАГАЗИН (За R$)</b>\nБаланс: <b>{robux} R$</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"

    for gp_id, gp in GAMEPASSES.items():
        owned = await has_gamepass(user_id, gp_id)
        status = "✅ КУПЛЕНО" if owned else f"{gp['robux']} R$"
        text += f"• <b>{gp['title']}</b> — {status}\n  └ {gp['desc']}\n"
        if not owned:
            kb.append([InlineKeyboardButton(text=f"Купить {gp['title']} ({gp['robux']} R$)", callback_data=f"buy_f2p:{gp_id}")])

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_donate")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "donate_p2w")
async def cb_donate_p2w(callback: CallbackQuery):
    user_id = callback.from_user.id
    kb = []
    text = f"🌟 <b>P2W МАГАЗИН (За Telegram Stars)</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"

    for gp_id, gp in GAMEPASSES.items():
        owned = await has_gamepass(user_id, gp_id)
        status = "✅ КУПЛЕНО" if owned else f"{gp['stars']} ⭐️"
        text += f"• <b>{gp['title']}</b> — {status}\n  └ {gp['desc']}\n"
        if not owned:
            kb.append([InlineKeyboardButton(text=f"Купить {gp['title']} ({gp['stars']} ⭐️)", callback_data=f"buy_p2w:{gp_id}")])

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_donate")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("buy_f2p:") | F.data.startswith("buy_p2w:"))
async def cb_buy_select_mode(callback: CallbackQuery):
    parts = callback.data.split(":")
    mode, gp_id = parts[0], parts[1]
    gp = GAMEPASSES.get(gp_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Себе", callback_data=f"proc_buy:{mode}:{gp_id}:self")],
        [InlineKeyboardButton(text="🎁 Подарить другу", callback_data=f"proc_buy:{mode}:{gp_id}:gift")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_donate")]
    ])

    await callback.message.edit_text(f"Кому вы хотите приобрести <b>{gp['title']}</b>?", reply_markup=kb)

@dp.callback_query(F.data.startswith("proc_buy:"))
async def cb_process_buy(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    mode, gp_id, target = parts[1], parts[2], parts[3]
    user_id = callback.from_user.id
    gp = GAMEPASSES[gp_id]

    if target == "gift":
        await state.update_data(gamepass_id=gp_id, currency_type=mode)
        await state.set_state(GiftState.target_user)
        return await callback.message.edit_text("🎁 Введите <b>Username</b> (@username) или <b>Telegram ID</b> получателя:")

    if mode == "buy_f2p":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT robux FROM users WHERE user_id = ?", (user_id,)) as cursor:
                robux = (await cursor.fetchone())[0]

            if robux < gp["robux"]:
                return await callback.answer(f"Недостаточно R$! Нужно: {gp['robux']}", show_alert=True)

            await db.execute("UPDATE users SET robux = robux - ? WHERE user_id = ?", (gp["robux"], user_id))
            await db.commit()

        await give_gamepass(user_id, gp_id)
        await callback.message.edit_text(f"🎉 Вы успешно купили <b>{gp['title']}</b>!")

    elif mode == "buy_p2w":
        prices = [LabeledPrice(label=gp["title"], amount=gp["stars"])]
        await bot.send_invoice(chat_id=user_id, title=gp['title'], description=gp["desc"], payload=f"self:{gp_id}:{user_id}", currency="XTR", prices=prices)

@dp.message(GiftState.target_user)
async def process_gift_target(message: types.Message, state: FSMContext):
    target_input = message.text.strip().replace("@", "")
    data = await state.get_data()
    gp_id = data["gamepass_id"]
    mode = data["currency_type"]
    gp = GAMEPASSES[gp_id]
    buyer_id = message.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        if target_input.isdigit():
            async with db.execute("SELECT user_id, username FROM users WHERE user_id = ?", (int(target_input),)) as cursor:
                target_row = await cursor.fetchone()
        else:
            async with db.execute("SELECT user_id, username FROM users WHERE LOWER(username) = LOWER(?)", (target_input,)) as cursor:
                target_row = await cursor.fetchone()

    if not target_row:
        await state.clear()
        return await message.answer("❌ Пользователь не найден!")

    target_id, target_name = target_row[0], target_row[1]

    if mode == "buy_f2p":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT robux FROM users WHERE user_id = ?", (buyer_id,)) as cursor:
                robux = (await cursor.fetchone())[0]

            if robux < gp["robux"]:
                await state.clear()
                return await message.answer("❌ Недостаточно R$!")

            await db.execute("UPDATE users SET robux = robux - ? WHERE user_id = ?", (gp["robux"], buyer_id))
            await db.commit()

        await give_gamepass(target_id, gp_id)
        await state.clear()
        await message.answer(f"🎁 Вы успешно подарили <b>{gp['title']}</b> игроку <b>{target_name}</b>!")

        try:
            await bot.send_message(chat_id=target_id, text=f"🎉 Игрок <b>@{message.from_user.username}</b> подарил вам геймпасс: <b>{gp['title']}</b>!")
        except Exception:
            pass

@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    parts = payload.split(":")
    gp_id, target_id = parts[1], int(parts[2])
    gp = GAMEPASSES[gp_id]
    await give_gamepass(target_id, gp_id)
    await message.answer(f"🎉 Оплата принята! Геймпасс <b>{gp['title']}</b> выдан!")

@dp.callback_query(F.data.startswith("menu_inventory"))
async def cb_inventory(callback: CallbackQuery):
    page = 0
    if ":" in callback.data:
        page = int(callback.data.split(":")[1])

    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT c.name, i.mutation, COUNT(*) as cnt, i.serial_number 
            FROM inventory i JOIN cards c ON i.card_id = c.card_id 
            WHERE i.user_id = ? GROUP BY c.name, i.mutation ORDER BY c.rarity DESC
        """, (user_id,)) as cursor:
            items = await cursor.fetchall()

    per_page = 50
    total_pages = math.ceil(len(items) / per_page) or 1
    page_items = items[page * per_page:(page + 1) * per_page]

    text = f"🎒 <b>ИНВЕНТАРЬ КАРТ (Стр. {page+1}/{total_pages})</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for item in page_items:
        mut = MUTATIONS.get(item[1], MUTATIONS["Normal"])["name"]
        ser_str = f" ({item[3]})" if item[3] else ""
        text += f"• {mut} {item[0]}{ser_str} — {item[2]} шт.\n"

    if not page_items:
        text += "<i>Инвентарь пуст...</i>"

    kb = []
    nav = []
    if page > 0: nav.append(InlineKeyboardButton(text="◀️ Пред", callback_data=f"menu_inventory:{page-1}"))
    if page < total_pages - 1: nav.append(InlineKeyboardButton(text="След ▶️", callback_data=f"menu_inventory:{page+1}"))
    if nav: kb.append(nav)

    kb.append([
        InlineKeyboardButton(text="🌱 Сид-паки", callback_data="menu_seeds"),
        InlineKeyboardButton(text="📦 Крейты", callback_data="menu_crates"),
        InlineKeyboardButton(text="🛡 Экипировка", callback_data="menu_equip")
    ])
    kb.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="menu_main")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "menu_seeds")
async def cb_seeds_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT pack_type, amount FROM seed_packs WHERE user_id = ?", (user_id,)) as cursor:
            packs = await cursor.fetchall()

    kb = []
    text = "🌱 <b>СИД-ПАКИ В ИНВЕНТАРЕ:</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for p in packs:
        text += f"• {p[0]}: <b>{p[1]} шт.</b>\n"
        kb.append([
            InlineKeyboardButton(text=f"Открыть 1 {p[0]}", callback_data=f"open_seed:1:{p[0]}"),
            InlineKeyboardButton(text=f"Открыть 10", callback_data=f"open_seed:10:{p[0]}")
        ])

    if not packs:
        text += "<i>У вас пока нет сид-паков. Выполняйте квесты!</i>"

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_inventory")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("open_seed:"))
async def cb_open_seed(callback: CallbackQuery):
    parts = callback.data.split(":")
    count, pack_type = int(parts[1]), parts[2]
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT amount FROM seed_packs WHERE user_id = ? AND pack_type = ?", (user_id, pack_type)) as cursor:
            row = await cursor.fetchone()

        if not row or row[0] < count:
            return await callback.answer("Недостаточно сид-паков!", show_alert=True)

        await db.execute("UPDATE seed_packs SET amount = amount - ? WHERE user_id = ? AND pack_type = ?", (count, user_id, pack_type))
        await db.commit()

    obtained = []
    for _ in range(count):
        card_res = await add_card_to_user(user_id)
        if card_res[0]:
            obtained.append(f"{card_res[0]} [{card_res[1]}]")

    msg = f"🎉 <b>Вы открыли {count}x {pack_type}!</b>\n\nВыпавшие карты:\n" + "\n".join([f"• {c}" for c in obtained])
    await callback.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ К сид-пакам", callback_data="menu_seeds")]]))

@dp.callback_query(F.data == "menu_crates")
async def cb_crates_menu(callback: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT crate_id, name, price, contents_json FROM crates") as cursor:
            crates = await cursor.fetchall()

    text = "📦 <b>МАГАЗИН И ИНВЕНТАРЬ КРЕЙТОВ</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
    kb = []
    for c in crates:
        text += f"• <b>{c[1]}</b> — Цена: {c[2]} Шекелей\n"
        kb.append([
            InlineKeyboardButton(text=f"Купить 1 ({c[2]} 🪙)", callback_data=f"buy_crate_amt:1:{c[0]}"),
            InlineKeyboardButton(text=f"Купить 10 ({c[2]*10} 🪙)", callback_data=f"buy_crate_amt:10:{c[0]}")
        ])

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("buy_crate_amt:"))
async def cb_buy_crate_amt(callback: CallbackQuery):
    parts = callback.data.split(":")
    count, crate_id = int(parts[1]), int(parts[2])
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, price, contents_json FROM crates WHERE crate_id = ?", (crate_id,)) as cursor:
            crate = await cursor.fetchone()

        if not crate: return await callback.answer("Крейт не найден!")

        total_cost = crate[1] * count
        async with db.execute("SELECT shekels FROM users WHERE user_id = ?", (user_id,)) as cursor:
            shekels = (await cursor.fetchone())[0]

        if shekels < total_cost:
            return await callback.answer(f"Недостаточно шекелей! Нужно: {total_cost}", show_alert=True)

        await db.execute("UPDATE users SET shekels = shekels - ? WHERE user_id = ?", (total_cost, user_id))
        await db.commit()

    results = []
    for _ in range(count):
        card_res = await add_card_to_user(user_id)
        if card_res[0]:
            mut_name = MUTATIONS.get(card_res[2], MUTATIONS["Normal"])["name"]
            results.append(f"{mut_name} {card_res[0]} [{card_res[1]}]")

    msg = f"🎉 <b>ВЫ ОТКРЫЛИ {count}x {crate[0]}!</b>\n\nВыпавшие карты:\n" + "\n".join([f"• {r}" for r in results])
    await callback.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад к крейтам", callback_data="menu_crates")]]))

@dp.callback_query(F.data == "menu_equip")
async def cb_equipment(callback: CallbackQuery):
    user_id = callback.from_user.id
    has_slot5 = await has_gamepass(user_id, "slot_5")

    kb = [
        [InlineKeyboardButton(text="Слот 1", callback_data="equip_slot:1"), InlineKeyboardButton(text="Слот 2", callback_data="equip_slot:2")],
        [InlineKeyboardButton(text="Слот 3", callback_data="equip_slot:3"), InlineKeyboardButton(text="Слот 4", callback_data="equip_slot:4")]
    ]
    if has_slot5:
        kb.append([InlineKeyboardButton(text="🌟 Слот 5 (Геймпасс)", callback_data="equip_slot:5")])

    kb.append([InlineKeyboardButton(text="❌ Снять всё", callback_data="equip_clear")])
    kb.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="menu_main")])

    await callback.message.edit_text("🛡 Выберите слот для установки карты:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("equip_slot:"))
async def cb_equip_select_slot(callback: CallbackQuery):
    slot = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT i.item_id, c.name, i.mutation, c.rarity, i.serial_number 
            FROM inventory i JOIN cards c ON i.card_id = c.card_id 
            WHERE i.user_id = ? AND i.is_equipped = 0 LIMIT 15
        """, (user_id,)) as cursor:
            items = await cursor.fetchall()

    kb = []
    for item in items:
        mut = MUTATIONS.get(item[2], MUTATIONS["Normal"])["name"]
        ser_str = f" ({item[4]})" if item[4] else ""
        kb.append([InlineKeyboardButton(text=f"{mut} {item[1]}{ser_str} [{item[3]}]", callback_data=f"set_equip:{item[0]}:{slot}")])

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_equip")])
    await callback.message.edit_text(f"Выберите карту для <b>Слота {slot}</b>:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("set_equip:"))
async def cb_set_equip(callback: CallbackQuery):
    parts = callback.data.split(":")
    item_id, slot = int(parts[1]), int(parts[2])
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE inventory SET is_equipped = 0, equip_slot = 0 WHERE user_id = ? AND equip_slot = ?", (user_id, slot))
        await db.execute("UPDATE inventory SET is_equipped = 1, equip_slot = ? WHERE item_id = ? AND user_id = ?", (slot, item_id, user_id))
        await db.commit()

    await callback.answer("Карта экипирована!")
    await cb_equipment(callback)

@dp.callback_query(F.data == "equip_clear")
async def cb_equip_clear(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE inventory SET is_equipped = 0, equip_slot = 0 WHERE user_id = ?", (user_id,))
        await db.commit()
    await callback.answer("Вся экипировка снята!")
    await cb_equipment(callback)

@dp.callback_query(F.data.startswith("menu_index"))
async def cb_index(callback: CallbackQuery):
    page = 0
    if ":" in callback.data:
        page = int(callback.data.split(":")[1])

    user_id = callback.from_user.id
    per_page = 8

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT card_id, name, rarity, damage, hp, is_hidden_index FROM cards WHERE is_hidden_index = 0 ORDER BY card_id ASC") as cursor:
            all_cards = await cursor.fetchall()

        async with db.execute("SELECT DISTINCT card_id FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
            unlocked_ids = [r[0] for r in await cursor.fetchall()]

    total_pages = math.ceil(len(all_cards) / per_page) or 1
    page_cards = all_cards[page * per_page:(page + 1) * per_page]

    text = f"📖 <b>ОСНОВНОЙ ИНДЕКС КАРТ (Стр. {page+1}/{total_pages})</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"

    async with aiosqlite.connect(DB_PATH) as db:
        for idx, c in enumerate(page_cards, start=page * per_page + 1):
            c_id, name, rarity, dmg, hp, _ = c
            async with db.execute("SELECT COUNT(*), SUM(CASE WHEN mutation='Gold' THEN 1 ELSE 0 END), SUM(CASE WHEN mutation='Rainbow' THEN 1 ELSE 0 END) FROM inventory WHERE card_id=?", (c_id,)) as cur2:
                st = await cur2.fetchone()
                total_exist, g_exist, r_exist = st[0] or 0, st[1] or 0, st[2] or 0

            if c_id in unlocked_ids:
                text += f"{idx}. 🃏 <b>{name}</b>\n   └  <b>{rarity}</b>\n   └ Урон: {dmg} // Здоровье: {hp}\n   └ Существует: {total_exist} шт. (Золотых: {g_exist}, Радужных: {r_exist})\n\n"
            else:
                text += f"{idx}. ❓ <b>??? (Не открыто)</b>\n   └  <b>{rarity}</b>\n   └ Существует: {total_exist} шт. (Золотых: {g_exist}, Радужных: {r_exist})\n\n"

    kb = []
    nav = []
    if page > 0: nav.append(InlineKeyboardButton(text="◀️ Пред", callback_data=f"menu_index:{page-1}"))
    if page < total_pages - 1: nav.append(InlineKeyboardButton(text="След ▶️", callback_data=f"menu_index:{page+1}"))
    if nav: kb.append(nav)
    kb.append([InlineKeyboardButton(text="⬅️ Главное меню", callback_data="menu_main")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "menu_top")
async def cb_top_leaderboard(callback: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT username, trophies FROM users ORDER BY trophies DESC LIMIT 20") as cursor:
            top_users = await cursor.fetchall()

        async with db.execute("SELECT tier, reward_desc FROM top_rewards") as cursor:
            rewards = await cursor.fetchall()

    text = "🏆 <b>ТОП-20 ИГРОКОВ ПО ТРОФЕЯМ</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for idx, u in enumerate(top_users, start=1):
        u_name = u[0] or f"Игрок #{idx}"
        rank_name = get_rank_by_trophies(u[1])
        text += f"{idx}. <b>{u_name}</b> — 🏆 {u[1]} кубков [{rank_name}]\n"

    text += "\n━━━━━━━━━━━━━━━━━━━━━━━━\n🎁 <b>НАГРАДЫ ЗА ТОП (Выдача раз в 3 дня):</b>\n"
    if rewards:
        for r in rewards:
            text += f"• <b>{r[0]}:</b> {r[1]}\n"
    else:
        text += "<i>1 место: 1000 Шекелей | 2 место: 500 Шекелей | 3 место: 250 Шекелей</i>"

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]]))

@dp.callback_query(F.data == "menu_skills")
async def cb_skills_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT points FROM skills WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            pts = row[0] if row else 0

    if pts == 0:
        return await callback.answer("У вас нет свободных очков навыков! Сражайтесь на Арене.", show_alert=True)

    kb = []
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT i.item_id, c.name, i.hp_pts, i.dmg_pts, i.cld_pts 
            FROM inventory i JOIN cards c ON i.card_id = c.card_id 
            WHERE i.user_id = ? AND i.is_equipped = 1 ORDER BY i.equip_slot
        """, (user_id,)) as cursor:
            equipped = await cursor.fetchall()
            for eq in equipped:
                kb.append([InlineKeyboardButton(text=f"✨ {eq[1]} (Сумма: {eq[2]+eq[3]+eq[4]})", callback_data=f"skill_card:{eq[0]}")])

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")])
    await callback.message.edit_text(
        f"✨ Свободно очков: <b>{pts}</b>\nВыберите экипированную карту для распределения:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

@dp.callback_query(F.data.startswith("skill_card:"))
async def cb_skill_show(callback: CallbackQuery):
    item_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT i.hp_pts, i.dmg_pts, i.cld_pts, c.name 
            FROM inventory i JOIN cards c ON i.card_id = c.card_id 
            WHERE i.item_id = ? AND i.user_id = ?
        """, (item_id, user_id)) as cursor:
            card_data = await cursor.fetchone()

        async with db.execute("SELECT points FROM skills WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            skill_pts = row[0] if row else 0

    if not card_data:
        return await callback.answer("Карта не найдена!")

    hp_p, dmg_p, cld_p, name = card_data
    img_bytes = generate_skill_panel(hp_p, dmg_p, cld_p, skill_pts, card_name=name)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="HP [x1]", callback_data=f"add_sk:{item_id}:hp:1"), InlineKeyboardButton(text="HP [x5]", callback_data=f"add_sk:{item_id}:hp:5"), InlineKeyboardButton(text="HP [x10]", callback_data=f"add_sk:{item_id}:hp:10"), InlineKeyboardButton(text="HP [max]", callback_data=f"add_sk:{item_id}:hp:100")],
        [InlineKeyboardButton(text="DMG [x1]", callback_data=f"add_sk:{item_id}:dmg:1"), InlineKeyboardButton(text="DMG [x5]", callback_data=f"add_sk:{item_id}:dmg:5"), InlineKeyboardButton(text="DMG [x10]", callback_data=f"add_sk:{item_id}:dmg:10"), InlineKeyboardButton(text="DMG [max]", callback_data=f"add_sk:{item_id}:dmg:100")],
        [InlineKeyboardButton(text="CLD [x1]", callback_data=f"add_sk:{item_id}:cld:1"), InlineKeyboardButton(text="CLD [x5]", callback_data=f"add_sk:{item_id}:cld:5"), InlineKeyboardButton(text="CLD [x10]", callback_data=f"add_sk:{item_id}:cld:10"), InlineKeyboardButton(text="CLD [max]", callback_data=f"add_sk:{item_id}:cld:100")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_skills")]
    ])

    await callback.message.delete()
    await bot.send_photo(
        chat_id=callback.message.chat.id,
        photo=BufferedInputFile(img_bytes, filename="skills.jpg"),
        caption=f"🎯 <b>Очки навыков — {name}</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\nСвободных очков: <b>{skill_pts}</b>",
        reply_markup=kb
    )

@dp.callback_query(F.data.startswith("add_sk:"))
async def cb_add_skill(callback: CallbackQuery):
    parts = callback.data.split(":")
    item_id, stat, requested_amt = int(parts[1]), parts[2], int(parts[3])
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT points FROM skills WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            avail_pts = row[0] if row else 0

        col = "hp_pts" if stat == "hp" else ("dmg_pts" if stat == "dmg" else "cld_pts")
        async with db.execute(f"SELECT {col} FROM inventory WHERE item_id = ?", (item_id,)) as cursor:
            curr_val = (await cursor.fetchone())[0]

        max_addable = max(0, 100 - curr_val)
        actual_add = min(avail_pts, requested_amt, max_addable)

        if actual_add <= 0:
            return await callback.answer("Максимум 100 очков на стат или недостаточно очков!", show_alert=True)

        await db.execute(f"UPDATE inventory SET {col} = {col} + ? WHERE item_id = ?", (actual_add, item_id))
        await db.execute("UPDATE skills SET points = points - ? WHERE user_id = ?", (actual_add, user_id))
        await db.commit()

    await callback.answer(f"Добавлено +{actual_add} к {stat.upper()}!")
    await cb_skill_show(callback)

@dp.callback_query(F.data == "menu_battle")
async def cb_battle_menu(callback: CallbackQuery):
    await callback.message.edit_text("⚔️ <b>ПОИСК БОЯ НА АРЕНЕ</b>\nВыберите сложность соперника:", reply_markup=battle_difficulty_kb())

@dp.callback_query(F.data.startswith("battle_start_"))
async def process_battle(callback: CallbackQuery):
    difficulty = callback.data.split("_")[2]
    user_id = callback.from_user.id

    team_player = []
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT c.name, c.damage, c.hp, c.cooldown, c.card_class, i.mutation, i.hp_pts, i.dmg_pts, i.cld_pts
            FROM inventory i JOIN cards c ON i.card_id = c.card_id 
            WHERE i.user_id = ? AND i.is_equipped = 1 ORDER BY i.equip_slot
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            for r in rows:
                mut_buff = MUTATIONS.get(r[5], MUTATIONS["Normal"])["buff"]
                hp_mult = 1.0 + (r[6] * 0.05)
                dmg_mult = 1.0 + (r[7] * 0.05)
                cld_mult = max(0.1, 1.0 - (r[8] * 0.05))

                f_hp = int(r[2] * mut_buff * hp_mult)
                f_dmg = int(r[1] * mut_buff * dmg_mult)
                f_cld = max(0.04, r[3] * cld_mult)

                team_player.append({
                    "name": r[0], "base_hp": f_hp, "hp": f_hp, "dmg": f_dmg,
                    "cld": f_cld, "class": r[4], "next_attack": f_cld, "owner": "player"
                })

    if not team_player:
        return await callback.answer("У вас нет экипированных карт!", show_alert=True)

    await callback.message.edit_text("⏳ <b>ПОИСК СОПЕРНИКА... (3 сек)</b>")
    await asyncio.sleep(3)

    stats = await get_user_stats(user_id)
    rank = get_rank_by_trophies(stats[2])
    base_rank_group = rank.split()[0]

    allowed_rarities = AI_MATCHING_TABLE.get(difficulty, {}).get(base_rank_group, ["Basic", "Uncommon"])

    team_ai = []
    async with aiosqlite.connect(DB_PATH) as db:
        placeholders = ",".join(["?"] * len(allowed_rarities))
        async with db.execute(f"SELECT name, damage, hp, cooldown, card_class FROM cards WHERE is_banned_ai = 0 AND rarity IN ({placeholders}) ORDER BY RANDOM() LIMIT ?", (*allowed_rarities, len(team_player))) as cursor:
            ai_rows = await cursor.fetchall()

            for r in ai_rows:
                team_ai.append({
                    "name": f"Враг {r[0]}", "base_hp": r[2], "hp": r[2], "dmg": r[1],
                    "cld": r[3], "class": r[4], "next_attack": r[3], "owner": "ai"
                })

    if not team_ai:
        team_ai = [{"name": "Тренировочный Бот", "base_hp": 200, "hp": 200, "dmg": 30, "cld": 2.0, "class": "Single", "next_attack": 2.0, "owner": "ai"}]

    log = []
    time_passed = 0.0
    max_time = 60.0
    all_units = team_player + team_ai

    while time_passed < max_time and any(u["hp"] > 0 for u in team_player) and any(u["hp"] > 0 for u in team_ai):
        alive_units = [u for u in all_units if u["hp"] > 0]
        next_unit = min(alive_units, key=lambda x: x["next_attack"])
        time_passed = next_unit["next_attack"]

        enemies = team_ai if next_unit["owner"] == "player" else team_player
        alive_enemies = [e for e in enemies if e["hp"] > 0]

        if not alive_enemies: break

        target = random.choice(alive_enemies)

        if next_unit["class"] == "Single":
            target["hp"] -= next_unit["dmg"]
            log.append(f"⚔️ {next_unit['name']} бьет {target['name']} на {next_unit['dmg']}!")
        elif next_unit["class"] == "Splash":
            target["hp"] -= next_unit["dmg"]
            for e in alive_enemies:
                if e != target: e["hp"] -= int(next_unit["dmg"] * 0.5)
            log.append(f"💥 {next_unit['name']} сплеш по {target['name']} на {next_unit['dmg']}!")
        elif next_unit["class"] == "AOE":
            for e in alive_enemies: e["hp"] -= next_unit["dmg"]
            log.append(f"🔥 {next_unit['name']} АОЕ по всем на {next_unit['dmg']}!")
        else:
            target["hp"] -= next_unit["dmg"]
            log.append(f"⚔️ {next_unit['name']} бьет {target['name']} на {next_unit['dmg']}!")

        next_unit["next_attack"] += next_unit["cld"]

    player_won = any(u["hp"] > 0 for u in team_player)

    r_data = RANKS[rank]
    base_trop = random.randint(r_data["trophies"][0], r_data["trophies"][1])
    base_shek = random.randint(r_data["shekels"][0], r_data["shekels"][1])

    if difficulty == "easy": base_trop = int(base_trop * 0.5)
    elif difficulty == "hard": base_trop = int(base_trop * 1.3)
    elif difficulty == "nightmare": base_trop = int(base_trop * 1.8)

    sp_chances = {"easy": 0.1, "medium": 0.2, "hard": 0.35, "nightmare": 0.5}
    skill_pts = 0
    if random.random() < sp_chances[difficulty]:
        skill_pts = 1 if difficulty in ["easy", "medium"] else (2 if difficulty == "hard" else 3)

    if not player_won:
        base_trop = -int(base_trop * 0.3)
        base_shek = 1
        skill_pts = 0
        res_title = "❌ ПОРАЖЕНИЕ"
    else:
        res_title = "🏆 ПОБЕДА"

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET trophies = MAX(0, trophies + ?), shekels = shekels + ? WHERE user_id = ?", (base_trop, base_shek, user_id))
        if skill_pts > 0:
            await db.execute("INSERT INTO skills (user_id, points) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET points = points + ?", (user_id, skill_pts, skill_pts))
        await db.commit()

    p_team_str = "\n".join([f"• {u['name']} ({u['dmg']} | {max(0, u['hp'])}/{u['base_hp']})" for u in team_player])
    ai_team_str = "\n".join([f"• {u['name']} ({u['dmg']} | {max(0, u['hp'])}/{u['base_hp']})" for u in team_ai])
    log_str = "\n".join(log[-6:])

    msg = (
        f"⚔️ <b>АРЕНА: БИТВА ({res_title})</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Команда {stats[5]}:</b>\n{p_team_str}\n\n"
        f"<b>Команда AI ({difficulty}):</b>\n{ai_team_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📜 <b>Лог боя:</b>\n{log_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 <b>Награды:</b>\n🏆 Трофеи: <b>{base_trop}</b> | 🪙 Шекели: <b>+{base_shek}</b>\n"
    )
    if skill_pts > 0: msg += f"✨ Очки навыков: <b>+{skill_pts}</b>\n"

    await callback.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")]]))

@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery):
    if not await check_is_admin(callback.from_user.id):
        return await callback.answer("Отказано в доступе!", show_alert=True)
    await callback.message.edit_text("⚙️ <b>АДМИНИСТРАТИВНАЯ ПАНЕЛЬ</b>", reply_markup=admin_panel_kb())

@dp.callback_query(F.data == "admin_cards")
async def cb_admin_cards(callback: CallbackQuery):
    if not await check_is_admin(callback.from_user.id): return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать карту", callback_data="admin_create_card")],
        [InlineKeyboardButton(text="🗑 Удалить карту", callback_data="admin_delete_card")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")]
    ])
    await callback.message.edit_text("🃏 <b>Управление картами</b>", reply_markup=kb)

@dp.callback_query(F.data == "admin_create_card")
async def create_card_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CardCreation.photo)
    await callback.message.edit_text("Отправьте фото для новой карты (как изображение):")

@dp.message(CardCreation.photo, F.photo)
async def create_card_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await state.set_state(CardCreation.name)
    await message.answer("Введите название новой карты:")

@dp.message(CardCreation.name)
async def create_card_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=r, callback_data=f"set_rarity:{r}") for r in list(RARITY_COLORS.keys())[i:i+3]]
        for i in range(0, len(RARITY_COLORS), 3)
    ])
    await state.set_state(CardCreation.rarity)
    await message.answer("Выберите редкость карты:", reply_markup=kb)

@dp.callback_query(CardCreation.rarity, F.data.startswith("set_rarity:"))
async def create_card_rarity(callback: CallbackQuery, state: FSMContext):
    rarity = callback.data.split(":")[1]
    await state.update_data(rarity=rarity)
    classes = ["Single", "Splash", "AOE", "Booster", "Fire"]
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=c, callback_data=f"set_class:{c}")] for c in classes])
    await state.set_state(CardCreation.c_class)
    await callback.message.edit_text("Выберите класс карты:", reply_markup=kb)

@dp.callback_query(CardCreation.c_class, F.data.startswith("set_class:"))
async def create_card_class(callback: CallbackQuery, state: FSMContext):
    c_class = callback.data.split(":")[1]
    await state.update_data(c_class=c_class)
    await state.set_state(CardCreation.damage)
    await callback.message.edit_text("Введите Урон (число):")

@dp.message(CardCreation.damage)
async def create_card_dmg(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Введите число!")
    await state.update_data(damage=int(message.text))
    await state.set_state(CardCreation.hp)
    await message.answer("Введите Здоровье (число):")

@dp.message(CardCreation.hp)
async def create_card_hp(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Введите число!")
    await state.update_data(hp=int(message.text))
    await state.set_state(CardCreation.cooldown)
    await message.answer("Введите кулдаун в секундах (например 1.5):")

@dp.message(CardCreation.cooldown)
async def create_card_cld(message: types.Message, state: FSMContext):
    try: cld = float(message.text)
    except ValueError: return await message.answer("Введите число!")

    await state.update_data(cooldown=cld)
    data = await state.get_data()

    file = await bot.get_file(data['photo_id'])
    photo_bytes = await bot.download_file(file.file_path)
    framed_photo = generate_card_frame(photo_bytes.read(), data['rarity'])

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO cards (name, rarity, card_class, damage, hp, cooldown, photo_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (data['name'], data['rarity'], data['c_class'], data['damage'], data['hp'], data['cooldown'], data['photo_id']))
        await db.commit()

    await state.clear()
    await message.answer_photo(
        photo=BufferedInputFile(framed_photo, filename="card.png"),
        caption=f"✅ Карта <b>{data['name']}</b> [{data['rarity']}] успешно создана!",
        reply_markup=admin_panel_kb()
    )

@dp.callback_query(F.data == "admin_players")
async def cb_admin_players(callback: CallbackQuery):
    if not await check_is_admin(callback.from_user.id): return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏆 Выдать кубки", callback_data="adm_p:trophies"), InlineKeyboardButton(text="🪙 Выдать шекели", callback_data="adm_p:shekels")],
        [InlineKeyboardButton(text="🚫 Бан/Разбан", callback_data="adm_p:ban")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel")]
    ])
    await callback.message.edit_text("👥 <b>Управление игроками</b>", reply_markup=kb)

@dp.callback_query(F.data == "admin_backup")
async def cb_admin_backup(callback: CallbackQuery):
    if not await check_is_admin(callback.from_user.id): return
    if os.path.exists(DB_PATH):
        await callback.message.answer_document(FSInputFile(DB_PATH), caption="💾 Файл базы данных бота.")
    else:
        await callback.answer("Файл БД не найден!", show_alert=True)

async def setup_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="🏠 Главное меню"),
        BotCommand(command="afk", description="⏳ AFK Экспедиция"),
        BotCommand(command="donate", description="💎 Донат Магазин"),
        BotCommand(command="profile", description="👤 Мой профиль"),
        BotCommand(command="inventory", description="🎒 Мой инвентарь"),
        BotCommand(command="help", description="📖 Справка по командам")
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())

async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()
    await setup_bot_commands(bot)
    logging.info("Бот успешно запущен! Меню команд обновлено.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
