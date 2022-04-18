import datetime
import os
import telebot
import settings
from telebot import types
import service
import re
import logging
import base64
import tempfile

logging.basicConfig(level='INFO', filename=settings.LOGFILE_PATH)
logger = logging.getLogger()



db = service.DB()
db.create_tables()

bot = telebot.TeleBot(settings.TELEGRAM_API_TOKEN)


@bot.message_handler(commands=['start'])
def welcome(message):
    if message.chat.type == 'private':
        db.user_create(id=message.chat.id)
        db.set_state(id=message.chat.id, state='')
        markup = get_common_markup()
        username = message.from_user.first_name
        sticker = open('static/AnimatedSticker.tgs', 'rb')
        bot.send_message(message.chat.id, f'<b>Вітаю {username}</b>!', parse_mode='html', reply_markup=markup)
        bot.send_sticker(message.chat.id, sticker)


@bot.message_handler(content_types=['text'])
def send_message(message):
    chat_id = message.chat.id
    if message.chat.type == 'private':
        current_state = db.get_state(id=message.chat.id)

        if 'Відміна' in message.text and \
             (current_state == 'selectpayment' or current_state == 'inputamount'):

            clear_user_data(id=chat_id)
            markup = get_common_markup()
            bot.send_message(chat_id, 'Донат відмінено', reply_markup=markup)

        elif 'Відміна' in message.text and current_state != '':
            clear_user_data(id=chat_id)
            markup = get_common_markup()
            bot.send_message(chat_id, 'Репорт відмінено', reply_markup=markup)

        elif 'Надіслати репорт' in message.text and current_state == 'reportcomplete':
            data = db.get_current_report(id=chat_id)
            markup = get_common_markup()
            email = db.get_email(id=chat_id)
            try:
                db.add_user_report(id=data['id'], img=data['img'], email=data['email'], info=data['info'], geo=data['geo'])
                service.send_report(data=data, mail=email)
                bot.send_message(chat_id, 'Репорт успішно відправлено! Дякуємо за допомогу!', reply_markup=markup)
                db.set_state(id=chat_id, state='')
            except Exception as e:
                logger.critical(e)
                bot.send_message(chat_id, 'Нажаль сталася помилка при надсилані репорту. Спробуйте пізніше',
                                 reply_markup=markup)

        elif 'Повідомити про пожежу' in message.text:
            clear_user_data(id=chat_id)
            db.set_state(id=chat_id, state='gettinglocation')
            button = types.KeyboardButton('Відправити ГЕО', request_location=True)
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(button)
            add_cancel_button(markup)
            bot.send_message(message.chat.id, text='Створення репорту:')
            bot.send_message(message.chat.id, text='Натисніть "Відправити ГЕО" для '
                                                   'додавання геолокації пожежі', reply_markup=markup)

        elif current_state == 'gettingemail' and 'Відміна' not in message.text:
            db.set_state(id=chat_id, state='reportcomplete')
            db.set_email(id=chat_id, email=message.text)
            next_button = types.KeyboardButton('Надіслати репорт')
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(next_button)
            add_cancel_button(markup)
            bot.send_message(message.chat.id,
                             'Репорт готовий, натисніть "Надіслати репорт" '
                             'для надсилання на репорту на пошту" ',
                             reply_markup=markup)

        elif current_state == 'gettinginfo' \
                and message.text not in 'Відміна' \
                or 'Інформаця відсутня' in message.text:

            db.set_info(id=chat_id, info=message.text)
            db.set_state(id=chat_id, state='gettingemail')
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            add_cancel_button(markup)
            bot.send_message(message.chat.id, 'Вкажіть Ваш "@мейл:',
                             reply_markup=markup)

        elif 'Підтримати проект' in message.text:
            db.set_state(id=chat_id, state='selectpayment')
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            for title in service.PAYMENT_SERVICES:
                btn = types.KeyboardButton(title)
                markup.add(btn)
            add_cancel_button(markup)
            bot.send_message(chat_id, 'Виберіть варіант донату',  reply_markup=markup)

        elif message.text in service.PAYMENT_SERVICES and current_state == 'selectpayment':
            db.set_payment_method(id=chat_id, payment_method=message.text)
            db.set_state(id=chat_id, state='inputamount')
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            add_cancel_button(markup)
            bot.send_message(chat_id, 'Вкажіть сумму якою Ви хочете підтримати проект:',
                             reply_markup=markup)

        elif current_state == 'inputamount':
            amount = message.text
            if re.search('[0-9]', amount):
                payment_method = db.get_payment_method(id=chat_id)
                msg_pay_not_work = f'Оплата({payment_method}) поки не доступна'

                if payment_method == 'liqpay':
                    ref_invoice = service.create_invoice(amount, settings.LIQPAY_PUBLIC_KEY, settings.LIQPAY_PRIVATE_KEY)
                    if ref_invoice is not None:
                        bot.send_message(
                            chat_id,
                            f'Перейдіть за посиланням для переказу коштів на підтримку проекту {ref_invoice}',
                            reply_markup=get_common_markup()
                        )
                    else:
                        bot.send_message(chat_id, 'Сталась помилка при генерації посилання')

                elif payment_method == 'paypal':
                    bot.send_message(chat_id, msg_pay_not_work, reply_markup=get_common_markup())

                elif payment_method == 'bitcoin':
                    with open('static/bitcoinQR.png', 'rb') as binary:
                        bot.send_message(chat_id, 'Відскануйте або скопіюйте QR для переходу до сторінки оплати')
                        bot.send_message(chat_id, settings.BITCOIN_PAYMENT_KEY)
                        bot.send_photo(chat_id, binary, reply_markup=get_common_markup())

                elif payment_method == 'easypay':
                    bot.send_message(chat_id, msg_pay_not_work, reply_markup=get_common_markup())
            else:
                bot.send_message(chat_id, 'Треба ввести число')

            db.set_state(id=chat_id, state='')

        elif 'Мої репорти' in message.text:

            cursor = db.get_user_reports(id=chat_id)
            if cursor.rowcount:
                for i in cursor:
                    file_path = i[5]
                    date = i[4].strftime('%d-%m-%Y')
                    str_report = f'ДАТА: {date}\nГЕО: {i[1]}\nІНФО: {i[2]}\nПОШТА: {i[3]}'
                    with open(file_path, 'rb') as photo:
                        bot.send_photo(chat_id, photo=photo, caption=str_report)


            else:
                bot.send_message(chat_id, 'У Вас ще немає жодного репорту')

        else:
            bot.send_message(chat_id, 'Нажаль, я не розумію цю команду( '
                                      'Спробуйте щось інше, або скористайтесь командою /start')


