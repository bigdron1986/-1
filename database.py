# database.py
import sqlite3
import logging
from sqlite3 import Error

# Оперативные силосы, исключаемые из анализа
OPERATIONAL_SILOS = ['1а', '1б', '2а', '2б', '1a', '1b', '2a', '2b']
OPERATIONAL_PLACEHOLDERS = ','.join('?' * len(OPERATIONAL_SILOS))

def create_connection(db_file):
    """ Create a database connection to the SQLite database specified by db_file """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        print(e)
    return conn

def create_table(conn):
    """ Create a table for thermometry readings """
    try:
        sql_create_readings_table = """ CREATE TABLE IF NOT EXISTS readings (
                                            id integer PRIMARY KEY,
                                            silo text NOT NULL,
                                            suspension integer NOT NULL,
                                            sensor integer NOT NULL,
                                            temperature real NOT NULL,
                                            date text NOT NULL,
                                            UNIQUE(silo, suspension, sensor, date)
                                        ); """
        c = conn.cursor()
        c.execute(sql_create_readings_table)
    except Error as e:
        print(e)

def insert_readings(conn, readings):
    """
    Insert multiple readings into the readings table.
    It will replace the reading if it already exists.
    """
    sql = ''' INSERT OR REPLACE INTO readings(silo, suspension, sensor, temperature, date)
              VALUES(?,?,?,?,?) '''
    cur = conn.cursor()
    data_to_insert = [(r['silo'], r['suspension'], r['sensor'], r['temperature'], r['date']) for r in readings]
    cur.executemany(sql, data_to_insert)
    conn.commit()
    return cur.lastrowid

def setup_database(db_file):
    """ Setup the database: create connection and table """
    conn = create_connection(db_file)
    if conn is not None:
        create_table(conn)
        create_user_settings_table(conn)
        return conn
    else:
        print("Error! cannot create the database connection.")
        return None


def create_user_settings_table(conn):
    """Создать таблицу пользовательских настроек"""
    try:
        sql_create_settings_table = """ CREATE TABLE IF NOT EXISTS user_settings (
                                            key text PRIMARY KEY,
                                            value text NOT NULL
                                        ); """
        c = conn.cursor()
        c.execute(sql_create_settings_table)

        # Инициализировать настройки по умолчанию, если их нет
        default_settings = {
            'temp_threshold': '15.0',
            'change_threshold': '3.0',
            'date_format_with_year': 'false',
            'graph_start_date': '',
            'graph_end_date': '',
            'graph_zoom_percent': '100',
            'color_hotspot': '#f38ba8',
            'color_error': '#fab387',
            'color_normal': '#a6e3a1',
            'color_warning': '#f9e2af',
        }

        for key, value in default_settings.items():
            c.execute("SELECT 1 FROM user_settings WHERE key = ?", (key,))
            if not c.fetchone():
                c.execute("INSERT INTO user_settings (key, value) VALUES (?, ?)", (key, value))

        # Создать таблицу комментариев (без UNIQUE — можно несколько за дату)
        sql_create_comments_table = """ CREATE TABLE IF NOT EXISTS comments (
                                            id integer PRIMARY KEY AUTOINCREMENT,
                                            silo text NOT NULL,
                                            date text NOT NULL,
                                            comment text NOT NULL,
                                            created_at text DEFAULT CURRENT_TIMESTAMP
                                        ); """
        c.execute(sql_create_comments_table)

        # Создать таблицу истории лидеров (лидер по каждому силосу отдельно)
        sql_create_leader_history_table = """ CREATE TABLE IF NOT EXISTS leader_history (
                                                date text NOT NULL,
                                                silo text NOT NULL,
                                                suspension integer NOT NULL,
                                                sensor integer NOT NULL,
                                                temperature real NOT NULL,
                                                changed_from_prev BOOLEAN DEFAULT FALSE,
                                                processed_at text DEFAULT CURRENT_TIMESTAMP,
                                                PRIMARY KEY (date, silo)
                                            ); """
        c.execute(sql_create_leader_history_table)

        # Создать индексы для ускорения запросов
        c.execute("CREATE INDEX IF NOT EXISTS idx_readings_date ON readings(date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_readings_silo ON readings(silo)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_readings_silo_date ON readings(silo, date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_readings_silo_temp ON readings(silo, temperature)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_comments_silo_date ON comments(silo, date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_leader_history_date ON leader_history(date)")

        conn.commit()
    except Error as e:
        print(e)


