import asyncio
import logging
import random
import math
import io
import time
import json
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputFile, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
import aiosqlite
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ----------------- КОНФИГУРАЦИЯ И КОНСТАНТЫ -----------------
# Вставь сюда токен своего бота
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
MAIN_ADMIN_ID = 123456789  # Замени на свой Telegram ID

DB_FILE = "gamedata.db"

# Редкости и их цвета (RGB) для рамок
RARITIES = {
    "Basic": {"color": (128, 128, 128), "ru": "Серый"},
    "Uncommon": {"color": (0, 255, 0), "ru": "Зеленый"},
    "Rare": {"color": (0, 255, 255), "ru": "Голубой"},
    "Epic": {"color": (128, 0, 128), "ru": "Фиолетовый"},
    "Legendary": {"color": (255, 255, 0), "ru": "Желтый"},
    "Mythic": {"color": (255, 0, 0), "ru": "Красный"},
    "Super": {"color": (255, 105, 180), "ru": "Радужный"}, # Будет имитация перелива
    "Secret": {"color": (0, 0, 0), "ru": "Черный"},
    "Exclusive": {"color": (255, 192, 203), "ru": "Розовый"},
    "Leaderboard": {"color": (255, 215, 0), "ru": "Золотой"}
}

# Классы карт
CLASSES = ["Single", "Splash", "AOE", "Booster", "Fire"]

# Шансы мутаций
MUTATIONS = {
    "Normal": {"chance": 88, "mult": 1.0, "name": "Обычная"},
    "Gold": {"chance": 10, "mult": 1.15, "name": "Золотая 🌟"},
    "Rainbow": {"chance": 2, "mult": 1.30, "name": "Радужная 🌈"}
}

# Ранги: Название, мин. трофеи, макс. трофеи, (награда от, до), шекели базово
RANKS_DATA = [
    ("Rock I", 0, 150, 60, 80, 2), ("Rock II", 151, 350, 55, 70, 4), ("Rock III", 351, 600, 50, 65, 4), ("Rock IV", 601, 1000, 50, 60, 4),
    ("Bronze I", 1001, 1275, 45, 60, 5), ("Bronze II", 1276, 1600, 45, 55, 5), ("Bronze III", 1601, 1800, 40, 50, 6), ("Bronze IV", 1801, 2250, 40, 48, 7),
    ("Iron I", 2251, 2700, 38, 45, 7), ("Iron II", 2701, 3200, 35, 42, 9), ("Iron III", 3201, 3800, 32, 38, 11), ("Iron IV", 3801, 4500, 28, 35, 13),
    ("Gold I", 4501, 5300, 25, 32, 15), ("Gold II", 5301, 6200, 22, 28, 17), ("Gold III", 6201, 7200, 20, 25, 19), ("Gold IV", 7201, 8300, 18, 22, 21),
    ("Diamond I", 8301, 9500, 16, 20, 23), ("Diamond II", 9501, 10800, 14, 18, 25), ("Diamond III", 10801, 12200, 12, 16, 27), ("Diamond IV", 12201, 13700, 10, 14, 29),
    ("Platina I", 13701, 15300, 9, 13, 31), ("Platina II", 15301, 17000, 8, 11, 33), ("Platina III", 17001, 18800, 7, 10, 35), ("Platina IV", 18801, 20700, 6, 9, 37),
    ("Modern I", 20701, 22700, 6, 8, 39), ("Modern II", 22701, 24800, 5, 7, 41), ("Modern III", 24801, 27000, 4, 6, 43), ("Modern IV", 27001, 29300, 4, 5, 45),
    ("Digital I", 29301, 31700, 3, 5, 47), ("Digital II", 31701, 34200, 3, 4, 49), ("Digital III", 34201, 36800, 2, 4, 51), ("Digital IV", 36801, 39500, 2, 3, 53),
    ("Cosmic I", 39501, 42300, 2, 3, 55), ("Cosmic II", 42301, 45200, 2, 2, 57), ("Cosmic III", 45201, 48200, 1, 2, 59), ("Cosmic IV", 48201, 50000, 1, 1, 61),
    ("Ultimate I", 50001, 999999, 1, 1, 75)
]

def get_rank_info(trophies):
    for r in RANKS_DATA:
        if r[1] <= trophies <= r[2]:
            return {"name": r[0], "min_t": r[1], "max_t": r[2], "cup_min": r[3], "cup_max": r[4], "shekels": r[5]}
    return {"name": "Ultimate I", "min_t": 50001, "max_t": 999999, "cup_min": 1, "cup_max": 1, "shekels": 75}

# Инициализация роутера
router = Router()

# FSM Состояния
class AdminStates(StatesGroup):
    waiting_for_card_photo = State()
    waiting_for_card_name = State()
    waiting_for_card_rarity = State()
    waiting_for_card_class = State()
    waiting_for_card_damage = State()
    waiting_for_card_health = State()
    waiting_for_card_cooldown = State()
    waiting_for_card_confirm = State()
    
    waiting_for_give_cups_user = State()
    waiting_for_give_cups_amount = State()
    
    waiting_for_give_shekels_user = State()
    waiting_for_give_shekels_amount = State()
    
    waiting_for_crate_photo = State()
    waiting_for_crate_price = State()
    waiting_for_crate_card_chances = State()

class UserStates(StatesGroup):
    waiting_for_gift_user = State()

