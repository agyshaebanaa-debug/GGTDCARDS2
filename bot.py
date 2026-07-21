import asyncio
import logging
import random
import json
import math
from datetime import datetime, timedelta
from io import BytesIO

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile, BufferedInputFile
from aiogram.enums import ParseMode

import aiosqlite
from PIL import Image, ImageDraw, ImageFont, ImageOps

# ==========================================
# КОНФИГУРАЦИЯ И КОНСТАНТЫ
# ==========================================
BOT_TOKEN = "8949953502:AAGwrEWWVST3yXRNA57yLWl8RXDdmr9WRQs" # Замени на свой токен
ADMIN_IDS = [5341904332] # Замени на свой Telegram ID

DB_PATH = "game_database.db"

# Цвета редкостей (для рамок карт)
RARITY_COLORS = {
    "Basic": (128, 128, 128),       # серый
    "Uncommon": (0, 255, 0),        # зеленый
    "Rare": (0, 191, 255),          # голубой
    "Epic": (128, 0, 128),          # фиолетовый
    "Legendary": (255, 215, 0),     # жёлтый
    "Mythic": (255, 0, 0),          # красный
    "Super": (255, 0, 255),         # радужный (заглушка цвета)
    "Secret": (0, 0, 0),            # чёрный
    "Exclusive": (255, 105, 180),   # розовый
    "Leaderboard": (218, 165, 32)   # золотой
}

MUTATIONS = {
    "Normal": {"chance": 0.88, "buff": 1.0, "name": "Обычная"},
    "Gold": {"chance": 0.10, "buff": 1.15, "name": "✨ Золотая"},
    "Rainbow": {"chance": 0.02, "buff": 1.30, "name": "🌈 Радужная"}
}

# Ранги, кубки, и награды (шекели УМНОЖЕНЫ НА 2, как просили)
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

# ==========================================
# ИНИЦИАЛИЗАЦИЯ БОТА И БД
# ==========================================
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            shekels INTEGER DEFAULT 10,
            trophies INTEGER DEFAULT 0,
            pity_mythic INTEGER DEFAULT 0,
            pity_super INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            last_quest_time TEXT DEFAULT '2000-01-01 00:00:00',
            quests_done_hour INTEGER DEFAULT 0
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
        
        await db.execute('''CREATE TABLE IF NOT EXISTS crates (
            crate_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            price INTEGER,
            photo_id TEXT,
            contents TEXT
        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS skills (
            user_id INTEGER PRIMARY KEY,
            points INTEGER DEFAULT 0
        )''')

        await db.execute('''CREATE TABLE IF NOT EXISTS global_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT,
            multiplier REAL,
            end_time TEXT
        )''')

        await db.commit()

# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (УТИЛИТЫ)
# ==========================================
def get_rank_by_trophies(trophies):
    for rank, data in RANKS.items():
        if data["min"] <= trophies <= data["max"]:
            return rank
    return "Ultimate I"

