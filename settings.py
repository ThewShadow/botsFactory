import os
import sys

if len(sys.argv) > 1:
    if sys.argv[1] == '-t':
        TELEGRAM_API_TOKEN = '5147041361:AAGQM-EGM5J_jZmc2xVVafpsrmNjXUGK830'
else:
    TELEGRAM_API_TOKEN = os.getenv('TELEGRAM_API_TOKEN')

DB_NAME = 'db'
DB_HOST = 'localhost'
DB_PASS = '123'
DB_USER = 'postgres'

SENDER_MAIL = os.getenv('SENDER_MAIL')
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PASS = os.getenv('SMTP_PASS')
SMTP_PORT = 465

BITCOIN_PAYMENT_KEY = 'qqjzw8ggm3srt420ewz24kg594gz05y5ku64gqnexa'

LIQPAY_PUBLIC_KEY = os.getenv('LIQPAY_PUBLIC_KEY')
LIQPAY_PRIVATE_KEY = os.getenv('LIQPAY_PRIVATE_KEY')

LOGFILE_PATH = 'logs.log'

