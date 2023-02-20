import json
import sqlite3
import sys
import configparser
import threading
import asyncio

from gevent import pywsgi
from flask import Flask, render_template
from flask_websockets import WebSockets
from geventwebsocket.handler import WebSocketHandler

app = Flask(__name__)
sockets = WebSockets(app)


class Kettle (threading.Thread):
    """Класс чайника, описывает структуру чайника в коде Python"""
    
    def __init__(self) -> None:
        """Блок инициализации, вызывается при создании объекта класса Чайник"""
        
        threading.Thread.__init__(self)

        # Загрузка конфига
        config = configparser.ConfigParser()
        config.read('config.ini')
        config_data = config['DEFAULT']

        # Загрузка значений конфига
        try:
            # Текущая и максимальная температура чайника
            self.kettle_temperature = 0
            self.kettle_temperature_max = float(config_data['kettle_temperature_max'])

            # Текущее и максимальное время закипания воды в чайнике
            self.kettle_time = 0
            self.kettle_time_max = float(config_data['kettle_time_max'])

            # Текущий и максимальный объём воды в чайнике
            self.water_volume = 0
            self.water_volume_max = float(config_data['water_volume_max'])

            print('Данные успешно загружены')

        except TypeError as _except:
            print(_except)
            self.kettle_temperature = 0
            self.kettle_temperature_max = 100

            self.kettle_time = 0
            self.kettle_time_max = 10

            self.water_volume = 0
            self.water_volume_max = 0

        self.isWorking = False

    # Вызов асинхронного метода для работы чайника
    def run(self) -> None:
        asyncio.run(self.start_working())

    # Получение текущей температуры
    def get_temperature(self) -> str:
        if self.isWorking and self.water_volume > 0:
            return 'temperature', self.kettle_temperature
        elif self.water_volume == 0:
            return 'power_off', f'В чайнике нет воды, чайник выключился'
        else:
            return 'power_off', f'Чайник выключился (температура {kettle.kettle_temperature})'

    # Здесь мы задаём объём ворды в чайнике
    def set_water_volume(self, vol) -> float:
        try:
            volume = float(vol)
            if volume <= self.water_volume_max:
                self.water_volume = volume
                return volume
            else:
                return -1

        except TypeError as _except:
            print(_except)
            self.water_volume = 0

    # Ассинхронный метод работы чайник, всегда работает в фоне
    async def start_working(self) -> None:
        while True:
            # Если чайник включен - вода нагревается
            if self.isWorking:
                # Проверка текущего состояния закипания воды
                if self.kettle_time < self.kettle_time_max and self.water_volume > 0:
                    await asyncio.sleep(1)
                    self.kettle_time += 1
                    self.kettle_temperature += 10
                    
                # Если вода вскипела, либо пользователь нажал кнопку выключения, 
                # то чайник прекращает работу
                else:
                    self.power_off()

            # Если нет - чайник ждёт включения
            else:
                await asyncio.sleep(0.2)

    # Метод включения чайника
    def power_on(self) -> None:
        self.kettle_time = 0
        self.kettle_temperature = 0
        self.isWorking = True

    # Метод выключения чайника
    def power_off(self) -> None:
        self.kettle_time = 0
        self.isWorking = False


# Получение комманд от пользователя и из обработка
@sockets.on_message
def echo(message) -> str:
    message_type = 'message'

    # Включить чайник
    if message == 'start':
        kettle.power_on()
        message = 'Чайник включился'
        
    # Выключить чайник
    elif message == 'stop':
        kettle.power_off()
        message = f'Чайник выключился (температура {kettle.kettle_temperature})'
        
    # Запрос температуры 
    elif message == 'temperature':
        message_type, message = kettle.get_temperature()
        
    # Налить воды в чайник
    elif message[0:3] == 'vol':
        if len(message) < 4:
            message = f'Недостаточно воды'
        elif (ans := kettle.set_water_volume(message[3:])) > 0:
            message = f'Чайник налили воды({ans})'
        else:
            message = f'Максимальный объём воды в чайнике - {kettle.water_volume_max}'

    else:
        message = 'Команда не найдена'
        message_type = 'sys'

    # Логирование комманд
    db_connection.execute(f'INSERT INTO logs (context) VALUES ("{message}")')
    
    # отправка ответа пользователю
    return json.dumps(
        {
            'type': message_type,
            'message': message
        }
    )


# Рендер страны пользователя
@app.route('/')
def index():
    return render_template('index.html')


# Подключение к файлу базы данных
def get_db_connection():
    _conn = sqlite3.connect('database.db')
    _conn.row_factory = sqlite3.Row
    return _conn


if __name__ == '__main__':
    # Создание подключения к БД
    db_connection = get_db_connection()
    
    # Логирование включения программы
    db_connection.execute('INSERT INTO logs (context) VALUES ("Программа запущена")')
    
    # Запрос и вывод всех логов
    logs = db_connection.execute('SELECT * FROM logs').fetchall()
    for el in logs:
        print(f"{el['context']} [{el['created']}]")

    # Создание и инициализация объекта чайник
    kettle = Kettle()
    kettle.start()

    # Создание WebSocket для непрерывной связи клиента и сервера без перезагрузки страницы
    server = pywsgi.WSGIServer(('127.0.0.1', 5000), app, handler_class=WebSocketHandler)
    
    try:
        server.serve_forever()

    except KeyboardInterrupt:
        server.stop()

    finally:
        # Логирование выхода из програмы
        db_connection.execute('INSERT INTO logs (context) VALUES ("Выход из программы")')
        db_connection.commit()
        db_connection.close()

        sys.exit()
