# config.py
"""Модуль для сохранения настроек приложения"""
import json
import os

CONFIG_FILE = "app_config.json"

DEFAULT_CONFIG = {
    "temp_threshold": 15.0,
    "window_width": 1400,
    "window_height": 900,
    "start_date": None,
    "end_date": None,
    "active_tab": 0,  # 0 = Перегрев, 1 = Обрывы
    "splitter_sizes": [490, 910]  # Размеры сплиттера: [таблица, график]
}

def load_config():
    """Загрузить конфигурацию из файла"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                # Добавить значения по умолчанию для отсутствующих ключей
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                return config
        except Exception as e:
            print(f"Ошибка загрузки конфигурации: {e}")
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """Сохранить конфигурацию в файл"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Ошибка сохранения конфигурации: {e}")
        return False