@bot.message_handler(content_types=['location'])
def getting_location(message):
    state = db.get_state(id=message.chat.id)
    if state == 'gettinglocation':
        coords = f'{message.location.latitude}, {message.location.longitude}'
        db.set_geo(id=message.chat.id, geo=coords)
        db.set_state(id=message.chat.id, state='gettingimg')
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        add_cancel_button(markup)
        bot.send_message(message.chat.id, 'Прикріпіть фотографію як документ '
                                          '(без стиснення) щоб не втратити якість', reply_markup=markup)


@bot.message_handler(content_types=['document', 'photo'])
def data_processing(message):
    chat_id = message.chat.id
    state = db.get_state(id=message.chat.id)
    if state != 'gettingimg':
        bot.send_message(message.chat.id, 'Ви робите щось не те. Будь-ласка, перевірте інструкції.')
        return

    try:
        if message.document:
            file = message.document
        else:
            file = message.photo[0]

        """Скачивание файл по айди """
        info = bot.get_file(file.file_id)
        type = service.get_doc_type(info.file_path)
        if type != 'png' and type != 'jpg':
            bot.send_message(message.chat.id, 'Не корректний тип файлу')
            return

        file = bot.download_file(info.file_path)
        path = service.save_document(info, file)
        db.set_img(id=message.chat.id, img=path)

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        button1 = types.KeyboardButton('Інформаця відсутня')
        markup.add(button1)
        add_cancel_button(markup)
        bot.send_message(message.chat.id,
                         'По можливості додайте більше інформації про порушника (ПІБ, номер телефону і т.д)',
                         reply_markup=markup)
        db.set_state(id=message.chat.id, state='gettinginfo')

    except Exception as e:
        logger.critical(e)
        bot.send_message(chat_id, 'Ойой, щось пішло не так і ми не змогли виконати Ваш запит((')


def get_common_markup():
    but1 = types.KeyboardButton('🔔 Повідомити про пожежу')
    but2 = types.KeyboardButton('💸 Підтримати проект')
    but3 = types.KeyboardButton('Мої репорти')

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(but1)
    markup.add(but2)
    markup.add(but3)

    return markup


def add_cancel_button(markup):
    cancel_button = types.KeyboardButton('Відміна')
    markup.add(cancel_button)


def clear_user_data(id):
    db.clear_user_data(id=id)
    db.delete_user_attach(id=id)
    db.set_state(id=id, state='')


def run():
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        logger.critical(e)
        run()

if __name__ == '__main__':
    print('bot is started')
    run()




