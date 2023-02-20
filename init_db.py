import sqlite3

# Создание файла БД, если его нет и создание таблицы на logs
connection = sqlite3.connect('database.db')
with open('schema.sql') as f:
    connection.executescript(f.read())

cur = connection.cursor()

connection.commit()
connection.close()

print('Подготовка базы данных завершена')