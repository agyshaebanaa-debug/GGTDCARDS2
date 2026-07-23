import asyncio
import logging
import random
import json
import math
import os
from datetime import datetime, timedelta
from io import BytesIO

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery,
    BufferedInputFile, LabeledPrice, PreCheckoutQuery, Message,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder
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

# --- БАЗА ДАННЫХ ---
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

        await db.execute('''CREATE TABLE IF NOT EXISTS afk_expeditions (
            user_id INTEGER PRIMARY KEY,
            cards_json TEXT,
            duration_hours INTEGER,
            start_time TEXT,
            end_time TEXT,
            claimed INTEGER DEFAULT 0
        )''')
        
        # Новая таблица для Сид-Паков
        await db.execute('''CREATE TABLE IF NOT EXISTS seed_packs (
            pack_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price INTEGER,
            cards_amount INTEGER DEFAULT 3
        )''')

        async with db.execute("SELECT COUNT(*) FROM cards") as cursor:
            count = (await cursor.fetchone())[0]
            if count == 0:
                await db.execute("""
                    INSERT INTO cards (name, rarity, card_class, damage, hp, cooldown, photo_id)
                    VALUES ('Стартовый Шрекс', 'Basic', 'Single', 25, 100, 2.0, '')
                """)

        await db.commit()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
async def is_user_admin(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            return bool(res[0]) if res else False

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

# --- КЛАВИАТУРЫ (REPLY) ---
def get_main_reply_keyboard(is_admin: bool) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    
    # Ряд 1
    builder.button(text="🃏 Выбить карту")
    builder.button(text="⚔️ Поиск боя (боты)")
    builder.button(text="⚔️ PvP Дуэль")
    
    # Ряд 2
    builder.button(text="🎒 Инвентарь")
    builder.button(text="👤 Профиль")
    builder.button(text="🛡 Экипировка")
    
    # Ряд 3
    builder.button(text="📜 Квесты")
    builder.button(text="🛒 Магазин")
    builder.button(text="🎟 Батл-пассы")
    
    # Ряд 4
    builder.button(text="🏆 Топ игроков")
    builder.button(text="📖 Индекс")
    builder.button(text="📦 Сид-Паки")
    
    # Ряд 5
    builder.button(text="⚽️ World Cup 2026")
    builder.button(text="🔨 Крафт")
    
    # Дополнительные функции бота, которых нет на фото, но они есть в коде
    builder.button(text="🎁 Награды")
    builder.button(text="⏳ AFK Экспедиция")
    builder.button(text="✨ Навыки")
    
    if is_admin:
        builder.button(text="⚙️ Админ панель")
        
    builder.adjust(3, 3, 3, 3, 2, 3, 1)
    return builder.as_markup(resize_keyboard=True)

# --- FSM СТЕЙТЫ ---
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

class AdminPlayers(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_card_id = State()
    waiting_for_take_item_id = State()

class AdminSeedPacks(StatesGroup):
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_amount = State()

# --- СТАРТ ---
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

    is_admin = await is_user_admin(user_id)

    text = (
        f"👋 Привет, <b>{username}</b>!\n\n"
        f"Добро пожаловать в карточную арену <b>Card Battle Bot</b>!\n"
        f"Используйте клавиатуру снизу для навигации 👇"
    )
    await message.answer(text, reply_markup=get_main_reply_keyboard(is_admin))

# Универсальный закрыватель инлайн-сообщений
@dp.callback_query(F.data == "close_menu")
async def cb_close_menu(callback: CallbackQuery):
    try:
        await callback.message.delete()
    except:
        pass

# --- ПРОФИЛЬ ---
@dp.message(F.text == "👤 Профиль")
async def menu_profile(message: types.Message):
    user_id = message.from_user.id
    stats = await get_user_stats(user_id)
    if not stats:
        return await message.answer("Ошибка загрузки профиля!")

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

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")]]))

# --- ТОП ИГРОКОВ ---
@dp.message(F.text == "🏆 Топ игроков")
async def menu_top_players(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT username, trophies FROM users ORDER BY trophies DESC LIMIT 10") as cursor:
            top_users = await cursor.fetchall()
            
    text = "🏆 <b>ТОП-10 ИГРОКОВ АРЕНЫ:</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
    for idx, (uname, troph) in enumerate(top_users, 1):
        medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"🔹 {idx}."
        text += f"{medal} <b>{uname}</b> — {troph} 🏆\n"
        
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")]]))

# --- ИНДЕКС ---
@dp.message(F.text == "📖 Индекс")
async def menu_index_trigger(message: types.Message):
    await show_index_page(message.chat.id, message.from_user.id, 0)

async def show_index_page(chat_id: int, user_id: int, page: int, message_to_edit: types.Message = None):
    per_page = 5

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT card_id, name, rarity, damage, hp, cooldown, is_hidden_index FROM cards ORDER BY rarity DESC, damage DESC") as cursor:
            all_cards = await cursor.fetchall()

        async with db.execute("SELECT DISTINCT card_id FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
            unlocked_ids = [r[0] for r in await cursor.fetchall()]

    visible_cards = [c for c in all_cards if not c[6]]
    total_pages = math.ceil(len(visible_cards) / per_page) or 1

    start_idx = page * per_page
    page_cards = visible_cards[start_idx:start_idx + per_page]

    text = f"📚 <b>ИНДЕКС КАРТ (Стр. {page+1}/{total_pages})</b>\nЗдесь собраны все известные карты мира.\n━━━━━━━━━━━━━━━━━━━━━━━━\n"

    async with aiosqlite.connect(DB_PATH) as db:
        for idx, c in enumerate(page_cards, start=start_idx+1):
            c_id, name, rarity, dmg, hp, cld, _ = c
            async with db.execute("SELECT COUNT(*) FROM inventory WHERE card_id=?", (c_id,)) as cur2:
                total_exist = (await cur2.fetchone())[0]

            if c_id in unlocked_ids:
                text += f"🔹 <b>[{rarity}]</b> 🃏 <b>{name}</b>\n"
                text += f"   ⚔️ Урон: <b>{dmg}</b> | ❤️ HP: <b>{hp}</b> | ⏱ КД: <b>{cld}s</b>\n"
                text += f"   🌍 Всего в мире: {total_exist} шт.\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
            else:
                text += f"❓ <b>[{rarity}]</b> <i>??? (Не открыто)</i>\n"
                text += f"   🌍 Всего в мире: {total_exist} шт.\n━━━━━━━━━━━━━━━━━━━━━━━━\n"

    kb = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Пред.", callback_data=f"menu_index:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="След. ▶️", callback_data=f"menu_index:{page+1}"))
    if nav:
        kb.append(nav)
    kb.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")])

    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    
    if message_to_edit:
        await message_to_edit.edit_text(text, reply_markup=markup)
    else:
        await bot.send_message(chat_id, text, reply_markup=markup)

@dp.callback_query(F.data.startswith("menu_index:"))
async def cb_index_nav(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    await show_index_page(callback.message.chat.id, callback.from_user.id, page, callback.message)

# --- КРЕЙТЫ (Выбить карту) ---
@dp.message(F.text.in_(["🃏 Выбить карту", "📦 Крейты"]))
async def menu_crates(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📦 Базовый Крейт (50 Шекелей)", callback_data="buy_crate:basic")],
        [InlineKeyboardButton(text="🎁 Эпический Крейт (250 Шекелей)", callback_data="buy_crate:epic")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")]
    ])
    await message.answer("📦 <b>МАГАЗИН КРЕЙТОВ</b>\nОткрывайте крейты, чтобы выбивать новых уникальных юнитов!", reply_markup=kb)

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
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📦 Открыть еще один", callback_data=f"buy_crate:{crate_type}")],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")]
        ])
        await callback.message.edit_text(
            f"🎉 <b>ВЫ ОТКРЫЛИ КРЕЙТ!</b>\n\nВам выпал юнит:\n🌟 <b>{mut_str} {c_name}</b> [{c_rar}]{ser_str}!",
            reply_markup=kb
        )

