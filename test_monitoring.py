# -*- coding: utf-8 -*-
from database import setup_database, get_temperature_changes

conn = setup_database('temperatures.db')

# Проверка с разными параметрами
print("=== Тест мониторинга изменений ===\n")

# Тест 1: Все силосы, большой диапазон
print("Тест 1: Все силосы, 2026-03-04 - 2026-03-05, порог 1.0")
changes = get_temperature_changes(conn, None, '2026-03-04', '2026-03-05', 1.0)
print(f"  Найдено: {len(changes)}")
if changes:
    print(f"  Пример: {changes[0]}")

# Тест 2: Конкретный силос
print("\nТест 2: Силос '4р', 2026-03-04 - 2026-03-05, порог 1.0")
changes = get_temperature_changes(conn, '4р', '2026-03-04', '2026-03-05', 1.0)
print(f"  Найдено: {len(changes)}")
if changes:
    print(f"  Пример: {changes[0]}")

# Тест 3: Большой диапазон
print("\nТест 3: Все силосы, 2026-02-25 - 2026-03-07, порог 3.0")
changes = get_temperature_changes(conn, None, '2026-02-25', '2026-03-07', 3.0)
print(f"  Найдено: {len(changes)}")
if changes:
    print(f"  Пример: {changes[0]}")

# Проверка данных в базе
print("\n=== Проверка данных в базе ===")
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM readings")
print(f"Всего записей: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(DISTINCT silo) FROM readings")
print(f"Всего силосов: {cur.fetchone()[0]}")

cur.execute("SELECT silo, COUNT(*) FROM readings GROUP BY silo ORDER BY silo")
print("\nЗаписей по силосам:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]}")

conn.close()
