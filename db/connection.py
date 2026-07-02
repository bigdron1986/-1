import sqlite3
from sqlite3 import Error


def create_connection(db_file):
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        print(e)
    return conn


def create_table(conn):
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


def create_user_settings_table(conn):
    try:
        sql_create_settings_table = """ CREATE TABLE IF NOT EXISTS user_settings (
                                            key text PRIMARY KEY,
                                            value text NOT NULL
                                        ); """
        c = conn.cursor()
        c.execute(sql_create_settings_table)

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

        sql_create_comments_table = """ CREATE TABLE IF NOT EXISTS comments (
                                            id integer PRIMARY KEY AUTOINCREMENT,
                                            silo text NOT NULL,
                                            date text NOT NULL,
                                            comment text NOT NULL,
                                            created_at text DEFAULT CURRENT_TIMESTAMP
                                        ); """
        c.execute(sql_create_comments_table)

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

        c.execute("CREATE INDEX IF NOT EXISTS idx_readings_date ON readings(date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_readings_silo ON readings(silo)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_readings_silo_date ON readings(silo, date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_readings_silo_temp ON readings(silo, temperature)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_comments_silo_date ON comments(silo, date)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_leader_history_date ON leader_history(date)")

        conn.commit()
    except Error as e:
        print(e)


def setup_database(db_file):
    conn = create_connection(db_file)
    if conn is not None:
        create_table(conn)
        create_user_settings_table(conn)
        return conn
    else:
        print("Error! cannot create the database connection.")
        return None