# --- ИНВЕНТАРЬ ---
@dp.message(F.text == "🎒 Инвентарь")
async def menu_inventory_trigger(message: types.Message):
    await show_inventory(message.chat.id, message.from_user.id, 0)

async def show_inventory(chat_id: int, user_id: int, page: int, message_to_edit: types.Message = None):
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
        text += "<i>Ваш инвентарь пуст...</i>"

    kb = []
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="◀️ Пред.", callback_data=f"menu_inventory:{page-1}"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton(text="След. ▶️", callback_data=f"menu_inventory:{page+1}"))
    if nav:
        kb.append(nav)

    kb.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")])
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    
    if message_to_edit:
        await message_to_edit.edit_text(text, reply_markup=markup)
    else:
        await bot.send_message(chat_id, text, reply_markup=markup)

@dp.callback_query(F.data.startswith("menu_inventory:"))
async def cb_inventory_nav(callback: CallbackQuery):
    page = int(callback.data.split(":")[1])
    await show_inventory(callback.message.chat.id, callback.from_user.id, page, callback.message)

# --- ЭКИПИРОВКА ---
@dp.message(F.text == "🛡 Экипировка")
async def menu_equip_trigger(message: types.Message):
    await show_equip_menu(message.chat.id, message.from_user.id)