def get_user_setting(conn, key, default=None):
    """Получить пользовательскую настройку"""
    cur = conn.cursor()
    cur.execute("SELECT value FROM user_settings WHERE key = ?", (key,))
    result = cur.fetchone()
    return result[0] if result else default


def set_user_setting(conn, key, value):
    """Установить пользовательскую настройку"""
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO user_settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()


def get_all_user_settings(conn):
    """Получить все пользовательские настройки"""
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM user_settings")
    return dict(cur.fetchall())

def get_unique_silos(conn):
    """ Query all unique silos from the readings table (исключая оперативные 1а, 1б, 2а, 2б) """
    cur = conn.cursor()
    cur.execute(f"""
        SELECT DISTINCT silo FROM readings
        WHERE silo NOT IN ({OPERATIONAL_PLACEHOLDERS})
        ORDER BY silo
    """, OPERATIONAL_SILOS)
    silos = [row[0] for row in cur.fetchall()]
    return silos

def get_readings(conn, silo=None, start_date=None, end_date=None):
    """ Query readings based on filters (исключая оперативные силосы). """
    cur = conn.cursor()
    query = f"""
        SELECT silo, suspension, sensor, temperature, date
        FROM readings
        WHERE 1=1
        AND silo NOT IN ({OPERATIONAL_PLACEHOLDERS})
    """
    params = list(OPERATIONAL_SILOS)

    if silo:
        query += " AND silo = ?"
        params.append(silo)
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    cur.execute(query, params)
    return cur.fetchall()

def get_sensor_history(conn, silo, suspension, sensor):
    """ Query all historical temperature readings for a specific sensor. """
    cur = conn.cursor()
    query = """
        SELECT date, temperature
        FROM readings
        WHERE silo = ? AND suspension = ? AND sensor = ?
        ORDER BY date
    """
    cur.execute(query, (silo, suspension, sensor))
    return cur.fetchall()

def get_sensor_history_with_dates(conn, silo, suspension, sensor, start_date, end_date):
    """ Query historical temperature readings for a specific sensor with date filters. """
    cur = conn.cursor()
    query = """
        SELECT date, temperature
        FROM readings
        WHERE silo = ? AND suspension = ? AND sensor = ?
        AND date >= ? AND date <= ?
        ORDER BY date
    """
    cur.execute(query, (silo, suspension, sensor, start_date, end_date))
    return cur.fetchall()

def get_suspensions_for_silo(conn, silo):
    """ Query all unique suspension numbers for a given silo """
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT suspension FROM readings WHERE silo = ? ORDER BY suspension", (silo,))
    suspensions = [row[0] for row in cur.fetchall()]
    return suspensions

def get_date_range(conn):
    """ Получить минимальную и максимальную дату в базе (исключая оперативные силосы) """
    cur = conn.cursor()
    cur.execute(f"""
        SELECT MIN(date), MAX(date) FROM readings
        WHERE silo NOT IN ({OPERATIONAL_PLACEHOLDERS})
    """, OPERATIONAL_SILOS)
    result = cur.fetchone()
    return result[0], result[1]

def get_available_dates(conn):
    """ Получить список всех дат с данными (исключая оперативные силосы) """
    cur = conn.cursor()
    cur.execute(f"""
        SELECT DISTINCT date FROM readings
        WHERE silo NOT IN ({OPERATIONAL_PLACEHOLDERS})
        ORDER BY date
    """, OPERATIONAL_SILOS)
    return [row[0] for row in cur.fetchall()]

def check_date_exists(conn, date):
    """ Check if any readings exist for a given date. """
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM readings WHERE date = ? LIMIT 1", (date,))
    return cur.fetchone() is not None

def get_all_dates(conn):
    """ Получить список всех дат с данными """
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT date FROM readings ORDER BY date")
    return [row[0] for row in cur.fetchall()]

