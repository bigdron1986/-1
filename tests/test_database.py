from database import (create_connection, create_table, create_user_settings_table,
                       insert_readings, get_readings, get_unique_silos,
                       get_sensor_history, get_date_range, check_date_exists,
                       get_user_setting, set_user_setting, get_all_user_settings,
                       get_available_dates, delete_readings_for_date,
                       get_suspensions_for_silo, OPERATIONAL_SILOS)


def test_create_connection_in_memory():
    conn = create_connection(":memory:")
    assert conn is not None
    conn.close()


def test_create_table(db_conn):
    # table already created by fixture; verify it exists
    cur = db_conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='readings'")
    assert cur.fetchone() is not None


def test_insert_and_read_readings(db_conn):
    readings = [
        {"silo": "3", "suspension": 1, "sensor": 1, "temperature": 22.5, "date": "2026-01-15"},
        {"silo": "3", "suspension": 1, "sensor": 2, "temperature": 18.0, "date": "2026-01-15"},
    ]
    insert_readings(db_conn, readings)
    rows = get_readings(db_conn, silo="3")
    assert len(rows) == 2


def test_insert_readings_replaces_duplicate(db_conn):
    r = {"silo": "3", "suspension": 1, "sensor": 1, "temperature": 10.0, "date": "2026-01-15"}
    insert_readings(db_conn, [r])
    r["temperature"] = 99.0
    insert_readings(db_conn, [r])
    rows = get_sensor_history(db_conn, "3", 1, 1)
    assert len(rows) == 1
    assert rows[0][1] == 99.0


def test_get_unique_silos_excludes_operational(db_conn):
    readings = [
        {"silo": s, "suspension": 1, "sensor": 1, "temperature": 20.0, "date": "2026-01-15"}
        for s in ["3", "4", "1а", "1б"]
    ]
    insert_readings(db_conn, readings)
    silos = get_unique_silos(db_conn)
    assert "3" in silos
    assert "4" in silos
    for ops in OPERATIONAL_SILOS:
        assert ops not in silos


def test_get_date_range(db_conn):
    readings = [
        {"silo": "3", "suspension": 1, "sensor": 1, "temperature": 20.0, "date": "2026-01-01"},
        {"silo": "3", "suspension": 1, "sensor": 2, "temperature": 21.0, "date": "2026-01-10"},
    ]
    insert_readings(db_conn, readings)
    min_date, max_date = get_date_range(db_conn)
    assert min_date == "2026-01-01"
    assert max_date == "2026-01-10"


def test_check_date_exists(db_conn):
    r = {"silo": "3", "suspension": 1, "sensor": 1, "temperature": 20.0, "date": "2026-02-01"}
    insert_readings(db_conn, [r])
    assert check_date_exists(db_conn, "2026-02-01") is True
    assert check_date_exists(db_conn, "2099-12-31") is False


def test_delete_readings_for_date(db_conn):
    r = {"silo": "3", "suspension": 1, "sensor": 1, "temperature": 20.0, "date": "2026-03-01"}
    insert_readings(db_conn, [r])
    assert check_date_exists(db_conn, "2026-03-01") is True
    delete_readings_for_date(db_conn, "2026-03-01")
    assert check_date_exists(db_conn, "2026-03-01") is False


def test_get_suspensions_for_silo(db_conn):
    readings = [
        {"silo": "5", "suspension": 1, "sensor": 1, "temperature": 20.0, "date": "2026-04-01"},
        {"silo": "5", "suspension": 3, "sensor": 1, "temperature": 21.0, "date": "2026-04-01"},
    ]
    insert_readings(db_conn, readings)
    susp = get_suspensions_for_silo(db_conn, "5")
    assert susp == [1, 3]


def test_get_available_dates(db_conn):
    readings = [
        {"silo": "3", "suspension": 1, "sensor": 1, "temperature": 20.0, "date": "2026-05-01"},
        {"silo": "4", "suspension": 1, "sensor": 1, "temperature": 21.0, "date": "2026-06-01"},
    ]
    insert_readings(db_conn, readings)
    dates = get_available_dates(db_conn)
    assert "2026-05-01" in dates
    assert "2026-06-01" in dates


def test_get_readings_with_filters(db_conn):
    readings = [
        {"silo": "3", "suspension": 1, "sensor": 1, "temperature": 10.0, "date": "2026-07-01"},
        {"silo": "4", "suspension": 1, "sensor": 1, "temperature": 20.0, "date": "2026-07-10"},
    ]
    insert_readings(db_conn, readings)
    rows = get_readings(db_conn, silo="3", start_date="2026-07-01", end_date="2026-07-05")
    assert len(rows) == 1
    assert rows[0][0] == "3"


def test_user_settings(db_conn):
    set_user_setting(db_conn, "theme", "dark")
    assert get_user_setting(db_conn, "theme") == "dark"
    assert get_user_setting(db_conn, "nonexistent", "default") == "default"


def test_get_all_user_settings(db_conn):
    set_user_setting(db_conn, "key1", "val1")
    set_user_setting(db_conn, "key2", "val2")
    all_settings = get_all_user_settings(db_conn)
    assert all_settings["key1"] == "val1"
    assert all_settings["key2"] == "val2"
