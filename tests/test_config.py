import os
from config import load_config, save_config, DEFAULT_CONFIG


def test_default_config_when_no_file(temp_dir):
    cfg = load_config()
    assert cfg["temp_threshold"] == 15.0
    assert cfg["window_width"] == 1400


def test_save_and_load_config(temp_dir):
    path = os.path.join(temp_dir, "app_config.json")
    data = {"temp_threshold": 25.0, "window_width": 1920}
    save_config(data)
    assert os.path.isfile(path)

    loaded = load_config()
    assert loaded["temp_threshold"] == 25.0
    assert loaded["window_width"] == 1920


def test_load_config_merges_missing_keys(temp_dir):
    data = {"temp_threshold": 99.0}
    path = os.path.join(temp_dir, "app_config.json")
    with open(path, "w", encoding="utf-8") as f:
        import json
        json.dump(data, f)

    loaded = load_config()
    assert loaded["temp_threshold"] == 99.0
    assert loaded["window_width"] == DEFAULT_CONFIG["window_width"]


def test_save_config_creates_file(temp_dir):
    data = {"temp_threshold": 10.0}
    assert save_config(data) is True
    assert os.path.isfile(os.path.join(temp_dir, "app_config.json"))
