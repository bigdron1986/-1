import os
import tempfile
from env_loader import find_env_file, load_env_file, get_env


def test_find_env_file_returns_none_when_missing(temp_dir):
    assert find_env_file() is None


def test_find_env_file_finds_dotenv(temp_dir, temp_env_file):
    result = find_env_file()
    assert result is not None
    assert result.endswith(".env")


def test_load_env_file_parses_correctly(temp_dir, temp_env_file):
    vals = load_env_file()
    assert vals["EMAIL_LOGIN"] == "test@yandex.ru"
    assert vals["EMAIL_PASSWORD"] == "secret123"


def test_get_env_returns_value(temp_dir, temp_env_file):
    assert get_env("EMAIL_LOGIN") == "test@yandex.ru"


def test_get_env_returns_default_when_missing(temp_dir, temp_env_file):
    assert get_env("NONEXISTENT", "fallback") == "fallback"


def test_load_env_file_skips_comments_and_blanks(temp_dir, temp_env_file):
    vals = load_env_file()
    assert "test" not in vals
