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
    BufferedInputFile, LabeledPrice, PreCheckoutQuery, Message
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

import aiosqlite
from PIL import Image, ImageDraw, ImageFont, ImageOps

BOT_TOKEN = "8949953502:AAGwrEWWVST3yXRNA57yLWl8RXDdmr9WRQs"  # Замените при необходимости
ADMIN_IDS = [5341904332]  # Список ID администраторов

DB_PATH = "game_database.db"

# Цвета редкостей для рамок карт
RARITY_COLORS = {
    "Basic": (128, 128, 128),       # Серый
    "Uncommon": (0, 255, 0),        # Зеленый
    "Rare": (0, 191, 255),          # Голубой
    "Epic": (128, 0, 128),          # Фиолетовый
    "Legendary": (255, 215, 0),     # Жёлтый
    "Mythic": (255, 0, 0),          # Красный
    "Super": (255, 0, 255),         # Пурпурный/Радужный
    "Secret": (0, 0, 0),            # Чёрный
    "Exclusive": (255, 105, 180),   # Розовый
    "Leaderboard": (218, 165, 32)   # Золотой
}

# Мутации карт
MUTATIONS = {
    "Normal": {"chance": 0.88, "buff": 1.0, "name": "Обычная"},
    "Gold": {"chance": 0.10, "buff": 1.15, "name": "✨ Золотая"},
    "Rainbow": {"chance": 0.02, "buff": 1.30, "name": "🌈 Радужная"}
}

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
        "desc": "Открывает 5-й слот для установки юнита в бой!",
        "robux": 99,
        "stars": 49
    },
    "vip": {
        "title": "👑 VIP Статус",
        "desc": "x1.5 Шекели, x1.3 Удача карт, +5% к Очкам навыков, 4 слота в AFK режимах и специальный значок!",
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
            is_hidden_index INTEGER DEFAULT 0
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

        await db.execute('''CREATE TABLE IF NOT EXISTS skills (
            user_id INTEGER PRIMARY KEY,
            points INTEGER DEFAULT 0
        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS user_gamepasses (
            user_id INTEGER,
            gamepass_id TEXT,
            PRIMARY KEY (user_id, gamepass_id)
        )''')

        # Таблица для AFK экспедиций
        await db.execute('''CREATE TABLE IF NOT EXISTS afk_expeditions (
            user_id INTEGER PRIMARY KEY,
            cards_json TEXT,
            duration_hours INTEGER,
            start_time TEXT,
            end_time TEXT,
            claimed INTEGER DEFAULT 0
        )''')

        async with db.execute("SELECT COUNT(*) FROM cards") as cursor:
            count = (await cursor.fetchone())[0]
            if count == 0:
                await db.execute("""
                    INSERT INTO cards (name, rarity, card_class, damage, hp, cooldown, photo_id)
                    VALUES ('Стартовый Шрекс', 'Basic', 'Single', 25, 100, 2.0, '')
                """)

        await db.commit()

def get_rank_by_trophies(trophies: int) -> str:
    for rank, data in RANKS.items():
        if data["min"] <= trophies <= data["max"]:
            return rank
    return "Ultimate I"

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

def generate_skill_panel(hp_pts: int, dmg_pts: int, cld_pts: int, available_pts: int, card_name: str = "Карта") -> bytes:
    width, height = 550, 320
    img = Image.new('RGB', (width, height), color=(24, 28, 36))
    draw = ImageDraw.Draw(img)

    try:
        font_large = ImageFont.truetype("arial.ttf", 24)
        font_medium = ImageFont.truetype("arial.ttf", 18)
        font_small = ImageFont.truetype("arial.ttf", 14)
    except IOError:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()

    draw.rectangle([10, 10, width-10, height-10], outline=(255, 140, 0), width=3)
    draw.text((30, 20), f"⚡️ ПРОКАЧКА: {card_name[:20]}", fill=(255, 200, 50), font=font_large)
    draw.text((30, 55), f"Свободных очков навыков: {available_pts}", fill=(50, 255, 150), font=font_medium)

    stats = [
        ("❤️ Здоровье (HP)", hp_pts, (255, 70, 70), 100),
        ("⚔️ Урон (DMG)", dmg_pts, (255, 170, 0), 160),
        ("⚡️ Перезарядка (CLD)", cld_pts, (70, 170, 255), 220)
    ]

    for name, pts, color, y in stats:
        draw.text((30, y), name, fill=color, font=font_medium)
        bonus = f"-{pts * 5}% кд" if "CLD" in name else f"+{pts * 5}% стат"
        draw.text((250, y), bonus, fill=(220, 220, 220), font=font_small)

        bar_x = 350
        draw.rectangle([bar_x, y + 2, bar_x + 120, y + 18], fill=(40, 45, 55), outline=(100, 100, 110))
        fill_w = int(120 * (pts / 100.0))
        if fill_w > 0:
            draw.rectangle([bar_x, y + 2, bar_x + min(fill_w, 120), y + 18], fill=color)

        draw.text((480, y), f"{pts}/100", fill=(180, 180, 180), font=font_small)

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

class ExchangeState(StatesGroup):
    amount = State()

class GiftState(StatesGroup):
    gamepass_id = State()
    currency_type = State()
    target_user = State()

class AFKState(StatesGroup):
    selecting_cards = State()

def main_menu_kb(is_admin=False):
    kb = [
        [InlineKeyboardButton(text="🎁 Ежедневные награды", callback_data="menu_daily"), InlineKeyboardButton(text="💎 Донат Магазин", callback_data="menu_donate")],
        [InlineKeyboardButton(text="⏳ AFK Экспедиция", callback_data="menu_afk"), InlineKeyboardButton(text="⚔️ Поиск боя", callback_data="menu_battle")],
        [InlineKeyboardButton(text="📦 Крейты", callback_data="menu_crates"), InlineKeyboardButton(text="🏆 Топ игроков", callback_data="menu_top")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile"), InlineKeyboardButton(text="✨ Очки навыков", callback_data="menu_skills")],
        [InlineKeyboardButton(text="🎒 Инвентарь", callback_data="menu_inventory"), InlineKeyboardButton(text="📖 Индекс", callback_data="menu_index")],
        [InlineKeyboardButton(text="🛡 Экипировка", callback_data="menu_equip")]
    ]
    if is_admin:
        kb.append([InlineKeyboardButton(text="⚙️ Админ панель", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def donate_main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обменять Шекели ➡️ Робуксы", callback_data="donate_exchange")],
        [InlineKeyboardButton(text="🛒 F2P Магазин (Робуксы R$)", callback_data="donate_f2p")],
        [InlineKeyboardButton(text="🌟 P2W Магазин (Telegram Stars)", callback_data="donate_p2w")],
        [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="menu_main")]
    ])

def admin_panel_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🃏 Карты", callback_data="admin_cards"), InlineKeyboardButton(text="👥 Игроки", callback_data="admin_players")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ])

def battle_difficulty_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Лёгкий (-50% трофеев)", callback_data="battle_start_easy")],
        [InlineKeyboardButton(text="🟡 Средний (Базовые награды)", callback_data="battle_start_medium")],
        [InlineKeyboardButton(text="🔴 Сложный (+30% трофеев)", callback_data="battle_start_hard")],
        [InlineKeyboardButton(text="💀 КОШМАР (+80% трофеев)", callback_data="battle_start_nightmare")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ])

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

        async with db.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            is_admin = bool(res[0]) if res else (user_id in ADMIN_IDS)

    text = (
        f"👋 Привет, <b>{username}</b>!\n\n"
        f"Добро пожаловать в карточную арену <b>Card Battle Bot</b>!\n"
        f"Собирайте редкие карты, прокачивайте навыки, отправляйте отряды в AFK-экспедиции и сражайтесь на арене!"
    )
    await message.answer(text, reply_markup=main_menu_kb(is_admin))

@dp.callback_query(F.data == "menu_main")
async def cb_menu_main(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            is_admin = bool(res[0]) if res else (user_id in ADMIN_IDS)
    await callback.message.edit_text("Главное меню:", reply_markup=main_menu_kb(is_admin))

@dp.callback_query(F.data == "menu_profile")
async def cb_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    stats = await get_user_stats(user_id)
    if not stats:
        return await callback.answer("Ошибка загрузки профиля!")

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
            SELECT c.name, i.mutation, c.rarity, i.hp_pts, i.dmg_pts, i.cld_pts, i.equip_slot
            FROM inventory i JOIN cards c ON i.card_id = c.card_id 
            WHERE i.user_id = ? AND i.is_equipped = 1 ORDER BY i.equip_slot
        """, (user_id,)) as cursor:
            equipped = await cursor.fetchall()
            for eq in equipped:
                mut = MUTATIONS.get(eq[1], MUTATIONS["Normal"])["name"]
                equipped_text += f"• Слот {eq[6]}: {mut} {eq[0]} [{eq[2]}] (Очки: {eq[3]+eq[4]+eq[5]})\n"

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
        f"🔮 <b>Гарант Мифик:</b> {pity_m}/1000\n"
        f"🌈 <b>Гарант Супер:</b> {pity_s}/10000\n"
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

    text = "🎁 <b>ЕЖЕДНЕВНЫЕ НАГРАДЫ</b>\nЗаходите каждый день и получайте ценные призы!\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
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
            # Награда готова!
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎁 Забрать награду!", callback_data="afk_claim_reward")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
            ])
            await callback.message.edit_text(
                f"🎉 <b>AFK Экспедиция завершена!</b>\n"
                f"Ваш отряд успешно вернулся из похода на <b>{duration_h} ч.</b>!\n"
                f"Заберите заслуженные шекели и очки навыков!",
                reply_markup=kb
            )
        else:
            # Экспедиция ещё идёт
            rem = end_time - now
            rem_h, rem_m = rem.seconds // 3600, (rem.seconds % 3600) // 60
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Досрочно отменить", callback_data="afk_cancel")],
                [InlineKeyboardButton(text="🔄 Обновить статус", callback_data="menu_afk")],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
            ])
            await callback.message.edit_text(
                f"⏳ <b>AFK Экспедиция в процессе...</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏱ Длительность: <b>{duration_h} часов</b>\n"
                f"⏳ Осталось времени: <b>{rem_h} ч. {rem_m} мин.</b>\n\n"
                f"<i>Пока идёт экспедиция, ваш отряд ищет сокровища!</i>",
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
            f"⏳ <b>AFK ЭКСПЕДИЦИИ</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Отправляйте юнитов в автоматические походы и получайте награды!\n\n"
            f"• Слотов для карт: <b>{max_afk_cards} шт.</b> {'👑 (VIP)' if is_vip else '(Купите VIP для 4 слотов)'}\n"
            f"• Варианты походов: <b>2, 4, 6, 10 или 24 часа</b>\n"
            f"• Награды: <b>1 — 500 шекелей</b> 🪙 и <b>1 — 35 очков навыков</b> ✨ (в зависимости от силы отряда и времени)!",
            reply_markup=kb
        )

@dp.callback_query(F.data == "afk_setup_cards")
async def cb_afk_setup_cards(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    is_vip = await has_gamepass(user_id, "vip")
    max_slots = 4 if is_vip else 3

    # Выбираем доступные карты
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT i.item_id, c.name, i.mutation, c.rarity, c.damage, c.hp
            FROM inventory i JOIN cards c ON i.card_id = c.card_id
            WHERE i.user_id = ? LIMIT 20
        """, (user_id,)) as cursor:
            items = await cursor.fetchall()

    if not items:
        return await callback.answer("У вас нет карт для отправки в экспедицию!", show_alert=True)

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
    data = await state.get_data()
    selected = data.get("selected_cards", [])

    if not selected:
        return await callback.answer("Выберите хотя бы одну карту!", show_alert=True)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏱ 2 Часа", callback_data="afk_start_exp:2"), InlineKeyboardButton(text="⏱ 4 Часа", callback_data="afk_start_exp:4")],
        [InlineKeyboardButton(text="⏱ 6 Часов", callback_data="afk_start_exp:6"), InlineKeyboardButton(text="⏱ 10 Часов", callback_data="afk_start_exp:10")],
        [InlineKeyboardButton(text="🌟 24 Часа (Макс. награды)", callback_data="afk_start_exp:24")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="afk_setup_cards")]
    ])

    await callback.message.edit_text("⏱ Выберите время экспедиции:", reply_markup=kb)