async def get_user_stats(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT shekels, trophies, pity_mythic, pity_super, username FROM users WHERE user_id = ?", (user_id,)) as cursor:
            return await cursor.fetchone()

def generate_card_frame(photo_bytes: bytes, rarity: str) -> bytes:
    """Накладывает цветную рамку на фото карты в зависимости от редкости."""
    try:
        img = Image.open(BytesIO(photo_bytes)).convert("RGBA")
        color = RARITY_COLORS.get(rarity, (255, 255, 255))
        
        # Добавляем толстую рамку 15px
        img_with_border = ImageOps.expand(img, border=15, fill=color)
        
        out = BytesIO()
        img_with_border.save(out, format="JPEG")
        return out.getvalue()
    except Exception as e:
        logging.error(f"Error generating frame: {e}")
        return photo_bytes

def generate_skill_panel(hp_pts, dmg_pts, cld_pts, available_pts) -> bytes:
    """Генерирует изображение как на референсе для прокачки навыков."""
    width, height = 500, 300
    img = Image.new('RGB', (width, height), color=(30, 35, 45))
    draw = ImageDraw.Draw(img)
    
    try:
        font_large = ImageFont.truetype("arial.ttf", 28)
        font_medium = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()

    # Отрисовка внешней рамки
    draw.rectangle([10, 10, width-10, height-10], outline=(255, 100, 50), width=3)
    
    # Заголовок
    draw.text((120, 20), "ОЧКИ НАВЫКОВ", fill=(255, 150, 50), font=font_large)
    draw.text((150, 60), f"Осталось: {available_pts}", fill=(50, 255, 100), font=font_medium)
    
    # Полоски (HP, DMG, CLD)
    stats = [
        ("HP", hp_pts, (255, 50, 50), 120),
        ("DMG", dmg_pts, (255, 165, 0), 170),
        ("CLD", cld_pts, (50, 150, 255), 220) # Используем CLD вместо DEF
    ]
    
    for name, pts, color, y in stats:
        draw.text((30, y-10), name, fill=color, font=font_large)
        
        # Значение множителя
        mult = 1.0 + (pts * 0.05)
        draw.text((120, y-5), f"x{mult:.2f}", fill=(255,255,255), font=font_medium)
        
        # Прогресс бар фон
        bar_x = 220
        draw.rectangle([bar_x, y, bar_x+150, y+15], fill=(50, 50, 60), outline=(100, 100, 100))
        # Прогресс бар заливка
        if pts > 0:
            fill_width = int(150 * (pts / 100.0))
            draw.rectangle([bar_x, y, bar_x+fill_width, y+15], fill=color)
            
        # Текст прогресса
        draw.text((390, y-5), f"[{pts}/100]", fill=(200, 200, 200), font=font_medium)

    out = BytesIO()
    img.save(out, format="JPEG")
    return out.getvalue()

async def get_next_serial(rarity):
    if rarity not in ["Mythic", "Super", "Exclusive", "Leaderboard"]:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM inventory i JOIN cards c ON i.card_id = c.card_id WHERE c.rarity = ?", (rarity,)) as cursor:
            count = await cursor.fetchone()
            serial = count[0] + 1
            if serial > 9999: return 9999
            return f"#{serial:04d}"

# ==========================================
# МАШИНА СОСТОЯНИЙ (FSM)
# ==========================================
class CardCreation(StatesGroup):
    photo = State()
    name = State()
    rarity = State()
    c_class = State()
    damage = State()
    hp = State()
    cooldown = State()
    confirm = State()

class CrateCreation(StatesGroup):
    photo = State()
    price = State()
    cards = State() # Выбор шансов

# ==========================================
# КЛАВИАТУРЫ
# ==========================================
def main_menu_kb(is_admin=False):
    kb = [
        [InlineKeyboardButton(text="📦 Крейты", callback_data="menu_crates"), InlineKeyboardButton(text="⚔️ Поиск боя", callback_data="menu_battle"), InlineKeyboardButton(text="📜 Квесты", callback_data="menu_quests")],
        [InlineKeyboardButton(text="🏆 Топ-игроков", callback_data="menu_top"), InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile"), InlineKeyboardButton(text="✨ Очки навыков", callback_data="menu_skills")],
        [InlineKeyboardButton(text="🎒 Инвентарь", callback_data="menu_inventory"), InlineKeyboardButton(text="📖 Индекс", callback_data="menu_index"), InlineKeyboardButton(text="🛡 Экипировка", callback_data="menu_equip")],
        [InlineKeyboardButton(text="🌱 Сид-паки", callback_data="menu_seeds")]
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
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ])

def battle_difficulty_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Лёгкий (-50% трофеев)", callback_data="battle_start_easy")],
        [InlineKeyboardButton(text="🟡 Средний (базовые награды)", callback_data="battle_start_medium")],
        [InlineKeyboardButton(text="🔴 Сложный (+30% трофеев)", callback_data="battle_start_hard")],
        [InlineKeyboardButton(text="💀 КОШМАР (+80% трофеев)", callback_data="battle_start_nightmare")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ])

# ==========================================
# ОБРАБОТЧИКИ ОСНОВНОГО МЕНЮ И ПРОФИЛЯ
# ==========================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, username, shekels) VALUES (?, ?, 10)", (user_id, username))
        await db.commit()
        
        async with db.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            is_admin = bool(res[0]) or user_id in ADMIN_IDS

    text = f"👋 Привет, <b>{username}</b>!\nДобро пожаловать в Карточную Битву! Выбирай действие ниже:"
    await message.answer(text, reply_markup=main_menu_kb(is_admin))

