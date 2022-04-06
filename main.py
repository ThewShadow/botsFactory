import telebot
import settings
from telebot import types
import os
import json
import smtplib, ssl
from service import db
import email
from email.mime.multipart import MIMEMultipart
from email.mime.multipart import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from email.utils import formataddr
import os

db = db()
bot = telebot.TeleBot(settings.TELEGRAM_API_TOKEN)
TEST = True

def send_report(chat_id, message):
    msg = MIMEMultipart()
    msg['Subject'] = 'Пожежа'
    msg['From'] = formataddr(('@FireReportBot', settings.SENDER_MAIL))
    msg['To'] = settings.SENDER_MAIL

    part = MIMEBase('application', "octet-stream")
    part.set_payload(open(message['img'], "rb").read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f'attachment; filename="{message["img"]}"')

    msg.attach(part)

    text_message = f'''
        <b>Пожежа за координатами:</b> <p>{message['geo']}</p> \n
        
        <b>Інформація від відправника:</b> <p>{message['info']}</p>   
    '''
    msg.attach(MIMEText(text_message, "html"))

    receiver_email = db.get_email(chat_id)
    if not receiver_email:
        return

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(settings.SMTP_SERVER, settings.SMTP_PORT, context=context) as server:
        server.login(settings.SENDER_MAIL, settings.SMTP_PASS)
        server.sendmail(settings.SENDER_MAIL, receiver_email, msg.as_string())
        os.remove(message["img"])


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

        db.set_img(chat_id, path)

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

        add_cancel_button(markup)

        bot.send_message(message.chat.id,
                         'По можливості додайте більше інформації про порушника (ПІБ, номер телефону і т.д)',
                         reply_markup=markup)

        db.set_state(message.chat.id, 'gettinginfo')

    except :
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
            report = db.get_current_report(chat_id)
            markup = get_common_markup()
            try:
                send_report(chat_id, report)

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

        elif current_state == 'gettingemail' and message.text != 'Відміна':
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

        elif current_state == 'gettinginfo' and message.text != 'Відміна':
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

        else:
            bot.send_message(chat_id, 'Нажаль, я не розумію цю команду( '
                                      'Спробуйте щось інше, або скористайтесь командою /start')

def get_common_markup():
    but1 = types.KeyboardButton('Повідомити про пожежу')
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(but1)
    return markup

def add_cancel_button(markup):
    cancel_button = types.KeyboardButton('Відміна')
    markup.add(cancel_button)


if __name__ == '__main__':
    print('bot is started')
    bot.polling(none_stop=True)
