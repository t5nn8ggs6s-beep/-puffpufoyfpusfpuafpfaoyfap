import logging
import random
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, executor, types

TOKEN = "8795245479:AAEJDUaWQuyekjxdLRWPapCL0tgzJzuiDks"

ADMIN_ID = 1541550837

PAYMENT_USERNAME = "@fullworko"

COURSE_CHANNELS = [
"https://t.me/+l7wDQSWoxkgyN2Nh",
"https://t.me/+sb1wu5Am_P9lM2Yx",
"https://t.me/+6m85D-iIvSRlNmEx"
]

TARIFFS = {
"day": {"name":"День","price":50,"days":1},
"week": {"name":"Неделя","price":100,"days":7},
"month": {"name":"Месяц","price":220,"days":30},
"year": {"name":"Год","price":310,"days":365}
}

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

db = sqlite3.connect("courses.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
id INTEGER PRIMARY KEY,
username TEXT,
sub_until TEXT,
banned INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS payments(
user_id INTEGER,
tariff TEXT,
status TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS admins(
id INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS logs(
user_id INTEGER,
action TEXT,
date TEXT
)
""")

db.commit()

cursor.execute("INSERT OR IGNORE INTO admins(id) VALUES(?)",(ADMIN_ID,))
db.commit()


def random_course():
    return random.choice(COURSE_CHANNELS)
  @dp.message_handler(commands=["start"])
async def start(message: types.Message):

    user_id = message.from_user.id
    username = message.from_user.username

    cursor.execute(
    "INSERT OR IGNORE INTO users(id,username) VALUES(?,?)",
    (user_id,username)
    )

    db.commit()

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)

    kb.add("📚 Каталог курсов")
    kb.add("👤 Моя подписка")

    await message.answer(
"""
🧠 Добро пожаловать в магазин

Курсы Лины

Здесь вы можете получить доступ
к курсам по телекинезу.

Выберите раздел ниже
""",
reply_markup=kb
)
  @dp.message_handler(lambda m: m.text == "📚 Каталог курсов")
async def shop(message: types.Message):

    kb = types.InlineKeyboardMarkup()

    for key,data in TARIFFS.items():

        kb.add(
        types.InlineKeyboardButton(
        f"{data['name']} — {data['price']}⭐",
        callback_data=f"buy_{key}"
        )
        )

    await message.answer(
"""
📚 Доступные тарифы

Выберите срок доступа к курсу
""",
reply_markup=kb
)
  @dp.callback_query_handler(lambda c: c.data.startswith("buy_"))
async def buy(callback: types.CallbackQuery):

    tariff = callback.data.split("_")[1]

    data = TARIFFS[tariff]

    kb = types.InlineKeyboardMarkup()

    kb.add(
    types.InlineKeyboardButton(
    "✅ Я оплатил",
    callback_data=f"paid_{tariff}"
    )
    )

    await callback.message.answer(
f"""
💳 Оплата курса

Тариф: {data['name']}
Цена: {data['price']}⭐

Отправьте ⭐ подарком пользователю

{PAYMENT_USERNAME}

После оплаты нажмите кнопку ниже
""",
reply_markup=kb
)

    await callback.answer()
  # -------------------- ЧАСТЬ 2 --------------------

@dp.callback_query_handler(lambda c: c.data.startswith("paid_"))
async def paid(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    tariff = callback.data.split("_")[1]

    # Проверка на бан
    cursor.execute("SELECT banned FROM users WHERE id=?", (user_id,))
    banned = cursor.fetchone()
    if banned and banned[0] == 1:
        await callback.answer("Вы забанены, доступ запрещен!", show_alert=True)
        return

    # Сохранение заявки в базе
    cursor.execute(
        "INSERT INTO payments(user_id, tariff, status) VALUES(?,?,?)",
        (user_id, tariff, "pending")
    )
    db.commit()

    await callback.message.answer(
f"""
💳 Заявка создана!

Вы выбрали тариф: {TARIFFS[tariff]['name']}
Цена: {TARIFFS[tariff]['price']}⭐

Админ проверит вашу оплату и выдаст курс.
"""
    )

    # Уведомление админу
    await bot.send_message(
        ADMIN_ID,
        f"📌 Новая заявка на оплату\n"
        f"Пользователь: @{callback.from_user.username}\n"
        f"ID: {user_id}\n"
        f"Тариф: {TARIFFS[tariff]['name']}\n"
        f"Цена: {TARIFFS[tariff]['price']}⭐"
    )

    await callback.answer("Заявка отправлена админу!")
  # -------------------- ЧАСТЬ 3 --------------------

# Подтвердить оплату
@dp.message_handler(lambda m: m.from_user.id in [ADMIN_ID] and m.text.startswith("/approve"))
async def approve_payment(message: types.Message):
    try:
        user_id = int(message.text.split()[1])
        cursor.execute("SELECT tariff FROM payments WHERE user_id=? AND status='pending'", (user_id,))
        res = cursor.fetchone()
        if not res:
            await message.reply("❌ Нет активной заявки для этого пользователя")
            return

        tariff = res[0]

        # Выдача курса (рандомная ссылка)
        link = random_course()

        # Обновление подписки
        cursor.execute("SELECT sub_until FROM users WHERE id=?", (user_id,))
        sub = cursor.fetchone()[0]
        now = datetime.now()
        days = TARIFFS[tariff]['days']

        if sub:
            sub_date = datetime.strptime(sub, "%Y-%m-%d %H:%M:%S")
            if sub_date > now:
                new_date = sub_date + timedelta(days=days)
            else:
                new_date = now + timedelta(days=days)
        else:
            new_date = now + timedelta(days=days)

        cursor.execute("UPDATE users SET sub_until=? WHERE id=?", (new_date.strftime("%Y-%m-%d %H:%M:%S"), user_id))
        cursor.execute("UPDATE payments SET status='approved' WHERE user_id=? AND status='pending'", (user_id,))
        db.commit()

        # Отправка курса пользователю
        await bot.send_message(
            user_id,
            f"✅ Оплата подтверждена!\n\n"
            f"Вам выдан доступ к курсу по телекинезу:\n\n{link}\n\n"
            f"⚠️ Не передавайте ссылку другим пользователям."
        )

        await message.reply(f"✅ Курс выдан пользователю {user_id}")

    except Exception as e:
        await message.reply(f"Ошибка: {e}")

# Отклонить оплату
@dp.message_handler(lambda m: m.from_user.id in [ADMIN_ID] and m.text.startswith("/decline"))
async def decline_payment(message: types.Message):
    try:
        user_id = int(message.text.split()[1])
        cursor.execute("SELECT tariff FROM payments WHERE user_id=? AND status='pending'", (user_id,))
        res = cursor.fetchone()
        if not res:
            await message.reply("❌ Нет активной заявки для этого пользователя")
            return

        cursor.execute("UPDATE payments SET status='declined' WHERE user_id=? AND status='pending'", (user_id,))
        db.commit()

        await bot.send_message(user_id, "❌ Ваша оплата не подтверждена админом. Попробуйте снова.")
        await message.reply(f"❌ Заявка отклонена для пользователя {user_id}")

    except Exception as e:
        await message.reply(f"Ошибка: {e}")
      # -------------------- ЧАСТЬ 4 --------------------

# Проверка на админа
def is_admin(user_id):
    cursor.execute("SELECT id FROM admins WHERE id=?", (user_id,))
    return cursor.fetchone() is not None

# Список пользователей
@dp.message_handler(lambda m: is_admin(m.from_user.id) and m.text == "/users")
async def list_users(message: types.Message):
    cursor.execute("SELECT id, username, sub_until, banned FROM users")
    users = cursor.fetchall()
    if not users:
        await message.reply("Пользователи не найдены.")
        return

    text = "👥 Список пользователей:\n\n"
    for u in users:
        uid, uname, sub_until, banned = u
        status = "Забанен" if banned else "Активен"
        text += f"ID: {uid}, @{uname}, Подписка до: {sub_until}, Статус: {status}\n"

    await message.reply(text)

# Список активных подписок
@dp.message_handler(lambda m: is_admin(m.from_user.id) and m.text == "/subscriptions")
async def list_subscriptions(message: types.Message):
    cursor.execute("SELECT id, username, sub_until FROM users WHERE sub_until IS NOT NULL")
    subs = cursor.fetchall()
    if not subs:
        await message.reply("Нет активных подписок.")
        return

    text = "📊 Активные подписки:\n\n"
    for s in subs:
        uid, uname, sub_until = s
        text += f"ID: {uid}, @{uname}, до: {sub_until}\n"

    await message.reply(text)

# Статистика бота
@dp.message_handler(lambda m: is_admin(m.from_user.id) and m.text == "/stats")
async def stats(message: types.Message):
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM payments WHERE status='approved'")
    total_paid = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM payments WHERE status='pending'")
    total_pending = cursor.fetchone()[0]

    text = (
        f"📊 Статистика бота:\n\n"
        f"Всего пользователей: {total_users}\n"
        f"Оплачено курсов: {total_paid}\n"
        f"Заявок в ожидании: {total_pending}"
    )
    await message.reply(text)
  # -------------------- ЧАСТЬ 5 --------------------

# Бан пользователя
@dp.message_handler(lambda m: is_admin(m.from_user.id) and m.text.startswith("/ban"))
async def ban_user(message: types.Message):
    try:
        user_id = int(message.text.split()[1])
        cursor.execute("UPDATE users SET banned=1 WHERE id=?", (user_id,))
        db.commit()
        await message.reply(f"✅ Пользователь {user_id} забанен")
    except:
        await message.reply("Ошибка. Используйте: /ban <id>")

# Разбан пользователя
@dp.message_handler(lambda m: is_admin(m.from_user.id) and m.text.startswith("/unban"))
async def unban_user(message: types.Message):
    try:
        user_id = int(message.text.split()[1])
        cursor.execute("UPDATE users SET banned=0 WHERE id=?", (user_id,))
        db.commit()
        await message.reply(f"✅ Пользователь {user_id} разбанен")
    except:
        await message.reply("Ошибка. Используйте: /unban <id>")

# Рассылка
@dp.message_handler(lambda m: is_admin(m.from_user.id) and m.text.startswith("/broadcast"))
async def broadcast(message: types.Message):
    try:
        text = message.text.replace("/broadcast ","")
        cursor.execute("SELECT id FROM users")
        users = cursor.fetchall()
        count = 0
        for u in users:
            try:
                await bot.send_message(u[0], text)
                count +=1
            except:
                continue
        await message.reply(f"✅ Рассылка завершена. Отправлено {count} пользователям")
    except Exception as e:
        await message.reply(f"Ошибка: {e}")

# Изменение цены тарифов
@dp.message_handler(lambda m: is_admin(m.from_user.id) and m.text.startswith("/setprice"))
async def set_price(message: types.Message):
    try:
        parts = message.text.split()
        key = parts[1]
        price = int(parts[2])
        if key in TARIFFS:
            TARIFFS[key]['price'] = price
            await message.reply(f"✅ Цена тарифа {TARIFFS[key]['name']} изменена на {price}⭐")
        else:
            await message.reply("Тариф не найден")
    except:
        await message.reply("Используйте: /setprice <day/week/month/year> <цена>")

# Изменение ссылки курсов
@dp.message_handler(lambda m: is_admin(m.from_user.id) and m.text.startswith("/setlink"))
async def set_link(message: types.Message):
    try:
        parts = message.text.split()
        index = int(parts[1])-1
        url = parts[2]
        if 0 <= index < len(COURSE_CHANNELS):
            COURSE_CHANNELS[index] = url
            await message.reply(f"✅ Ссылка {index+1} обновлена на {url}")
        else:
            await message.reply("Неверный индекс (1-3)")
    except:
        await message.reply("Используйте: /setlink <1-3> <ссылка>")
      # -------------------- ЧАСТЬ 6 --------------------

# Логирование действий
def log_action(user_id, action):
    cursor.execute(
        "INSERT INTO logs(user_id, action, date) VALUES(?,?,?)",
        (user_id, action, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    db.commit()

# Проверка подписки
def has_active_sub(user_id):
    cursor.execute("SELECT sub_until FROM users WHERE id=?", (user_id,))
    res = cursor.fetchone()
    if res and res[0]:
        sub_date = datetime.strptime(res[0], "%Y-%m-%d %H:%M:%S")
        return sub_date > datetime.now()
    return False

# Анти-флуд: ограничение по времени для заявок
USER_LAST_REQUEST = {}

def can_request(user_id):
    from datetime import timedelta
    now = datetime.now()
    last = USER_LAST_REQUEST.get(user_id)
    if last and (now - last).total_seconds() < 30:  # 30 секунд между заявками
        return False
    USER_LAST_REQUEST[user_id] = now
    return True

# Проверка перед созданием новой заявки
@dp.callback_query_handler(lambda c: c.data.startswith("buy_"))
async def check_flood(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if not can_request(user_id):
        await callback.answer("⏳ Подождите 30 секунд перед новой заявкой", show_alert=True)
        return
    # Если прошло — продолжаем обычный процесс покупки
    await shop(callback.message)
  # -------------------- ЧАСТЬ 7 --------------------

# Финальная команда для админа: логи
@dp.message_handler(lambda m: is_admin(m.from_user.id) and m.text == "/logs")
async def show_logs(message: types.Message):
    cursor.execute("SELECT user_id, action, date FROM logs ORDER BY date DESC LIMIT 20")
    logs = cursor.fetchall()
    if not logs:
        await message.reply("Нет записей логов")
        return
    text = "📋 Последние действия:\n\n"
    for log in logs:
        text += f"ID: {log[0]}, Действие: {log[1]}, Время: {log[2]}\n"
    await message.reply(text)

# Проверка подписки пользователем
@dp.message_handler(lambda m: m.text == "👤 Моя подписка")
async def my_subscription(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT sub_until FROM users WHERE id=?", (user_id,))
    res = cursor.fetchone()
    if res and res[0]:
        sub_date = datetime.strptime(res[0], "%Y-%m-%d %H:%M:%S")
        if sub_date > datetime.now():
            await message.reply(f"✅ Ваша подписка активна до {sub_date.strftime('%d-%m-%Y %H:%M:%S')}")
            return
    await message.reply("❌ У вас нет активной подписки")

# Финальный запуск бота
if __name__ == "__main__":
    from aiogram import executor
    print("Бот Курсы Лины запущен...")
    executor.start_polling(dp, skip_updates=True)
      