@dp.callback_query(F.data == "menu_main")
async def cb_menu_main(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            is_admin = bool(res[0]) or user_id in ADMIN_IDS
    await callback.message.edit_text("Выбирай действие ниже:", reply_markup=main_menu_kb(is_admin))

@dp.callback_query(F.data == "menu_profile")
async def cb_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    stats = await get_user_stats(user_id)
    if not stats:
        return await callback.answer("Ошибка профиля!")
    
    shekels, trophies, pity_m, pity_s, username = stats
    rank = get_rank_by_trophies(trophies)

    # Получение экипировки
    equipped_text = ""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT c.name, i.mutation, c.rarity, i.hp_pts, i.dmg_pts, i.cld_pts
            FROM inventory i JOIN cards c ON i.card_id = c.card_id 
            WHERE i.user_id = ? AND i.is_equipped = 1 ORDER BY i.equip_slot
        """, (user_id,)) as cursor:
            equipped = await cursor.fetchall()
            for eq in equipped:
                mut = MUTATIONS[eq[1]]["name"]
                equipped_text += f"• {mut} {eq[0]} [{eq[2]}] (Очки: {eq[3]+eq[4]+eq[5]})\n"
            if not equipped:
                equipped_text = "<i>Пусто</i>"

    text = (
        f"👤 <b>Профиль игрока:</b> {username}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💠 <b>Ранг:</b> {rank}\n"
        f"🏆 <b>Кубки:</b> {trophies}\n"
        f"🪙 <b>Шекелей:</b> {shekels}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔮 <b>Гарант на Мифик:</b> {pity_m}/1000\n"
        f"🌈 <b>Гарант на Супер:</b> {pity_s}/10000\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🛡 <b>Экипировка:</b>\n{equipped_text}"
    )
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]]))

# ==========================================
# ИНВЕНТАРЬ И ЭКИПИРОВКА
# ==========================================
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

    per_page = 50
    total_pages = math.ceil(len(items) / per_page)
    if total_pages == 0: total_pages = 1
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_items = items[start_idx:end_idx]

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
    kb = [
        [InlineKeyboardButton(text="Слот 1", callback_data="equip_slot:1"), InlineKeyboardButton(text="Слот 2", callback_data="equip_slot:2")],
        [InlineKeyboardButton(text="Слот 3", callback_data="equip_slot:3"), InlineKeyboardButton(text="Слот 4", callback_data="equip_slot:4")],
        [InlineKeyboardButton(text="❌ Снять всё", callback_data="equip_clear")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ]
    await callback.message.edit_text("🛡 Выберите слот для экипировки:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

# ==========================================
# ИНДЕКС
# ==========================================
@dp.callback_query(F.data.startswith("menu_index"))
async def cb_index(callback: CallbackQuery):
    page = 0
    if ":" in callback.data:
        page = int(callback.data.split(":")[1])
        
    user_id = callback.from_user.id
    per_page = 8
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT card_id, name, rarity, damage, hp, is_hidden_index FROM cards ORDER BY rarity DESC") as cursor:
            all_cards = await cursor.fetchall()
            
        # Получаем открытые пользователем карты
        async with db.execute("SELECT DISTINCT card_id FROM inventory WHERE user_id = ?", (user_id,)) as cursor:
            unlocked_ids = [r[0] for r in await cursor.fetchall()]

    # Фильтруем скрытые
    visible_cards = [c for c in all_cards if not c[5]]
    total_pages = math.ceil(len(visible_cards) / per_page)
    if total_pages == 0: total_pages = 1
    
    start_idx = page * per_page
    end_idx = start_idx + per_page
    page_cards = visible_cards[start_idx:end_idx]

    text = f"📖 <b>ОСНОВНОЙ ИНДЕКС КАРТ (Стр. {page+1}/{total_pages})</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    async with aiosqlite.connect(DB_PATH) as db:
        for idx, c in enumerate(page_cards, start=start_idx+1):
            c_id, name, rarity, dmg, hp, _ = c
            
            # Статистика по карте в мире
            async with db.execute("SELECT COUNT(*), SUM(CASE WHEN mutation='Gold' THEN 1 ELSE 0 END), SUM(CASE WHEN mutation='Rainbow' THEN 1 ELSE 0 END) FROM inventory WHERE card_id=?", (c_id,)) as cur2:
                stats = await cur2.fetchone()
                total_exist = stats[0] or 0
                g_exist = stats[1] or 0
                r_exist = stats[2] or 0
            
            if c_id in unlocked_ids:
                text += f"{idx}. 🃏 <b>{name}</b>\n"
                text += f"   └  {rarity}\n"
                text += f"   └ Урон: {dmg} // Здоровье: {hp}\n"
            else:
                text += f"{idx}. ❓ <b>??? (Не открыто)</b>\n"
                text += f"   └  {rarity}\n"
                
            text += f"   └ Существует: {total_exist} шт.\n"
            text += f"   └ Из них: Золотых: {g_exist}, Радужных: {r_exist}\n\n"

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

# ==========================================
# БОЕВАЯ СИСТЕМА И ИИ
# ==========================================
@dp.callback_query(F.data == "menu_battle")
async def cb_battle_menu(callback: CallbackQuery):
    await callback.message.edit_text("⚔️ Выберите сложность боя:", reply_markup=battle_difficulty_kb())

@dp.callback_query(F.data.startswith("battle_start_"))
async def process_battle(callback: CallbackQuery):
    difficulty = callback.data.split("_")[2]
    user_id = callback.from_user.id
    
    # 1. Получаем команду игрока
    team_player = []
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT c.name, c.damage, c.hp, c.cooldown, c.card_class, i.mutation, i.hp_pts, i.dmg_pts, i.cld_pts
            FROM inventory i JOIN cards c ON i.card_id = c.card_id 
            WHERE i.user_id = ? AND i.is_equipped = 1 ORDER BY i.equip_slot
        """, (user_id,)) as cursor:
            rows = await cursor.fetchall()
            for r in rows:
                mut_buff = MUTATIONS[r[5]]["buff"]
                hp_mult = 1.0 + (r[6] * 0.05)
                dmg_mult = 1.0 + (r[7] * 0.05)
                cld_mult = 1.0 - (r[8] * 0.05) # Меньше кд = быстрее бьет
                
                final_hp = int(r[2] * mut_buff * hp_mult)
                final_dmg = int(r[1] * mut_buff * dmg_mult)
                final_cld = max(0.1, r[3] * cld_mult) # Кд не меньше 0.1s
                
                team_player.append({
                    "name": r[0], "base_hp": final_hp, "hp": final_hp, "dmg": final_dmg,
                    "cld": final_cld, "class": r[4], "next_attack": final_cld, "owner": "player"
                })

    if not team_player:
        return await callback.answer("У вас нет экипированных карт!", show_alert=True)

    await callback.message.edit_text("⏳ Подготовка к бою...")
    await asyncio.sleep(3)

    # 2. Генерация команды ИИ
    stats = await get_user_stats(user_id)
    rank = get_rank_by_trophies(stats[1])
    
    # Заглушка генерации ИИ: случайные карты в зависимости от сложности
    team_ai = []
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name, damage, hp, cooldown, card_class FROM cards WHERE is_banned_ai = 0 ORDER BY RANDOM() LIMIT 4") as cursor:
            ai_rows = await cursor.fetchall()
            
            # Баффы ИИ в зависимости от сложности
            ai_diff_mult = {"easy": 0.6, "medium": 1.0, "hard": 1.4, "nightmare": 2.0}[difficulty]
            
            for r in ai_rows:
                f_hp = int(r[2] * ai_diff_mult)
                f_dmg = int(r[1] * ai_diff_mult)
                team_ai.append({
                    "name": f"AI {r[0]}", "base_hp": f_hp, "hp": f_hp, "dmg": f_dmg,
                    "cld": r[3], "class": r[4], "next_attack": r[3], "owner": "ai"
                })

    # 3. Симуляция боя (АВТОБОЙ)
    log = []
    time_passed = 0.0
    max_time = 60.0 # Ограничение по времени боя (защита от бесконечного цикла)
    
    all_units = team_player + team_ai
    
    while time_passed < max_time and len([u for u in team_player if u["hp"] > 0]) > 0 and len([u for u in team_ai if u["hp"] > 0]) > 0:
        # Находим юнита с минимальным временем до следующей атаки
        next_unit = min([u for u in all_units if u["hp"] > 0], key=lambda x: x["next_attack"])
        step = next_unit["next_attack"] - time_passed
        time_passed = next_unit["next_attack"]
        
        # Определение целей
        enemies = team_ai if next_unit["owner"] == "player" else team_player
        alive_enemies = [e for e in enemies if e["hp"] > 0]
        
        if not alive_enemies:
            break
            
        target = random.choice(alive_enemies)
        
        # Применение урона по классу
        if next_unit["class"] == "Single":
            target["hp"] -= next_unit["dmg"]
            log.append(f"⚔️ {next_unit['name']} бьет {target['name']} на {next_unit['dmg']}!")
        elif next_unit["class"] == "Splash":
            target["hp"] -= next_unit["dmg"]
            log.append(f"💥 {next_unit['name']} сплеш по {target['name']} на {next_unit['dmg']}!")
            for e in alive_enemies:
                if e != target:
                    e["hp"] -= int(next_unit["dmg"] * 0.5)
        elif next_unit["class"] == "AOE":
            for e in alive_enemies:
                e["hp"] -= next_unit["dmg"]
            log.append(f"🔥 {next_unit['name']} АОЕ атака на {next_unit['dmg']} по всем!")
        elif next_unit["class"] == "Booster":
            # Простой буст (лечит своих)
            allies = team_player if next_unit["owner"] == "player" else team_ai
            for a in allies:
                if a["hp"] > 0:
                    a["hp"] = min(a["base_hp"], a["hp"] + next_unit["dmg"])
            log.append(f"✨ {next_unit['name']} исцеляет команду на {next_unit['dmg']}!")
        
        next_unit["next_attack"] += next_unit["cld"]

    # 4. Итоги боя
    player_won = len([u for u in team_player if u["hp"] > 0]) > 0
    
    # Награды
    r_data = RANKS[rank]
    base_trop = random.randint(r_data["trophies"][0], r_data["trophies"][1])
    base_shek = random.randint(r_data["shekels"][0], r_data["shekels"][1])
    
    if difficulty == "easy":
        base_trop = int(base_trop * 0.5)
    elif difficulty == "hard":
        base_trop = int(base_trop * 1.3)
    elif difficulty == "nightmare":
        base_trop = int(base_trop * 1.8)
        
    skill_pts = 0
    sp_chances = {"easy": 0.1, "medium": 0.2, "hard": 0.35, "nightmare": 0.5}
    if random.random() < sp_chances[difficulty]:
        skill_pts = 1 if difficulty in ["easy", "medium"] else (2 if difficulty == "hard" else 3)

    if not player_won:
        base_trop = -int(base_trop * 0.3) # При поражении отнимается немного
        base_shek = 1
        skill_pts = 0
        result_title = "❌ ПОРАЖЕНИЕ"
    else:
        result_title = "🏆 ПОБЕДА"

    # Обновление БД
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET trophies = trophies + ?, shekels = shekels + ? WHERE user_id = ?", (base_trop, base_shek, user_id))
        if skill_pts > 0:
            await db.execute("INSERT OR IGNORE INTO skills (user_id, points) VALUES (?, 0)", (user_id,))
            await db.execute("UPDATE skills SET points = points + ? WHERE user_id = ?", (skill_pts, user_id))
        await db.commit()

    # Формирование сообщения
    log_text = "\n".join(log[-8:]) # Последние 8 логов
    
    def team_str(team):
        res = ""
        for u in team:
            hp = max(0, u["hp"])
            res += f"• {u['name']} (⚔️{u['dmg']} | ❤️{hp}/{u['base_hp']})\n"
        return res

    msg = (
        f"🏟 <b>АРЕНА: БИТВА</b> ({result_title})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🟦 <b>Команда {callback.from_user.username}:</b>\n{team_str(team_player)}\n"
        f"🟥 <b>Команда AI ({difficulty}):</b>\n{team_str(team_ai)}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📜 <b>Лог (последние события):</b>\n{log_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 <b>Награды:</b>\n"
        f"🏆 Трофеи: {base_trop}\n"
        f"🪙 Шекели: {base_shek}\n"
    )
    if skill_pts > 0:
        msg += f"✨ Очки навыков: +{skill_pts}\n"

    await callback.message.edit_text(msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ В меню", callback_data="menu_main")]]))

# ==========================================
# ОЧКИ НАВЫКОВ (ВЫВОД ГРАФИКИ)
# ==========================================
@dp.callback_query(F.data == "menu_skills")
async def cb_skills_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT points FROM skills WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            pts = row[0] if row else 0
            
    if pts == 0:
        return await callback.answer("У вас нет свободных очков навыков! Сражайтесь, чтобы получить их.", show_alert=True)
        
    # Выбор карты для прокачки
    # Здесь упрощенно выдаем инвентарь (на самом деле нужно меню как в инвентаре, но для экономии строк выводим экипированные)
    kb = []
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("""
            SELECT i.item_id, c.name, i.hp_pts, i.dmg_pts, i.cld_pts 
            FROM inventory i JOIN cards c ON i.card_id = c.card_id 
            WHERE i.user_id = ? AND i.is_equipped = 1
        """, (user_id,)) as cursor:
            equipped = await cursor.fetchall()
            for eq in equipped:
                kb.append([InlineKeyboardButton(text=f"✨ {eq[1]}", callback_data=f"skill_card:{eq[0]}")])
                
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")])
    await callback.message.edit_text(f"У вас <b>{pts}</b> очков навыков.\nВыберите экипированную карту для прокачки:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("skill_card:"))
async def cb_skill_show(callback: CallbackQuery):
    item_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT hp_pts, dmg_pts, cld_pts FROM inventory WHERE item_id = ?", (item_id,)) as cursor:
            card_data = await cursor.fetchone()
        async with db.execute("SELECT points FROM skills WHERE user_id = ?", (user_id,)) as cursor:
            skill_pts = (await cursor.fetchone())[0]

    if not card_data:
        return await callback.answer("Карта не найдена.")

    hp_p, dmg_p, cld_p = card_data
    
    # Генерация картинки
    img_bytes = generate_skill_panel(hp_p, dmg_p, cld_p, skill_pts)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="HP [+1]", callback_data=f"add_skill:{item_id}:hp:1"), InlineKeyboardButton(text="HP [+5]", callback_data=f"add_skill:{item_id}:hp:5")],
        [InlineKeyboardButton(text="DMG [+1]", callback_data=f"add_skill:{item_id टाइगर}:dmg:1"), InlineKeyboardButton(text="DMG [+5]", callback_data=f"add_skill:{item_id}:dmg:5")],
        [InlineKeyboardButton(text="CLD [+1]", callback_data=f"add_skill:{item_id}:cld:1"), InlineKeyboardButton(text="CLD [+5]", callback_data=f"add_skill:{item_id}:cld:5")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_skills")]
    ])
    
    # Удаляем старое сообщение и отправляем фото с кнопками
    await callback.message.delete()
    await bot.send_photo(chat_id=callback.message.chat.id, photo=BufferedInputFile(img_bytes, filename="skills.jpg"), caption="Распределите очки навыков:", reply_markup=kb)

