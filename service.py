import sqlite3
import logging
import settings
import os

logging.basicConfig(level=logging.DEBUG)

def db_name():
    return settings.DB_NAME

class db():
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
        self.conn = sqlite3.connect(db_name(), check_same_thread = False)
        self.cursor = self.conn.cursor()

    def disconnect(self):
        if self.conn:
            self.conn.close()

    def create_tables(self):

        if self.cursor:
            self.cursor.execute('''
                    CREATE TABLE IF NOT EXISTS USERS  (
                    id INTEGER,
                    state TEXT,
                    geo TEXT,
                    img BLOB,
                    report_info TEXT          
                );  
            ''')
        if self.cursor:
            self.cursor.execute('''
                    CREATE TABLE IF NOT EXISTS REPORTS  (
                    id INTEGER ,
                    img BLOB NOT NULL,
                    text TEXT NOT NULL,
                    refloction TEXT NOT NULL
                          
                );  
            ''')

    def user_create(self, id):
        self.connect()
        r = self.cursor.execute('SELECT * FROM USERS WHERE id = ? ;', (id,))
        if r.fetchone() is None:
            self.cursor.execute('INSERT INTO USERS (id) VALUES (?);', (id,))
            logging.info(f'user is create (id={id})')
        self.disconnect()

    def get_state(self, id):
        self.connect()
        self.cursor.execute('SELECT state FROM USERS WHERE id = ? ;', (id,))

        rows = self.cursor.fetchall()
        self.disconnect()
        if len(rows):
            for str in rows:
                return str[0]

    def query(func):
        def wrapper(self, id, param):
            self.connect()
            func(self, id, param)
            self.conn.commit()
            self.disconnect()

        return wrapper

    @query
    def set_geo(self, id, geo):
        self.cursor.execute('UPDATE USERS SET geo = ? WHERE id = ? ;',(geo, id))
        logging.info(f'user (id={id}) add geo ({geo})')

    @query
    def set_img(self, id, img):
        self.cursor.execute('UPDATE USERS SET img = ? WHERE id = ? ;', (img, id))
        logging.info(f'user (id={id}) add img ({img})')

    @query
    def set_info(self, id, info):
        self.cursor.execute('UPDATE USERS SET report_info = ? WHERE id = ? ;', (info, id))
        logging.info(f'user (id={id}) add info ({info})')

    @query
    def set_state(self, id, state):
        self.cursor.execute(f'UPDATE USERS SET state = ? WHERE id = ? ;', (state, id))
        logging.info(f'user (id={id}) moved to next state ({state})')


    def get_current_report(self, id):
        report = None
        self.connect()
        r = self.cursor.execute('SELECT * FROM USERS WHERE id = ? ;', (id,)).fetchone()
        self.disconnect()
        if r is not None:
            geo = r[2]
            img = r[3]
            info = r[4]
            report = {'geo': geo, 'img': img, 'info': info}

        return report


    def delete_current_attach(self, id):
        self.connect()
        r = self.cursor.execute('SELECT img FROM USERS WHERE id = ?', (id,)).fetchone()
        self.disconnect()
        if r:
            attach = r[0]
            os.remove(attach)


