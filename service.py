import logging
import settings
import os
import threading
import psycopg2
from psycopg2 import sql
from liqpay import LiqPay
import email
from email.mime.multipart import MIMEMultipart
from email.mime.multipart import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from email.utils import formataddr
import smtplib
import ssl
import telebot
from PIL import Image

logging.basicConfig()


def query(func):
    def wrapper(self, **kwargs):
        try:
            res = func(self, **kwargs)
            self.conn.commit()
            return res
        except Exception as e:
            self.conn = psycopg2.connect(dbname=settings.DB_NAME, user=settings.DB_USER,
                                         host=settings.DB_HOST, password=settings.DB_PASS)
            self.cursor = self.conn.cursor()
            logging.critical(e)

    return wrapper


class DB():
    def __init__(self):
        try:
            self.conn = psycopg2.connect(dbname=settings.DB_NAME, user=settings.DB_USER,
                                         host=settings.DB_HOST, password=settings.DB_PASS)
            self.cursor = self.conn.cursor()
        except Exception as e:
            logging.critical(e)
            raise e

    def disconnect(self):
        try:
            if self.cursor:
                self.cursor.close()

            if self.conn:
                self.conn.close()
        except Exception as e:
            logging.critical(e)

    @query
    def create_tables(self):
        self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS USERS  (
                id INTEGER,
                state varchar,
                geo varchar,
                img varchar,
                info varchar,
                email varchar,
                payment_method varchar          
            );  
        ''')

    @query
    def user_create(self, **kwargs):
        user_exists = False
        self.cursor.execute('SELECT * FROM USERS WHERE id = %s ;', (kwargs['id'],))
        for u in self.cursor:
            user_exists = True

        if not user_exists:
            self.cursor.execute('INSERT INTO USERS (id) VALUES (%s);', (kwargs['id'],))
            logging.info(f"user is create (id={kwargs['id']})")

    @query
    def get_payment_method(self, **kwargs):
        self.cursor.execute('SELECT payment_method FROM USERS WHERE id = %s ;', (kwargs['id'],))
        for str in self.cursor:
            return str[0]

    @query
    def get_state(self, **kwargs):
        self.cursor.execute('SELECT state FROM USERS WHERE id = %s ;', (kwargs['id'],))
        for str in self.cursor:
            return str[0]

    @query
    def get_email(self, **kwargs):
        self.cursor.execute('SELECT email FROM USERS WHERE id = %s ;', (kwargs['id'],))
        for str in self.cursor:
            return str[0]

    @query
    def set_geo(self, **kwargs):
        self.cursor.execute('UPDATE USERS SET geo = %s WHERE id = %s ;', (kwargs['geo'], kwargs['id']))
        logging.info(f"user (id={kwargs['id']}) add geo ({kwargs['geo']})")

    @query
    def set_img(self, **kwargs):
        self.cursor.execute('UPDATE USERS SET img = %s WHERE id = %s ;', (kwargs['img'], kwargs['id']))
        logging.info(f"user (id={kwargs['id']}) add img ({kwargs['img']})")

    @query
    def set_info(self, **kwargs):
        self.cursor.execute('UPDATE USERS SET info = %s WHERE id = %s ;', (kwargs['info'], kwargs['id']))
        logging.info(f"user (id={kwargs['id']}) add info ({kwargs['info']})")

    @query
    def set_state(self, **kwargs):
        self.cursor.execute(f'UPDATE USERS SET state = %s WHERE id = %s ;', (kwargs['state'], kwargs['id']))
        logging.info(f"user (id={kwargs['id']}) moved to next state ({kwargs['state']})")

    @query
    def set_email(self, **kwargs):
        self.cursor.execute(f'UPDATE USERS SET email = %s WHERE id = %s ;', (kwargs['email'], kwargs['id']))
        logging.info(f"user (id={kwargs['id']}) add email ({kwargs['email']})")

    @query
    def set_payment_method(self, **kwargs):
        self.cursor.execute(f'UPDATE USERS SET payment_method = %s WHERE id = %s ;', (
            kwargs['payment_method'], kwargs['id']
        ))
        logging.info(f"user (id={kwargs['id']}) select payment method ({kwargs['payment_method']})")

    @query
    def get_current_report(self, **kwargs):
        report = None
        self.cursor.execute('SELECT * FROM USERS WHERE id = %s ;', (kwargs['id'],))
        for data in self.cursor:
            geo = data[2]
            img = data[3]
            info = data[4]
            report = {'geo': geo, 'img': img, 'info': info}
            break
        return report

    @query
    def delete_user_attach(self, **kwargs):
        self.cursor.execute('SELECT img FROM USERS WHERE id = %s', (kwargs['id'],))
        for data in self.cursor:
            attach = data[0]
            if attach:
                os.remove(attach)

    @query
    def clear_user_data(self, **kwargs):
        self.cursor.execute("UPDATE USERS SET geo='', img='', info='', email='' WHERE id = %s ;", (kwargs['id'],))


def send_report(data, mail):
    if not mail:
        return

    msg = MIMEMultipart()
    msg['Subject'] = 'Пожежа'
    msg['From'] = formataddr(('@FireReportBot', settings.SENDER_MAIL))
    msg['To'] = settings.SENDER_MAIL

    part = MIMEBase('application', "octet-stream")
    part.set_payload(open(data['img'], "rb").read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f'attachment; filename="{data["img"]}"')

    msg.attach(part)

    text_message = f'''
        <b>Пожежа за координатами:</b> <p>{data['geo']}</p> \n

        <b>Інформація від відправника:</b> <p>{data['info']}</p>   
    '''
    msg.attach(MIMEText(text_message, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(settings.SMTP_SERVER, settings.SMTP_PORT, context=context) as server:
        server.login(settings.SENDER_MAIL, settings.SMTP_PASS)
        server.sendmail(settings.SENDER_MAIL, mail, msg.as_string())
        os.remove(data["img"])


def get_full_file_path(info):
    return 'static/' + info.file_path


def get_file_directory(info):
    arr = info.file_path.split('/')
    return 'static/' + arr[0]


def save_document(info, binary):
    """Создание папки для хранения файла"""
    dir = get_file_directory(info)
    if os.path.exists(dir) == False:
        os.mkdir(dir)

    """Запись бинарника в файл"""
    path = get_full_file_path(info)
    with open(path, 'wb') as f:
        f.write(binary)

    return path


def get_doc_type(path):
    type = path.split('.')
    return type[len(type) - 1]


def create_invoice(amount, public_key, private_key):
    liqpay = LiqPay(public_key, private_key)
    res = liqpay.api("request", {
        "action": "invoice_bot",
        "version": "3",
        "amount": amount,
        "currency": "UAH",
        "phone": "380950000001",
        "server_url": '46.118.172.5'
    })
    if 'href' in res:
        return res['href']


PAYMENT_SERVICES = [
    'liqpay',
    'paypal',
    'easypay',
    'bitcoin'
]