# ==========================================
# АДМИН ПАНЕЛЬ - КАРТЫ
# ==========================================
@dp.callback_query(F.data == "admin_panel")
async def cb_admin_panel(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        return await callback.answer("У вас нет доступа!", show_alert=True)
    await callback.message.edit_text("⚙️ <b>АДМИН ПАНЕЛЬ</b>\nВыберите раздел:", reply_markup=admin_panel_kb())

@dp.callback_query(F.data == "admin_cards")
async def cb_admin_cards(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Создать карту", callback_data="admin_create_card")],
        [InlineKeyboardButton(text="✏️ Изменить карту", callback_data="admin_edit_card")],
        [InlineKeyboardButton(text="🗑 Удалить карту", callback_data="admin_del_card")],
        [InlineKeyboardButton(text="⬅️ В админ-меню", callback_data="admin_panel")]
    ])
    await callback.message.edit_text("🃏 <b>Управление картами</b>", reply_markup=kb)

# FSM: Создание карты
@dp.callback_query(F.data == "admin_create_card")
async def create_card_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CardCreation.photo)
    await callback.message.edit_text("Отправьте фото для новой карты:")

@dp.message(CardCreation.photo, F.photo)
async def create_card_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await state.set_state(CardCreation.name)
    await message.answer("Введите название карты:")

