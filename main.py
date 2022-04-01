import telebot
import settings
from telebot import types
import os
import redis as Redis
import json

redis = Redis.Redis(host='localhost', port=6379, db=0)

bot = telebot.TeleBot(settings.TELEGRAM_API_TOKET)

@bot.message_handler(content_types=['document'])
def data_processing(message):
    chat_id = message.chat.id
    file = message.document

    try:
        """Скачивание файл по айди """
        r = bot.get_file(file.file_id)

        ftype = r.file_path.split('.')
        ftype = ftype[len(ftype)-1]
        if ftype != 'png' and ftype != 'jpg':
            bot.send_message(message.chat.id, 'Не корректний тип файлу')
            return

        file = bot.download_file(r.file_path)

        """Создание папки для хранения файла"""
        arr = r.file_path.split('/')
        dir = 'static/'+arr[0]
        if os.path.exists(dir) == False:
            os.mkdir(dir)

        """Запись бинарника в файл"""
        path = 'static/' + r.file_path
        with open(path, 'wb') as f:
            f.write(file)

        """Отправка файла пользователю"""
        file = open(path, 'rb')
        file.close()

        but = types.KeyboardButton('Відправити')
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(but)

        bot.send_message(message.chat.id,
                         'По можливості додайте більше інформації про порушника (ПІБ, номер телефону і т.д)',
                         reply_markup=markup)

        user_data = get_current_step(message.chat.id)
        if type(user_data) is dict:
            add_next_step(2, user_data, chat_id)
        else:
            return
    except:
        bot.send_message(chat_id, 'Ойой, щось пішло не так і ми не змогли виконати Ваш запит((')

@bot.message_handler(content_types=['location'])
def fire_report(message):
    chat_id = message.chat.id
    add_next_step(1, {'step': 1}, chat_id)
    bot.send_message(chat_id, 'Будь-ласка, прикріпіть фото пожежі як документ (Без стиснення)')


@bot.message_handler(commands=['start'])
def welcome(message):
    markup = get_common_markup()
    if message.text == '/start':
        username = message.from_user.first_name
        sticker = open('static/AnimatedSticker.tgs', 'rb')
        bot.send_message(message.chat.id, f'<b>Вітаю {username}</b>!', parse_mode='html', reply_markup=markup)
        bot.send_sticker(message.chat.id, sticker)


@bot.message_handler(content_types=['text'])
def send_message(message):
    chat_id = message.chat.id
    user_data = get_current_step(chat_id)
    if type(user_data) is dict and user_data['step'] == 2:
        err = add_next_step(3, user_data, chat_id)
        if err:
            return
        bot.send_message(message.chat.id, 'Натисніть "Відправити" для відправки репорту')
    else:
        if message.chat.type == 'private':
            if message.text == 'Відправити':
                markup = get_common_markup()
                bot.send_message(chat_id, 'Репорт успішно відправлено! Дякуємо за допомогу!', reply_markup=markup)
                redis.delete(chat_id)
            else:
                bot.send_message(chat_id, 'Нажаль, я не розумію цю команду( Спробуйте щось інше, або скористайтесь кнопками')


def get_common_markup():
    but1 = types.KeyboardButton('Повідомити про пожежу', request_location=True)
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(but1)
    return markup


def get_current_step(chat_id):
    try:
        d = redis.get(chat_id)
        if d:
            d = json.loads(d)
            return d
    except TypeError:
        redis.delete(chat_id)
        bot.send_message(chat_id, 'Ойой, щось пішло не так і ми не змогли виконати Ваш запит((')
        return


def add_next_step(step, user_data, chat_id):
    try:
        user_data['step'] = step
        redis.set(chat_id, json.dumps(user_data))
        return 0
    except:
        redis.delete(chat_id)
        bot.send_message(chat_id, 'Ойой, щось пішло не так і ми не змогли виконати Ваш запит((')
        return 1

if __name__ == '__main__':
    print('bot is started')
    bot.polling(none_stop=True)
