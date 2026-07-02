# -*- coding: utf-8 -*-
from database import setup_database, get_temperature_changes

conn = setup_database('temperatures.db')

# Тест с разными названиями силосов
print("Тест фильтрации по силосам:")

# Проверка: какие силосы есть в базе
cur = conn.cursor()
cur.execute("SELECT DISTINCT silo FROM readings ORDER BY silo")
silos = [r[0] for r in cur.fetchall()]
print(f"Силосы в базе: {silos}")

# Тест с каждым силосом
for silo in ['3а', '3с', '4р', '4с', '5а', '5с']:
    changes = get_temperature_changes(conn, silo, '2026-03-04', '2026-03-05', 1.0)
    print(f"  {silo}: {len(changes)} изменений")

conn.close()