async def show_equip_menu(chat_id: int, user_id: int, message_to_edit: types.Message = None):
    has_slot5 = await has_gamepass(user_id, "slot_5")

    kb = [
        [InlineKeyboardButton(text="Слот 1", callback_data="equip_slot:1"), InlineKeyboardButton(text="Слот 2", callback_data="equip_slot:2")],
        [InlineKeyboardButton(text="Слот 3", callback_data="equip_slot:3"), InlineKeyboardButton(text="Слот 4", callback_data="equip_slot:4")]
    ]

    if has_slot5:
        kb.append([InlineKeyboardButton(text="🌟 Слот 5 (Геймпасс)", callback_data="equip_slot:5")])

    kb.append([InlineKeyboardButton(text="🗑 Снять всё", callback_data="equip_clear")])
    kb.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")])

    text = "🛡 <b>ЭКИПИРОВКА ОТРЯДА</b>\nВыберите слот, чтобы установить юнита для битв на арене:"
    markup = InlineKeyboardMarkup(inline_keyboard=kb)
    
    if message_to_edit:
        await message_to_edit.edit_text(text, reply_markup=markup)
    else:
        await bot.send_message(chat_id, text, reply_markup=markup)

@dp.callback_query(F.data == "menu_equip_back")
async def cb_equip_back(callback: CallbackQuery):
    await show_equip_menu(callback.message.chat.id, callback.from_user.id, callback.message)