async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        # Игроки
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            display_name TEXT,
            trophies INTEGER DEFAULT 0,
            shekels INTEGER DEFAULT 10,
            robux INTEGER DEFAULT 0,
            stars INTEGER DEFAULT 0,
            vip_status INTEGER DEFAULT 0,
            mythic_pity INTEGER DEFAULT 0,
            super_pity INTEGER DEFAULT 0,
            is_banned INTEGER DEFAULT 0,
            is_admin INTEGER DEFAULT 0,
            equip_slots INTEGER DEFAULT 4,
            in_battle INTEGER DEFAULT 0
        )''')
        # Инвентарь
        await db.execute('''CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            card_id INTEGER,
            mutation TEXT DEFAULT 'Normal',
            serial_number INTEGER DEFAULT 0,
            skill_hp INTEGER DEFAULT 0,
            skill_dmg INTEGER DEFAULT 0,
            skill_cld INTEGER DEFAULT 0,
            is_equipped INTEGER DEFAULT 0,
            equip_slot INTEGER DEFAULT 0,
            in_afk INTEGER DEFAULT 0
        )''')
        # Карты
        await db.execute('''CREATE TABLE IF NOT EXISTS cards (
            card_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            photo_id TEXT,
            rarity TEXT,
            char_class TEXT,
            damage INTEGER,
            health INTEGER,
            cooldown REAL,
            ai_banned INTEGER DEFAULT 0,
            index_hidden INTEGER DEFAULT 0
        )''')
        # Крейты и Пакеты
        await db.execute('''CREATE TABLE IF NOT EXISTS gacha_boxes (
            box_id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT, -- 'crate' или 'seed_pack'
            name TEXT,
            photo_id TEXT,
            price INTEGER,
            contents TEXT -- JSON dict {card_id: chance_percentage}
        )''')
        # Ивенты и Настройки
        await db.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')
        # Инициализация базовых настроек
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('luck_multiplier', '1.0')")
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('shekel_multiplier', '1.0')")
        
        # Добавляем главного админа если его нет
        await db.execute("INSERT OR IGNORE INTO users (user_id, username, is_admin) VALUES (?, ?, 1)", (MAIN_ADMIN_ID, "MAIN_ADMIN"))
        
        await db.commit()

def create_card_image(photo_bytes, rarity):
    """Накладывает рамку редкости на фото карты"""
    try:
        base_img = Image.open(io.BytesIO(photo_bytes)).convert("RGBA")
        base_img = base_img.resize((512, 512)) # Стандартизируем размер
        
        color = RARITIES.get(rarity, RARITIES["Basic"])["color"]
        
        # Создаем рамку
        border_size = 20
        bordered_img = Image.new('RGBA', (512 + border_size*2, 512 + border_size*2), color)
        bordered_img.paste(base_img, (border_size, border_size))
        
        # Эффект для Super/Mythic
        if rarity == "Super":
            # Простой эффект переливания (радужная рамка) - градиент
            draw = ImageDraw.Draw(bordered_img)
            for i in range(border_size):
                r = int(255 * (i / border_size))
                g = int(105 + 150 * (i / border_size))
                b = int(180 + 75 * (i / border_size))
                draw.rectangle([i, i, bordered_img.width-i, bordered_img.height-i], outline=(r,g,b))
                
        out_bytes = io.BytesIO()
        bordered_img.save(out_bytes, format='PNG')
        out_bytes.seek(0)
        return out_bytes.getvalue()
    except Exception as e:
        logging.error(f"Error creating card image: {e}")
        return photo_bytes

def generate_skill_points_image(card_name, free_points, hp_pts, dmg_pts, cld_pts):
    """
    Генерирует изображение прокачки навыков в стиле предоставленного референса photo_5400123185572813894_x.jpg.
    Черный фон, неоновые акценты, прогресс-бары.
    """
    width, height = 600, 450
    # Темно-синий/почти черный фон как на скрине
    img = Image.new('RGB', (width, height), (25, 30, 40))
    draw = ImageDraw.Draw(img)
    
    try:
        # Попытка загрузить шрифты. В реальной среде лучше использовать пути к ttf файлам
        font_title = ImageFont.truetype("arialbd.ttf", 36)
        font_text = ImageFont.truetype("arial.ttf", 24)
        font_small = ImageFont.truetype("arial.ttf", 18)
    except:
        font_title = ImageFont.load_default()
        font_text = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # Оранжевая внешняя рамка
    draw.rounded_rectangle([10, 10, width-10, height-10], radius=15, outline=(255, 100, 50), width=4)
    
    # Заголовок
    draw.text((width//2, 30), "ОЧКИ НАВЫКОВ", font=font_title, fill=(255, 120, 50), anchor="mt")
    draw.text((width//2, 70), f"Осталось: {free_points}", font=font_title, fill=(100, 255, 100), anchor="mt")
    
    # Линия разделитель
    draw.line([(50, 120), (width-50, 120)], fill=(255, 100, 50), width=2)
    
    # Функция для отрисовки одной строки навыка
    def draw_skill_row(y_pos, title, color, current_pts, mult_text):
        # Текст навыка
        draw.text((50, y_pos), title, font=font_title, fill=color)
        # Множитель
        draw.text((180, y_pos+5), mult_text, font=font_title, fill=(255, 255, 255))
        # Текст прогресса [8/100]
        draw.text((width-150, y_pos+10), f"[{current_pts}/100]", font=font_text, fill=(200, 200, 200))
        
        # Прогресс бар фон
        bar_x, bar_y, bar_w, bar_h = 50, y_pos + 45, width - 100, 10
        draw.rounded_rectangle([bar_x, bar_y, bar_x+bar_w, bar_y+bar_h], radius=5, fill=(40, 45, 60))
        # Заполненный прогресс бар
        if current_pts > 0:
            fill_w = int(bar_w * (current_pts / 100.0))
            draw.rounded_rectangle([bar_x, bar_y, bar_x+fill_w, bar_y+bar_h], radius=5, fill=color)

    # HP
    hp_mult = 1.0 + (hp_pts * 0.05)
    draw_skill_row(140, "HP", (255, 80, 80), hp_pts, f"x{hp_mult:.2f}")
    
    # DMG
    dmg_mult = 1.0 + (dmg_pts * 0.05)
    draw_skill_row(230, "DMG", (255, 165, 0), dmg_pts, f"x{dmg_mult:.2f}")
    
    # CLD (Перезарядка) - отображаем как множитель скорости атаки или уменьшение кд
    cld_mult = 1.0 - (cld_pts * 0.005) # 100 очков = -50% кд
    draw_skill_row(320, "CLD", (100, 180, 255), cld_pts, f"x{cld_mult:.2f}")

    out_bytes = io.BytesIO()
    img.save(out_bytes, format='PNG')
    out_bytes.seek(0)
    return out_bytes.getvalue()

async def get_user(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return await cursor.fetchone()

async def check_and_register_user(message: types.Message):
    user = await get_user(message.from_user.id)
    if not user:
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute(
                "INSERT INTO users (user_id, username, display_name) VALUES (?, ?, ?)",
                (message.from_user.id, message.from_user.username, message.from_user.full_name)
            )
            await db.commit()
        return await get_user(message.from_user.id)
    return user

def build_main_menu():
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📦 Крейты", callback_data="menu_crates"),
        InlineKeyboardButton(text="⚔️ Поиск боя", callback_data="menu_battle"),
        InlineKeyboardButton(text="📜 Квесты", callback_data="menu_quests")
    )
    builder.row(
        InlineKeyboardButton(text="🏆 Топ игроков", callback_data="menu_top"),
        InlineKeyboardButton(text="👤 Профиль", callback_data="menu_profile"),
        InlineKeyboardButton(text="🎯 Очки навыков", callback_data="menu_skills")
    )
    builder.row(
        InlineKeyboardButton(text="🎒 Инвентарь", callback_data="menu_inv"),
        InlineKeyboardButton(text="📚 Индекс", callback_data="menu_index"),
        InlineKeyboardButton(text="🛡 Экипировка", callback_data="menu_equip")
    )
    builder.row(
        InlineKeyboardButton(text="💤 AFK Мод", callback_data="menu_afk"),
        InlineKeyboardButton(text="💳 Донат", callback_data="menu_donate"),
        InlineKeyboardButton(text="🌱 Сид-паки", callback_data="menu_seedpacks")
    )
    builder.row(
        InlineKeyboardButton(text="🎁 Ежедневные награды", callback_data="menu_daily")
    )
    return builder.as_markup()

@router.message(Command("start", "menu"))
async def cmd_start(message: types.Message):
    user = await check_and_register_user(message)
    if user['is_banned']:
        await message.answer("🚫 Вы забанены в системе.")
        return

    text = f"👋 Привет, <b>{user['display_name']}</b>!\n\nДобро пожаловать в Карточную RPG! 🃏\nВыбери действие ниже:"
    
    markup = build_main_menu()
    
    if user['is_admin']:
        builder = InlineKeyboardBuilder()
        builder.attach(InlineKeyboardBuilder.from_markup(markup))
        builder.row(InlineKeyboardButton(text="👑 Админ Панель", callback_data="admin_panel"))
        markup = builder.as_markup()

    await message.answer(text, reply_markup=markup, parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "menu_profile")
async def show_profile(callback: types.CallbackQuery):
    user = await get_user(callback.from_user.id)
    rank_info = get_rank_info(user['trophies'])
    
    text = f"👤 <b>Профиль:</b> {user['display_name']}\n"
    text += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"🎖 <b>Ранг:</b> {rank_info['name']}\n"
    text += f"🏆 <b>Кубки:</b> {user['trophies']}\n"
    text += f"💰 <b>Шекели:</b> {user['shekels']}\n"
    text += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"🔮 <b>Гарант на Мифика:</b> {user['mythic_pity']}/1000\n"
    text += f"🌈 <b>Гарант на Супера:</b> {user['super_pity']}/10000\n"
    text += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"🛡 <b>Экипировка:</b>\n"
    
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('''
            SELECT i.equip_slot, c.name, c.rarity, i.mutation
            FROM inventory i
            JOIN cards c ON i.card_id = c.card_id
            WHERE i.user_id = ? AND i.is_equipped = 1
            ORDER BY i.equip_slot
        ''', (user['user_id'],))
        equipped = await cursor.fetchall()
        
    if not equipped:
        text += "<i>Нет экипированных карт</i>\n"
    else:
        for item in equipped:
            mut_text = f" [{MUTATIONS[item['mutation']]['name']}]" if item['mutation'] != 'Normal' else ""
            text += f"Слот {item['equip_slot']}: {item['name']} ({item['rarity']}){mut_text}\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Назад", callback_data="back_to_main")
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    user = await get_user(callback.from_user.id)
    text = f"👋 Главное меню\nВыбери действие ниже:"
    markup = build_main_menu()
    if user['is_admin']:
        builder = InlineKeyboardBuilder()
        builder.attach(InlineKeyboardBuilder.from_markup(markup))
        builder.row(InlineKeyboardButton(text="👑 Админ Панель", callback_data="admin_panel"))
        markup = builder.as_markup()
    await callback.message.edit_text(text, reply_markup=markup, parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: types.CallbackQuery):
    user = await get_user(callback.from_user.id)
    if not user['is_admin']:
        await callback.answer("У вас нет прав!", show_alert=True)
        return
        
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🃏 Карты", callback_data="admin_cards"),
        InlineKeyboardButton(text="👥 Игроки", callback_data="admin_users")
    )
    builder.row(
        InlineKeyboardButton(text="🎉 Ивенты", callback_data="admin_events"),
        InlineKeyboardButton(text="👮‍♂️ Админы", callback_data="admin_admins")
    )
    builder.row(
        InlineKeyboardButton(text="📦 Крейты", callback_data="admin_crates"),
        InlineKeyboardButton(text="🏆 Награды топ", callback_data="admin_top_rewards")
    )
    builder.row(
        InlineKeyboardButton(text="🌱 Сид-паки", callback_data="admin_seedpacks"),
        InlineKeyboardButton(text="🚫 Запреты ИИ", callback_data="admin_bans")
    )
    builder.row(
        InlineKeyboardButton(text="💾 Бекап БД", callback_data="admin_backup")
    )
    builder.row(InlineKeyboardButton(text="◀️ Выход", callback_data="back_to_main"))
    
    await callback.message.edit_text("👑 <b>Панель Администратора</b>\nВыберите категорию:", reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "admin_cards")
async def admin_cards_menu(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Создать карту", callback_data="admin_card_create"))
    builder.row(InlineKeyboardButton(text="✏️ Изменить карту", callback_data="admin_card_edit_list_0"))
    builder.row(InlineKeyboardButton(text="❌ Удалить карту", callback_data="admin_card_delete_list_0"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin_panel"))
    await callback.message.edit_text("🃏 <b>Управление картами</b>", reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "admin_card_create")
async def start_card_creation(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("Отправьте фото для новой карты:")
    await state.set_state(AdminStates.waiting_for_card_photo)

@router.message(AdminStates.waiting_for_card_photo, F.photo)
async def card_photo_received(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    await state.update_data(photo_id=photo_id)
    await message.answer("Отлично. Теперь введите <b>название карты</b>:", parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_for_card_name)

@router.message(AdminStates.waiting_for_card_name)
async def card_name_received(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    
    builder = InlineKeyboardBuilder()
    for rarity in RARITIES.keys():
        builder.button(text=rarity, callback_data=f"setrarity_{rarity}")
    builder.adjust(2)
    
    await message.answer("Выберите <b>редкость</b>:", reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_for_card_rarity)

@router.callback_query(AdminStates.waiting_for_card_rarity, F.data.startswith("setrarity_"))
async def card_rarity_selected(callback: types.CallbackQuery, state: FSMContext):
    rarity = callback.data.split("_")[1]
    await state.update_data(rarity=rarity)
    
    builder = InlineKeyboardBuilder()
    for cls in CLASSES:
        builder.button(text=cls, callback_data=f"setclass_{cls}")
    builder.adjust(2)
    
    await callback.message.edit_text("Выберите <b>класс</b>:", reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_for_card_class)

@router.callback_query(AdminStates.waiting_for_card_class, F.data.startswith("setclass_"))
async def card_class_selected(callback: types.CallbackQuery, state: FSMContext):
    cls = callback.data.split("_")[1]
    await state.update_data(char_class=cls)
    await callback.message.answer("Введите базовый <b>урон (Damage)</b> (число):", parse_mode=ParseMode.HTML)
    await state.set_state(AdminStates.waiting_for_card_damage)

@router.message(AdminStates.waiting_for_card_damage)
async def card_dmg_received(message: types.Message, state: FSMContext):
    try:
        dmg = int(message.text)
        await state.update_data(damage=dmg)
        await message.answer("Введите базовое <b>здоровье (HP)</b> (число):", parse_mode=ParseMode.HTML)
        await state.set_state(AdminStates.waiting_for_card_health)
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число.")

@router.message(AdminStates.waiting_for_card_health)
async def card_hp_received(message: types.Message, state: FSMContext):
    try:
        hp = int(message.text)
        await state.update_data(health=hp)
        await message.answer("Введите <b>перезарядку (Cooldown)</b> в секундах (например, 1.2):", parse_mode=ParseMode.HTML)
        await state.set_state(AdminStates.waiting_for_card_cooldown)
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число.")

@router.message(AdminStates.waiting_for_card_cooldown)
async def card_cd_received(message: types.Message, state: FSMContext, bot: Bot):
    try:
        cd = float(message.text)
        data = await state.get_data()
        data['cooldown'] = cd
        await state.update_data(cooldown=cd)
        
        # Загружаем фото для генерации рамки
        file_info = await bot.get_file(data['photo_id'])
        file_bytes = io.BytesIO()
        await bot.download_file(file_info.file_path, destination=file_bytes)
        
        # Генерируем картинку с рамкой
        framed_image = create_card_image(file_bytes.getvalue(), data['rarity'])
        
        text = f"📊 <b>Проверьте данные карты:</b>\n\n"
        text += f"Название: {data['name']}\n"
        text += f"Редкость: {data['rarity']}\n"
        text += f"Класс: {data['char_class']}\n"
        text += f"Урон: {data['damage']}\n"
        text += f"HP: {data['health']}\n"
        text += f"Кулдаун: {data['cooldown']}s\n"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="✅ Подтвердить", callback_data="confirm_card_creation")
        builder.button(text="❌ Отмена", callback_data="cancel_card_creation")
        
        await message.answer_photo(BufferedInputFile(framed_image, filename="card.png"), caption=text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)
        await state.set_state(AdminStates.waiting_for_card_confirm)
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число (можно с точкой).")

@router.callback_query(AdminStates.waiting_for_card_confirm, F.data == "confirm_card_creation")
async def save_new_card(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('''
            INSERT INTO cards (name, photo_id, rarity, char_class, damage, health, cooldown)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (data['name'], data['photo_id'], data['rarity'], data['char_class'], data['damage'], data['health'], data['cooldown']))
        await db.commit()
    
    await callback.message.edit_caption(caption="✅ Карта успешно создана и добавлена в базу!")
    await state.clear()