@dp.message(CardCreation.name)
async def create_card_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=r, callback_data=f"set_rarity:{r}") for r in list(RARITY_COLORS.keys())[i:i+3]]
        for i in range(0, len(RARITY_COLORS), 3)
    ])
    await state.set_state(CardCreation.rarity)
    await message.answer("Выберите редкость:", reply_markup=kb)

@dp.callback_query(CardCreation.rarity, F.data.startswith("set_rarity:"))
async def create_card_rarity(callback: CallbackQuery, state: FSMContext):
    rarity = callback.data.split(":")[1]
    await state.update_data(rarity=rarity)
    
    classes = ["Single", "Splash", "AOE", "Booster", "Fire"]
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=c, callback_data=f"set_class:{c}")] for c in classes])
    
    await state.set_state(CardCreation.c_class)
    await callback.message.edit_text("Выберите класс:", reply_markup=kb)

@dp.callback_query(CardCreation.c_class, F.data.startswith("set_class:"))
async def create_card_class(callback: CallbackQuery, state: FSMContext):
    c_class = callback.data.split(":")[1]
    await state.update_data(c_class=c_class)
    await state.set_state(CardCreation.damage)
    await callback.message.edit_text("Введите значение урона (число):")

@dp.message(CardCreation.damage)
async def create_card_dmg(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Это должно быть число!")
    await state.update_data(damage=int(message.text))
    await state.set_state(CardCreation.hp)
    await message.answer("Введите значение здоровья (число):")

@dp.message(CardCreation.hp)
async def create_card_hp(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("Это должно быть число!")
    await state.update_data(hp=int(message.text))
    await state.set_state(CardCreation.cooldown)
    await message.answer("Введите кулдаун (в секундах, например 1.5):")

@dp.message(CardCreation.cooldown)
async def create_card_cld(message: types.Message, state: FSMContext):
    try:
        cld = float(message.text)
    except ValueError:
        return await message.answer("Это должно быть число с точкой (например 1.5)!")
        
    await state.update_data(cooldown=cld)
    data = await state.get_data()
    
    # Скачиваем фото и накладываем рамку
    file = await bot.get_file(data['photo_id'])
    photo_bytes = await bot.download_file(file.file_path)
    
    framed_photo = generate_card_frame(photo_bytes.read(), data['rarity'])
    
    # Сохраняем в Telegram (отправляем себе, берем новый ID)
    sent_msg = await message.answer_photo(
        photo=BufferedInputFile(framed_photo, filename="framed.jpg"),
        caption=f"📝 <b>ПРОВЕРКА КАРТЫ:</b>\nНазвание: {data['name']}\nРедкость: {data['rarity']}\nКласс: {data['c_class']}\nУрон: {data['damage']} | Здоровье: {data['hp']} | КД: {data['cooldown']}s",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_card_create"), InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_state")]
        ])
    )
    # Обновляем photo_id на новое с рамкой
    await state.update_data(final_photo_id=sent_msg.photo[-1].file_id)
    await state.set_state(CardCreation.confirm)

@dp.callback_query(CardCreation.confirm, F.data == "confirm_card_create")
async def finish_card_create(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO cards (name, rarity, card_class, damage, hp, cooldown, photo_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (data['name'], data['rarity'], data['c_class'], data['damage'], data['hp'], data['cooldown'], data['final_photo_id']))
        await db.commit()
        
    await state.clear()
    await callback.message.edit_caption(caption="✅ Карта успешно создана и добавлена в БД!")

@dp.callback_query(F.data == "cancel_state")
async def cancel_state(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Действие отменено.", reply_markup=admin_panel_kb())

# ==========================================
# ЗАПУСК БОТА
# ==========================================
async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()
    
    # Регистрация команд
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