def get_last_n_dates(conn, n=2):
    """ Получить последние N дат с данными """
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT date FROM readings
        ORDER BY date DESC
        LIMIT ?
    """, (n,))
    dates = [row[0] for row in cur.fetchall()]
    return sorted(dates)  # Вернуть в прямом порядке

def delete_readings_for_date(conn, date):
    """ Delete all readings for a specific date. """
    cur = conn.cursor()
    cur.execute("DELETE FROM readings WHERE date = ?", (date,))
    conn.commit()

def get_average_temp_by_silo(conn, silo, start_date=None, end_date=None):
    """ Calculate the average temperature per day for a silo. """
    cur = conn.cursor()
    query = """
        SELECT date, AVG(temperature)
        FROM readings
        WHERE silo = ? AND temperature != 71.2
    """
    params = [silo]
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    query += " GROUP BY date ORDER BY date"
    cur.execute(query, params)
    return cur.fetchall()

def get_average_temp_by_suspension(conn, silo, suspension, start_date=None, end_date=None):
    """ Calculate the average temperature per day for a suspension. """
    cur = conn.cursor()
    query = """
        SELECT date, AVG(temperature)
        FROM readings
        WHERE silo = ? AND suspension = ? AND temperature != 71.2
    """
    params = [silo, suspension]
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    query += " GROUP BY date ORDER BY date"
    cur.execute(query, params)
    return cur.fetchall()


def get_hot_spots_for_date(conn, silo, date, threshold):
    """Получить горячие точки за конкретную дату"""
    cur = conn.cursor()
    query = f"""
        SELECT silo, suspension, sensor, temperature, date
        FROM readings
        WHERE date = ? AND temperature > ? AND temperature != 71.2
        AND silo NOT IN ({OPERATIONAL_PLACEHOLDERS})
    """
    params = [date, threshold] + list(OPERATIONAL_SILOS)
    
    if silo and silo != "Все силосы":
        query += " AND silo = ?"
        params.append(silo)
    
    query += " ORDER BY temperature DESC"
    
    cur.execute(query, params)
    return cur.fetchall()


def get_temperature_changes(conn, silo, start_date, end_date, threshold):
    """
    Получить изменения температуры между периодами.
    Сравнивает среднюю температуру за первые 2 дня диапазона с последними 2 днями.
    Возвращает датчики, где изменение превышает порог.
    """
    from datetime import datetime, timedelta

    cur = conn.cursor()

    # Получить все показания для выбранного силоса и диапазона дат
    query = f"""
        SELECT silo, suspension, sensor, date, temperature
        FROM readings
        WHERE silo NOT IN ({OPERATIONAL_PLACEHOLDERS})
    """
    params = list(OPERATIONAL_SILOS)

    if silo and silo != "Все силосы":
        query += " AND silo = ?"
        params.append(silo)

    if start_date:
        query += " AND date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    query += " ORDER BY silo, suspension, sensor, date"

    cur.execute(query, params)
    all_readings = cur.fetchall()

    # Вычислить даты для сравнения (первые 2 дня vs последние 2 дня)
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
        end = datetime.strptime(end_date, '%Y-%m-%d') if end_date else None
        
        if start and end:
            days_diff = (end - start).days
            
            if days_diff <= 2:
                # Короткий диапазон: сравниваем первый день с последним
                first_period_dates = [start.strftime('%Y-%m-%d')]
                last_period_dates = [end.strftime('%Y-%m-%d')]
            else:
                # Длинные диапазон: первые 2 дня vs последние 2 дня
                first_period_end = start + timedelta(days=1)
                last_period_start = end - timedelta(days=1)
                
                first_period_dates = [
                    start.strftime('%Y-%m-%d'),
                    first_period_end.strftime('%Y-%m-%d')
                ]
                last_period_dates = [
                    last_period_start.strftime('%Y-%m-%d'),
                    end.strftime('%Y-%m-%d')
                ]
        else:
            first_period_dates = None
            last_period_dates = None
    except:
        first_period_dates = None
        last_period_dates = None

    # Группировка по датчикам
    sensor_readings = {}
    for row in all_readings:
        key = (row[0], row[1], row[2])  # silo, suspension, sensor
        if key not in sensor_readings:
            sensor_readings[key] = []
        sensor_readings[key].append((row[3], row[4]))  # date, temperature

    # Найти изменения
    changes = []
    for (silo_name, susp_num, sensor_num), readings in sensor_readings.items():
        if len(readings) < 2:
            continue

        # Сортировка по дате
        readings.sort(key=lambda x: x[0])

        if first_period_dates and last_period_dates:
            # Сравнение средних за первые 2 дня с последними 2 днями
            first_temps = [t for d, t in readings if d in first_period_dates]
            last_temps = [t for d, t in readings if d in last_period_dates]
            
            if not first_temps or not last_temps:
                # Если нет данных за периоды, используем первый и последний день
                first_temps = [readings[0][1]]
                last_temps = [readings[-1][1]]
                first_date = readings[0][0]
                last_date = readings[-1][0]
            else:
                first_date = first_period_dates[0]
                last_date = last_period_dates[-1]
            
            prev_temp = sum(first_temps) / len(first_temps)
            last_temp = sum(last_temps) / len(last_temps)
        else:
            # Старый метод: сравнение последней температуры с предыдущей
            if len(readings) < 2:
                continue
            last_date, last_temp = readings[-1]
            prev_date, prev_temp = readings[-2]
            first_date = prev_date

        delta = last_temp - prev_temp

        if abs(delta) >= threshold:
            changes.append({
                'silo': silo_name,
                'suspension': susp_num,
                'sensor': sensor_num,
                'last_date': last_date,
                'last_temp': last_temp,
                'prev_date': first_date,
                'prev_temp': prev_temp,
                'delta': delta
            })

    # Сортировка по абсолютному значению изменения
    changes.sort(key=lambda x: abs(x['delta']), reverse=True)
    
    return changes


def get_silo_list(conn, exclude_operational=True):
    """Получить список всех силосов (опционально исключая оперативные)"""
    cur = conn.cursor()
    if exclude_operational:
        cur.execute(f"""
            SELECT DISTINCT silo FROM readings
            WHERE silo NOT IN ({OPERATIONAL_PLACEHOLDERS})
            ORDER BY silo
        """, OPERATIONAL_SILOS)
    else:
        cur.execute("""
            SELECT DISTINCT silo FROM readings
            ORDER BY silo
        """)
    return [row[0] for row in cur.fetchall()]


def get_hot_spots_for_silo(conn, silo, start_date, end_date, threshold):
    """Получить список горячих точек для силоса за период"""
    cur = conn.cursor()
    query = """
        SELECT silo, suspension, sensor, temperature, date
        FROM readings
        WHERE silo = ? AND temperature > ? AND temperature != 71.2
    """
    params = [silo, threshold]

    if start_date:
        query += " AND date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    query += " ORDER BY temperature DESC"

    cur.execute(query, params)
    return cur.fetchall()


def get_hottest_sensors_by_silo(conn, start_date, end_date, threshold=15):
    """
    Получить самые горячие датчики по каждому силосу.
    Для каждого силоса возвращает датчик с максимальной температурой.
    
    Параметры:
    - conn: соединение с БД
    - start_date: начальная дата (YYYY-MM-DD)
    - end_date: конечная дата (YYYY-MM-DD)
    - threshold: порог температуры для горячих точек
    
    Возвращает:
    - list of dict: [{silo, suspension, sensor, max_temp, date}, ...]
    """
    cur = conn.cursor()

    query = f"""
        SELECT silo, suspension, sensor, temperature, date
        FROM readings
        WHERE temperature > ? AND temperature != 71.2
        AND silo NOT IN ({OPERATIONAL_PLACEHOLDERS})
    """
    params = [threshold] + list(OPERATIONAL_SILOS)
    
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    
    query += " ORDER BY silo, temperature DESC"
    
    cur.execute(query, params)
    all_hot_spots = cur.fetchall()
    
    # Для каждого силоса выбрать самый горячий датчик
    hottest_by_silo = {}
    for row in all_hot_spots:
        silo, suspension, sensor, temp, date = row
        if silo not in hottest_by_silo:
            hottest_by_silo[silo] = {
                'silo': silo,
                'suspension': suspension,
                'sensor': sensor,
                'max_temp': temp,
                'date': date
            }
    
    # Сортировка по температуре (убывание)
    result = sorted(hottest_by_silo.values(), key=lambda x: x['max_temp'], reverse=True)
    
    return result


def get_all_sensors_for_silo(conn, silo, start_date, end_date):
    """
    Получить все датчики для силоса с температурами.

    Параметры:
    - conn: соединение с БД
    - silo: название силоса
    - start_date: начальная дата
    - end_date: конечная дата

    Возвращает:
    - list of dict: [{suspension, sensor, temperature, date}, ...]
    """
    cur = conn.cursor()

    query = """
        SELECT suspension, sensor, temperature, date
        FROM readings
        WHERE silo = ?
    """
    params = [silo]

    if start_date:
        query += " AND date >= ?"
        params.append(start_date)

    if end_date:
        query += " AND date <= ?"
        params.append(end_date)

    query += " ORDER BY suspension, sensor, date"

    cur.execute(query, params)
    rows = cur.fetchall()

    result = []
    for row in rows:
        result.append({
            'suspension': row[0],
            'sensor': row[1],
            'temperature': row[2],
            'date': row[3]
        })

    return result


def get_all_silos_with_data():
    """
    Получить список всех силосов в базе данных.
    
    Возвращает:
    - list: отсортированный список названий силосов
    """
    conn = None
    try:
        from database import setup_database, get_silo_list
        conn = setup_database('temperatures.db')
        return get_silo_list(conn, exclude_operational=False)
    finally:
        if conn:
            conn.close()


def get_silo_data_for_date(conn, silo, date):
    """
    Получить все показания для силоса на конкретную дату.
    
    Параметры:
    - conn: соединение с БД
    - silo: название силоса
    - date: дата в формате YYYY-MM-DD
    
    Возвращает:
    - dict: {(suspension, sensor): temperature, ...}
    """
    cur = conn.cursor()
    
    query = """
        SELECT suspension, sensor, temperature
        FROM readings
        WHERE silo = ? AND date = ?
    """
    
    cur.execute(query, (silo, date))
    rows = cur.fetchall()
    
    result = {}
    for row in rows:
        result[(row[0], row[1])] = row[2]
    
    return result


def get_previous_date(conn, current_date):
    """
    Получить предыдущую дату с данными.
    
    Параметры:
    - conn: соединение с БД
    - current_date: текущая дата в формате YYYY-MM-DD
    
    Возвращает:
    - str: предыдущая дата в формате YYYY-MM-DD или None
    """
    cur = conn.cursor()
    
    query = """
        SELECT MAX(date)
        FROM readings
        WHERE date < ?
    """
    
    cur.execute(query, (current_date,))
    result = cur.fetchone()
    
    return result[0] if result else None


def get_temperature_delta_for_silo(conn, silo, date):
    """
    Получить изменение температуры за сутки для всех датчиков силоса.
    Сравнивает температуру на указанную дату с предыдущей датой.
    Исключает показания 71.2 (обрыв датчика).

    Параметры:
    - conn: соединение с БД
    - silo: название силоса
    - date: дата в формате YYYY-MM-DD

    Возвращает:
    - dict: {(suspension, sensor): {'current': temp, 'previous': temp, 'delta': delta}, ...}
    """
    # Получить текущие показания (исключая 71.2)
    current_data = get_silo_data_for_date(conn, silo, date)
    
    # Исключить 71.2 (обрыв датчика)
    current_data = {k: v for k, v in current_data.items() if v != 71.2}

    if not current_data:
        return {}

    # Получить предыдущую дату
    prev_date = get_previous_date(conn, date)

    if not prev_date:
        # Нет предыдущей даты - дельта равна 0
        return {key: {'current': val, 'previous': None, 'delta': 0.0}
                for key, val in current_data.items()}

    # Получить предыдущие показания (исключая 71.2)
    previous_data = get_silo_data_for_date(conn, silo, prev_date)
    previous_data = {k: v for k, v in previous_data.items() if v != 71.2}

    result = {}
    for key, current_temp in current_data.items():
        prev_temp = previous_data.get(key)
        if prev_temp is not None:
            delta = current_temp - prev_temp
        else:
            delta = 0.0

        result[key] = {
            'current': current_temp,
            'previous': prev_temp,
            'delta': delta,
            'prev_date': prev_date
        }
    
    return result


def get_all_silos_delta_for_date(conn, date):
    """
    Получить дельты температур за сутки для всех силосов на дату.
    
    Параметры:
    - conn: соединение с БД
    - date: дата в формате YYYY-MM-DD
    
    Возвращает:
    - dict: {silo: {(suspension, sensor): delta, ...}, ...}
    """
    result = {}
    
    # Получить все силоса
    silos = get_silo_list(conn, exclude_operational=False)
    
    for silo in silos:
        delta_data = get_temperature_delta_for_silo(conn, silo, date)
        if delta_data:
            # Преобразовать в формат {silo: {suspension: {sensor: delta}}}
            result[silo] = {}
            for (susp, sensor), data in delta_data.items():
                if susp not in result[silo]:
                    result[silo][susp] = {}
                result[silo][susp][sensor] = data
    
    return result


def get_date_range_for_slider(conn, start_date, end_date):
    """
    Получить список всех дат в диапазоне для шкалы времени.
    
    Параметры:
    - conn: соединение с БД
    - start_date: начальная дата
    - end_date: конечная дата
    
    Возвращает:
    - list: отсортированный список дат
    """
    cur = conn.cursor()
    
    query = """
        SELECT DISTINCT date
        FROM readings
        WHERE date >= ? AND date <= ?
        ORDER BY date
    """
    
    cur.execute(query, (start_date, end_date))
    return [row[0] for row in cur.fetchall()]


# === Функции для работы с комментариями ===

def get_comment(conn, comment_id):
    """
    Получить комментарий по id.
    """
    cur = conn.cursor()
    cur.execute("SELECT id, silo, date, comment, created_at FROM comments WHERE id = ?", (comment_id,))
    return cur.fetchone()


def save_comment(conn, silo, date, comment):
    """
    Добавить новый комментарий для силоса на дату (не заменяет старые).
    """
    cur = conn.cursor()
    if comment:
        cur.execute("""
            INSERT INTO comments (silo, date, comment)
            VALUES (?, ?, ?)
        """, (silo, date, comment))
        conn.commit()
        return cur.lastrowid
    return None


def delete_comment(conn, comment_id):
    """
    Удалить комментарий по id.
    """
    cur = conn.cursor()
    cur.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    conn.commit()


def delete_comments_for_silo_date(conn, silo, date):
    """
    Удалить все комментарии для силоса на дату.
    """
    cur = conn.cursor()
    cur.execute("DELETE FROM comments WHERE silo = ? AND date = ?", (silo, date))
    conn.commit()


def get_comments_for_silo(conn, silo):
    """
    Получить все комментарии для силоса.
    Возвращает: [(id, date, comment, created_at), ...]
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT id, date, comment, created_at
        FROM comments
        WHERE silo = ?
        ORDER BY date DESC, id DESC
    """, (silo,))
    return cur.fetchall()


def has_comment(conn, silo, date):
    """
    Проверить наличие комментария для силоса на дату.
    """
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM comments WHERE silo = ? AND date = ? LIMIT 1", (silo, date))
    return cur.fetchone() is not None


def has_any_comment(conn, silo):
    """
    Проверить наличие хотя бы одного комментария для силоса (в любой дате).
    """
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM comments WHERE silo = ? LIMIT 1", (silo,))
    return cur.fetchone() is not None


def get_hottest_sensor_for_date(conn, date, threshold=15):
    """
    Получить самый горячий датчик за конкретную дату (глобально, среди всех силосов).
    Для обратной совместимости.
    """
    cur = conn.cursor()
    query = f"""
        SELECT silo, suspension, sensor, temperature, date
        FROM readings
        WHERE date = ? AND temperature > ? AND temperature != 71.2
        AND silo NOT IN ({OPERATIONAL_PLACEHOLDERS})
        ORDER BY temperature DESC
        LIMIT 1
    """
    cur.execute(query, (date, threshold) + tuple(OPERATIONAL_SILOS))
    row = cur.fetchone()
    if row:
        return {
            'silo': row[0],
            'suspension': row[1],
            'sensor': row[2],
            'temperature': row[3],
            'date': row[4]
        }
    return None


def get_hottest_sensor_for_silo_date(conn, silo, date, threshold=15):
    """
    Получить самый горячий датчик для конкретного силоса на дату.

    Возвращает:
    - dict: {silo, suspension, sensor, temperature, date} или None
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT silo, suspension, sensor, temperature, date
        FROM readings
        WHERE silo = ? AND date = ? AND temperature > ? AND temperature != 71.2
        ORDER BY temperature DESC
        LIMIT 1
    """, (silo, date, threshold))
    row = cur.fetchone()
    if row:
        return {
            'silo': row[0],
            'suspension': row[1],
            'sensor': row[2],
            'temperature': row[3],
            'date': row[4]
        }
    return None


def get_all_silos_leaders_for_date(conn, date, threshold=15):
    """
    Получить лидеров (самые горячие датчики) для каждого силоса на дату.

    Возвращает:
    - dict: {silo: {silo, suspension, sensor, temperature}, ...}
    """
    cur = conn.cursor()
    cur.execute(f"""
        SELECT r.silo, r.suspension, r.sensor, r.temperature, r.date
        FROM readings r
        INNER JOIN (
            SELECT silo, MAX(temperature) as max_temp
            FROM readings
            WHERE date = ? AND temperature > ? AND temperature != 71.2
            AND silo NOT IN ({OPERATIONAL_PLACEHOLDERS})
            GROUP BY silo
        ) best ON r.silo = best.silo AND r.temperature = best.max_temp
        WHERE r.date = ?
        ORDER BY r.silo
    """, (date, threshold) + tuple(OPERATIONAL_SILOS) + (date,))
    result = {}
    for row in cur.fetchall():
        result[row[0]] = {
            'silo': row[0],
            'suspension': row[1],
            'sensor': row[2],
            'temperature': row[3]
        }
    return result


def get_previous_date_with_data(conn, date):
    """
    Получить предыдущую дату с данными.

    Параметры:
    - conn: соединение с БД
    - date: текущая дата в формате YYYY-MM-DD

    Возвращает:
    - str: предыдущая дата в формате YYYY-MM-DD или None
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT MAX(date)
        FROM readings
        WHERE date < ?
    """, (date,))
    result = cur.fetchone()
    return result[0] if result else None


def get_sensor_temperature_on_date(conn, silo, suspension, sensor, date):
    """
    Получить температуру конкретного датчика на указанную дату.

    Параметры:
    - conn: соединение с БД
    - silo: название силоса
    - suspension: номер подвески
    - sensor: номер датчика
    - date: дата в формате YYYY-MM-DD

    Возвращает:
    - float: температура или None
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT temperature
        FROM readings
        WHERE silo = ? AND suspension = ? AND sensor = ? AND date = ?
    """, (silo, suspension, sensor, date))
    result = cur.fetchone()
    return result[0] if result else None


def get_leader_change_info(conn, current_date, threshold=15):
    """
    Получить информацию о смене самого горячего датчика.
    Сравнивает самый горячий датчик за текущую дату с предыдущей.

    Параметры:
    - conn: соединение с БД
    - current_date: текущая дата в формате YYYY-MM-DD
    - threshold: порог температуры для горячих точек

    Возвращает:
    - dict: {
        'current': {silo, suspension, sensor, temperature},
        'previous': {silo, suspension, sensor, temperature},
        'changed': bool  # True если датчик изменился
      } или None если нет данных
    """
    # Получить текущий самый горячий датчик
    current_hottest = get_hottest_sensor_for_date(conn, current_date, threshold)
    if not current_hottest:
        return None

    # Получить предыдущую дату
    prev_date = get_previous_date_with_data(conn, current_date)
    if not prev_date:
        return {
            'current': current_hottest,
            'previous': None,
            'changed': False
        }

    # Получить предыдущий самый горячий датчик
    prev_hottest = get_hottest_sensor_for_date(conn, prev_date, threshold)

    # Проверить смену лидера
    changed = False
    if prev_hottest:
        changed = (
            current_hottest['silo'] != prev_hottest['silo'] or
            current_hottest['suspension'] != prev_hottest['suspension'] or
            current_hottest['sensor'] != prev_hottest['sensor']
        )

    return {
        'current': current_hottest,
        'previous': prev_hottest,
        'changed': changed,
        'prev_date': prev_date
    }


def save_leader_change_comment(conn, silo, date, current_leader, previous_leader):
    """
    Сохранить комментарий о смене лидера для конкретного силоса.
    """
    if not current_leader or not previous_leader:
        return

    comment = (
        f"🔄 СМЕНА ЛИДЕРА в {silo}:\n"
        f"Был: Подвеска {previous_leader['suspension']}, Датчик {previous_leader['sensor']} ({previous_leader['temperature']:.1f}°C)\n"
        f"Стал: Подвеска {current_leader['suspension']}, Датчик {current_leader['sensor']} ({current_leader['temperature']:.1f}°C)\n"
        f"Дельта: {current_leader['temperature'] - previous_leader['temperature']:+.1f}°C"
    )

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO comments (silo, date, comment)
        VALUES (?, ?, ?)
    """, (silo, date, comment))
    conn.commit()


