from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
import pyrandonaut
import math
import os

API_TOKEN = os.environ.get('BOT_TOKEN')

class Form(StatesGroup):
    new_location = State()
    getting_location = State()
    waiting_for_reach = State()

check_btn = KeyboardButton('/check')
start_btn = KeyboardButton('/start')
gotto_keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
gotto_keyboard.add(check_btn, start_btn)

location_button = KeyboardButton('Поделиться', request_location=True)
loc_keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
loc_keyboard.add(location_button)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(LoggingMiddleware())


# Calculate distance between two points using the Haversine formula
def is_nearby(lat1, lon1, lat2, lon2, threshold=100):
    R = 6371e3  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c  # in meters

    return distance <= threshold, distance


@dp.message_handler(commands=['help'], state="*")
async def send_help(message: types.Message):
    await message.reply("""*Использование бота:*
                        \n/start - выдать новую случайную точку в указанном радиусе
                        \n/check - проверить, достигли ли вы указанную точку и узнать оставшееся расстояние
                        \n***Для того чтобы добраться до точки, достаточно быть в пределах 100 метров от неё.***\n
                        \n*Информация о боте:*
                        \nБот напрямую вдохновлён приложением [Randonautica](https://www.randonautica.com/)
                        \n***Бот не собирает никакую информацию !!!***
                        \nИсходный код доступен на [GitHub]()""", parse_mode='Markdown', disable_web_page_preview=True)

@dp.message_handler(commands=['start'], state="*")
async def send_welcome(message: types.Message):
    await dp.current_state().reset_data()
    await dp.current_state().reset_state()
    
    await message.reply("""Добро пожаловать! Укажите радиус случайной точки (в метрах).\n
                        \n(информацию о боте можно узнать в /help)""")
    await Form.getting_location.set()


@dp.message_handler(state=Form.getting_location)
async def process_location(message: types.Message):
    try:
        radius = int(message.text)
        await dp.current_state().update_data(radius=radius)
        await message.reply("Пожалуйста, поделитесь свойм местоположением, нажав кнопку ниже.", reply_markup=loc_keyboard)
    except ValueError:
        await message.reply("Пожалуйста, введите целое число в метрах.")


@dp.message_handler(content_types=['location'], state=Form.getting_location)
async def handle_location(message: types.Message):
    user_location = message.location
    user_lat = user_location.latitude
    user_lon = user_location.longitude


    cr = await dp.current_state().get_data()
    target_lat, target_lon = pyrandonaut.get_coordinate(user_lat, user_lon, radius=cr["radius"])
    await dp.current_state().update_data(target_lat=target_lat, target_lon=target_lon)

    # Sending the target location as a map point
    await bot.send_location(message.chat.id, target_lat, target_lon)

    # Inform the user how to check proximity
    await message.reply(f"""Отправлена новая точка:
                        \n<code>{target_lat}, {target_lon}</code>
                        \nРасстояние: {round(is_nearby(user_lat, user_lon, target_lat, target_lon)[1])}м
                        \n(вы должны быть в радиусе 100 метров, чтобы закрыть точку)
                        \nЧтобы проверить расстояние и достигли ли вы точку, используйте /check
                        \nЕсли вы хотите новую точку, используйте /start""", parse_mode='HTML', reply_markup=gotto_keyboard)
    

    await Form.waiting_for_reach.set()


@dp.message_handler(commands=['check'], state=Form.waiting_for_reach)
async def check_nearby(message: types.Message):
    await message.reply("Отправьте свое местоположение, чтобы проверить, достигли ли вы точку.", reply_markup=loc_keyboard)


@dp.message_handler(content_types=['location'], state=Form.waiting_for_reach)
async def handle_proximity_check(message: types.Message):
    user_location = message.location

    if user_location:
        user_lat = user_location.latitude
        user_lon = user_location.longitude

        s = await dp.current_state().get_data()
        reached, d = is_nearby(user_lat, user_lon, s['target_lat'], s['target_lon'])

        if reached:
            start_btn = KeyboardButton('/start')
            keyboard = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            keyboard.add(start_btn)

            await message.reply("Вы достигли точку! Поздравляем!", reply_markup=keyboard)
        else:
            await message.reply(f"Вы ещё не на месте, осталось {round(d)} метров.", reply_markup=gotto_keyboard)
    else:
        await message.reply("Сначала поделитесь свойм местоположением.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
