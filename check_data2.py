# -*- coding: utf-8 -*-
from database import setup_database
import pandas as pd

conn = setup_database('temperatures.db')

# Проверка по всем силосам
df_all = pd.read_sql('SELECT silo, suspension, sensor FROM readings ORDER BY silo, suspension, sensor', conn)

print("По всем силосам:")
for silo in sorted(df_all['silo'].unique()):
    df_silo = df_all[df_all['silo'] == silo]
    suspensions = sorted(df_silo['suspension'].unique())
    sensors = sorted(df_silo['sensor'].unique())
    print(f"  {silo}: подвески={suspensions}, датчики={sensors}")

conn.close()
