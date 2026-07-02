# -*- coding: utf-8 -*-
from database import setup_database

conn = setup_database('temperatures.db')
cur = conn.cursor()

# Проверка данных за разные даты
print("=== Данные за 06-07 марта ===")
cur.execute("""
    SELECT silo, suspension, sensor, date, temperature 
    FROM readings 
    WHERE date IN ('2026-03-06', '2026-03-07')
    AND silo = '3а'
    ORDER BY suspension, sensor, date
    LIMIT 20
""")
for row in cur.fetchall():
    print(f"{row[0]} | Подв.{row[1]}, Дат.{row[2]}: {row[3]} = {row[4]}°C")

# Проверка: сколько дат для каждого датчика
print("\n=== Количество дат на датчик (3а) ===")
cur.execute("""
    SELECT suspension, sensor, COUNT(DISTINCT date) as days
    FROM readings
    WHERE silo = '3а'
    GROUP BY suspension, sensor
    ORDER BY suspension, sensor
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"Подв.{row[0]}, Дат.{row[1]}: {row[2]} дней")

# Проверка изменений для 3а
print("\n=== Изменения для 3а (04-07 марта, порог 1.0) ===")
from database import get_temperature_changes
changes = get_temperature_changes(conn, '3а', '2026-03-04', '2026-03-07', 1.0)
print(f"Найдено: {len(changes)}")
for c in changes[:5]:
    print(f"  Подв.{c['suspension']}, Дат.{c['sensor']}: {c['prev_date']} {c['prev_temp']}°C -> {c['last_date']} {c['last_temp']}°C (Δ={c['delta']:+.1f}°C)")

conn.close()
