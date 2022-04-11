import telebot
import settings
from telebot import types
import os
import json
import service
import os
import sys
import service
import re

db = service.DB()
bot = telebot.TeleBot(settings.TELEGRAM_API_TOKEN)

@bot.message_handler(content_types=['document', 'photo'])
def data_processing(message):
    chat_id = message.chat.id
    state = db.get_state(message.chat.id)
    if state != 'gettingimg':
        bot.send_message(message.chat.id, 'Ви робите щось не те. Будь-ласка, перевірте інструкції.')
        return

    if message.document:
        file = message.document
    else:
        file = message.photo[0]

    try:
        """Скачивание файл по айди """
        info = bot.get_file(file.file_id)

        type = service.get_doc_type(info.file_path)
        if type != 'png' and type != 'jpg':
            bot.send_message(message.chat.id, 'Не корректний тип файлу')
            return

        file = bot.download_file(info.file_path)
        path = service.save_document(info, file)
        db.set_img(chat_id, path)

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

        button1 = types.KeyboardButton('Інформаця відсутня')
        markup.add(button1)
        add_cancel_button(markup)

        bot.send_message(message.chat.id,
                         'По можливості додайте більше інформації про порушника (ПІБ, номер телефону і т.д)',
                         reply_markup=markup)

        db.set_state(message.chat.id, 'gettinginfo')

    except:
        bot.send_message(chat_id, 'Ойой, щось пішло не так і ми не змогли виконати Ваш запит((')


@bot.message_handler(content_types=['location'])
def getting_location(message):
    state = db.get_state(message.chat.id)
    if state == 'gettinglocation':

        coords = f'{message.location.latitude}, {message.location.longitude}'

        db.set_geo(message.chat.id, coords)
        db.set_state(message.chat.id, 'gettingimg')

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        add_cancel_button(markup)

        bot.send_message(message.chat.id, 'Прикріпіть фотографію як документ '
                                          '(без стиснення) щоб не втратити якість', reply_markup=markup)



@bot.message_handler(commands=['start'])
def welcome(message):
    if message.chat.type == 'private':
        db.user_create(message.chat.id)
        db.set_state(message.chat.id, '')
        markup = get_common_markup()
        username = message.from_user.first_name
        sticker = open('static/AnimatedSticker.tgs', 'rb')
        bot.send_message(message.chat.id, f'<b>Вітаю {username}</b>!', parse_mode='html', reply_markup=markup)
        bot.send_sticker(message.chat.id, sticker)


@bot.message_handler(content_types=['text'])
def send_message(message):
    chat_id = message.chat.id
    if message.chat.type == 'private':
        current_state = db.get_state(message.chat.id)

        if message.text == 'Надіслати репорт' and current_state == 'reportcomplete':
            db.set_state(chat_id, 'reportfinished')
            data = db.get_current_report(chat_id)
            markup = get_common_markup()
            email = db.get_email(chat_id)
            try:
                service.send_report(data, email)
                bot.send_message(chat_id, 'Репорт успішно відправлено! Дякуємо за допомогу!',
                                 reply_markup=markup)
            except:
                bot.send_message(chat_id, 'Нажаль сталася помилка при надсилані репорту. Спробуйте пізніше',
                                 reply_markup=markup)


        elif message.text == 'Повідомити про пожежу':
            db.set_geo(chat_id, '')
            db.set_info(chat_id, '')
            db.set_img(chat_id, '')
            db.set_state(chat_id, 'gettinglocation')

            button = types.KeyboardButton('Відправити ГЕО', request_location=True)
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(button)

            add_cancel_button(markup)

            bot.send_message(message.chat.id, text='Створення репорту:')
            bot.send_message(message.chat.id, text='Натисніть "Відправити ГЕО" для '
                                                   'додавання геолокації пожежі', reply_markup=markup)

        elif (current_state == 'gettingemail' and message.text != 'Відміна'):

            db.set_state(chat_id, 'reportcomplete')
            db.set_email(chat_id, message.text)

            next_button = types.KeyboardButton('Надіслати репорт')
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(next_button)

            add_cancel_button(markup)

            bot.send_message(message.chat.id,
                             'Репорт готовий, натисніть "Надіслати репорт" '
                             'для надсилання на репорту на пошту" ',
                             reply_markup=markup)

        elif current_state == 'gettinginfo' \
                and message.text != 'Відміна' \
                or message.text == 'Інформаця відсутня':

            db.set_info(chat_id, message.text)
            db.set_state(chat_id, 'gettingemail')

            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            add_cancel_button(markup)

            bot.send_message(message.chat.id, 'Вкажіть Ваш "@мейл:',
                             reply_markup=markup)

        elif current_state == 'reportfinished':
            db.set_state(chat_id, '')

        elif message.text == 'Відміна' and current_state != '':
            db.set_state(chat_id, '')
            db.delete_current_attach(chat_id)
            db.set_geo(chat_id, '')
            db.set_info(chat_id, '')
            db.set_img(chat_id, '')

            markup = get_common_markup()
            bot.send_message(chat_id, 'Репорт відмінено', reply_markup=markup)
        elif message.text == 'Підтримати проект':

            db.set_state(chat_id, 'inputamount')
            bot.send_message(chat_id, 'Вкажіть сумму якою Ви хочете підтримати проект:')

        elif current_state == 'inputamount':

            if re.search('[0-9]', message.text):
                amount = message.text
                ref_invoice = service.create_invoice(amount, settings.LIQPAY_PUBLIC_KEY, settings.LIQPAY_PRIVATE_KEY)

                if ref_invoice is None:
                    bot.send_message(chat_id, 'Сталась помилка при генерації посилання')
                    return

                response = f'Перейдіть за посиланням для переказу коштів на підтримку проекту {ref_invoice}'
                bot.send_message(chat_id, response)
            else:
                bot.send_message(chat_id, 'Ви вказали невірну сумму')

        else:
            bot.send_message(chat_id, 'Нажаль, я не розумію цю команду( '
                                      'Спробуйте щось інше, або скористайтесь командою /start')



def get_common_markup():
    but1 = types.KeyboardButton('Повідомити про пожежу')
    but2 = types.KeyboardButton('Підтримати проект')

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(but1)
    markup.add(but2)
    return markup

def add_cancel_button(markup):
    cancel_button = types.KeyboardButton('Відміна')
    markup.add(cancel_button)


if __name__ == '__main__':
    print('bot is started')
    bot.polling(none_stop=True)