@router.callback_query(AdminStates.waiting_for_card_confirm, F.data == "cancel_card_creation")
async def cancel_new_card(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_caption(caption="❌ Создание карты отменено.")
    await state.clear()


class CombatUnit:
    def __init__(self, is_player, index, name, hp, dmg, cld, cls, rarity, mutation="Normal"):
        self.is_player = is_player
        self.index = index
        self.name = name
        self.max_hp = hp
        self.hp = hp
        self.dmg = dmg
        self.base_cld = cld
        self.cld = cld
        self.cls = cls
        self.rarity = rarity
        self.mutation = mutation
        self.time_to_act = cld
        self.is_dead = False
        
        # Применение множителей мутации
        mult = MUTATIONS.get(mutation, MUTATIONS["Normal"])["mult"]
        self.max_hp = int(self.max_hp * mult)
        self.hp = self.max_hp
        self.dmg = int(self.dmg * mult)

def select_targets(attacker, enemies):
    alive_enemies = [e for e in enemies if not e.is_dead]
    if not alive_enemies:
        return []
        
    if attacker.cls == "Single":
        return [(random.choice(alive_enemies), 1.0)]
    elif attacker.cls == "Splash":
        main_target = random.choice(alive_enemies)
        targets = [(main_target, 1.0)]
        for e in alive_enemies:
            if e != main_target:
                targets.append((e, 0.5))
        return targets
    elif attacker.cls == "AOE":
        return [(e, 1.0) for e in alive_enemies]
    return []

async def simulate_battle(player_team, enemy_team):
    """
    Симуляция боя. Возвращает (победитель: 'player' или 'enemy', лог_боя(list))
    Оптимизированная логика для Telegram (выдаем только ключевые логи, чтобы не спамить)
    """
    log = []
    time_elapsed = 0.0
    
    all_units = player_team + enemy_team
    
    # Booster логика - бафф в начале боя
    for u in all_units:
        if u.cls == "Booster":
            team = player_team if u.is_player else enemy_team
            for ally in team:
                if ally != u:
                    ally.dmg = int(ally.dmg * 1.2) # Бафф урона на 20%
                    log.append(f"🌀 {u.name} баффает урон команды!")

    step = 0
    max_steps = 150 # Защита от бесконечного цикла
    
    while step < max_steps:
        step += 1
        alive_p = [u for u in player_team if not u.is_dead]
        alive_e = [u for u in enemy_team if not u.is_dead]
        
        if not alive_p:
            return "enemy", log
        if not alive_e:
            return "player", log
            
        # Ищем следующего атакующего
        all_alive = alive_p + alive_e
        next_unit = min(all_alive, key=lambda x: x.time_to_act)
        time_advance = next_unit.time_to_act
        time_elapsed += time_advance
        
        # Продвигаем время
        for u in all_alive:
            u.time_to_act -= time_advance
            
            # Fire класс - пассивный урон каждую секунду (упрощенно: если прошло > 1 сек суммарно)
            if u.cls == "Fire" and time_advance > 0.5:
                enemy_side = enemy_team if u.is_player else player_team
                alive_enemies = [e for e in enemy_side if not e.is_dead]
                for e in alive_enemies:
                    burn_dmg = int(u.dmg * 0.1)
                    if burn_dmg < 1: burn_dmg = 1
                    e.hp -= burn_dmg
                    if e.hp <= 0: e.is_dead = True
        
        # Атака
        next_unit.time_to_act = next_unit.cld # Сброс КД
        
        if next_unit.cls in ["Single", "Splash", "AOE"]:
            enemies = enemy_team if next_unit.is_player else player_team
            targets = select_targets(next_unit, enemies)
            
            for target, mult in targets:
                actual_dmg = int(next_unit.dmg * mult)
                target.hp -= actual_dmg
                log_entry = f"{'[ИГРОК]' if next_unit.is_player else '[ИИ]'} {next_unit.name} бьет {target.name} на {actual_dmg}"
                if target.hp <= 0:
                    target.hp = 0
                    target.is_dead = True
                    log_entry += " 💀(Убит)"
                
                # Сохраняем только часть логов чтобы влезло в сообщение
                if len(log) < 30 or (target.is_dead):
                    log.append(log_entry)

    return "enemy", log # Тайм-аут = поражение

@router.callback_query(F.data == "menu_battle")
async def battle_menu(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🟢 Лёгкий (-50% кубков)", callback_data="start_battle_easy"))
    builder.row(InlineKeyboardButton(text="🟡 Средний (База)", callback_data="start_battle_medium"))
    builder.row(InlineKeyboardButton(text="🔴 Сложный (+30% кубков)", callback_data="start_battle_hard"))
    builder.row(InlineKeyboardButton(text="💀 КОШМАР (+80% кубков)", callback_data="start_battle_nightmare"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main"))
    
    await callback.message.edit_text("⚔️ <b>Выбор сложности боя:</b>\nВыберите противника:", reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)

def get_allowed_rarities_for_ai(rank_lvl, diff):
    # Упрощенная таблица редкостей ИИ в зависимости от уровня ранга (0-8)
    # 0: Rock, 1: Bronze, 2: Iron, 3: Gold, 4: Platina, 5: Modern, 6: Digital, 7: Cosmic, 8: Ultimate
    table = {
        "easy": [
            ["Basic", "Uncommon"], ["Uncommon", "Rare"], ["Uncommon", "Rare"], ["Rare", "Epic"],
            ["Epic", "Legendary"], ["Legendary", "Mythic"], ["Mythic"], ["Mythic", "Super"], ["Super"]
        ],
        "medium": [
            ["Basic", "Uncommon"], ["Uncommon", "Rare"], ["Rare", "Epic"], ["Epic", "Legendary"],
            ["Legendary", "Mythic"], ["Legendary", "Mythic", "Super"], ["Mythic", "Super"], ["Mythic", "Super"], ["Super"]
        ],
        "hard": [
            ["Uncommon"], ["Uncommon", "Rare", "Epic"], ["Rare", "Epic", "Legendary"], ["Epic", "Legendary"],
            ["Legendary", "Mythic"], ["Mythic", "Super"], ["Mythic", "Super"], ["Mythic", "Super"], ["Super"]
        ],
        "nightmare": [
            ["Uncommon", "Rare"], ["Rare", "Epic"], ["Epic", "Legendary"], ["Legendary", "Mythic"],
            ["Mythic", "Super"], ["Mythic", "Super"], ["Super"], ["Super"], ["Super"]
        ]
    }
    safe_rank = min(8, max(0, rank_lvl))
    return table[diff][safe_rank]

async def generate_enemy_team(player_trophies, diff):
    rank_info = get_rank_info(player_trophies)
    rank_idx = [r[0].split()[0] for r in RANKS_DATA].index(rank_info['name'].split()[0]) // 4 # Приблизительный уровень лиги
    allowed_rarities = get_allowed_rarities_for_ai(rank_idx, diff)
    
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        placeholders = ','.join(['?']*len(allowed_rarities))
        cursor = await db.execute(f"SELECT * FROM cards WHERE ai_banned = 0 AND rarity IN ({placeholders})", allowed_rarities)
        possible_cards = await cursor.fetchall()
        
    if not possible_cards:
        # Fallback
        async with aiosqlite.connect(DB_FILE) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM cards LIMIT 5")
            possible_cards = await cursor.fetchall()

    team_size = 4
    selected = random.sample(possible_cards, min(team_size, len(possible_cards)))
    
    enemy_team = []
    for i, card in enumerate(selected):
        mutation = "Normal"
        if diff == "nightmare" and random.random() < 0.3:
            mutation = "Gold"
        elif diff == "nightmare" and random.random() < 0.05:
            mutation = "Rainbow"
            
        unit = CombatUnit(False, i, card['name'], card['health'], card['damage'], card['cooldown'], card['char_class'], card['rarity'], mutation)
        enemy_team.append(unit)
    return enemy_team

@router.callback_query(F.data.startswith("start_battle_"))
async def execute_battle(callback: types.CallbackQuery):
    diff = callback.data.split("_")[2]
    user = await get_user(callback.from_user.id)
    
    if user['in_battle']:
        await callback.answer("Вы уже в бою!", show_alert=True)
        return
        
    # Блокируем игрока
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute("UPDATE users SET in_battle = 1 WHERE user_id = ?", (user['user_id'],))
        await db.commit()

    try:
        # Собираем команду игрока
        async with aiosqlite.connect(DB_FILE) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT i.mutation, i.skill_hp, i.skill_dmg, i.skill_cld, c.*
                FROM inventory i
                JOIN cards c ON i.card_id = c.card_id
                WHERE i.user_id = ? AND i.is_equipped = 1
            ''', (user['user_id'],))
            player_cards = await cursor.fetchall()

        if not player_cards:
            await callback.message.edit_text("У вас нет экипированных карт! Зайдите в меню 'Экипировка'.")
            return

        player_team = []
        for i, card in enumerate(player_cards):
            # Применяем скилл поинты
            hp_mult = 1.0 + (card['skill_hp'] * 0.05)
            dmg_mult = 1.0 + (card['skill_dmg'] * 0.05)
            cld_mult = 1.0 - (card['skill_cld'] * 0.005)
            
            unit = CombatUnit(True, i, card['name'], int(card['health'] * hp_mult), int(card['damage'] * dmg_mult), card['cooldown'] * cld_mult, card['char_class'], card['rarity'], card['mutation'])
            player_team.append(unit)

        enemy_team = await generate_enemy_team(user['trophies'], diff)
        
        # Стартовое сообщение
        team_p_str = "\n".join([f"• {u.name} (⚔️{u.dmg} | ❤️{u.hp})" for u in player_team])
        team_e_str = "\n".join([f"• {u.name} (⚔️{u.dmg} | ❤️{u.hp})" for u in enemy_team])
        
        battle_text = f"⚔️ <b>АРЕНА: БИТВА ({diff.upper()})</b> ⚔️\n"
        battle_text += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        battle_text += f"🛡 <b>Команда {user['display_name']}:</b>\n{team_p_str}\n\n"
        battle_text += f"💀 <b>Команда AI:</b>\n{team_e_str}\n"
        battle_text += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        battle_text += f"<i>Бой начнется через 3 секунды...</i>"
        
        await callback.message.edit_text(battle_text, parse_mode=ParseMode.HTML)
        await asyncio.sleep(3) # Анимация перед боем
        
        # Симуляция
        winner, log = await simulate_battle(player_team, enemy_team)
        
        # Расчет наград
        rank_info = get_rank_info(user['trophies'])
        base_cups = random.randint(rank_info['cup_min'], rank_info['cup_max'])
        base_shekels = rank_info['shekels'] * 2 # Из ТЗ: "шекелей дают в 2 раза больше чем написано"
        
        # Глобальные множители
        async with aiosqlite.connect(DB_FILE) as db:
            cursor = await db.execute("SELECT value FROM settings WHERE key = 'shekel_multiplier'")
            res = await cursor.fetchone()
            global_shekel_mult = float(res[0]) if res else 1.0
            
        vip_mult = 1.5 if user['vip_status'] else 1.0
        
        earned_cups = 0
        earned_shekels = 0
        sp_chance = 0.0
        sp_amount = 0
        
        if diff == "easy":
            cups_mult, shekel_mult, sp_chance, sp_amount = 0.5, 0.8, 0.10, 1
        elif diff == "medium":
            cups_mult, shekel_mult, sp_chance, sp_amount = 1.0, 1.0, 0.20, 1
        elif diff == "hard":
            cups_mult, shekel_mult, sp_chance, sp_amount = 1.3, 1.2, 0.35, 2
        else: # nightmare
            cups_mult, shekel_mult, sp_chance, sp_amount = 1.8, 1.5, 0.50, 3

        if winner == "player":
            earned_cups = int(base_cups * cups_mult)
            earned_shekels = int(base_shekels * shekel_mult * global_shekel_mult * vip_mult)
            result_title = "🏆 ПОБЕДА!"
        else:
            earned_cups = -int(base_cups * 0.2) # Потеря кубков
            earned_shekels = int((base_shekels * 0.2) * vip_mult) # Утешительный приз
            result_title = "☠️ ПОРАЖЕНИЕ!"

        # Сохранение результатов
        new_cups = max(0, user['trophies'] + earned_cups)
        
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("UPDATE users SET trophies = ?, shekels = shekels + ? WHERE user_id = ?", (new_cups, earned_shekels, user['user_id']))
            await db.commit()

        # Формирование лога
        log_text = "\n".join(log[-10:]) if log else "Бой завершился мгновенно."
        
        final_text = f"{result_title}\n"
        final_text += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        final_text += f"📜 <b>Краткий лог (последние события):</b>\n{log_text}\n"
        final_text += f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        final_text += f"Награда:\n"
        final_text += f"🏆 Трофеи: {earned_cups} (Всего: {new_cups})\n"
        final_text += f"💰 Шекели: +{earned_shekels}\n"
        
        # Дроп очков навыков (SP)
        if winner == "player" and random.random() < sp_chance:
            final_text += f"🎯 Выпало Очков Навыков: {sp_amount}!\n"
            # TODO: Add logic to store SP globally for user or per-card? The requirement says SP is per skill, meaning we just give a global SP currency first, then they allocate it.
            # Let's add unallocated_sp to users table (implied by "Осталось: 0" in screenshot)
            async with aiosqlite.connect(DB_FILE) as db:
                # Add column if not exists
                try:
                    await db.execute("ALTER TABLE users ADD COLUMN unallocated_sp INTEGER DEFAULT 0")
                except:
                    pass
                await db.execute("UPDATE users SET unallocated_sp = unallocated_sp + ? WHERE user_id = ?", (sp_amount, user['user_id']))
                await db.commit()

        builder = InlineKeyboardBuilder()
        builder.button(text="🔄 Играть снова", callback_data=f"start_battle_{diff}")
        builder.button(text="◀️ В меню", callback_data="back_to_main")
        
        await callback.message.edit_text(final_text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)
        
    finally:
        # Разблокируем игрока
        async with aiosqlite.connect(DB_FILE) as db:
            await db.execute("UPDATE users SET in_battle = 0 WHERE user_id = ?", (user['user_id'],))
            await db.commit()

@router.callback_query(F.data == "menu_crates")
async def show_crates(callback: types.CallbackQuery):
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM gacha_boxes WHERE type = 'crate'")
        crates = await cursor.fetchall()
        
    if not crates:
        await callback.answer("Пока нет доступных крейтов.", show_alert=True)
        return
        
    builder = InlineKeyboardBuilder()
    for crate in crates:
        builder.row(InlineKeyboardButton(text=f"📦 {crate['name']} - {crate['price']}💰", callback_data=f"view_crate_{crate['box_id']}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main"))
    
    await callback.message.edit_text("📦 <b>Магазин Крейтов</b>\nВыберите крейт для просмотра:", reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data.startswith("view_crate_"))
async def view_crate(callback: types.CallbackQuery):
    crate_id = callback.data.split("_")[2]
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM gacha_boxes WHERE box_id = ?", (crate_id,))
        crate = await cursor.fetchone()
        
    if not crate:
        return
        
    contents = json.loads(crate['contents']) # {card_id: chance}
    text = f"📦 <b>{crate['name']}</b>\nЦена: {crate['price']} Шекелей\n\n<b>Содержимое:</b>\n"
    
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        for c_id, chance in contents.items():
            cursor = await db.execute("SELECT name, rarity FROM cards WHERE card_id = ?", (c_id,))
            c_data = await cursor.fetchone()
            if c_data:
                text += f"• {c_data['name']} ({c_data['rarity']}) - {chance}%\n"

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="Купить 1x", callback_data=f"buy_crate_{crate_id}_1"),
        InlineKeyboardButton(text="Купить 10x", callback_data=f"buy_crate_{crate_id}_10")
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu_crates"))
    
    # Если есть фото крейта
    if crate['photo_id']:
        await callback.message.answer_photo(crate['photo_id'], caption=text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)
    else:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data.startswith("buy_crate_"))
async def buy_crate(callback: types.CallbackQuery):
    _, _, crate_id, amount_str = callback.data.split("_")
    amount = int(amount_str)
    
    user = await get_user(callback.from_user.id)
    
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM gacha_boxes WHERE box_id = ?", (crate_id,))
        crate = await cursor.fetchone()
        
    if not crate: return
    
    total_price = crate['price'] * amount
    if user['shekels'] < total_price:
        await callback.answer("Недостаточно шекелей!", show_alert=True)
        return
        
    contents = json.loads(crate['contents'])
    cards_list = list(contents.keys())
    weights = [float(w) for w in contents.values()]
    
    # Применение ивента удачи (увеличивает шансы дропа < 10%)
    async with aiosqlite.connect(DB_FILE) as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = 'luck_multiplier'")
        res = await cursor.fetchone()
        luck_mult = float(res[0]) if res else 1.0
        
    if luck_mult > 1.0:
        for i in range(len(weights)):
            if weights[i] < 10.0:
                weights[i] *= luck_mult
        # Нормализация до 100%
        total_w = sum(weights)
        weights = [w / total_w * 100 for w in weights]

    pulled_cards = random.choices(cards_list, weights=weights, k=amount)
    
    # Генерация мутаций
    results = []
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        
        # Списываем шекели
        await db.execute("UPDATE users SET shekels = shekels - ? WHERE user_id = ?", (total_price, user['user_id']))
        
        for c_id in pulled_cards:
            # Выбор мутации
            m_rand = random.randint(1, 100)
            mutation = "Normal"
            if m_rand <= 2: mutation = "Rainbow"
            elif m_rand <= 12: mutation = "Gold"
            
            # Серийный номер (только для Mythic+)
            cursor = await db.execute("SELECT name, rarity FROM cards WHERE card_id = ?", (c_id,))
            card_info = await cursor.fetchone()
            
            serial = 0
            if card_info['rarity'] in ["Mythic", "Super", "Secret", "Exclusive", "Leaderboard"]:
                cursor = await db.execute("SELECT COUNT(*) FROM inventory WHERE card_id = ?", (c_id,))
                count = await cursor.fetchone()
                serial = count[0] + 1
            
            await db.execute('''
                INSERT INTO inventory (user_id, card_id, mutation, serial_number)
                VALUES (?, ?, ?, ?)
            ''', (user['user_id'], c_id, mutation, serial))
            
            mut_icon = "🌈" if mutation == "Rainbow" else "🌟" if mutation == "Gold" else ""
            ser_text = f" #{serial:04d}" if serial > 0 else ""
            results.append(f"• {card_info['name']} ({card_info['rarity']}){mut_icon}{ser_text}")
            
        await db.commit()

    text = f"🎉 <b>Вы открыли {crate['name']} x{amount}!</b>\n\n<b>Получено:</b>\n" + "\n".join(results)
    
    builder = InlineKeyboardBuilder()
    builder.button(text="◀️ Вернуться к крейтам", callback_data="menu_crates")
    
    # Отправляем новым сообщением, так как могли быть картинки в прошлом
    await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data == "menu_skills")
async def menu_skills_select_card(callback: types.CallbackQuery):
    user = await get_user(callback.from_user.id)
    
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('''
            SELECT i.id, c.name, i.skill_hp, i.skill_dmg, i.skill_cld
            FROM inventory i
            JOIN cards c ON i.card_id = c.card_id
            WHERE i.user_id = ?
            LIMIT 50
        ''', (user['user_id'],))
        inv = await cursor.fetchall()

    if not inv:
        await callback.answer("У вас нет карт для прокачки!", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for item in inv:
        builder.button(text=f"{item['name']} [HP:{item['skill_hp']} DMG:{item['skill_dmg']}]", callback_data=f"skill_card_{item['id']}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main"))
    
    # Добавляем колонку unallocated_sp если её нет (на случай ошибки)
    unallocated = user.get('unallocated_sp', 0) if 'unallocated_sp' in user.keys() else 0

    await callback.message.edit_text(f"🎯 <b>Очки Навыков</b>\nСвободных очков: {unallocated}\n\nВыберите карту для прокачки:", reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data.startswith("skill_card_"))
async def show_skill_board(callback: types.CallbackQuery):
    inv_id = callback.data.split("_")[2]
    user = await get_user(callback.fromuser.id)
    unallocated = user.get('unallocated_sp', 0) if 'unallocated_sp' in user.keys() else 0
    
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('''
            SELECT i.*, c.name 
            FROM inventory i
            JOIN cards c ON i.card_id = c.card_id
            WHERE i.id = ? AND i.user_id = ?
        ''', (inv_id, user['user_id']))
        item = await cursor.fetchone()

    if not item: return

    # Генерация картинки
    img_bytes = generate_skill_points_image(item['name'], unallocated, item['skill_hp'], item['skill_dmg'], item['skill_cld'])
    
    # Создаем клавиатуру как на скрине
    builder = InlineKeyboardBuilder()
    for stat in ["hp", "dmg", "cld"]:
        builder.button(text=f"{stat.upper()} [+1]", callback_data=f"addskill_{inv_id}_{stat}_1")
        builder.button(text=f"{stat.upper()} [+5]", callback_data=f"addskill_{inv_id}_{stat}_5")
        builder.button(text=f"{stat.upper()} [+10]", callback_data=f"addskill_{inv_id}_{stat}_10")
        builder.button(text=f"{stat.upper()} [MAX]", callback_data=f"addskill_{inv_id}_{stat}_max")
    builder.adjust(4, 4, 4)
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu_skills"))
    
    caption = f"🎯 <b>Очки навыков — {item['name']}</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\nСвободных очков: {unallocated}\nКаждое очко: +0.05 к множителю (макс. 100 в навык)."
    
    # Удаляем старое сообщение и шлем новое с фото (чтобы не баговало edit_text -> edit_caption)
    await callback.message.delete()
    await callback.message.answer_photo(BufferedInputFile(img_bytes, filename="skills.png"), caption=caption, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)

@router.callback_query(F.data.startswith("addskill_"))
async def process_add_skill(callback: types.CallbackQuery):
    _, inv_id, stat, amount_str = callback.data.split("_")
    
    user = await get_user(callback.from_user.id)
    unallocated = user.get('unallocated_sp', 0) if 'unallocated_sp' in user.keys() else 0
    
    if unallocated <= 0:
        await callback.answer("У вас нет свободных очков!", show_alert=True)
        return
        
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM inventory WHERE id = ? AND user_id = ?", (inv_id, user['user_id']))
        item = await cursor.fetchone()
        
    if not item: return
    
    current_stat_val = item[f"skill_{stat}"]
    total_skills = item["skill_hp"] + item["skill_dmg"] + item["skill_cld"]
    
    if current_stat_val >= 100:
        await callback.answer("Этот навык уже прокачан на максимум!", show_alert=True)
        return
    if total_skills >= 300:
        await callback.answer("Эта карта достигла лимита общих навыков (300)!", show_alert=True)
        return
        
    # Вычисляем сколько можем добавить
    add_amount = 0
    if amount_str == "max":
        add_amount = min(unallocated, 100 - current_stat_val, 300 - total_skills)
    else:
        add_amount = min(int(amount_str), unallocated, 100 - current_stat_val, 300 - total_skills)
        
    if add_amount <= 0:
        await callback.answer("Невозможно добавить очки.", show_alert=True)
        return

    # Сохраняем
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(f"UPDATE inventory SET skill_{stat} = skill_{stat} + ? WHERE id = ?", (add_amount, inv_id))
        await db.execute("UPDATE users SET unallocated_sp = unallocated_sp - ? WHERE user_id = ?", (add_amount, user['user_id']))
        await db.commit()
        
    # Перерисовываем интерфейс
    await show_skill_board(callback)

@router.callback_query(F.data.startswith("menu_inv"))
async def show_inventory(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    page = int(parts[2]) if len(parts) > 2 else 0
    ITEMS_PER_PAGE = 50
    
    user = await get_user(callback.from_user.id)
    
    async with aiosqlite.connect(DB_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('''
            SELECT c.name, i.mutation, COUNT(*) as count
            FROM inventory i
            JOIN cards c ON i.card_id = c.card_id
            WHERE i.user_id = ?
            GROUP BY i.card_id, i.mutation
            ORDER BY c.rarity, c.name
            LIMIT ? OFFSET ?
        ''', (user['user_id'], ITEMS_PER_PAGE, page * ITEMS_PER_PAGE))
        items = await cursor.fetchall()
        
        cursor = await db.execute("SELECT COUNT(DISTINCT card_id) FROM inventory WHERE user_id = ?", (user['user_id'],))
        total_items = (await cursor.fetchone())[0]
        
    total_pages = math.ceil(total_items / ITEMS_PER_PAGE) if total_items > 0 else 1
    
    text = f"🎒 <b>ИНВЕНТАРЬ КАРТ (Стр. {page+1}/{total_pages})</b>\n━━━━━━━━━━━━━━━━━━━━━━━━\n"
    if not items:
        text += "<i>Пусто</i>\n"
    else:
        for item in items:
            mut = f" [{MUTATIONS[item['mutation']]['name']}]" if item['mutation'] != 'Normal' else ""
            text += f"• {item['name']}{mut} — {item['count']} шт.\n"
            
    builder = InlineKeyboardBuilder()
    if page > 0:
        builder.button(text="⬅️ Пред", callback_data=f"menu_inv_{page-1}")
    if page < total_pages - 1:
        builder.button(text="След ➡️", callback_data=f"menu_inv_{page+1}")
    builder.row(InlineKeyboardButton(text="◀️ В меню", callback_data="back_to_main"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode=ParseMode.HTML)


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    
    await init_db()
    logging.info("Starting bot...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
