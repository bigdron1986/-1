from db.common import OPERATIONAL_SILOS, OPERATIONAL_PLACEHOLDERS


def get_readings(conn, silo=None, start_date=None, end_date=None):
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


def insert_readings(conn, readings):
    sql = ''' INSERT OR REPLACE INTO readings(silo, suspension, sensor, temperature, date)
              VALUES(?,?,?,?,?) '''
    cur = conn.cursor()
    data_to_insert = [(r['silo'], r['suspension'], r['sensor'], r['temperature'], r['date']) for r in readings]
    cur.executemany(sql, data_to_insert)
    conn.commit()
    return cur.lastrowid


def get_sensor_history(conn, silo, suspension, sensor):
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


def get_unique_silos(conn):
    cur = conn.cursor()
    cur.execute(f"""
        SELECT DISTINCT silo FROM readings
        WHERE silo NOT IN ({OPERATIONAL_PLACEHOLDERS})
        ORDER BY silo
    """, OPERATIONAL_SILOS)
    silos = [row[0] for row in cur.fetchall()]
    return silos


def get_suspensions_for_silo(conn, silo):
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT suspension FROM readings WHERE silo = ? ORDER BY suspension", (silo,))
    suspensions = [row[0] for row in cur.fetchall()]
    return suspensions


def get_date_range(conn):
    cur = conn.cursor()
    cur.execute(f"""
        SELECT MIN(date), MAX(date) FROM readings
        WHERE silo NOT IN ({OPERATIONAL_PLACEHOLDERS})
    """, OPERATIONAL_SILOS)
    result = cur.fetchone()
    return result[0], result[1]


def get_available_dates(conn):
    cur = conn.cursor()
    cur.execute(f"""
        SELECT DISTINCT date FROM readings
        WHERE silo NOT IN ({OPERATIONAL_PLACEHOLDERS})
        ORDER BY date
    """, OPERATIONAL_SILOS)
    return [row[0] for row in cur.fetchall()]


def check_date_exists(conn, date):
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM readings WHERE date = ? LIMIT 1", (date,))
    return cur.fetchone() is not None


def get_all_dates(conn):
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT date FROM readings ORDER BY date")
    return [row[0] for row in cur.fetchall()]


def get_last_n_dates(conn, n=2):
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT date FROM readings
        ORDER BY date DESC
        LIMIT ?
    """, (n,))
    dates = [row[0] for row in cur.fetchall()]
    return sorted(dates)


def delete_readings_for_date(conn, date):
    cur = conn.cursor()
    cur.execute("DELETE FROM readings WHERE date = ?", (date,))
    conn.commit()


def get_silo_data_for_date(conn, silo, date):
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
    cur = conn.cursor()
    cur.execute("""
        SELECT MAX(date)
        FROM readings
        WHERE date < ?
    """, (current_date,))
    result = cur.fetchone()
    return result[0] if result else None


def get_date_range_for_slider(conn, start_date, end_date):
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT date
        FROM readings
        WHERE date >= ? AND date <= ?
        ORDER BY date
    """, (start_date, end_date))
    return [row[0] for row in cur.fetchall()]


def get_sensor_temperature_on_date(conn, silo, suspension, sensor, date):
    cur = conn.cursor()
    cur.execute("""
        SELECT temperature
        FROM readings
        WHERE silo = ? AND suspension = ? AND sensor = ? AND date = ?
    """, (silo, suspension, sensor, date))
    result = cur.fetchone()
    return result[0] if result else None