@dp.callback_query(F.data.startswith("equip_slot:"))
async def cb_equip_select_slot(callback: CallbackQuery):
    slot = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT i.item_id, c.name, i.mutation, c.rarity 
            FROM inventory i JOIN cards c ON i.card_id = c.card_id 
            WHERE i.user_id = ? AND i.is_equipped = 0 LIMIT 20
        """, (user_id,)) as cursor:
            items = await cursor.fetchall()

    kb = []
    for item in items:
        mut = MUTATIONS.get(item[2], MUTATIONS["Normal"])["name"]
        kb.append([InlineKeyboardButton(text=f"{mut} {item[1]} [{item[3]}]", callback_data=f"set_equip:{item[0]}:{slot}")])

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_equip_back")])
    await callback.message.edit_text(f"⚔️ Выберите карту для <b>Слота {slot}</b>:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("set_equip:"))
async def cb_set_equip(callback: CallbackQuery):
    parts = callback.data.split(":")
    item_id, slot = int(parts[1]), int(parts[2])
    user_id = callback.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE inventory SET is_equipped = 0, equip_slot = 0 WHERE user_id = ? AND equip_slot = ?", (user_id, slot))
        await db.execute("UPDATE inventory SET is_equipped = 1, equip_slot = ? WHERE item_id = ? AND user_id = ?", (slot, item_id, user_id))
        await db.commit()

    await callback.answer("✅ Карта успешно экипирована!")
    await show_equip_menu(callback.message.chat.id, user_id, callback.message)

@dp.callback_query(F.data == "equip_clear")
async def cb_equip_clear(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE inventory SET is_equipped = 0, equip_slot = 0 WHERE user_id = ?", (user_id,))
        await db.commit()

    await callback.answer("🗑 Вся экипировка снята!")
    await show_equip_menu(callback.message.chat.id, user_id, callback.message)

# --- ЕЖЕДНЕВНЫЕ НАГРАДЫ ---
DAILY_REWARDS_INFO = {
    1: {"type": "shekels", "amount": 10, "desc": "10 шекелей 🪙"},
    2: {"type": "card", "rarity": "Uncommon", "desc": "Uncommon юнит 🟢"},
    3: {"type": "card", "rarity": "Epic", "desc": "Epic юнит 🟣"},
    4: {"type": "shekels", "amount": 400, "desc": "400 шекелей 🪙"},
    5: {"type": "card", "rarity": "Legendary", "desc": "Legendary юнит 🟡"},
    6: {"type": "shekels", "amount": 700, "desc": "700 шекелей 🪙"},
    7: {"type": "card", "rarity": "Mythic", "desc": "Mythic юнит 🔴"}
}

@dp.message(F.text == "🎁 Награды")
async def menu_daily_trigger(message: types.Message):
    user_id = message.from_user.id
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
    kb.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

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
                reward_msg = f"🪙 Компенсация: <b>{fallback_shekels} шекелей</b>!"

        await db.execute("UPDATE users SET daily_streak = ?, last_daily_claim = ? WHERE user_id = ?", (new_streak, today_str, user_id))
        await db.commit()

    await callback.message.edit_text(
        f"🎉 <b>НАГРАДА ПОЛУЧЕНА!</b>\n\n{reward_msg}\n\nВозвращайтесь завтра за следующей!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")]])
    )

# --- AFK ЭКСПЕДИЦИИ ---
@dp.message(F.text == "⏳ AFK Экспедиция")
async def menu_afk_trigger(message: types.Message):
    await show_afk_menu(message.chat.id, message.from_user.id)
    
@dp.callback_query(F.data == "menu_afk_back")
async def cb_menu_afk_back(callback: CallbackQuery):
    await show_afk_menu(callback.message.chat.id, callback.from_user.id, callback.message)

async def show_afk_menu(chat_id: int, user_id: int, message_to_edit: types.Message = None):
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
                [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")]
            ])
            text = (f"🎉 <b>AFK Экспедиция завершена!</b>\n"
                    f"Ваш отряд вернулся из похода на <b>{duration_h} ч.</b>!\n"
                    f"Заберите заслуженные шекели и очки навыков!")
        else:
            rem = end_time - now
            rem_h, rem_m = rem.seconds // 3600, (rem.seconds % 3600) // 60
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Обновить статус", callback_data="menu_afk_back")],
                [InlineKeyboardButton(text="❌ Досрочно отменить", callback_data="afk_cancel")],
                [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")]
            ])
            text = (f"⏳ <b>AFK Экспедиция в процессе...</b>\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"⏱ Длительность: <b>{duration_h} часов</b>\n"
                    f"⏳ Осталось: <b>{rem_h} ч. {rem_m} мин.</b>\n\n"
                    f"<i>Отряд ищет сокровища!</i>")
    else:
        is_vip = await has_gamepass(user_id, "vip")
        max_afk_cards = 4 if is_vip else 3

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Собрать отряд", callback_data="afk_setup_cards")],
            [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")]
        ])
        text = (f"⏳ <b>AFK ЭКСПЕДИЦИИ</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"Отправляйте юнитов в походы и получайте награды!\n\n"
                f"• Слотов для карт: <b>{max_afk_cards} шт.</b>\n"
                f"• Награды: Шекели 🪙 и Очки навыков ✨",)

    if message_to_edit:
        await message_to_edit.edit_text(text, reply_markup=kb)
    else:
        await bot.send_message(chat_id, text, reply_markup=kb)

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
        return await callback.answer("У вас нет карт!", show_alert=True)

    await state.update_data(selected_cards=[], max_slots=max_slots)
    await state.set_state(AFKState.selecting_cards)

    kb = []
    for item in items:
        mut = MUTATIONS.get(item[2], MUTATIONS["Normal"])["name"]
        kb.append([InlineKeyboardButton(text=f"▫️ {mut} {item[1]} [{item[3]}]", callback_data=f"afk_toggle:{item[0]}")])

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_afk_back")])

    await callback.message.edit_text(
        f"⏳ Выберите карты в отряд (<b>0/{max_slots}</b>):",
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
            return await callback.answer(f"Максимум карт: {max_slots}!", show_alert=True)
        selected.append(item_id)

    await state.update_data(selected_cards=selected)
    user_id = callback.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT i.item_id, c.name, i.mutation, c.rarity
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
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_afk_back")])

    await callback.message.edit_text(
        f"⏳ Выберите карты (<b>{len(selected)}/{max_slots}</b>):",
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
    await callback.message.edit_text("⏱ Выберите время экспедиции:", reply_markup=kb)

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
        f"🚀 <b>ОТРЯД ОТПРАВЛЕН!</b>\n\n⏱ Время: <b>{hours} часов</b>\n"
        f"Возвращайтесь позже, чтобы забрать сокровища!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ К меню AFK", callback_data="menu_afk_back")]])
    )

@dp.callback_query(F.data == "afk_claim_reward")
async def cb_afk_claim_reward(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT duration_hours FROM afk_expeditions WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()

        if not row:
            return await callback.answer("У вас нет экспедиции!")
        
        duration_h = row[0]
        shekels_won = max(10, duration_h * 20)
        skills_won = max(1, duration_h * 2)

        await db.execute("UPDATE users SET shekels = shekels + ? WHERE user_id = ?", (shekels_won, user_id))
        await db.execute("INSERT INTO skills (user_id, points) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET points = points + ?", (user_id, skills_won, skills_won))
        await db.execute("DELETE FROM afk_expeditions WHERE user_id = ?", (user_id,))
        await db.commit()

    await callback.message.edit_text(
        f"🎉 <b>ЭКСПЕДИЦИЯ ЗАВЕРШЕНА!</b>\n\n"
        f"🪙 <b>+{shekels_won} Шекелей</b>\n✨ <b>+{skills_won} Очков навыков</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")]])
    )

@dp.callback_query(F.data == "afk_cancel")
async def cb_afk_cancel(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM afk_expeditions WHERE user_id = ?", (user_id,))
        await db.commit()

    await callback.answer("Отменено!", show_alert=True)
    await show_afk_menu(callback.message.chat.id, user_id, callback.message)


# --- ПОИСК БОЯ (Бот/PvE) ---
@dp.message(F.text == "⚔️ Поиск боя (боты)")
async def menu_battle_trigger(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Лёгкий (-50% кубков)", callback_data="battle_start_easy")],
        [InlineKeyboardButton(text="🟡 Средний (Базовый)", callback_data="battle_start_medium")],
        [InlineKeyboardButton(text="🔴 Сложный (+30% кубков)", callback_data="battle_start_hard")],
        [InlineKeyboardButton(text="💀 КОШМАР (+80% кубков)", callback_data="battle_start_nightmare")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")]
    ])
    await message.answer("⚔️ <b>АРЕНА</b>\nВыберите сложность соперника:", reply_markup=kb)

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
                final_hp = int(r[2] * mut_buff * (1.0 + (r[6] * 0.05)))
                final_dmg = int(r[1] * mut_buff * (1.0 + (r[7] * 0.05)))
                final_cld = max(0.1, r[3] * max(0.2, 1.0 - (r[8] * 0.05)))

                team_player.append({
                    "name": r[0], "hp": final_hp, "dmg": final_dmg, "cld": final_cld, 
                    "class": r[4], "next_attack": final_cld, "owner": "player"
                })

    if not team_player:
        return await callback.answer("У вас нет экипированных карт!", show_alert=True)

    await callback.message.edit_text("⏳ Поиск соперника и симуляция боя...")
    await asyncio.sleep(1.5)

    ai_diff_mult = {"easy": 0.6, "medium": 1.0, "hard": 1.4, "nightmare": 2.0}[difficulty]
    team_ai = []

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, damage, hp, cooldown, card_class FROM cards WHERE is_banned_ai = 0 ORDER BY RANDOM() LIMIT ?", (len(team_player),)) as cursor:
            for r in await cursor.fetchall():
                team_ai.append({
                    "name": f"Враг {r[0]}", "hp": max(10, int(r[2] * ai_diff_mult)), 
                    "dmg": max(5, int(r[1] * ai_diff_mult)), "cld": r[3], 
                    "class": r[4], "next_attack": r[3], "owner": "ai"
                })

    log = []
    time_passed = 0.0
    all_units = team_player + team_ai

    while time_passed < 60.0 and any(u["hp"] > 0 for u in team_player) and any(u["hp"] > 0 for u in team_ai):
        alive = [u for u in all_units if u["hp"] > 0]
        next_u = min(alive, key=lambda x: x["next_attack"])
        time_passed = next_u["next_attack"]

        enemies = team_ai if next_u["owner"] == "player" else team_player
        alive_enemies = [e for e in enemies if e["hp"] > 0]
        if not alive_enemies: break

        target = random.choice(alive_enemies)
        target["hp"] -= next_u["dmg"]
        log.append(f"⚔️ {next_u['name']} бьет {target['name']} ({next_u['dmg']} dmg)!")
        next_u["next_attack"] += next_u["cld"]

    player_won = any(u["hp"] > 0 for u in team_player)
    
    base_trop = 20 if player_won else -10
    base_shek = 15 if player_won else 2
    
    if player_won:
        if difficulty == "easy": base_trop = int(base_trop * 0.5)
        elif difficulty == "hard": base_trop = int(base_trop * 1.3)
        elif difficulty == "nightmare": base_trop = int(base_trop * 1.8)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET trophies = MAX(0, trophies + ?), shekels = shekels + ? WHERE user_id = ?", (base_trop, base_shek, user_id))
        await db.commit()

    res_title = "🏆 ПОБЕДА" if player_won else "❌ ПОРАЖЕНИЕ"
    log_str = "\n".join(log[-5:])
    
    await callback.message.edit_text(
        f"🏟 <b>{res_title}</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📜 <b>Конец боя:</b>\n{log_str}\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 <b>Награды:</b>\n🏆 Трофеи: <b>{base_trop}</b>\n🪙 Шекели: <b>+{base_shek}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")]])
    )

# --- ДОНАТ И МАГАЗИН ---
@dp.message(F.text.in_(["🛒 Магазин", "💎 Донат Магазин"]))
async def menu_donate_trigger(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обменять Шекели ➡️ Робуксы", callback_data="donate_exchange")],
        [InlineKeyboardButton(text="🛒 F2P Магазин (R$)", callback_data="donate_f2p")],
        [InlineKeyboardButton(text="🌟 P2W Магазин (Telegram Stars)", callback_data="donate_p2w")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")]
    ])
    await message.answer("💎 <b>МАГАЗИН / ДОНАТ</b>\nВыберите раздел:", reply_markup=kb)

@dp.callback_query(F.data == "menu_donate_back")
async def cb_donate_back(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Обменять Шекели ➡️ Робуксы", callback_data="donate_exchange")],
        [InlineKeyboardButton(text="🛒 F2P Магазин (R$)", callback_data="donate_f2p")],
        [InlineKeyboardButton(text="🌟 P2W Магазин (Telegram Stars)", callback_data="donate_p2w")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")]
    ])
    await callback.message.edit_text("💎 <b>МАГАЗИН / ДОНАТ</b>\nВыберите раздел:", reply_markup=kb)

@dp.callback_query(F.data == "donate_exchange")
async def cb_exchange_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    stats = await get_user_stats(user_id)
    text = (f"🔄 <b>ОБМЕН ВАЛЮТЫ</b>\nКурс: <b>100 Шекелей = 1 R$</b>\n\n"
            f"💰 Ваши шекели: <b>{stats[0]}</b>\n💎 Ваши робуксы: <b>{stats[1]}</b>\n\n"
            f"Введите количество <b>R$</b> для покупки:")
    await state.set_state(ExchangeState.amount)
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_donate_back")]]))

@dp.message(ExchangeState.amount)
async def process_exchange_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) <= 0:
        return await message.answer("Введите корректное число!")
    
    rw = int(message.text)
    cost = rw * 100
    user_id = message.from_user.id

    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT shekels FROM users WHERE user_id = ?", (user_id,)) as cursor:
            shekels = (await cursor.fetchone())[0]

        if shekels < cost:
            await state.clear()
            return await message.answer(f"❌ Недостаточно шекелей! Нужно {cost}.")

        await db.execute("UPDATE users SET shekels = shekels - ?, robux = robux + ? WHERE user_id = ?", (cost, rw, user_id))
        await db.commit()

    await state.clear()
    await message.answer(f"✅ Вы обменяли <b>{cost} шекелей</b> на <b>{rw} R$</b>!")

# --- НАВЫКИ ---
@dp.message(F.text == "✨ Навыки")
async def menu_skills_trigger(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT points FROM skills WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            pts = row[0] if row else 0

    if pts == 0:
        return await message.answer("У вас нет свободных очков навыков!")

    kb = []
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT i.item_id, c.name, i.hp_pts, i.dmg_pts, i.cld_pts 
            FROM inventory i JOIN cards c ON i.card_id = c.card_id 
            WHERE i.user_id = ? AND i.is_equipped = 1
        """, (user_id,)) as cursor:
            for eq in await cursor.fetchall():
                kb.append([InlineKeyboardButton(text=f"✨ {eq[1]}", callback_data=f"skill_card:{eq[0]}")])

    kb.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")])
    await message.answer(f"✨ У вас доступно <b>{pts} очков</b>.\nВыберите карту для прокачки:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# --- ЗАГЛУШКИ ДЛЯ НОВЫХ КНОПОК ---
@dp.message(F.text.in_(["⚔️ PvP Дуэль", "📜 Квесты", "🎟 Батл-пассы", "⚽️ World Cup 2026", "🔨 Крафт"]))
async def placeholder_features(message: types.Message):
    await message.answer(f"🚧 Раздел <b>«{message.text}»</b> находится в разработке и появится в следующих обновлениях!", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Понятно", callback_data="close_menu")]]))

# --- СИД ПАКИ (ПОЛЬЗОВАТЕЛЬСКАЯ ЧАСТЬ) ---
@dp.message(F.text == "📦 Сид-Паки")
async def menu_seed_packs(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT pack_id, name, price, cards_amount FROM seed_packs") as cursor:
            packs = await cursor.fetchall()
            
    if not packs:
        return await message.answer("🌱 В данный момент Сид-Паки отсутствуют в магазине.")
        
    kb = []
    text = "📦 <b>МАГАЗИН СИД-ПАКОВ</b>\nОткрывайте Сид-Паки, чтобы получить сразу несколько карт!\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    for pid, name, price, amount in packs:
        text += f"🌱 <b>{name}</b>\n   └ Карт внутри: {amount} шт. | Стоимость: <b>{price}🪙</b>\n"
        kb.append([InlineKeyboardButton(text=f"Купить {name} ({price}🪙)", callback_data=f"buy_seed:{pid}")])
        
    kb.append([InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("buy_seed:"))
async def cb_buy_seed_pack(callback: CallbackQuery):
    pack_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, price, cards_amount FROM seed_packs WHERE pack_id = ?", (pack_id,)) as cursor:
            pack = await cursor.fetchone()
            
        if not pack: return await callback.answer("Пак не найден!")
        
        name, price, amount = pack
        
        async with db.execute("SELECT shekels FROM users WHERE user_id = ?", (user_id,)) as cursor:
            shekels = (await cursor.fetchone())[0]
            
        if shekels < price:
            return await callback.answer(f"Недостаточно шекелей! Нужно: {price}", show_alert=True)
            
        await db.execute("UPDATE users SET shekels = shekels - ? WHERE user_id = ?", (price, user_id))
        await db.commit()
        
    obtained_cards = []
    for _ in range(amount):
        res = await add_card_to_user(user_id) # Даем случайную карту
        if res and res[0]:
            obtained_cards.append(f"{res[2]} {res[0]} [{res[1]}]")
            
    text = f"🎉 <b>ВЫ ОТКРЫЛИ {name}!</b>\nВам выпали следующие карты:\n\n"
    for c in obtained_cards:
        text += f"• 🃏 {c}\n"
        
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")]]))


# ==========================================
# ======= АДМИН ПАНЕЛЬ И УПРАВЛЕНИЕ ========
# ==========================================

@dp.message(F.text == "⚙️ Админ панель")
async def admin_panel_trigger(message: types.Message):
    if not await is_user_admin(message.from_user.id):
        return
        
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🃏 Управление картами", callback_data="admin_cards")],
        [InlineKeyboardButton(text="👥 Управление игроками", callback_data="admin_players")],
        [InlineKeyboardButton(text="📦 Управление Сид-Паками", callback_data="admin_seed_packs")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")]
    ])
    await message.answer("⚙️ <b>ГЛАВНАЯ ПАНЕЛЬ АДМИНИСТРАТОРА</b>\nВыберите раздел для управления ботом:", reply_markup=kb)

@dp.callback_query(F.data == "admin_panel_back")
async def cb_admin_panel_back(callback: CallbackQuery):
    if not await is_user_admin(callback.from_user.id): return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🃏 Управление картами", callback_data="admin_cards")],
        [InlineKeyboardButton(text="👥 Управление игроками", callback_data="admin_players")],
        [InlineKeyboardButton(text="📦 Управление Сид-Паками", callback_data="admin_seed_packs")],
        [InlineKeyboardButton(text="❌ Закрыть", callback_data="close_menu")]
    ])
    await callback.message.edit_text("⚙️ <b>ГЛАВНАЯ ПАНЕЛЬ АДМИНИСТРАТОРА</b>\nВыберите раздел для управления ботом:", reply_markup=kb)

# --- АДМИН: КАРТЫ ---
@dp.callback_query(F.data == "admin_cards")
async def cb_admin_cards(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать новую карту", callback_data="admin_create_card")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel_back")]
    ])
    await callback.message.edit_text("🃏 <b>УПРАВЛЕНИЕ КАРТАМИ</b>", reply_markup=kb)