def save_leader_to_history(conn, date, silo, leader, changed_from_prev=False):
    """
    Сохранить информацию о лидере конкретного силоса в историю.
    """
    if not leader:
        return

    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO leader_history (date, silo, suspension, sensor, temperature, changed_from_prev)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (date, silo, leader['suspension'], leader['sensor'], leader['temperature'], changed_from_prev))
    conn.commit()


def get_last_processed_leader_date(conn):
    """
    Получить последнюю дату, когда проверяли лидеров.
    """
    cur = conn.cursor()
    cur.execute("SELECT MAX(date) FROM leader_history")
    result = cur.fetchone()
    return result[0] if result else None


def get_leader_for_silo_date(conn, silo, date):
    """
    Получить лидера конкретного силоса за дату из истории.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT silo, suspension, sensor, temperature
        FROM leader_history
        WHERE date = ? AND silo = ?
    """, (date, silo))
    result = cur.fetchone()
    if result:
        return {
            'silo': result[0],
            'suspension': result[1],
            'sensor': result[2],
            'temperature': result[3]
        }
    return None


def get_leaders_for_all_silos_date(conn, date):
    """
    Получить всех лидеров (по каждому силосу) за дату из истории.

    Возвращает:
    - dict: {silo: {silo, suspension, sensor, temperature}, ...}
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT silo, suspension, sensor, temperature
        FROM leader_history
        WHERE date = ?
    """, (date,))
    result = {}
    for row in cur.fetchall():
        result[row[0]] = {
            'silo': row[0],
            'suspension': row[1],
            'sensor': row[2],
            'temperature': row[3]
        }
    return result


