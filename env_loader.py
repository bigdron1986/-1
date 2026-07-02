"""Загрузка .env файла рядом с exe или исходником"""
import os
import sys


def find_env_file():
    dirs = [
        os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else None,
        os.path.dirname(os.path.abspath(__file__)),
    ]
    for d in dirs:
        if d:
            env_path = os.path.join(d, '.env')
            if os.path.isfile(env_path):
                return env_path
    return None


def load_env_file():
    env_path = find_env_file()
    if not env_path:
        return {}

    result = {}
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' not in line:
                    continue
                key, _, val = line.partition('=')
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                result[key] = val
    except Exception:
        return {}

    return result


def get_env(key, default=''):
    vals = load_env_file()
    return vals.get(key, default)
