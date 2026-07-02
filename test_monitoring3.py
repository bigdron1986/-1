# -*- coding: utf-8 -*-
from database import setup_database, get_temperature_changes

conn = setup_database('temperatures.db')

# Проверка изменений для 3а за 04-05 марта
changes = get_temperature_changes(conn, '3а', '2026-03-04', '2026-03-05', 1.0)
print(f'3а 04-05 марта: {len(changes)} изменений')

# Проверка изменений для всех силосов за 04-05 марта  
changes = get_temperature_changes(conn, None, '2026-03-04', '2026-03-05', 1.0)
print(f'Все силосы 04-05 марта: {len(changes)} изменений')

# Проверка данных за 05 марта
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM readings WHERE date='2026-03-05'")
print(f"Записей за 05 марта: {cur.fetchone()[0]}")

# Проверка данных за 07 марта
cur.execute("SELECT COUNT(*) FROM readings WHERE date='2026-03-07'")
print(f"Записей за 07 марта: {cur.fetchone()[0]}")

# Проверка: сравнение температур за 06 и 07 марта для 3а
print("\n=== Сравнение 06 vs 07 марта для 3а ===")
cur.execute("""
    SELECT a.suspension, a.sensor, a.temperature as t06, b.temperature as t07
    FROM readings a
    JOIN readings b ON a.suspension=b.suspension AND a.sensor=b.sensor 
        AND a.date='2026-03-06' AND b.date='2026-03-07'
    WHERE a.silo='3а' AND b.silo='3а'
    LIMIT 10
""")
for row in cur.fetchall():
    print(f"Подв.{row[0]}, Дат.{row[1]}: 06={row[2]}°C, 07={row[3]}°C, Δ={row[3]-row[2]:+.1f}°C")

conn.close()