def get_previous_leader_for_silo(conn, silo, before_date):
    """
    Получить предыдущего лидера для силоса (до указанной даты).
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT silo, suspension, sensor, temperature
        FROM leader_history
        WHERE silo = ? AND date < ?
        ORDER BY date DESC
        LIMIT 1
    """, (silo, before_date))
    result = cur.fetchone()
    if result:
        return {
            'silo': result[0],
            'suspension': result[1],
            'sensor': result[2],
            'temperature': result[3]
        }
    return None


def check_leader_changes_for_period(conn, start_date, end_date, threshold=15):
    """
    Проверить смену лидера для КАЖДОГО СИЛОСА за период дат.
    Сохраняет историю и создаёт комментарии при смене лидера.

    Возвращает:
    - int: количество смен лидера (суммарно по всем силосам)
    """
    from datetime import datetime

    # Получить все даты в диапазоне
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT date FROM readings
        WHERE date >= ? AND date <= ?
        ORDER BY date
    """, (start_date, end_date))
    dates = [row[0] for row in cur.fetchall()]

    if not dates:
        return 0

    # Получить все силосы
    silos = get_silo_list(conn, exclude_operational=True)

    # Для каждого силоса найти предыдущего лидера из истории
    previous_leaders = {}
    for silo in silos:
        prev = get_previous_leader_for_silo(conn, silo, start_date)
        previous_leaders[silo] = prev

    changes_count = 0

    for date in dates:
        # Получить лидеров для каждого силоса на эту дату
        current_leaders = get_all_silos_leaders_for_date(conn, date, threshold)

        for silo in silos:
            current_leader = current_leaders.get(silo)
            previous_leader = previous_leaders.get(silo)

            if not current_leader:
                continue

            # Проверить смену лидера
            changed_from_prev = False
            if previous_leader:
                changed_from_prev = (
                    current_leader['suspension'] != previous_leader['suspension'] or
                    current_leader['sensor'] != previous_leader['sensor']
                )

            # Сохранить в историю
            save_leader_to_history(conn, date, silo, current_leader, changed_from_prev)

            # Если лидер сменился — создать комментарий
            if changed_from_prev and previous_leader:
                save_leader_change_comment(conn, silo, date, current_leader, previous_leader)
                changes_count += 1
                logging.info(f"Смена лидера в {silo} за {date}: подв.{previous_leader['suspension']}-дат.{previous_leader['sensor']} → подв.{current_leader['suspension']}-дат.{current_leader['sensor']}")

            previous_leaders[silo] = current_leader

    return changes_count


if __name__ == '__main__':
    db_path = 'temperatures.db'
    conn = setup_database(db_path)
    if conn:
        # You can add test calls here if you want
        conn.close()