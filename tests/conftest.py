import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import tempfile
import json


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        orig_cwd = os.getcwd()
        os.chdir(d)
        yield d
        os.chdir(orig_cwd)


@pytest.fixture
def temp_config(temp_dir):
    data = {"temp_threshold": 20.0, "window_width": 800}
    path = os.path.join(temp_dir, "app_config.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


@pytest.fixture
def temp_env_file(temp_dir):
    path = os.path.join(temp_dir, ".env")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# test\nEMAIL_LOGIN=test@yandex.ru\nEMAIL_PASSWORD=secret123\n")
    return path


@pytest.fixture
def db_conn():
    import database
    conn = database.create_connection(":memory:")
    database.create_table(conn)
    database.create_user_settings_table(conn)
    yield conn
    conn.close()
