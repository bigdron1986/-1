# -*- coding: utf-8 -*-
from database import setup_database, get_temperature_changes, get_unique_silos

conn = setup_database('temperatures.db')

# Получить список силосов
silos = get_unique_silos(conn)
print(f"Силосы: {silos}")

# Тест с первым силосом из списка
if silos:
    test_silo = silos[0]
    print(f"\nТест для силоса: {repr(test_silo)}")
    
    changes = get_temperature_changes(conn, test_silo, '2026-03-04', '2026-03-05', 1.0)
    print(f"  Найдено изменений: {len(changes)}")
    
    if changes:
        print(f"  Пример: {changes[0]}")

conn.close()
