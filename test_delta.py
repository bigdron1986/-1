from database import setup_database, get_available_dates, get_silo_list, get_all_silos_delta_for_date

conn = setup_database('temperatures.db')

dates = get_available_dates(conn)
print('Даты (последние 5):', dates[-5:] if dates else 'Нет данных')

silos = get_silo_list(conn, exclude_operational=False)
print('Силоса:', silos)

if dates:
    today = dates[-1]
    print(f'\nПроверка даты: {today}')
    
    data = get_all_silos_delta_for_date(conn, today)
    print(f'Количество силосов с данными: {len(data) if data else 0}')
    
    if data:
        for silo, suspensions in list(data.items())[:3]:
            print(f'\n{silo}:')
            for susp, sensors in list(suspensions.items())[:2]:
                for sensor, delta_data in list(sensors.items())[:2]:
                    print(f"  П{susp}/Д{sensor}: t={delta_data.get('current')}, delta={delta_data.get('delta')}")

conn.close()