@dp.callback_query(F.data == "admin_create_card")
async def create_card_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CardCreation.photo)
    await callback.message.edit_text("Отправьте фото для новой карты (как изображение):")

@dp.message(CardCreation.photo, F.photo)
async def create_card_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
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
    await state.update_data(rarity=callback.data.split(":")[1])
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=c, callback_data=f"set_class:{c}")] for c in ["Single", "Splash", "AOE"]])
    await state.set_state(CardCreation.c_class)
    await callback.message.edit_text("Выберите класс карты:", reply_markup=kb)

@dp.callback_query(CardCreation.c_class, F.data.startswith("set_class:"))
async def create_card_class(callback: CallbackQuery, state: FSMContext):
    await state.update_data(c_class=callback.data.split(":")[1])
    await state.set_state(CardCreation.damage)
    await callback.message.edit_text("Введите Урон (число):")

@dp.message(CardCreation.damage)
async def create_card_dmg(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Введите целое число!")
    await state.update_data(damage=int(message.text))
    await state.set_state(CardCreation.hp)
    await message.answer("Введите Здоровье (число):")

@dp.message(CardCreation.hp)
async def create_card_hp(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Введите целое число!")
    await state.update_data(hp=int(message.text))
    await state.set_state(CardCreation.cooldown)
    await message.answer("Введите перезарядку в секундах (например, 1.5):")

@dp.message(CardCreation.cooldown)
async def create_card_cld(message: types.Message, state: FSMContext):
    try:
        cld = float(message.text)
    except ValueError:
        return await message.answer("Введите число!")

    data = await state.get_data()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO cards (name, rarity, card_class, damage, hp, cooldown, photo_id) VALUES (?, ?, ?, ?, ?, ?, ?)", 
                         (data['name'], data['rarity'], data['c_class'], data['damage'], data['hp'], cld, data['photo_id']))
        await db.commit()

    await state.clear()
    await message.answer(f"✅ Карта <b>{data['name']}</b> успешно добавлена в игру!")

# --- АДМИН: ИГРОКИ (Выдать/Забрать карту) ---
@dp.callback_query(F.data == "admin_players")
async def cb_admin_players(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Выдать карту игроку", callback_data="admin_give_card")],
        [InlineKeyboardButton(text="➖ Забрать карту у игрока", callback_data="admin_take_card")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel_back")]
    ])
    await callback.message.edit_text("👥 <b>УПРАВЛЕНИЕ ИГРОКАМИ</b>\nЧто вы хотите сделать?", reply_markup=kb)

@dp.callback_query(F.data == "admin_give_card")
async def cb_admin_give_card_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminPlayers.waiting_for_user_id)
    await state.update_data(action="give")
    await callback.message.edit_text("Введите <b>Telegram ID</b> игрока, которому хотите выдать карту:")

