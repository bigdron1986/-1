# -*- coding: utf-8 -*-
from database import setup_database
import pandas as pd

conn = setup_database('temperatures.db')
df = pd.read_sql('SELECT suspension, sensor FROM readings WHERE silo="3а" LIMIT 100', conn)

print('Уникальные подвески:', sorted(df['suspension'].unique()))
print('Уникальные датчики:', sorted(df['sensor'].unique()))
print('Всего подвесок:', df['suspension'].nunique())
print('Всего датчиков:', df['sensor'].nunique())

print('\nПример данных (первые 12 строк):')
print(df.head(12))

conn.close()
