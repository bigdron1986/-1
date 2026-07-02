# styles.py
"""
Стили для приложения Термометрия
Современный дизайн в темной теме
"""

STYLESHEET = """
/* === Общие стили === */
QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #1e1e2e;
}

/* === Группы и фреймы === */
QGroupBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 8px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
    font-size: 14px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 2px;
    padding: 0 8px;
    color: #89b4fa;
}

/* === Кнопки === */
QPushButton {
    background-color: #45475a;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    color: #cdd6f4;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #585b70;
}

QPushButton:pressed {
    background-color: #313244;
}

QPushButton:disabled {
    background-color: #45475a;
    color: #6c7086;
}

/* Кнопки быстрого выбора периода */
QPushButton#periodButton {
    background-color: #313244;
    border: 1px solid #45475a;
}

QPushButton#periodButton:hover {
    background-color: #45475a;
    border-color: #89b4fa;
}

QPushButton#periodButton:checked {
    background-color: #89b4fa;
    color: #1e1e2e;
    border-color: #89b4fa;
}

/* Кнопка загрузки */
QPushButton#loadButton {
    background-color: #a6e3a1;
    color: #1e1e2e;
    font-weight: bold;
}

QPushButton#loadButton:hover {
    background-color: #94e2d5;
}

/* Кнопка экспорта */
QPushButton#exportButton {
    background-color: #89b4fa;
    color: #1e1e2e;
}

QPushButton#exportButton:hover {
    background-color: #b4befe;
}

/* === Поля ввода === */
QLineEdit, QComboBox, QDateEdit, QDoubleSpinBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 10px;
    color: #cdd6f4;
    selection-background-color: #89b4fa;
}

QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QDoubleSpinBox:focus {
    border-color: #89b4fa;
}

QComboBox::drop-down {
    border: none;
    padding-right: 10px;
}

QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid #89b4fa;
    margin-right: 10px;
}

/* === Таблицы === */
QTableWidget {
    background-color: #313244;
    alternate-background-color: #45475a;
    border: 1px solid #45475a;
    border-radius: 8px;
    gridline-color: #585b70;
    selection-background-color: #45475a;
    selection-color: #cdd6f4;
}

QTableWidget::item {
    padding: 6px;
    border: none;
}

QTableWidget::item:selected {
    background-color: #585b70;
}

QHeaderView::section {
    background-color: #45475a;
    color: #89b4fa;
    padding: 8px;
    border: none;
    border-bottom: 2px solid #585b70;
    font-weight: bold;
    text-transform: uppercase;
    font-size: 11px;
}

/* === Scrollbar === */
QScrollBar:vertical {
    background-color: #1e1e2e;
    width: 12px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background-color: #45475a;
    border-radius: 6px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #585b70;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: #1e1e2e;
    height: 12px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background-color: #45475a;
    border-radius: 6px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #585b70;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* === Label === */
QLabel {
    color: #cdd6f4;
}

QLabel#statusLabel {
    color: #a6e3a1;
    font-size: 12px;
}

QLabel#deltaLabel {
    color: #f9e2af;
    font-weight: bold;
    font-size: 13px;
}

/* === ProgressBar === */
QProgressBar {
    background-color: #313244;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: #cdd6f4;
    height: 8px;
}

QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 4px;
}

/* === Tooltip === */
QToolTip {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 4px;
    padding: 4px 8px;
}

/* === QMessageBox === */
QMessageBox {
    background-color: #1e1e2e;
}

QMessageBox QLabel {
    color: #cdd6f4;
}

QMessageBox QPushButton {
    min-width: 80px;
}

/* === QFileDialog === */
QFileDialog {
    background-color: #1e1e2e;
}

/* === Разделители === */
Line {
    background-color: #45475a;
}

/* === ScrollArea === */
QScrollArea {
    background-color: #1e1e2e;
    border: none;
}

/* === CheckBox === */
QCheckBox {
    color: #cdd6f4;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid #45475a;
    background-color: #313244;
}

QCheckBox::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}

QCheckBox::indicator:hover {
    border-color: #89b4fa;
}

/* === RadioButton === */
QRadioButton {
    color: #cdd6f4;
    spacing: 8px;
}

QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border-radius: 9px;
    border: 2px solid #45475a;
    background-color: #313244;
}

QRadioButton::indicator:checked {
    background-color: #89b4fa;
    border-color: #89b4fa;
}

QRadioButton::indicator:hover {
    border-color: #89b4fa;
}

/* === SpinBox === */
QSpinBox, QDoubleSpinBox {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 10px;
    color: #cdd6f4;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #89b4fa;
}

QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {
    background-color: #45475a;
    border: none;
    width: 16px;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background-color: #585b70;
}

/* === TabWidget === */
QTabWidget::pane {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 8px;
}

QTabBar::tab {
    background-color: #45475a;
    color: #cdd6f4;
    padding: 8px 16px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QTabBar::tab:selected {
    background-color: #313244;
    color: #89b4fa;
}

QTabBar::tab:hover:!selected {
    background-color: #585b70;
}

/* === MenuBar === */
QMenuBar {
    background-color: #1e1e2e;
    color: #cdd6f4;
    padding: 4px;
}

QMenuBar::item:selected {
    background-color: #45475a;
    border-radius: 4px;
}

QMenu {
    background-color: #313244;
    border: 1px solid #45475a;
    border-radius: 8px;
}

QMenu::item:selected {
    background-color: #45475a;
}

QMenu::separator {
    height: 1px;
    background-color: #45475a;
    margin: 4px 8px;
}
"""

# Цветовая схема (Catppuccin Mocha)
COLORS = {
    'background': '#1e1e2e',
    'surface': '#313244',
    'overlay': '#45475a',
    'muted': '#585b70',
    'subtext': '#6c7086',
    'text': '#cdd6f4',
    'blue': '#89b4fa',
    'lavender': '#b4befe',
    'sapphire': '#74c7ec',
    'sky': '#89dceb',
    'teal': '#94e2d5',
    'green': '#a6e3a1',
    'yellow': '#f9e2af',
    'peach': '#fab387',
    'maroon': '#eba0ac',
    'red': '#f38ba8',
    'mauve': '#cba6f7',
    'pink': '#f5c2e7',
    'flamingo': '#f2cdcd',
    'rosewater': '#f5e0dc'
}

# Цвета для температурных режимов
TEMP_COLORS = {
    'normal': '#a6e3a1',      # Зеленый - норма
    'warning': '#f9e2af',     # Желтый - предупреждение
    'critical': '#f38ba8',    # Красный - критично
    'error': '#fab387'        # Оранжевый - ошибка датчика (71.2)
}