@dp.callback_query(F.data == "admin_take_card")
async def cb_admin_take_card_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminPlayers.waiting_for_user_id)
    await state.update_data(action="take")
    await callback.message.edit_text("Введите <b>Telegram ID</b> игрока, у которого хотите забрать карту:")

@dp.message(AdminPlayers.waiting_for_user_id)
async def admin_process_user_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("ID должен состоять из цифр!")
    target_id = int(message.text)
    data = await state.get_data()
    
    if data["action"] == "give":
        await state.update_data(target_id=target_id)
        await state.set_state(AdminPlayers.waiting_for_card_id)
        await message.answer("Отлично. Теперь введите <b>Card ID</b> (ID карты из БД), которую нужно выдать:")
    else:
        await state.update_data(target_id=target_id)
        await state.set_state(AdminPlayers.waiting_for_take_item_id)
        await message.answer("Введите <b>Item ID</b> (уникальный ID предмета в инвентаре игрока), который нужно удалить:")

@dp.message(AdminPlayers.waiting_for_card_id)
async def admin_give_card_final(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("ID должен состоять из цифр!")
    card_id = int(message.text)
    data = await state.get_data()
    target_id = data["target_id"]
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, rarity FROM cards WHERE card_id = ?", (card_id,)) as cursor:
            card = await cursor.fetchone()
            
        if not card:
            await state.clear()
            return await message.answer("❌ Карта с таким ID не найдена!")
            
        serial = await get_next_serial(card[1])
        await db.execute("INSERT INTO inventory (user_id, card_id, mutation, serial_number) VALUES (?, ?, 'Normal', ?)", (target_id, card_id, serial))
        await db.commit()
        
    await state.clear()
    await message.answer(f"✅ Карта <b>{card[0]}</b> успешно выдана игроку {target_id}!")

@dp.message(AdminPlayers.waiting_for_take_item_id)
async def admin_take_card_final(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("ID должен состоять из цифр!")
    item_id = int(message.text)
    data = await state.get_data()
    target_id = data["target_id"]
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM inventory WHERE item_id = ? AND user_id = ?", (item_id, target_id))
        await db.commit()
        
    await state.clear()
    await message.answer(f"✅ Предмет с ID {item_id} удален из инвентаря игрока {target_id} (если он там был).")

# --- АДМИН: СИД ПАКИ ---
@dp.callback_query(F.data == "admin_seed_packs")
async def cb_admin_seeds(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать Сид-Пак", callback_data="admin_create_seed")],
        [InlineKeyboardButton(text="🗑 Удалить Сид-Пак", callback_data="admin_delete_seed")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_panel_back")]
    ])
    await callback.message.edit_text("📦 <b>УПРАВЛЕНИЕ СИД-ПАКАМИ</b>", reply_markup=kb)

@dp.callback_query(F.data == "admin_create_seed")
async def cb_admin_create_seed(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AdminSeedPacks.waiting_for_name)
    await callback.message.edit_text("Введите <b>название</b> для нового Сид-Пака (например: <i>Новогодний Пак</i>):")

@dp.message(AdminSeedPacks.waiting_for_name)
async def admin_seed_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AdminSeedPacks.waiting_for_price)
    await message.answer("Введите <b>цену</b> (в шекелях):")

@dp.message(AdminSeedPacks.waiting_for_price)
async def admin_seed_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Цена должна быть числом!")
    await state.update_data(price=int(message.text))
    await state.set_state(AdminSeedPacks.waiting_for_amount)
    await message.answer("Введите <b>количество карт</b>, которое выпадет из пака (например: 3):")
    
@dp.message(AdminSeedPacks.waiting_for_amount)
async def admin_seed_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Количество должно быть числом!")
    data = await state.get_data()
    amount = int(message.text)
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO seed_packs (name, price, cards_amount) VALUES (?, ?, ?)", (data['name'], data['price'], amount))
        await db.commit()
        
    await state.clear()
    await message.answer(f"✅ Сид-Пак <b>{data['name']}</b> успешно создан!")

@dp.callback_query(F.data == "admin_delete_seed")
async def cb_admin_delete_seed(callback: CallbackQuery):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT pack_id, name FROM seed_packs") as cursor:
            packs = await cursor.fetchall()
            
    if not packs:
        return await callback.answer("Нет созданных Сид-Паков!", show_alert=True)
        
    kb = []
    for pid, name in packs:
        kb.append([InlineKeyboardButton(text=f"🗑 Удалить: {name}", callback_data=f"del_seed:{pid}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_seed_packs")])
    
    await callback.message.edit_text("Выберите пак для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("del_seed:"))
async def cb_admin_del_seed_exec(callback: CallbackQuery):
    pid = int(callback.data.split(":")[1])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM seed_packs WHERE pack_id = ?", (pid,))
        await db.commit()
    await callback.answer("✅ Сид-Пак удален!")
    await cb_admin_seeds(callback)

# --- ЗАПУСК БОТА ---
async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()
    logging.info("База данных инициализирована. Запуск бота...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
