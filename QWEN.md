# Термометрия — Проект контекста

## Обзор проекта

**Термометрия** — это десктопное приложение на Python для автоматизированного сбора, хранения и визуализации данных термометрии в силосах с пшеницей. Приложение предназначено для контроля динамики изменений температуры и выявления критических точек (перегрева зерна).

### Основные возможности

- **Загрузка данных** из CSV-файлов формата `termo_ДД.ММ.ГГГГ.csv` через диалог выбора или drag-and-drop
- **Хранение исторических данных** в SQLite базе данных (`temperatures.db`)
- **Фильтрация данных** по силосу, подвеске, диапазону дат
- **Таблица "Горячие точки"** с цветовым выделением критических значений:
  - Температура > 15°C (настраиваемый порог) — красный цвет
  - Значение 71.2 (ошибка/обрыв датчика) — оранжевый цвет
- **График динамики температур** с возможностью просмотра трендов (+24ч, +3 дня)
- **Экспорт данных** в Excel (XLSX) и сохранение графиков как PNG/JPG

### Архитектура приложения

```
термометрия/
├── main.py           # Точка входа, GUI на PyQt6
├── data_parser.py    # Парсинг CSV-файлов термометрии
├── database.py       # Работа с SQLite (CRUD операции)
├── plotter.py        # Визуализация графиков (matplotlib)
├── requirements.txt  # Зависимости Python
├── temperatures.db   # SQLite база данных
└── termo_*.csv       # Исходные данные
```

## Технологии

- **Язык:** Python 3.13
- **GUI:** PyQt6
- **Парсинг:** pandas, openpyxl
- **Визуализация:** matplotlib
- **База данных:** SQLite + SQLAlchemy
- **Экспорт:** fpdf, Pillow
- **Упаковка:** PyInstaller (для создания .exe)

## Сборка и запуск

### Установка зависимостей

```bash
pip install -r requirements.txt
```

### Запуск приложения

```bash
python main.py
```

### Создание исполняемого файла (.exe)

```bash
pyinstaller --onefile --windowed main.py
```

Или для создания папки с зависимостями:

```bash
pyinstaller main.py --windowed
```

## Структура данных

### Формат входного CSV-файла

- **Кодировка:** windows-1251
- **Разделитель:** точка с запятой (`;`)
- **Десятичный разделитель:** запятая (`,`)

**Пример структуры:**
```
;Силос 3а ; Датчик 1 ; Датчик 2 ; ... ; Датчик 6 ; ; Макс ;05.03.2026
;Подвеска 1 ;-3,5;-3,1;...;-3,0; ;-2,4;
;Подвеска 2 ;-2,2;-1,8;...;-1,0; ;-1,0;
```

### Схема базы данных (SQLite)

**Таблица `readings`:**
| Поле | Тип | Описание |
|------|-----|----------|
| id | INTEGER | Первичный ключ |
| silo | TEXT | Название силоса (например, "3а") |
| suspension | INTEGER | Номер подвески (1-11) |
| sensor | INTEGER | Номер датчика (1-6) |
| temperature | REAL | Температура в °C |
| date | TEXT | Дата в формате YYYY-MM-DD |

**Уникальность:** `(silo, suspension, sensor, date)` — дубликаты заменяются

## Ключевые функции API

### data_parser.py

```python
parse_thermometry_file(file_path: str) -> tuple[str, list[dict]]
```
Возвращает дату отчета и список показаний датчиков.

### database.py

```python
setup_database(db_file: str) -> sqlite3.Connection
insert_readings(conn, readings: list[dict]) -> int
get_unique_silos(conn) -> list[str]
get_readings(conn, silo=None, start_date=None, end_date=None) -> list[tuple]
get_sensor_history(conn, silo, suspension, sensor) -> list[tuple]
get_suspensions_for_silo(conn, silo) -> list[int]
check_date_exists(conn, date: str) -> bool
delete_readings_for_date(conn, date: str) -> None
get_average_temp_by_silo(conn, silo, start_date, end_date) -> list[tuple]
get_average_temp_by_suspension(conn, silo, suspension, start_date, end_date) -> list[tuple]
```

### plotter.py

```python
class PlotWidget(QWidget):
    plot_data(data_series: dict[str, list[tuple[str, float]]]) -> None
    save_plot(file_path: str) -> None
```

## Особенности предметной области

- **Силос** — ёмкость для хранения зерна (идентификатор: "3а", "4б", "5в" и т.д.)
- **Подвеска** — вертикальный ряд датчиков в силосе (1-11)
- **Датчик** — отдельный сенсор температуры на подвеске (1-6)
- **71.2°C** — специальное значение, обозначающее ошибку/обрыв датчика
- **Порог тревоги** — 15°C (настраивается в интерфейсе)

## Практики разработки

- **Стиль кода:** PEP 8, type hints не используются
- **Обработка ошибок:** try-except с выводом в консоль
- **GUI паттерн:** императивный стиль с прямым управлением виджетами
- **Тесты:** отсутствуют (приложение разрабатывается как прототип)

## Расширение функционала

При добавлении новых функций учитывайте:

1. **Парсер:** поддержка новых форматов файлов должна обрабатываться в `data_parser.py`
2. **База данных:** миграции схемы выполняются вручную через `database.py`
3. **GUI:** новые виджеты добавляются в `initUI()` класса `ThermometryApp`
4. **Экспорт:** используйте pandas для XLSX, fpdf для PDF
