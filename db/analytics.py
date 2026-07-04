import logging
from db.common import OPERATIONAL_SILOS, OPERATIONAL_PLACEHOLDERS
from db.readings import (get_silo_data_for_date, get_previous_date)


def get_average_temp_by_silo(conn, silo, start_date=None, end_date=None):
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
    from datetime import datetime, timedelta
    cur = conn.cursor()

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

    try:
        start = datetime.strptime(start_date, '%Y-%m-%d') if start_date else None
        end = datetime.strptime(end_date, '%Y-%m-%d') if end_date else None

        if start and end:
            days_diff = (end - start).days
            if days_diff <= 2:
                first_period_dates = [start.strftime('%Y-%m-%d')]
                last_period_dates = [end.strftime('%Y-%m-%d')]
            else:
                first_period_end = start + timedelta(days=1)
                last_period_start = end - timedelta(days=1)
                first_period_dates = [start.strftime('%Y-%m-%d'), first_period_end.strftime('%Y-%m-%d')]
                last_period_dates = [last_period_start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')]
        else:
            first_period_dates = None
            last_period_dates = None
    except:
        first_period_dates = None
        last_period_dates = None

    sensor_readings = {}
    for row in all_readings:
        key = (row[0], row[1], row[2])
        if key not in sensor_readings:
            sensor_readings[key] = []
        sensor_readings[key].append((row[3], row[4]))

    changes = []
    for (silo_name, susp_num, sensor_num), readings in sensor_readings.items():
        if len(readings) < 2:
            continue
        readings.sort(key=lambda x: x[0])

        if first_period_dates and last_period_dates:
            first_temps = [t for d, t in readings if d in first_period_dates]
            last_temps = [t for d, t in readings if d in last_period_dates]
            if not first_temps or not last_temps:
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

    changes.sort(key=lambda x: abs(x['delta']), reverse=True)
    return changes


def get_silo_list(conn, exclude_operational=True):
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

    hottest_by_silo = {}
    for row in all_hot_spots:
        silo, suspension, sensor, temp, date = row
        if silo not in hottest_by_silo:
            hottest_by_silo[silo] = {
                'silo': silo, 'suspension': suspension,
                'sensor': sensor, 'max_temp': temp, 'date': date
            }

    result = sorted(hottest_by_silo.values(), key=lambda x: x['max_temp'], reverse=True)
    return result


def get_all_sensors_for_silo(conn, silo, start_date, end_date):
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
    return [
        {'suspension': r[0], 'sensor': r[1], 'temperature': r[2], 'date': r[3]}
        for r in rows
    ]


def get_all_silos_with_data():
    conn = None
    try:
        from db.connection import setup_database
        conn = setup_database('temperatures.db')
        return get_silo_list(conn, exclude_operational=False)
    finally:
        if conn:
            conn.close()


def get_temperature_delta_for_silo(conn, silo, date):
    current_data = get_silo_data_for_date(conn, silo, date)
    current_data = {k: v for k, v in current_data.items() if v != 71.2}

    if not current_data:
        return {}

    prev_date = get_previous_date(conn, date)
    if not prev_date:
        return {key: {'current': val, 'previous': None, 'delta': 0.0}
                for key, val in current_data.items()}

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
    result = {}
    silos = get_silo_list(conn, exclude_operational=False)
    for silo in silos:
        delta_data = get_temperature_delta_for_silo(conn, silo, date)
        if delta_data:
            result[silo] = {}
            for (susp, sensor), data in delta_data.items():
                if susp not in result[silo]:
                    result[silo][susp] = {}
                result[silo][susp][sensor] = data
    return result


def get_hottest_sensor_for_date(conn, date, threshold=15):
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
            'silo': row[0], 'suspension': row[1],
            'sensor': row[2], 'temperature': row[3], 'date': row[4]
        }
    return None


def get_hottest_sensor_for_silo_date(conn, silo, date, threshold=15):
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
            'silo': row[0], 'suspension': row[1],
            'sensor': row[2], 'temperature': row[3], 'date': row[4]
        }
    return None


def get_all_silos_leaders_for_date(conn, date, threshold=15):
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
            'silo': row[0], 'suspension': row[1],
            'sensor': row[2], 'temperature': row[3]
        }
    return result