@dp.callback_query(AFKState.selecting_cards, F.data.startswith("afk_start_exp:"))
async def cb_afk_start_expedition(callback: CallbackQuery, state: FSMContext):
    hours = int(callback.data.split(":")[1])
    data = await state.get_data()
    selected = data.get("selected_cards", [])
    user_id = callback.from_user.id

    start_time = datetime.utcnow()
    end_time = start_time + timedelta(hours=hours)

    start_str = start_time.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end_time.strftime("%Y-%m-%d %H:%M:%S")

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO afk_expeditions (user_id, cards_json, duration_hours, start_time, end_time, claimed)
            VALUES (?, ?, ?, ?, ?, 0) ON CONFLICT(user_id) DO UPDATE SET
            cards_json=excluded.cards_json, duration_hours=excluded.duration_hours,
            start_time=excluded.start_time, end_time=excluded.end_time, claimed=0
        """, (user_id, json.dumps(selected), hours, start_str, end_str))
        await db.commit()

    await state.clear()
    await callback.message.edit_text(
        f"🚀 <b>ОТРЯД ОТПРАВЛЕН В ЭКСПЕДИЦИЮ!</b>\n\n"
        f"⏱ Время: <b>{hours} часов</b>\n"
        f"🎴 Карты в отряде: <b>{len(selected)} шт.</b>\n\n"
        f"Возвращайтесь через {hours} ч., чтобы забрать сокровища!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ К меню AFK", callback_data="menu_afk")]])
    )

@dp.callback_query(F.data == "afk_claim_reward")
async def cb_afk_claim_reward(callback: CallbackQuery):
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT cards_json, duration_hours, end_time FROM afk_expeditions WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

        if not row:
            return await callback.answer("У вас нет активной экспедиции!")

        cards_json, duration_h, end_str = row
        card_ids = json.loads(cards_json)

        # Считаем силу отряда
        total_power = 0
        if card_ids:
            placeholders = ",".join(["?"] * len(card_ids))
            async with db.execute(f"SELECT c.damage, c.hp FROM inventory i JOIN cards c ON i.card_id = c.card_id WHERE i.item_id IN ({placeholders})", card_ids) as cursor:
                for r in await cursor.fetchall():
                    total_power += r[0] + (r[1] // 5)

        # Расчет наград (от 1 до 500 шекелей, от 1 до 35 очков навыков)
        time_ratio = min(1.0, duration_h / 24.0)
        power_ratio = min(1.0, total_power / 300.0)
        combined_factor = (time_ratio * 0.6) + (power_ratio * 0.4)

        shekels_won = max(1, min(500, int(1 + combined_factor * 499)))
        skills_won = max(1, min(35, int(1 + combined_factor * 34)))

        is_vip = await has_gamepass(user_id, "vip")
        if is_vip:
            shekels_won = int(shekels_won * 1.5)

        has_x2_shek = await has_gamepass(user_id, "x2_shekels")
        if has_x2_shek:
            shekels_won *= 2

        has_x2_sk = await has_gamepass(user_id, "x2_skills")
        if has_x2_sk:
            skills_won *= 2

        # Начисляем награды
        await db.execute("UPDATE users SET shekels = shekels + ? WHERE user_id = ?", (shekels_won, user_id))
        await db.execute("INSERT INTO skills (user_id, points) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET points = points + ?", (user_id, skills_won, skills_won))
        await db.execute("DELETE FROM afk_expeditions WHERE user_id = ?", (user_id,))
        await db.commit()

    await callback.message.edit_text(
        f"🎉 <b>ЭКСПЕДИЦИЯ УСПЕШНО ЗАВЕРШЕНА!</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Ваш отряд добыл трофеи:\n"
        f"🪙 <b>+{shekels_won} Шекелей</b>\n"
        f"✨ <b>+{skills_won} Очков навыков</b>\n",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")]])
    )

@dp.callback_query(F.data == "afk_cancel")
async def cb_afk_cancel(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM afk_expeditions WHERE user_id = ?", (user_id,))
        await db.commit()

    await callback.answer("Экспедиция досрочно отменена. Награды сгорели.", show_alert=True)
    await cb_afk_menu(callback)

@dp.message(Command("donate"))
async def cmd_donate(message: types.Message):
    await message.answer("💎 <b>ДОНАТ МАГАЗИН</b>\nВыберите нужный раздел:", reply_markup=donate_main_kb())

@dp.callback_query(F.data == "menu_donate")
async def cb_donate_menu(callback: CallbackQuery):
    await callback.message.edit_text("💎 <b>ДОНАТ МАГАЗИН</b>\nВыберите нужный раздел:", reply_markup=donate_main_kb())

@dp.callback_query(F.data == "donate_exchange")
async def cb_exchange_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    stats = await get_user_stats(user_id)
    shekels, robux = stats[0], stats[1]

    text = (
        f"🔄 <b>ОБМЕН ВАЛЮТЫ</b>\n"
        f"Курс: <b>100 Шекелей = 1 R$ (Робукс)</b>\n\n"
        f"💰 Ваши шекели: <b>{shekels}</b>\n"
        f"💎 Ваши робуксы: <b>{robux}</b>\n\n"
        f"Введите количество <b>R$ (Робуксов)</b>, которое вы хотите купить за шекели:"
    )
    await state.set_state(ExchangeState.amount)
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="menu_donate")]]))

@dp.message(ExchangeState.amount)
async def process_exchange_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) <= 0:
        return await message.answer("Пожалуйста, введите корректное положительное число!")

    robux_wanted = int(message.text)
    shekels_cost = robux_wanted * 100
    user_id = message.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT shekels FROM users WHERE user_id = ?", (user_id,)) as cursor:
            shekels = (await cursor.fetchone())[0]

        if shekels < shekels_cost:
            await state.clear()
            return await message.answer(
                f"❌ Недостаточно шекелей! Вам нужно <b>{shekels_cost}</b>, а у вас <b>{shekels}</b>.",
                reply_markup=donate_main_kb()
            )

        await db.execute("UPDATE users SET shekels = shekels - ?, robux = robux + ? WHERE user_id = ?", (shekels_cost, robux_wanted, user_id))
        await db.commit()

    await state.clear()
    await message.answer(
        f"✅ <b>Успешный обмен!</b>\nВы обменяли <b>{shekels_cost} шекелей</b> на <b>{robux_wanted} R$</b>!",
        reply_markup=donate_main_kb()
    )

@dp.callback_query(F.data == "donate_f2p")
async def cb_donate_f2p(callback: CallbackQuery):
    user_id = callback.from_user.id
    stats = await get_user_stats(user_id)
    robux = stats[1]

    kb = []
    text = f"🛒 <b>F2P МАГАЗИН (За Робуксы R$)</b>\nБаланс: <b>{robux} R$</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"

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

    if not gp:
        return await callback.answer("Геймпасс не найден!")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Купить себе", callback_data=f"proc_buy:{mode}:{gp_id}:self")],
        [InlineKeyboardButton(text="🎁 Подарить другу", callback_data=f"proc_buy:{mode}:{gp_id}:gift")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_donate")]
    ])

    price_str = f"{gp['robux']} R$" if mode == "buy_f2p" else f"{gp['stars']} ⭐️"
    await callback.message.edit_text(
        f"Вы выбрали: <b>{gp['title']}</b> ({price_str})\nКому вы хотите приобрести товар?",
        reply_markup=kb
    )

@dp.callback_query(F.data.startswith("proc_buy:"))
async def cb_process_buy(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    mode, gp_id, target = parts[1], parts[2], parts[3]
    user_id = callback.from_user.id
    gp = GAMEPASSES[gp_id]

    if target == "gift":
        await state.update_data(gamepass_id=gp_id, currency_type=mode)
        await state.set_state(GiftState.target_user)
        return await callback.message.edit_text(
            f"🎁 <b>ПОДАРОК: {gp['title']}</b>\n\nВведите <b>Username</b> получателя (например, <code>@username</code>) или его <b>Telegram ID</b>:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="menu_donate")]])
        )

    if mode == "buy_f2p":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT robux FROM users WHERE user_id = ?", (user_id,)) as cursor:
                robux = (await cursor.fetchone())[0]

            if robux < gp["robux"]:
                return await callback.answer(f"Недостаточно Робуксов! Нужно: {gp['robux']} R$, у вас: {robux} R$", show_alert=True)

            await db.execute("UPDATE users SET robux = robux - ? WHERE user_id = ?", (gp["robux"], user_id))
            await db.commit()

        await give_gamepass(user_id, gp_id)
        await callback.message.edit_text(f"🎉 Вы успешно купили геймпасс <b>{gp['title']}</b>!", reply_markup=donate_main_kb())

    elif mode == "buy_p2w":
        prices = [LabeledPrice(label=gp["title"], amount=gp["stars"])]
        payload = f"self:{gp_id}:{user_id}"

        await bot.send_invoice(
            chat_id=user_id,
            title=f"Геймпасс: {gp['title']}",
            description=gp["desc"],
            payload=payload,
            currency="XTR",
            prices=prices
        )
        await callback.answer("Счет на оплату Stars отправлен!")

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
        return await message.answer("❌ Пользователь не найден в базе данных бота!", reply_markup=donate_main_kb())

    target_id, target_name = target_row[0], target_row[1]

    if await has_gamepass(target_id, gp_id):
        await state.clear()
        return await message.answer(f"❌ У игрока <b>{target_name}</b> уже есть этот геймпасс!", reply_markup=donate_main_kb())

    if mode == "buy_f2p":
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute("SELECT robux FROM users WHERE user_id = ?", (buyer_id,)) as cursor:
                robux = (await cursor.fetchone())[0]

            if robux < gp["robux"]:
                await state.clear()
                return await message.answer(f"❌ Недостаточно R$! Нужно {gp['robux']} R$, у вас {robux} R$.", reply_markup=donate_main_kb())

            await db.execute("UPDATE users SET robux = robux - ? WHERE user_id = ?", (gp["robux"], buyer_id))
            await db.commit()

        await give_gamepass(target_id, gp_id)
        await state.clear()

        buyer_name = message.from_user.username or message.from_user.first_name
        await message.answer(f"🎁 Вы успешно подарили <b>{gp['title']}</b> игроку <b>{target_name}</b>!", reply_markup=donate_main_kb())

        try:
            gift_card_text = (
                f"🎉 <b>ВАМ ПОСТУПИЛ ПОДАРОК!</b> 🎉\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Игрок <b>@{buyer_name}</b> подарил вам геймпасс:\n"
                f"✨ <b>{gp['title']}</b> ✨\n"
                f"<i>{gp['desc']}</i>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Бонус уже активирован на ваш аккаунт!"
            )
            await bot.send_message(chat_id=target_id, text=gift_card_text)
        except Exception:
            pass

    elif mode == "buy_p2w":
        prices = [LabeledPrice(label=f"Подарок: {gp['title']}", amount=gp["stars"])]
        payload = f"gift:{gp_id}:{target_id}:{buyer_id}"

        await bot.send_invoice(
            chat_id=buyer_id,
            title=f"Подарок для {target_name}: {gp['title']}",
            description=gp["desc"],
            payload=payload,
            currency="XTR",
            prices=prices
        )
        await state.clear()

@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def process_successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    parts = payload.split(":")

    if parts[0] == "self":
        gp_id = parts[1]
        user_id = int(parts[2])
        gp = GAMEPASSES[gp_id]
        await give_gamepass(user_id, gp_id)
        await message.answer(f"🎉 Оплата принята! Вы получили геймпасс <b>{gp['title']}</b>!")

    elif parts[0] == "gift":
        gp_id = parts[1]
        target_id = int(parts[2])
        buyer_id = int(parts[3])
        gp = GAMEPASSES[gp_id]

        await give_gamepass(target_id, gp_id)
        buyer_name = message.from_user.username or message.from_user.first_name

        await message.answer(f"🎁 Оплата прошла успешно! Подарок <b>{gp['title']}</b> отправлен получателю!")

        try:
            gift_card_text = (
                f"🎉 <b>ВАМ ПОСТУПИЛ ПОДАРОК (Telegram Stars)!</b> 🎉\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Игрок <b>@{buyer_name}</b> подарил вам геймпасс:\n"
                f"✨ <b>{gp['title']}</b> ✨\n"
                f"<i>{gp['desc']}</i>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Бонус уже активирован на ваш аккаунт!"
            )
            await bot.send_message(chat_id=target_id, text=gift_card_text)
        except Exception:
            pass

@dp.callback_query(F.data.startswith("menu_inventory"))
async def cb_inventory(callback: CallbackQuery):
    page = 0
    if ":" in callback.data:
        page = int(callback.data.split(":")[1])

    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT c.name, i.mutation, COUNT(*) as cnt 
            FROM inventory i JOIN cards c ON i.card_id = c.card_id 
            WHERE i.user_id = ? GROUP BY c.name, i.mutation ORDER BY c.rarity DESC
        """, (user_id,)) as cursor:
            items = await cursor.fetchall()

    per_page = 10
    total_pages = math.ceil(len(items) / per_page) or 1

    start_idx = page * per_page
    page_items = items[start_idx:start_idx + per_page]

    text = f"🎒 <b>ИНВЕНТАРЬ КАРТ (Стр. {page+1}/{total_pages})</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for item in page_items:
        mut = "✨" if item[1] == "Gold" else "🌈" if item[1] == "Rainbow" else "⚪️"
        text += f"• {mut} {item[0]} — {item[2]} шт.\n"

    if not page_items:
        text += "<i>Инвентарь пуст...</i>"

    kb = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Пред", callback_data=f"menu_inventory:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="След ▶️", callback_data=f"menu_inventory:{page+1}"))
    if nav:
        kb.append(nav)

    kb.append([InlineKeyboardButton(text="🛡 Экипировка", callback_data="menu_equip"), InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

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
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")])

    await callback.message.edit_text("🛡 Выберите слот для экипировки юнита:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("equip_slot:"))
async def cb_equip_select_slot(callback: CallbackQuery):
    slot = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT i.item_id, c.name, i.mutation, c.rarity 
            FROM inventory i JOIN cards c ON i.card_id = c.card_id 
            WHERE i.user_id = ? AND i.is_equipped = 0
        """, (user_id,)) as cursor:
            items = await cursor.fetchall()

    kb = []
    for item in items[:15]:
        mut = MUTATIONS.get(item[2], MUTATIONS["Normal"])["name"]
        kb.append([InlineKeyboardButton(text=f"{mut} {item[1]} [{item[3]}]", callback_data=f"set_equip:{item[0]}:{slot}")])

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

@dp.callback_query(F.data == "menu_skills")
async def cb_skills_menu(callback: CallbackQuery):
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT points FROM skills WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            pts = row[0] if row else 0

    if pts == 0:
        return await callback.answer("У вас нет свободных очков навыков! Сражайтесь на арене или отправляйте отряды в AFK-экспедиции.", show_alert=True)

    kb = []
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT i.item_id, c.name, i.hp_pts, i.dmg_pts, i.cld_pts 
            FROM inventory i JOIN cards c ON i.card_id = c.card_id 
            WHERE i.user_id = ? AND i.is_equipped = 1 ORDER BY i.equip_slot
        """, (user_id,)) as cursor:
            equipped = await cursor.fetchall()
            for eq in equipped:
                kb.append([InlineKeyboardButton(text=f"✨ {eq[1]} (Очки: {eq[2]+eq[3]+eq[4]})", callback_data=f"skill_card:{eq[0]}")])

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")])
    await callback.message.edit_text(
        f"✨ У вас доступно <b>{pts} очков навыков</b>.\nВыберите экипированную карту для распределения:",
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
        [InlineKeyboardButton(text="❤️ HP +1", callback_data=f"add_sk:{item_id}:hp:1"), InlineKeyboardButton(text="❤️ HP +5", callback_data=f"add_sk:{item_id}:hp:5")],
        [InlineKeyboardButton(text="⚔️ DMG +1", callback_data=f"add_sk:{item_id}:dmg:1"), InlineKeyboardButton(text="⚔️ DMG +5", callback_data=f"add_sk:{item_id}:dmg:5")],
        [InlineKeyboardButton(text="⚡️ CLD +1", callback_data=f"add_sk:{item_id}:cld:1"), InlineKeyboardButton(text="⚡️ CLD +5", callback_data=f"add_sk:{item_id}:cld:5")],
        [InlineKeyboardButton(text="⬅️ К выбору карт", callback_data="menu_skills")]
    ])

    await callback.message.delete()
    await bot.send_photo(
        chat_id=callback.message.chat.id,
        photo=BufferedInputFile(img_bytes, filename="skills.jpg"),
        caption=f"Управление прокачкой карты <b>{name}</b>:",
        reply_markup=kb
    )

@dp.callback_query(F.data.startswith("add_sk:"))
async def cb_add_skill(callback: CallbackQuery):
    parts = callback.data.split(":")
    item_id, stat, amount = int(parts[1]), parts[2], int(parts[3])
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT points FROM skills WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            avail_pts = row[0] if row else 0

        if avail_pts < amount:
            return await callback.answer(f"Недостаточно очков навыков! Доступно: {avail_pts}", show_alert=True)

        col = "hp_pts" if stat == "hp" else ("dmg_pts" if stat == "dmg" else "cld_pts")

        await db.execute(f"UPDATE inventory SET {col} = {col} + ? WHERE item_id = ?", (amount, item_id))
        await db.execute("UPDATE skills SET points = points - ? WHERE user_id = ?", (amount, user_id))
        await db.commit()

    await callback.answer(f"Успешно добавлено +{amount}!")
    await cb_skill_show(callback)

@dp.callback_query(F.data == "menu_battle")
async def cb_battle_menu(callback: CallbackQuery):
    await callback.message.edit_text("⚔️ Выберите сложность соперника на Арене:", reply_markup=battle_difficulty_kb())

@dp.callback_query(F.data.startswith("battle_start_"))
async def process_battle(callback: CallbackQuery):
    difficulty = callback.data.split("_")[2]
    user_id = callback.from_user.id

    has_x2_shekels = await has_gamepass(user_id, "x2_shekels")
    has_x2_skills = await has_gamepass(user_id, "x2_skills")
    is_vip = await has_gamepass(user_id, "vip")

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
                cld_mult = max(0.2, 1.0 - (r[8] * 0.05))

                final_hp = int(r[2] * mut_buff * hp_mult)
                final_dmg = int(r[1] * mut_buff * dmg_mult)
                final_cld = max(0.1, r[3] * cld_mult)

                team_player.append({
                    "name": r[0], "base_hp": final_hp, "hp": final_hp, "dmg": final_dmg,
                    "cld": final_cld, "class": r[4], "next_attack": final_cld, "owner": "player"
                })

    if not team_player:
        return await callback.answer("У вас нет экипированных карт!", show_alert=True)

    await callback.message.edit_text("⏳ Поиск соперника и симуляция боя...")
    await asyncio.sleep(2)

    stats = await get_user_stats(user_id)
    rank = get_rank_by_trophies(stats[2])

    ai_diff_mult = {"easy": 0.6, "medium": 1.0, "hard": 1.4, "nightmare": 2.0}[difficulty]
    team_ai = []

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, damage, hp, cooldown, card_class FROM cards WHERE is_banned_ai = 0 ORDER BY RANDOM() LIMIT ?", (len(team_player),)) as cursor:
            ai_rows = await cursor.fetchall()
            for r in ai_rows:
                f_hp = max(10, int(r[2] * ai_diff_mult))
                f_dmg = max(5, int(r[1] * ai_diff_mult))
                team_ai.append({
                    "name": f"Враг {r[0]}", "base_hp": f_hp, "hp": f_hp, "dmg": f_dmg,
                    "cld": r[3], "class": r[4], "next_attack": r[3], "owner": "ai"
                })

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

        if not alive_enemies:
            break

        target = random.choice(alive_enemies)

        if next_unit["class"] == "Single":
            target["hp"] -= next_unit["dmg"]
            log.append(f"⚔️ {next_unit['name']} наносит {next_unit['dmg']} урона по {target['name']}!")
        elif next_unit["class"] == "Splash":
            target["hp"] -= next_unit["dmg"]
            log.append(f"💥 {next_unit['name']} сплеш-атака по {target['name']} на {next_unit['dmg']}!")
            for e in alive_enemies:
                if e != target:
                    e["hp"] -= int(next_unit["dmg"] * 0.4)
        elif next_unit["class"] == "AOE":
            for e in alive_enemies:
                e["hp"] -= next_unit["dmg"]
            log.append(f"🔥 {next_unit['name']} АОЕ удар на {next_unit['dmg']} по ВСЕМ врагам!")
        else:
            target["hp"] -= next_unit["dmg"]
            log.append(f"⚔️ {next_unit['name']} бьет {target['name']} на {next_unit['dmg']}!")

        next_unit["next_attack"] += next_unit["cld"]

    player_won = any(u["hp"] > 0 for u in team_player)

    r_data = RANKS[rank]
    base_trop = random.randint(r_data["trophies"][0], r_data["trophies"][1])
    base_shek = random.randint(r_data["shekels"][0], r_data["shekels"][1])

    if difficulty == "easy":
        base_trop = int(base_trop * 0.5)
    elif difficulty == "hard":
        base_trop = int(base_trop * 1.3)
    elif difficulty == "nightmare":
        base_trop = int(base_trop * 1.8)

    shekel_multiplier = 1.0
    if has_x2_shekels:
        shekel_multiplier *= 2.0
    if is_vip:
        shekel_multiplier *= 1.5

    base_shek = int(base_shek * shekel_multiplier)

    sp_chance = 0.2 + (0.05 if is_vip else 0.0)
    skill_pts = 0
    if random.random() < sp_chance:
        skill_pts = 1 if difficulty in ["easy", "medium"] else 2
        if has_x2_skills:
            skill_pts *= 2

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

    log_str = "\n".join(log[-6:])
    msg_text = (
        f"🏟 <b>АРЕНА: {res_title}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📜 <b>Лог боя:</b>\n{log_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 <b>Награды:</b>\n"
        f"🏆 Трофеи: <b>{base_trop}</b>\n"
        f"🪙 Шекели: <b>+{base_shek}</b>\n"
    )
    if skill_pts > 0:
        msg_text += f"✨ Очки навыков: <b>+{skill_pts}</b>\n"

    await callback.message.edit_text(msg_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_main")]]))

@dp.callback_query(F.data.startswith("menu_index"))
async def cb_index(callback: CallbackQuery):
    page = 0
    if ":" in callback.data:
        page = int(callback.data.split(":")[1])

    user_id = callback.from_user.id
    per_page = 6

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT card_id, name, rarity, damage, hp, is_hidden_index FROM cards ORDER BY card_id DESC") as cursor:
            all_cards = await cursor.fetchall()

        async with db.execute("SELECT DISTINCT card_id FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
            unlocked_ids = [r[0] for r in await cursor.fetchall()]

    visible_cards = [c for c in all_cards if not c[5]]
    total_pages = math.ceil(len(visible_cards) / per_page) or 1

    start_idx = page * per_page
    page_cards = visible_cards[start_idx:start_idx + per_page]

    text = f"📖 <b>ОСНОВНОЙ ИНДЕКС КАРТ (Стр. {page+1}/{total_pages})</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"

    async with aiosqlite.connect(DB_PATH) as db:
        for idx, c in enumerate(page_cards, start=start_idx+1):
            c_id, name, rarity, dmg, hp, _ = c
            async with db.execute("SELECT COUNT(*) FROM inventory WHERE card_id=?", (c_id,)) as cur2:
                total_exist = (await cur2.fetchone())[0]

            if c_id in unlocked_ids:
                text += f"{idx}. 🃏 <b>{name}</b> [{rarity}]\n   └ Урон: {dmg} | ❤️ HP: {hp} (Всего в мире: {total_exist} шт.)\n"
            else:
                text += f"{idx}. ❓ <b>??? Не открыто</b> [{rarity}]\n   └ (Всего в мире: {total_exist} шт.)\n"

    kb = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Пред", callback_data=f"menu_index:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="След ▶️", callback_data=f"menu_index:{page+1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "menu_crates")
async def cb_crates_menu(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Базовый Крейт (50 Шекелей)", callback_data="buy_crate:basic")],
        [InlineKeyboardButton(text="🎁 Эпический Крейт (250 Шекелей)", callback_data="buy_crate:epic")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ])
    await callback.message.edit_text("📦 <b>МАГАЗИН КРЕЙТОВ</b>\nОткрывайте крейты, чтобы выбивать новых уникальных юнитов!", reply_markup=kb)

@dp.callback_query(F.data.startswith("buy_crate:"))
async def cb_buy_crate(callback: CallbackQuery):
    crate_type = callback.data.split(":")[1]
    cost = 50 if crate_type == "basic" else 250
    rarity_filter = "Basic" if crate_type == "basic" else "Epic"
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT shekels FROM users WHERE user_id = ?", (user_id,)) as cursor:
            shekels = (await cursor.fetchone())[0]

        if shekels < cost:
            return await callback.answer(f"Недостаточно шекелей! Нужно: {cost}", show_alert=True)

        await db.execute("UPDATE users SET shekels = shekels - ? WHERE user_id = ?", (cost, user_id))
        await db.commit()

    card_res = await add_card_to_user(user_id, rarity_filter)
    if card_res[0]:
        c_name, c_rar, c_mut, c_ser = card_res
        ser_str = f" ({c_ser})" if c_ser else ""
        mut_str = MUTATIONS.get(c_mut, MUTATIONS["Normal"])["name"]
        await callback.message.edit_text(
            f"🎉 <b>ВЫ ОТКРЫЛИ КРЕЙТ!</b>\n\nВам выпал юнит: <b>{mut_str} {c_name}</b> [{c_rar}]{ser_str}!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад к крейтам", callback_data="menu_crates")]])
        )

