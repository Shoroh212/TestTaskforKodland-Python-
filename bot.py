"""Telegram @catcoin_remote_bot ccылка на бота(управление )
"""
import requests
import telebot
from telebot import types

BOT_TOKEN = "9189700839:AAGPUyM0KxE7M-QoWmfa-WsYwmiLmToROEo"
API_URL = "http://127.0.0.1:8000/api"
REQUEST_TIMEOUT = 5

ARROWS = {
    "up": "⬆️",
    "down": "⬇️",
    "left": "⬅️",
    "right": "➡️",
}

bot = telebot.TeleBot(BOT_TOKEN)


def get_player_name(user):
    if user.username:
        return f"@{user.username}"
    return user.first_name


def build_control_keyboard():
    keyboard = types.InlineKeyboardMarkup()

    def button(direction):
        return types.InlineKeyboardButton(
            ARROWS[direction], callback_data=f"move:{direction}"
        )

    keyboard.row(button("up"))
    keyboard.row(button("left"), button("down"), button("right"))
    return keyboard


def send_to_server(payload):
    """POST an action to the game server. Returns (status_code, json)."""
    try:
        response = requests.post(API_URL, json=payload,
                                 timeout=REQUEST_TIMEOUT)
    except requests.RequestException:
        return None, {}
    return response.status_code, response.json()


@bot.message_handler(commands=["start", "help"])
def send_help(message):
    bot.reply_to(
        message,
        
        "Напиши /join, и получи пульт управления котом.",
    )


@bot.message_handler(commands=["join"])
def join_game(message):


    user = message.from_user
    status, data = send_to_server({
        "action": "join",
        "telegram_id": user.id,
        "name": get_player_name(user),
    })
    if status != 200:
        bot.reply_to(message, "Нужно подключить сервер ")
        return

    coins = data["player"]["coins"]
    try:
        bot.send_message(
            user.id,
            f"Твой кот в игре! Монет: {coins}\nУправляй стрелками:",
            reply_markup=build_control_keyboard(),
        )
    except telebot.apihelper.ApiTelegramException:
     
        bot.reply_to(message, "Сначала  /start.")
        return

    if message.chat.type != "private":
        bot.reply_to(message, "Отправил пульт тебе в личные сообщения.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("move:"))
def move_cat(call):
    direction = call.data.split(":", 1)[1]
    status, data = send_to_server({
        "action": "move",
        "telegram_id": call.from_user.id,
        "direction": direction,
    })
    if status == 200:
        bot.answer_callback_query(
            call.id, f"Монет: {data['player']['coins']}"
        )
    elif status == 404:
        bot.answer_callback_query(call.id, " напиши /join")



if __name__ == "__main__":
    print("Успешно запущен")
    bot.infinity_polling()