def get_leader_change_info(conn, current_date, threshold=15):
    current_hottest = get_hottest_sensor_for_date(conn, current_date, threshold)
    if not current_hottest:
        return None

    prev_date = get_previous_date(conn, current_date)
    if not prev_date:
        return {'current': current_hottest, 'previous': None, 'changed': False}

    prev_hottest = get_hottest_sensor_for_date(conn, prev_date, threshold)
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
    if not leader:
        return
    cur = conn.cursor()
    cur.execute("""
        INSERT OR REPLACE INTO leader_history (date, silo, suspension, sensor, temperature, changed_from_prev)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (date, silo, leader['suspension'], leader['sensor'], leader['temperature'], changed_from_prev))
    conn.commit()


def get_last_processed_leader_date(conn):
    cur = conn.cursor()
    cur.execute("SELECT MAX(date) FROM leader_history")
    result = cur.fetchone()
    return result[0] if result else None


def get_leader_for_silo_date(conn, silo, date):
    cur = conn.cursor()
    cur.execute("""
        SELECT silo, suspension, sensor, temperature
        FROM leader_history
        WHERE date = ? AND silo = ?
    """, (date, silo))
    result = cur.fetchone()
    if result:
        return {
            'silo': result[0], 'suspension': result[1],
            'sensor': result[2], 'temperature': result[3]
        }
    return None


def get_leaders_for_all_silos_date(conn, date):
    cur = conn.cursor()
    cur.execute("""
        SELECT silo, suspension, sensor, temperature
        FROM leader_history
        WHERE date = ?
    """, (date,))
    result = {}
    for row in cur.fetchall():
        result[row[0]] = {
            'silo': row[0], 'suspension': row[1],
            'sensor': row[2], 'temperature': row[3]
        }
    return result


def get_previous_leader_for_silo(conn, silo, before_date):
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
            'silo': result[0], 'suspension': result[1],
            'sensor': result[2], 'temperature': result[3]
        }
    return None


def check_leader_changes_for_period(conn, start_date, end_date, threshold=15):
    from datetime import datetime
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT date FROM readings
        WHERE date >= ? AND date <= ?
        ORDER BY date
    """, (start_date, end_date))
    dates = [row[0] for row in cur.fetchall()]

    if not dates:
        return 0

    silos = get_silo_list(conn, exclude_operational=True)

    previous_leaders = {}
    for silo in silos:
        prev = get_previous_leader_for_silo(conn, silo, start_date)
        previous_leaders[silo] = prev

    changes_count = 0
    for date in dates:
        current_leaders = get_all_silos_leaders_for_date(conn, date, threshold)
        for silo in silos:
            current_leader = current_leaders.get(silo)
            previous_leader = previous_leaders.get(silo)
            if not current_leader:
                continue

            changed_from_prev = False
            if previous_leader:
                changed_from_prev = (
                    current_leader['suspension'] != previous_leader['suspension'] or
                    current_leader['sensor'] != previous_leader['sensor']
                )

            save_leader_to_history(conn, date, silo, current_leader, changed_from_prev)

            if changed_from_prev and previous_leader:
                save_leader_change_comment(conn, silo, date, current_leader, previous_leader)
                changes_count += 1
                logging.info(f"Смена лидера в {silo} за {date}: подв.{previous_leader['suspension']}-дат.{previous_leader['sensor']} → подв.{current_leader['suspension']}-дат.{current_leader['sensor']}")

            previous_leaders[silo] = current_leader

    return changes_count


def get_comment(conn, comment_id):
    cur = conn.cursor()
    cur.execute("SELECT id, silo, date, comment, created_at FROM comments WHERE id = ?", (comment_id,))
    return cur.fetchone()


def save_comment(conn, silo, date, comment):
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
    cur = conn.cursor()
    cur.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    conn.commit()


def delete_comments_for_silo_date(conn, silo, date):
    cur = conn.cursor()
    cur.execute("DELETE FROM comments WHERE silo = ? AND date = ?", (silo, date))
    conn.commit()


def get_comments_for_silo(conn, silo):
    cur = conn.cursor()
    cur.execute("""
        SELECT id, date, comment, created_at
        FROM comments
        WHERE silo = ?
        ORDER BY date DESC, id DESC
    """, (silo,))
    return cur.fetchall()


def has_comment(conn, silo, date):
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM comments WHERE silo = ? AND date = ? LIMIT 1", (silo, date))
    return cur.fetchone() is not None


def has_any_comment(conn, silo):
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM comments WHERE silo = ? LIMIT 1", (silo,))
    return cur.fetchone() is not None