@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("Отказано в доступе!", show_alert=True)
    await callback.message.edit_text("⚙️ <b>АДМИНИСТРАТИВНАЯ ПАНЕЛЬ</b>", reply_markup=admin_panel_kb())

@dp.callback_query(F.data == "admin_cards")
async def cb_admin_cards(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать новую карту", callback_data="admin_create_card")],
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
    await message.answer("Введите имя новой карты:")

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
    classes = ["Single", "Splash", "AOE"]
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
    if not message.text.isdigit():
        return await message.answer("Введите целое число!")
    await state.update_data(damage=int(message.text))
    await state.set_state(CardCreation.hp)
    await message.answer("Введите Здоровье (число):")

@dp.message(CardCreation.hp)
async def create_card_hp(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("Введите целое число!")
    await state.update_data(hp=int(message.text))
    await state.set_state(CardCreation.cooldown)
    await message.answer("Введите перезарядку в секундах (например, 1.5):")

@dp.message(CardCreation.cooldown)
async def create_card_cld(message: types.Message, state: FSMContext):
    try:
        cld = float(message.text)
    except ValueError:
        return await message.answer("Введите число!")

    await state.update_data(cooldown=cld)
    data = await state.get_data()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO cards (name, rarity, card_class, damage, hp, cooldown, photo_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (data['name'], data['rarity'], data['c_class'], data['damage'], data['hp'], data['cooldown'], data['photo_id']))
        await db.commit()

    await state.clear()
    await message.answer(f"✅ Карта <b>{data['name']}</b> успешно добавлена в игру!", reply_markup=admin_panel_kb())

async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()
    logging.info("База данных инициализирована. Запуск бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
