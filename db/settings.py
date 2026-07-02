def get_user_setting(conn, key, default=None):
    cur = conn.cursor()
    cur.execute("SELECT value FROM user_settings WHERE key = ?", (key,))
    result = cur.fetchone()
    return result[0] if result else default


def set_user_setting(conn, key, value):
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO user_settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()


def get_all_user_settings(conn):
    cur = conn.cursor()
    cur.execute("SELECT key, value FROM user_settings")
    return dict(cur.fetchall())
