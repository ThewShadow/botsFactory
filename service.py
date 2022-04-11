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

logging.basicConfig(level=logging.WARNING)


def db_name():
    return settings.DB_NAME


class DB():
    cursor = None
    conn = None

    def __init__(self):
        try:
            print('good')
            pass
        except sqlite3.Error as err:
            logging.critical(f'{err}')
            pass
        self.connect()
        self.create_tables()
        self.disconnect()

    def connect(self):
        self.conn = psycopg2.connect(dbname=settings.DB_NAME,
                                     user=settings.DB_USER,
                                     host=settings.DB_HOST,
                                     password=settings.DB_PASS)

        self.cursor = self.conn.cursor()

    def disconnect(self):
        if self.cursor:
            self.cursor.close()

        if self.conn:
            self.conn.close()

    def create_tables(self):

        if self.cursor:
            self.cursor.execute('''
                    CREATE TABLE IF NOT EXISTS USERS  (
                    id INTEGER,
                    state varchar,
                    geo varchar,
                    img varchar,
                    report_info varchar,
                    email varchar          
                );  
            ''')
            self.conn.commit()

        if self.cursor:
            self.cursor.execute('''
                    CREATE TABLE IF NOT EXISTS REPORTS  (
                    id INTEGER ,
                    img TEXT NOT NULL,
                    text TEXT NOT NULL,
                    refloction TEXT NOT NULL
                          
                );  
            ''')

    def query(func):
        def wrapper(self, id, param):
            self.connect()
            func(self, id, param)
            self.conn.commit()
            self.disconnect()

        return wrapper

    def user_create(self, id):
        self.connect()
        self.cursor.execute('SELECT * FROM USERS WHERE id = %s ;', (id,))

        user_exists = False
        for u in self.cursor:
            user_exists = True
        if user_exists:
            return
        else:
            self.cursor.execute('INSERT INTO USERS (id) VALUES (%s);', (id,))
            self.conn.commit()
            logging.info(f'user is create (id={id})')
            self.disconnect()


    def get_state(self, id):
        self.connect()
        self.cursor.execute('SELECT state FROM USERS WHERE id = %s ;', (id,))
        for str in self.cursor:
            self.disconnect()
            return str[0]

    def get_email(self, id):
        self.connect()
        self.cursor.execute('SELECT email FROM USERS WHERE id = %s ;', (id,))
        for str in self.cursor:
            self.disconnect()
            return str[0]

    @query
    def set_geo(self, id, geo):
        self.cursor.execute('UPDATE USERS SET geo = %s WHERE id = %s ;',(geo, id))
        logging.info(f'user (id={id}) add geo ({geo})')

    @query
    def set_img(self, id, img):
        self.cursor.execute('UPDATE USERS SET img = %s WHERE id = %s ;', (img, id))
        logging.info(f'user (id={id}) add img ({img})')

    @query
    def set_info(self, id, info):
        self.cursor.execute('UPDATE USERS SET report_info = %s WHERE id = %s ;', (info, id))
        logging.info(f'user (id={id}) add info ({info})')

    @query
    def set_state(self, id, state):
        self.cursor.execute(f'UPDATE USERS SET state = %s WHERE id = %s ;', (state, id))
        logging.info(f'user (id={id}) moved to next state ({state})')

    @query
    def set_email(self, id, email):
        self.cursor.execute(f'UPDATE USERS SET email = %s WHERE id = %s ;', (email, id))
        logging.info(f'user (id={id}) add email ({email})')

    def get_current_report(self, id):
        report = None
        self.connect()
        self.cursor.execute('SELECT * FROM USERS WHERE id = %s ;', (id,))
        for data in self.cursor:
            geo = data[2]
            img = data[3]
            info = data[4]
            report = {'geo': geo, 'img': img, 'info': info}
            break
        self.disconnect()
        return report

    def delete_current_attach(self, id):
        self.connect()
        self.cursor.execute('SELECT img FROM USERS WHERE id = %s', (id,))
        for data in self.cursor:
            attach = data[0]
            if attach:
                os.remove(attach)
        self.disconnect()


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
        "phone": "380950000001"
    })
    if 'href' in res:
        return res['href']