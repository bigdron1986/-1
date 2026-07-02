import sys
import os
import logging
import pandas as pd
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog,
                             QHBoxLayout, QComboBox, QDateEdit, QTableWidget, QTableWidgetItem,
                             QGroupBox, QFormLayout, QAbstractItemView, QDoubleSpinBox, QSpinBox,
                             QMessageBox, QGridLayout, QSpacerItem, QSizePolicy, QSplitter, QTabWidget,
                             QCheckBox, QScrollArea, QFrame, QToolBar, QDialog)
from PyQt6.QtCore import QDate, Qt, QMimeData
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent, QAction
from data_parser import parse_thermometry_file
from config import load_config, save_config
from database import (setup_database, insert_readings, get_unique_silos, get_readings,
                      get_sensor_history, get_sensor_history_with_dates, get_suspensions_for_silo,
                      check_date_exists, delete_readings_for_date, get_average_temp_by_silo,
                      get_average_temp_by_suspension, get_date_range, get_available_dates,
                      get_user_setting, set_user_setting, get_all_user_settings,
                      get_hot_spots_for_date, get_temperature_changes, get_silo_list,
                      get_hot_spots_for_silo, get_hottest_sensors_by_silo, get_all_sensors_for_silo,
                       get_all_silos_delta_for_date, get_date_range_for_slider, get_last_n_dates,
                       get_hottest_sensor_for_date, get_hottest_sensor_for_silo_date, get_all_silos_leaders_for_date, get_previous_date_with_data, get_sensor_temperature_on_date,
                       get_leader_change_info,
                       save_leader_to_history, get_last_processed_leader_date, check_leader_changes_for_period,
                       has_comment, has_any_comment, get_comment)
from weather import get_weather_data, format_weather_display
from plotter import PlotWidget, DEFAULT_PLOT_COLORS
from styles import STYLESHEET, TEMP_COLORS
from config import load_config, save_config
from dialogs import SiloHotspotsDialog, ExportDropdownButton
from email_dialogs import EmailSettingsDialog, EmailDownloadDialog
from silo_3d import create_silo_3d, get_silo_data_with_errors, create_silo_3d_with_highlight
from silo_2d_widget import SilosOverviewWidget
from timeline_slider import DateSliderWidget
from comment_dialog import SiloCommentDialog
try:
    from plotly_widget import PlotlyWidget
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


class AdvancedPlotWidget(PlotWidget):
    """Расширенный виджет графика с поддержкой зума и панели значений"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.zoom_level = 1.0
        self.selected_point_info = None
        
    def enable_zoom(self, zoom_in=True):
        """Увеличить/уменьшить масштаб"""
        if zoom_in:
            self.zoom_level = min(2.0, self.zoom_level * 1.2)
        else:
            self.zoom_level = max(0.5, self.zoom_level / 1.2)
        
        # Перерисовать с новым масштабом
        self.figure.set_size_inches(
            self.figure.get_figwidth() * (1.2 if zoom_in else 0.83),
            self.figure.get_figheight() * (1.2 if zoom_in else 0.83)
        )
        self.canvas.draw()
    
    def reset_zoom(self):
        """Сбросить масштаб"""
        self.zoom_level = 1.0
        self.figure.set_size_inches(5, 3)
        self.canvas.draw()


class ThermometryApp(QWidget):
    def __init__(self):
        super().__init__()
        self.db_conn = setup_database("temperatures.db")
        self.config = load_config()
        self.user_settings = get_all_user_settings(self.db_conn)
        
        # Настройка логирования
        log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f'app_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
        
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        logging.info(f"=== Запуск приложения ===")
        logging.info(f"Лог файл: {log_file}")
        
        self.setWindowTitle("🌡️ Термометрия — Контроль температуры в силосах")
        self.setGeometry(100, 100, self.config.get("window_width", 1400), self.config.get("window_height", 1000))
        self.setMinimumSize(1400, 900)  # Увеличена минимальная высота для шкалы дат
        self.setAcceptDrops(True)
        
        # Загрузка настроек из БД
        self.temp_threshold = float(self.user_settings.get('temp_threshold', '15.0'))
        self.change_threshold = float(self.user_settings.get('change_threshold', '3.0'))
        self.date_format_with_year = self.user_settings.get('date_format_with_year', 'false') == 'true'
        
        # Цвета из настроек
        self.color_hotspot = self.user_settings.get('color_hotspot', '#f38ba8')
        self.color_error = self.user_settings.get('color_error', '#fab387')
        self.color_normal = self.user_settings.get('color_normal', '#a6e3a1')
        self.color_warning = self.user_settings.get('color_warning', '#f9e2af')
        
        self.initUI()
        self.populate_silo_filter()
        self.update_date_range()
        
        # Не вызывать update_data_view() для вкладки "Самые горячие датчики"
        # Она обновляется отдельно при переключении на неё
        self.update_data_view()
        
        # Загрузить погодные данные при запуске
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(500, self.refresh_weather_data)
        
        # Проверить смену лидера за все даты (при запуске)
        QTimer.singleShot(1000, self.check_leader_changes)

        # Открыть в полноэкранном режиме
        self.showMaximized()

    def closeEvent(self, event):
        """Сохранение настроек при закрытии"""
        print("closeEvent: приложение закрывается")
        try:
            # Сохранение в config.json
            self.config["window_width"] = self.width()
            self.config["window_height"] = self.height()
            self.config["start_date"] = self.start_date_edit.date().toString("yyyy-MM-dd")
            self.config["end_date"] = self.end_date_edit.date().toString("yyyy-MM-dd")
            self.config["active_tab"] = self.main_tabs.currentIndex()
            self.config["splitter_sizes"] = self.main_splitter.sizes()
            save_config(self.config)

            # Сохранение в БД
            set_user_setting(self.db_conn, 'temp_threshold', str(self.temp_threshold_spinbox.value()))
            set_user_setting(self.db_conn, 'change_threshold', str(self.change_threshold_spinbox.value()))
            set_user_setting(self.db_conn, 'date_format_with_year', 'true' if self.show_year_check.isChecked() else 'false')
            # graph_start_date и graph_end_date уже строки
            if self.graph_start_date:
                set_user_setting(self.db_conn, 'graph_start_date', self.graph_start_date)
            if self.graph_end_date:
                set_user_setting(self.db_conn, 'graph_end_date', self.graph_end_date)
            set_user_setting(self.db_conn, 'color_hotspot', self.color_hotspot)
            set_user_setting(self.db_conn, 'color_error', self.color_error)
            set_user_setting(self.db_conn, 'color_normal', self.color_normal)
            set_user_setting(self.db_conn, 'color_warning', self.color_warning)

            if self.db_conn:
                self.db_conn.close()
            event.accept()
            print("closeEvent: успешно завершено")
        except Exception as e:
            print(f"closeEvent: ошибка {e}")
            import traceback
            traceback.print_exc()
            event.ignore()  # Не закрывать при ошибке

    def handle_export(self, export_type):
        """Обработка экспорта из выпадающего меню"""
        if export_type == 'graph':
            self.save_graph_dialog()
        elif export_type == 'hotspots':
            self.export_table_dialog(self.hot_spots_table, "hot_spots")
        elif export_type == 'breaks':
            self.export_table_dialog(self.breaks_table, "breaks")
        elif export_type == 'changes':
            self.export_table_dialog(self.changes_table, "changes")

    def on_tab_changed(self, index):
        """Переключение вкладки - обновление состояния"""
        print(f"on_tab_changed: индекс {index}")

        # Синхронизировать с combo
        if hasattr(self, 'tabs_combo'):
            self.tabs_combo.blockSignals(True)
            self.tabs_combo.setCurrentIndex(index)
            self.tabs_combo.blockSignals(False)

        # Скрыть/показать фильтры данных для вкладки "Самые горячие датчики" (индекс 5)
        if hasattr(self, 'filter_group'):
            if index == 5:
                self.filter_group.setVisible(False)
            else:
                self.filter_group.setVisible(True)

        # Если вкладка "Самые горячие датчики" (индекс 5), загрузить данные
        if index == 5:
            print("Переключение на вкладку 'Самые горячие датчики'")
            logging.info("Переключение на вкладку 'Самые горячие датчики'")
            # Сразу очистить status_label
            self.status_label.setText("")
            logging.debug(f"status_label очищен: '{self.status_label.text()}'")
            # Небольшая задержка чтобы виджет успел инициализироваться
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(100, self.update_hottest_sensors_view)

    def on_tabs_combo_changed(self, index):
        """Переключение вкладки через combo"""
        if hasattr(self, 'main_tabs'):
            self.main_tabs.setCurrentIndex(index)

    def initUI(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # === Верхняя панель: заголовок + экспорт + загрузка + вкладки ===
        top_bar = QHBoxLayout()
        top_bar.setSpacing(15)

        # Заголовок
        title_label = QLabel("🌡️ Термометрия силосов")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #89b4fa; padding: 8px;")
        top_bar.addWidget(title_label)

        top_bar.addStretch()

        # Выпадающий список вкладок
        self.tabs_combo = QComboBox()
        self.tabs_combo.addItems([
            "🔥 Горячие точки",
            "📈 Графики по силосам",
            "📊 Мониторинг изменений",
            "⚠️ Обрывы",
            "🏭 3D Модель",
            "🔥 Самые горячие датчики"
        ])
        self.tabs_combo.setMaximumWidth(250)
        self.tabs_combo.currentIndexChanged.connect(self.on_tabs_combo_changed)
        self.tabs_combo.setStyleSheet("""
            QComboBox {
                background-color: #89b4fa;
                color: #1e1e2e;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QComboBox::drop-down {
                border: none;
                padding-right: 10px;
            }
            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
            }
        """)
        top_bar.addWidget(self.tabs_combo)

        # Кнопка экспорта с выпадающим меню
        self.export_button = ExportDropdownButton(on_export_callback=self.handle_export)
        top_bar.addWidget(self.export_button)

        # Кнопка почты с выпадающим меню
        self.email_button = QPushButton("📧 Почта ▼")
        self.email_button.setStyleSheet("""
            QPushButton {
                background-color: #f38ba8;
                color: #1e1e2e;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #f5c2e7;
            }
        """)
        self.email_button.setMinimumHeight(32)
        self.email_button.clicked.connect(self.show_email_menu)
        top_bar.addWidget(self.email_button)

        # Кнопка загрузки
        self.load_button = QPushButton("📂 Загрузить отчеты")
        self.load_button.setObjectName("loadButton")
        self.load_button.setMinimumHeight(32)
        self.load_button.clicked.connect(self.load_report_dialog)
        top_bar.addWidget(self.load_button)

        main_layout.addLayout(top_bar)

        # === Панель фильтров (общая для всех вкладок) ===
        self.filter_group = QGroupBox("📊 Фильтры данных")
        filter_layout = QVBoxLayout()
        filter_layout.setSpacing(8)

        # Первая строка фильтров
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(10)

        self.silo_combo = QComboBox()
        self.silo_combo.setMinimumWidth(180)
        self.silo_combo.currentIndexChanged.connect(self.populate_suspension_filter)

        self.suspension_combo = QComboBox()
        self.suspension_combo.setMinimumWidth(140)

        self.plot_type_combo = QComboBox()
        self.plot_type_combo.addItems(["По датчикам", "Средняя температура"])
        self.plot_type_combo.setMinimumWidth(160)

        self.temp_threshold_spinbox = QDoubleSpinBox()
        self.temp_threshold_spinbox.setValue(self.temp_threshold)
        self.temp_threshold_spinbox.setSuffix(" °C")
        self.temp_threshold_spinbox.setRange(0, 100)
        self.temp_threshold_spinbox.setMinimumWidth(90)
        self.temp_threshold_spinbox.valueChanged.connect(self.on_threshold_changed)

        row1_layout.addWidget(QLabel("Силос:"))
        row1_layout.addWidget(self.silo_combo)
        row1_layout.addWidget(QLabel("Подвеска:"))
        row1_layout.addWidget(self.suspension_combo)
        row1_layout.addWidget(QLabel("Тип графика:"))
        row1_layout.addWidget(self.plot_type_combo)
        row1_layout.addWidget(QLabel("Порог t°:"))
        row1_layout.addWidget(self.temp_threshold_spinbox)
        row1_layout.addStretch()

        # Вторая строка фильтров
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(10)

        self.start_date_edit = QDateEdit(calendarPopup=True)
        self.start_date_edit.setDate(QDate.currentDate().addMonths(-1))
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setMinimumWidth(120)

        self.end_date_edit = QDateEdit(calendarPopup=True)
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setMinimumWidth(120)

        # Загрузить сохранённые даты
        if self.config.get("start_date"):
            self.start_date_edit.setDate(QDate.fromString(self.config["start_date"], "yyyy-MM-dd"))
        if self.config.get("end_date"):
            self.end_date_edit.setDate(QDate.fromString(self.config["end_date"], "yyyy-MM-dd"))

        self.apply_button = QPushButton("✅ Применить фильтры")
        self.apply_button.setMinimumWidth(160)
        self.apply_button.setStyleSheet("font-weight: bold; background-color: #a6e3a1; color: #1e1e2e;")
        self.apply_button.clicked.connect(self.update_data_view)

        row2_layout.addWidget(QLabel("С:"))
        row2_layout.addWidget(self.start_date_edit)
        row2_layout.addWidget(QLabel("По:"))
        row2_layout.addWidget(self.end_date_edit)
        row2_layout.addWidget(QLabel("Период:"))

        # Label с диапазоном доступных дат
        self.date_range_label = QLabel("📅 Данные: —")
        self.date_range_label.setStyleSheet("font-size: 11px; color: #6c7086; padding: 4px;")
        row2_layout.addWidget(self.date_range_label)

        # Кнопки быстрого выбора периода
        period_layout = QHBoxLayout()
        period_layout.setSpacing(6)
        self.period_buttons = []
        periods = [
            ("1 день", 1),
            ("3 дня", 3),
            ("Неделя", 7),
            ("Месяц", 30),
            ("Всё время", 0)
        ]
        for text, days in periods:
            btn = QPushButton(text)
            btn.setObjectName("periodButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, d=days: self.set_period(d))
            period_layout.addWidget(btn)
            self.period_buttons.append(btn)

        row2_layout.addLayout(period_layout)
        row2_layout.addStretch()
        row2_layout.addWidget(self.apply_button)

        filter_layout.addLayout(row1_layout)
        filter_layout.addLayout(row2_layout)
        self.filter_group.setLayout(filter_layout)
        main_layout.addWidget(self.filter_group)

        # === Статус бар ===
        self.status_label = QLabel("✅ Готово")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setStyleSheet("font-size: 12px; padding: 4px; color: #a6e3a1;")
        main_layout.addWidget(self.status_label)

        # === Основные вкладки (скрытые) ===
        self.main_tabs = QTabWidget()

        # Вкладка 1: Горячие точки (основная)
        self.main_tabs.addTab(self.create_hotspots_tab(), "🔥 Горячие точки")

        # Вкладка 2: Графики по силосам
        self.main_tabs.addTab(self.create_silo_graphs_tab(), "📈 Графики по силосам")

        # Вкладка 3: Мониторинг изменений
        self.main_tabs.addTab(self.create_monitoring_tab(), "📊 Мониторинг изменений")

        # Вкладка 4: Обрывы датчиков
        self.main_tabs.addTab(self.create_breaks_tab(), "⚠️ Обрывы")

        # Вкладка 5: 3D Модель
        self.main_tabs.addTab(self.create_3d_model_tab(), "🏭 3D Модель")

        # Вкладка 6: Самые горячие датчики
        self.main_tabs.addTab(self.create_hottest_sensors_tab(), "🔥 Самые горячие датчики")

        self.main_tabs.currentChanged.connect(self.on_tab_changed)
        # Скрыть только заголовок вкладок, содержимое оставить видимым
        self.main_tabs.tabBar().setVisible(False)
        main_layout.addWidget(self.main_tabs, 1)  # 1 = stretch factor

        # Восстановить активную вкладку
        if self.config.get("active_tab"):
            self.main_tabs.setCurrentIndex(self.config["active_tab"])

        # Применить таблицу стилей
        self.setStyleSheet(STYLESHEET)
        self.setLayout(main_layout)

    def create_hotspots_tab(self):
        """Создать вкладку горячих точек"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Левая панель - Таблица
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setSpacing(0)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Настройки отображения даты
        settings_layout = QHBoxLayout()
        self.show_year_check = QCheckBox("Показывать год в дате")
        self.show_year_check.setChecked(self.date_format_with_year)
        self.show_year_check.stateChanged.connect(self.update_data_view)
        settings_layout.addWidget(self.show_year_check)
        
        # Настройка цветов
        colors_layout = QHBoxLayout()
        colors_layout.addWidget(QLabel("🎨 Цвет перегрева:"))
        self.hotspot_color_btn = QPushButton()
        self.hotspot_color_btn.setMaximumWidth(40)
        self.hotspot_color_btn.setStyleSheet(f"background-color: {self.color_hotspot};")
        self.hotspot_color_btn.clicked.connect(lambda: self.choose_color('hotspot'))
        colors_layout.addWidget(self.hotspot_color_btn)
        
        colors_layout.addWidget(QLabel("Цвет ошибки:"))
        self.error_color_btn = QPushButton()
        self.error_color_btn.setMaximumWidth(40)
        self.error_color_btn.setStyleSheet(f"background-color: {self.color_error};")
        self.error_color_btn.clicked.connect(lambda: self.choose_color('error'))
        colors_layout.addWidget(self.error_color_btn)
        
        settings_layout.addLayout(colors_layout)
        settings_layout.addStretch()
        
        left_layout.addLayout(settings_layout)
        
        self.hot_spots_label = QLabel("🔥 Горячих точек: 0")
        self.hot_spots_label.setStyleSheet("font-size: 12px; color: #f9e2af; padding: 4px; background-color: #313244;")
        left_layout.addWidget(self.hot_spots_label)

        # Метка самого горячего датчика с информацией о смене лидера
        self.hotspot_leader_label = QLabel("")
        self.hotspot_leader_label.setStyleSheet("font-size: 11px; color: #f38ba8; padding: 4px; background-color: #313244;")
        self.hotspot_leader_label.setWordWrap(True)
        left_layout.addWidget(self.hotspot_leader_label)

        self.hot_spots_table = QTableWidget()
        self.hot_spots_table.setColumnCount(5)
        self.hot_spots_table.setHorizontalHeaderLabels(["Силос", "Подвеска", "Датчик", "Температура", "Дата"])
        self.hot_spots_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.hot_spots_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.hot_spots_table.cellClicked.connect(self.on_hotspot_clicked)
        self.hot_spots_table.setAlternatingRowColors(True)
        self.hot_spots_table.horizontalHeader().setStretchLastSection(True)
        left_layout.addWidget(self.hot_spots_table)
        
        left_widget.setLayout(left_layout)
        
        # Правая панель - График
        graph_group = QGroupBox("📈 График динамики температур")
        graph_layout = QVBoxLayout()
        graph_layout.setSpacing(5)
        
        # Панель выбора цветов графика
        colors_panel = QHBoxLayout()
        colors_panel.setSpacing(5)
        
        colors_panel.addWidget(QLabel("🎨 Цвета:"))
        
        self.bg_color_btn = QPushButton("Фон")
        self.bg_color_btn.setMaximumWidth(50)
        self.bg_color_btn.setStyleSheet("background-color: #1e1e2e;")
        self.bg_color_btn.clicked.connect(lambda: self.change_graphic_color('background'))
        colors_panel.addWidget(self.bg_color_btn)

        self.grid_color_btn = QPushButton("Сетка")
        self.grid_color_btn.setMaximumWidth(50)
        self.grid_color_btn.setStyleSheet("background-color: #45475a;")
        self.grid_color_btn.clicked.connect(lambda: self.change_graphic_color('grid'))
        colors_panel.addWidget(self.grid_color_btn)

        self.axes_color_btn = QPushButton("Оси")
        self.axes_color_btn.setMaximumWidth(50)
        self.axes_color_btn.setStyleSheet("background-color: #313244;")
        self.axes_color_btn.clicked.connect(lambda: self.change_graphic_color('axes'))
        colors_panel.addWidget(self.axes_color_btn)
        
        colors_panel.addStretch()
        
        self.reset_colors_button = QPushButton("🔄 Сброс")
        self.reset_colors_button.setObjectName("periodButton")
        self.reset_colors_button.setMaximumWidth(100)
        self.reset_colors_button.clicked.connect(self.reset_plot_colors)
        colors_panel.addWidget(self.reset_colors_button)
        
        graph_layout.addLayout(colors_panel)

        # Панель выбора цветов линий
        colors_lines_panel = QHBoxLayout()
        colors_lines_panel.setSpacing(3)
        
        self.color_lines_label = QLabel("Линии:")
        self.color_lines_label.setStyleSheet("font-size: 11px; color: #6c7086;")
        colors_lines_panel.addWidget(self.color_lines_label)
        
        self.color_buttons_layout = QHBoxLayout()
        self.color_buttons_layout.setSpacing(3)
        colors_lines_panel.addLayout(self.color_buttons_layout)
        colors_lines_panel.addStretch()
        
        graph_layout.addLayout(colors_lines_panel)

        self.plot_widget = AdvancedPlotWidget()
        self.delta_label = QLabel("ℹ️ Кликните на ячейку в таблице для просмотра тренда")
        self.delta_label.setObjectName("deltaLabel")
        self.delta_label.setStyleSheet("font-size: 13px; padding: 6px; color: #f9e2af;")
        
        graph_layout.addWidget(self.delta_label)
        graph_layout.addWidget(self.plot_widget)
        graph_group.setLayout(graph_layout)
        
        # Сплиттер
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setObjectName("mainSplitter")
        self.main_splitter.addWidget(left_widget)
        self.main_splitter.addWidget(graph_group)
        self.main_splitter.setSizes([490, 910])
        self.main_splitter.setHandleWidth(6)
        self.main_splitter.setStyleSheet("QSplitter::handle { background-color: #45475a; border-radius: 2px; }")
        
        layout.addWidget(self.main_splitter)
        widget.setLayout(layout)
        
        # Восстановить размеры сплиттера
        if self.config.get("splitter_sizes"):
            self.main_splitter.setSizes(self.config["splitter_sizes"])
        
        return widget

    def create_silo_graphs_tab(self):
        """Создать вкладку графиков по нескольким силосам - оптимизированная версия"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

        # Кнопка выбора данных
        select_btn = QPushButton("📊 Выбрать силос и горячие точки для графика")
        select_btn.setStyleSheet("""
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                font-weight: bold;
                font-size: 13px;
                padding: 10px 20px;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #b4befe;
            }
        """)
        select_btn.clicked.connect(self.show_silo_select_dialog)
        layout.addWidget(select_btn)

        # График - занимает всё доступное место
        self.silo_graph_widget = AdvancedPlotWidget()
        self.silo_graph_widget.on_point_selected = self.on_silo_graph_point_selected
        layout.addWidget(self.silo_graph_widget, 1)  # stretch = 1

        # Панель: Информация о выбранном
        info_layout = QHBoxLayout()

        self.silo_graph_info = QLabel("Данные не выбраны. Нажмите кнопку выше для выбора.")
        self.silo_graph_info.setStyleSheet("font-size: 11px; color: #6c7086; padding: 4px;")
        info_layout.addWidget(self.silo_graph_info, 1)

        layout.addLayout(info_layout)

        # Панель значений в точке
        self.point_info_group = QGroupBox("📍 Значения в точке")
        point_info_layout = QVBoxLayout()
        point_info_layout.setSpacing(8)

        # Верхняя строка: дата + навигация
        date_row_layout = QHBoxLayout()
        
        # Кнопка влево
        self.prev_date_btn = QPushButton("◀")
        self.prev_date_btn.setMaximumWidth(30)
        self.prev_date_btn.setStyleSheet("font-size: 12px; font-weight: bold; padding: 4px;")
        self.prev_date_btn.clicked.connect(self.navigate_to_prev_date)
        self.prev_date_btn.setEnabled(False)  # Пока не выбрано
        date_row_layout.addWidget(self.prev_date_btn)
        
        self.point_date_label = QLabel("📍 Дата: —")
        self.point_date_label.setStyleSheet("font-size: 12px; color: #cdd6f4; font-weight: bold;")
        self.point_date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_row_layout.addWidget(self.point_date_label, 1)  # stretch = 1
        
        # Кнопка вправо
        self.next_date_btn = QPushButton("▶")
        self.next_date_btn.setMaximumWidth(30)
        self.next_date_btn.setStyleSheet("font-size: 12px; font-weight: bold; padding: 4px;")
        self.next_date_btn.clicked.connect(self.navigate_to_next_date)
        self.next_date_btn.setEnabled(False)  # Пока не выбрано
        date_row_layout.addWidget(self.next_date_btn)
        
        date_row_layout.addStretch()
        point_info_layout.addLayout(date_row_layout)

        # Контейнер для значений с прокруткой и кнопками
        scroll_controls_layout = QHBoxLayout()
        scroll_controls_layout.setSpacing(4)
        
        # Кнопка вверх
        self.scroll_up_btn = QPushButton("▲")
        self.scroll_up_btn.setMaximumWidth(30)
        self.scroll_up_btn.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px;")
        self.scroll_up_btn.clicked.connect(self.scroll_values_up)
        scroll_controls_layout.addWidget(self.scroll_up_btn)
        
        # Scroll area
        self.point_values_scroll = QScrollArea()
        self.point_values_scroll.setWidgetResizable(True)
        self.point_values_scroll.setMaximumHeight(150)
        self.point_values_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.point_values_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.point_values_content = QWidget()
        self.point_values_layout = QVBoxLayout()
        self.point_values_layout.setSpacing(4)
        self.point_values_layout.setContentsMargins(5, 5, 5, 5)
        self.point_values_content.setLayout(self.point_values_layout)
        self.point_values_scroll.setWidget(self.point_values_content)
        scroll_controls_layout.addWidget(self.point_values_scroll, 1)  # stretch = 1
        
        # Кнопка вниз
        self.scroll_down_btn = QPushButton("▼")
        self.scroll_down_btn.setMaximumWidth(30)
        self.scroll_down_btn.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px;")
        self.scroll_down_btn.clicked.connect(self.scroll_values_down)
        scroll_controls_layout.addWidget(self.scroll_down_btn)
        
        point_info_layout.addLayout(scroll_controls_layout)

        # Настройка количества значений в строке
        values_per_row_layout = QHBoxLayout()
        values_per_row_layout.addWidget(QLabel("Значений в строке:"))
        
        self.values_per_row_combo = QComboBox()
        self.values_per_row_combo.addItems(["3", "6", "9"])
        self.values_per_row_combo.setCurrentText("6")  # По умолчанию 6
        self.values_per_row_combo.setMaximumWidth(60)
        self.values_per_row_combo.currentTextChanged.connect(self.update_values_display)
        values_per_row_layout.addWidget(self.values_per_row_combo)
        
        values_per_row_layout.addStretch()
        point_info_layout.addLayout(values_per_row_layout)

        # Подсказка
        hint_label = QLabel("💡 Кликните на точку графика для просмотра значений")
        hint_label.setStyleSheet("font-size: 11px; color: #6c7086;")
        point_info_layout.addWidget(hint_label)

        self.point_info_group.setLayout(point_info_layout)
        layout.addWidget(self.point_info_group)

        # Переменные для хранения выбранных данных
        self.selected_silo = None
        self.selected_points = []
        self.graph_start_date = None
        self.graph_end_date = None

        widget.setLayout(layout)
        return widget

    def show_silo_select_dialog(self):
        """Показать диалог выбора силоса и горячих точек"""
        try:
            print(f"Открытие диалога. last_silo={self.selected_silo}, last_points={self.selected_points}")
            
            dialog = SiloHotspotsDialog(
                self.db_conn,
                self,
                self.temp_threshold_spinbox.value(),
                last_silo=self.selected_silo,
                last_points=self.selected_points
            )

            # Установить текущие даты из главного фильтра
            dialog.start_date.setDate(self.start_date_edit.date())
            dialog.end_date.setDate(self.end_date_edit.date())

            print("Выполнение диалога...")
            result = dialog.exec()
            print(f"Результат диалога: {result}")

            if result == QDialog.DialogCode.Accepted:
                data = dialog.get_data()
                print(f"Данные из диалога: {data}")
                self.selected_silo = data['silo']
                self.selected_points = data['points']
                self.graph_start_date = data['start_date']
                self.graph_end_date = data['end_date']

                # Обновить информацию
                self.silo_graph_info.setText(
                    f"✅ Силос: {self.selected_silo} | Точек: {len(self.selected_points)} | "
                    f"Период: {self.graph_start_date} — {self.graph_end_date}"
                )

                # Построить график
                self.build_multi_silo_graph()
            else:
                print("Диалог отменен")
        except Exception as e:
            print(f"Ошибка в show_silo_select_dialog: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка: {e}")

    def create_3d_model_tab(self):
        """Создать вкладку 3D модели силоса"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Панель управления
        control_group = QGroupBox("🎛️ Параметры 3D визуализации")
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)
        
        # Выбор силоса
        control_layout.addWidget(QLabel("Силос:"))
        self.silo_3d_combo = QComboBox()
        self.silo_3d_combo.setMinimumWidth(150)
        self.silo_3d_combo.currentTextChanged.connect(self.update_3d_model)
        control_layout.addWidget(self.silo_3d_combo)
        
        # Даты
        control_layout.addWidget(QLabel("С:"))
        self.silo_3d_start_date = QDateEdit(calendarPopup=True)
        self.silo_3d_start_date.setDate(QDate.currentDate())
        self.silo_3d_start_date.setCalendarPopup(True)
        self.silo_3d_start_date.setMinimumWidth(120)
        control_layout.addWidget(self.silo_3d_start_date)

        control_layout.addWidget(QLabel("По:"))
        self.silo_3d_end_date = QDateEdit(calendarPopup=True)
        self.silo_3d_end_date.setDate(QDate.currentDate())
        self.silo_3d_end_date.setCalendarPopup(True)
        self.silo_3d_end_date.setMinimumWidth(120)
        control_layout.addWidget(self.silo_3d_end_date)
        
        # Кнопка обновления
        self.update_3d_btn = QPushButton("🔄 Обновить")
        self.update_3d_btn.setObjectName("loadButton")
        self.update_3d_btn.clicked.connect(self.update_3d_model)
        control_layout.addWidget(self.update_3d_btn)

        # Кнопка полного экрана
        self.fullscreen_3d_btn = QPushButton("🖥️ На весь экран")
        self.fullscreen_3d_btn.setStyleSheet("background-color: #89b4fa; color: #1e1e2e; font-weight: bold; padding: 8px 16px;")
        self.fullscreen_3d_btn.clicked.connect(self.open_3d_fullscreen)
        control_layout.addWidget(self.fullscreen_3d_btn)
        
        control_layout.addStretch()
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # Информация
        self.silo_3d_info = QLabel("ℹ️ Выберите силос и нажмите 'Обновить'")
        self.silo_3d_info.setStyleSheet("font-size: 12px; color: #6c7086; padding: 4px;")
        layout.addWidget(self.silo_3d_info)
        
        # 3D виджет
        if PLOTLY_AVAILABLE:
            self.silo_3d_widget = PlotlyWidget()
            self.silo_3d_widget.setMinimumHeight(500)
            layout.addWidget(self.silo_3d_widget, 1)
        else:
            from plotly_widget import PlotlyPlaceholder
            placeholder = PlotlyPlaceholder()
            layout.addWidget(placeholder, 1)
        
        # Легенда
        legend_group = QGroupBox("🎨 Цветовая легенда")
        legend_layout = QHBoxLayout()
        legend_layout.setSpacing(15)
        
        legend_items = [
            ("❄️ < 0°C", "rgba(59, 130, 246, 0.8)", "Мороз"),
            ("✅ 0-15°C", "rgba(34, 197, 94, 0.8)", "Норма"),
            ("⚠️ 15-25°C", "rgba(254, 240, 138, 0.8)", "Внимание"),
            ("🔥 25-35°C", "rgba(248, 113, 113, 0.9)", "Перегрев"),
            ("🚨 > 35°C", "rgba(220, 38, 38, 1.0)", "Критично"),
            ("⚠️ 71.2°C", "rgba(128, 128, 128, 0.3)", "Обрыв"),
        ]
        
        for text, color, tooltip in legend_items:
            color_box = QLabel()
            color_box.setMaximumSize(20, 20)
            color_box.setStyleSheet(f"background-color: {color}; border-radius: 3px;")
            color_box.setToolTip(tooltip)
            legend_layout.addWidget(color_box)
            legend_layout.addWidget(QLabel(text))
        
        legend_layout.addStretch()
        legend_group.setLayout(legend_layout)
        layout.addWidget(legend_group)
        
        widget.setLayout(layout)

        # Заполнить список силосов
        self.populate_silo_3d_combo()
        
        # Установить последние 2 даты из базы
        self.set_3d_dates_from_database()

        return widget

    def set_3d_dates_from_database(self):
        """Установить последние 2 даты из базы для 3D вкладки"""
        try:
            dates = get_last_n_dates(self.db_conn, 2)
            if len(dates) >= 2:
                start_date = QDate.fromString(dates[0], "yyyy-MM-dd")
                end_date = QDate.fromString(dates[1], "yyyy-MM-dd")
                self.silo_3d_start_date.setDate(start_date)
                self.silo_3d_end_date.setDate(end_date)
            elif len(dates) == 1:
                date = QDate.fromString(dates[0], "yyyy-MM-dd")
                self.silo_3d_start_date.setDate(date)
                self.silo_3d_end_date.setDate(date)
        except Exception as e:
            print(f"Ошибка при установке дат 3D: {e}")

    def populate_silo_3d_combo(self):
        """Заполнить комбобокс силосов для 3D"""
        self.silo_3d_combo.clear()
        silos = get_unique_silos(self.db_conn)
        self.silo_3d_combo.addItems(silos)
    
    def update_3d_model(self):
        """Обновить 3D модель силоса"""
        try:
            silo = self.silo_3d_combo.currentText()
            start_date = self.silo_3d_start_date.date().toString("yyyy-MM-dd")
            end_date = self.silo_3d_end_date.date().toString("yyyy-MM-dd")
            
            print(f"3D: Загрузка данных для {silo}, {start_date} - {end_date}")
            
            # Получить данные
            df = get_silo_data_with_errors(self.db_conn, silo, start_date, end_date)
            
            if df.empty:
                self.silo_3d_info.setText(f"⚠️ Нет данных для {silo} в выбранном диапазоне")
                return
            
            print(f"3D: Загружено {len(df)} записей")
            
            # Создать 3D визуализацию
            fig = create_silo_3d(df, silo, date=None, suspension_range=None)
            
            # Загрузить в виджет
            if PLOTLY_AVAILABLE:
                self.silo_3d_widget.load_plotly_figure(fig)
            
            self.silo_3d_info.setText(
                f"✅ {silo} | Записей: {len(df)} | "
                f"Дат: {df['date'].nunique()} | "
                f"Датчиков: {len(df.groupby(['suspension', 'sensor']))}"
            )
            
        except Exception as e:
            print(f"Ошибка в update_3d_model: {e}")
            import traceback
            traceback.print_exc()
            self.silo_3d_info.setText(f"⚠️ Ошибка: {e}")

    def open_3d_fullscreen(self):
        """Открыть 3D модель в отдельном окне на весь экран"""
        silo = self.silo_3d_combo.currentText()
        start_date = self.silo_3d_start_date.date().toString("yyyy-MM-dd")
        end_date = self.silo_3d_end_date.date().toString("yyyy-MM-dd")

        # Создать диалог полноэкранной 3D визуализации
        dialog = FullScreen3DDialog(self, silo, start_date, end_date)
        dialog.exec()

    def create_monitoring_tab(self):
        """Создать вкладку мониторинга изменений"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Панель управления
        control_group = QGroupBox("🎛️ Параметры мониторинга")
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)
        
        control_layout.addWidget(QLabel("Порог изменения температуры:"))
        self.change_threshold_spinbox = QDoubleSpinBox()
        self.change_threshold_spinbox.setValue(self.change_threshold)
        self.change_threshold_spinbox.setSuffix(" °C")
        self.change_threshold_spinbox.setRange(0.1, 50)
        self.change_threshold_spinbox.setMinimumWidth(100)
        control_layout.addWidget(self.change_threshold_spinbox)
        
        self.monitoring_apply_btn = QPushButton("✅ Применить")
        self.monitoring_apply_btn.setObjectName("loadButton")
        self.monitoring_apply_btn.clicked.connect(self.update_monitoring_view)
        control_layout.addWidget(self.monitoring_apply_btn)
        
        control_layout.addStretch()
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        # Таблица изменений
        self.changes_table = QTableWidget()
        self.changes_table.setColumnCount(8)
        self.changes_table.setHorizontalHeaderLabels([
            "Силос", "Подвеска", "Датчик", "Дата", "Пред. t°", "Тек. t°", "Δ t°", "Статус"
        ])
        self.changes_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.changes_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.changes_table.setAlternatingRowColors(True)
        self.changes_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.changes_table)
        
        self.changes_label = QLabel("📊 Изменений не найдено")
        self.changes_label.setStyleSheet("font-size: 12px; color: #cdd6f4; padding: 4px;")
        layout.addWidget(self.changes_label)
        
        widget.setLayout(layout)
        return widget

    def create_breaks_tab(self):
        """Создать вкладку обрывов датчиков"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.breaks_label = QLabel("⚠️ Обрывов: 0")
        self.breaks_label.setStyleSheet("font-size: 12px; color: #fab387; padding: 4px; background-color: #313244;")
        layout.addWidget(self.breaks_label)

        self.breaks_table = QTableWidget()
        self.breaks_table.setColumnCount(6)
        self.breaks_table.setHorizontalHeaderLabels(["Силос", "Подвеска", "Датчик", "Первый обрыв", "Посл. t°", "Дата"])
        self.breaks_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.breaks_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.breaks_table.cellClicked.connect(self.on_break_cell_clicked)
        self.breaks_table.setAlternatingRowColors(True)
        self.breaks_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.breaks_table)
        
        widget.setLayout(layout)
        return widget

    def create_hottest_sensors_tab(self):
        """Создать вкладку самых горячих датчиков (2D схема с дельтой)"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        # Панель управления (период, обновление и сброс)
        control_group = QGroupBox("Параметры отображения")
        control_layout = QHBoxLayout()
        control_layout.setSpacing(15)

        control_layout.addWidget(QLabel("Период на шкале:"))
        self.timeline_days_spinbox = QSpinBox()
        self.timeline_days_spinbox.setValue(7)  # По умолчанию 7 дней
        self.timeline_days_spinbox.setSuffix(" дн.")
        self.timeline_days_spinbox.setRange(1, 60)
        self.timeline_days_spinbox.setMinimumWidth(70)
        # При изменении периода обновлять timeline
        self.timeline_days_spinbox.valueChanged.connect(
            lambda: self.update_hottest_sensors_view(refresh_timeline=True)
        )
        control_layout.addWidget(self.timeline_days_spinbox)

        # Кнопка обновления
        self.refresh_silos_btn = QPushButton("🔄 Обновить силоса")
        self.refresh_silos_btn.setObjectName("loadButton")
        self.refresh_silos_btn.clicked.connect(self.force_refresh_silos)
        control_layout.addWidget(self.refresh_silos_btn)

        # Кнопка сброса истории лидеров
        self.reset_leader_history_btn = QPushButton("🗑️ Сброс истории лидеров")
        self.reset_leader_history_btn.setStyleSheet("background-color: #f38ba8; color: #1e1e2e; font-weight: bold; padding: 8px 16px;")
        self.reset_leader_history_btn.setToolTip("Очистить таблицу истории лидеров для повторной проверки")
        self.reset_leader_history_btn.clicked.connect(self.reset_leader_history)
        control_layout.addWidget(self.reset_leader_history_btn)

        # Кнопка полного сброса БД
        self.reset_db_btn = QPushButton("☢️ Сброс ВСЕЙ базы")
        self.reset_db_btn.setStyleSheet("background-color: #930000; color: #ffffff; font-weight: bold; padding: 8px 16px;")
        self.reset_db_btn.setToolTip("Полностью удалить базу данных (все показания, комментарии, историю)")
        self.reset_db_btn.clicked.connect(self.reset_database_full)
        control_layout.addWidget(self.reset_db_btn)

        control_layout.addStretch()
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        # Панель погоды (отдельный блок)
        self.weather_group = QGroupBox("🌤️ Погода на улице")
        weather_layout = QHBoxLayout()
        weather_layout.setSpacing(15)
        weather_layout.setContentsMargins(10, 8, 10, 8)

        # Температура
        self.weather_temp_label = QLabel("Н/Д")
        self.weather_temp_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #89b4fa; padding: 4px;")
        self.weather_temp_label.setToolTip("Температура на улице")
        weather_layout.addWidget(self.weather_temp_label)

        # Влажность
        self.weather_humidity_label = QLabel("Н/Д")
        self.weather_humidity_label.setStyleSheet("font-size: 13px; color: #cdd6f4; padding: 4px;")
        self.weather_humidity_label.setToolTip("Влажность воздуха")
        weather_layout.addWidget(self.weather_humidity_label)

        # Статус/время обновления
        self.weather_status_label = QLabel("")
        self.weather_status_label.setStyleSheet("font-size: 10px; color: #6c7086; padding: 4px;")
        weather_layout.addWidget(self.weather_status_label)

        weather_layout.addStretch()

        # Кнопка настроек
        self.weather_settings_btn = QPushButton("⚙️")
        self.weather_settings_btn.setMaximumWidth(30)
        self.weather_settings_btn.setToolTip("Настроить API ключ OpenWeatherMap")
        self.weather_settings_btn.clicked.connect(self.show_weather_settings)
        weather_layout.addWidget(self.weather_settings_btn)

        self.weather_group.setLayout(weather_layout)
        layout.addWidget(self.weather_group)

        # 2D схема силосов
        self.silos_overview = SilosOverviewWidget()
        self.silos_overview.silo_clicked.connect(self.on_silo_clicked)
        layout.addWidget(self.silos_overview, 1)

        # Шкала дат (timeline)
        self.timeline_slider = DateSliderWidget()
        self.timeline_slider.date_selected.connect(self.on_timeline_date_selected)
        self.timeline_slider.setMinimumHeight(80)
        layout.addWidget(self.timeline_slider)

        widget.setLayout(layout)

        # Загрузить данные сразу при создании вкладки
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(200, self.update_hottest_sensors_view)
        
        # Инициализировать timeline при запуске
        QTimer.singleShot(300, lambda: self.update_hottest_sensors_view(refresh_timeline=True))

        return widget

    def on_timeline_date_selected(self, date):
        """Обработка выбора даты на шкале"""
        # При выборе даты НЕ обновлять timeline, только силоса
        self.update_hottest_sensors_view(selected_date=date, refresh_timeline=False)
    
    def on_silo_clicked(self, silo_name, date):
        """Обработка клика по силосу"""
        dialog = SiloCommentDialog(self, silo_name, date, self.db_conn)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Обновить иконку комментария после закрытия диалога
            self.update_hottest_sensors_view(selected_date=date, refresh_timeline=False)

    def force_refresh_silos(self):
        """Принудительное обновление силосов"""
        print("=== Принудительное обновление ===")
        self.update_hottest_sensors_view(refresh_timeline=True)

    def reset_leader_history(self):
        """Сброс таблицы истории лидеров"""
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setText("Вы уверены, что хотите сбросить историю лидеров?")
        msg_box.setInformativeText(
            "Это удалит все записи из таблицы leader_history.\n"
            "При следующей проверке будут созданы новые записи и комментарии о смене лидера."
        )
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        
        reply = msg_box.exec()
        if reply == QMessageBox.StandardButton.Yes:
            try:
                cur = self.db_conn.cursor()
                cur.execute("DELETE FROM leader_history")
                self.db_conn.commit()
                
                logging.info("История лидеров сброшена")
                self.status_label.setText("🗑️ История лидеров сброшена")
                
                # Запустить проверку лидеров заново
                self.check_leader_changes()
                
            except Exception as e:
                logging.error(f"Ошибка сброса истории лидеров: {e}")
                QMessageBox.critical(self, "Ошибка", f"Ошибка сброса: {e}")

    def reset_database_full(self):
        """Полный сброс базы данных (удаление всех таблиц)"""
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setText("⚠️ ПОЛНЫЙ СБРОС БАЗЫ ДАННЫХ")
        msg_box.setInformativeText(
            "Это действие УДАЛИТ ВСЕ данные:\n"
            "• Все показания датчиков\n"
            "• Все комментарии\n"
            "• Историю лидеров\n"
            "• Пользовательские настройки\n\n"
            "Это действие НЕЛЬЗЯ ОТМЕНИТЬ!\n"
            "Вы уверены?"
        )
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)
        
        # Добавить дополнительный вопрос подтверждения
        confirm_box = QMessageBox()
        confirm_box.setIcon(QMessageBox.Icon.Critical)
        confirm_box.setText("Последнее предупреждение!")
        confirm_box.setInformativeText("Все данные будут безвозвратно удалены. Продолжить?")
        confirm_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        confirm_box.setDefaultButton(QMessageBox.StandardButton.No)
        
        reply = msg_box.exec()
        if reply == QMessageBox.StandardButton.Yes:
            reply2 = confirm_box.exec()
            if reply2 == QMessageBox.StandardButton.Yes:
                try:
                    # Закрыть текущее соединение
                    self.db_conn.close()
                    
                    # Удалить файл БД
                    import os
                    db_path = "temperatures.db"
                    if os.path.exists(db_path):
                        os.remove(db_path)
                        logging.info(f"База данных {db_path} удалена")
                    
                    # Создать новую БД
                    self.db_conn = setup_database(db_path)
                    
                    logging.info("База данных создана заново")
                    self.status_label.setText("🗑️ База данных сброшена")
                    
                    # Обновить интерфейс
                    self.populate_silo_filter()
                    self.update_date_range()
                    self.update_data_view()
                    
                    QMessageBox.information(
                        self, "Сброс выполнен",
                        "✅ База данных полностью сброшена.\n"
                        "Теперь загрузите новые отчеты для тестирования."
                    )
                    
                except Exception as e:
                    logging.error(f"Ошибка сброса БД: {e}")
                    QMessageBox.critical(self, "Ошибка", f"Ошибка сброса: {e}\n\nПопробуйте закрыть приложение и удалить файл temperatures.db вручную")

    def update_hottest_sensors_view(self, selected_date=None, refresh_timeline=True):
        """Обновить вкладку самых горячих датчиков"""
        try:
            # Порог дельты по умолчанию 1.0°C
            threshold = 1.0
            # Период из настройки
            timeline_days = self.timeline_days_spinbox.value() if hasattr(self, 'timeline_days_spinbox') else 7

            # Если дата не выбрана, использовать последнюю из доступных
            if not selected_date:
                # Получить последнюю дату из БД
                all_dates = get_available_dates(self.db_conn)
                if not all_dates:
                    self.silos_overview.update_silos({})
                    return
                selected_date = all_dates[-1]

            # Установить дату в timeline (только если нужно обновить timeline)
            if refresh_timeline and hasattr(self, 'timeline_slider'):
                all_dates = get_available_dates(self.db_conn)
                # Загрузить даты за последние N дней от selected_date
                from datetime import datetime, timedelta
                try:
                    end_dt = datetime.strptime(selected_date, "%Y-%m-%d")
                    start_dt = end_dt - timedelta(days=timeline_days)
                    start_date_str = start_dt.strftime("%Y-%m-%d")
                    dates_range = get_date_range_for_slider(self.db_conn, start_date_str, selected_date)
                    self.timeline_slider.set_dates(dates_range, selected_date)
                except:
                    self.timeline_slider.set_dates(all_dates, selected_date)
            elif hasattr(self, 'timeline_slider'):
                # Просто обновить выделение
                self.timeline_slider.update_selection(selected_date)

            print(f"Дельта температур: дата={selected_date}, порог={threshold}, период={timeline_days} дн.")

            # Получить дельты для всех силосов на выбранную дату
            silos_delta_data = get_all_silos_delta_for_date(self.db_conn, selected_date)

            print(f"Получено данных по силосам: {len(silos_delta_data) if silos_delta_data else 0}")
            if silos_delta_data:
                print(f"Силоса: {list(silos_delta_data.keys())}")

            if not silos_delta_data:
                self.silos_overview.update_silos({})
                return

            # Получить информацию о комментариях для каждого силоса (хотя бы один в истории)
            comments = {}
            for silo in silos_delta_data.keys():
                comments[silo] = has_any_comment(self.db_conn, silo)

            print(f"Комментарии: {comments}")
            
            # Получить информацию о лидерах по каждому силосу (для отображения смены)
            current_leaders = get_all_silos_leaders_for_date(self.db_conn, selected_date, threshold)
            prev_date = get_previous_date_with_data(self.db_conn, selected_date)
            previous_leaders = {}
            if prev_date:
                previous_leaders = get_all_silos_leaders_for_date(self.db_conn, prev_date, threshold)

            print(f"Лидеры по силосам: {list(current_leaders.keys())}")

            # Передать данные в виджет (с порогом, датой, комментариями и лидерами по силосам)
            self.silos_overview.delta_threshold = threshold
            self.silos_overview.update_silos(silos_delta_data, date=selected_date, comments=comments, previous_leaders=previous_leaders, current_leaders=current_leaders)

        except Exception as e:
            print(f"Ошибка в update_hottest_sensors_view: {e}")
            import traceback
            traceback.print_exc()

    def set_period(self, days):
        """Установить период дат в зависимости от выбранной кнопки"""
        for btn in self.period_buttons:
            btn.setChecked(False)

        sender = self.sender()
        if sender:
            sender.setChecked(True)

        today = QDate.currentDate()

        if days == 0:
            all_data = get_readings(self.db_conn)
            if all_data:
                dates = [row[4] for row in all_data if row[4]]
                if dates:
                    min_date = QDate.fromString(min(dates), "yyyy-MM-dd")
                    self.start_date_edit.setDate(min_date)
                else:
                    self.start_date_edit.setDate(today.addYears(-1))
            else:
                self.start_date_edit.setDate(today.addYears(-1))
            self.end_date_edit.setDate(today)
        else:
            self.start_date_edit.setDate(today.addDays(-days + 1))
            self.end_date_edit.setDate(today)

        self.update_data_view()

    def on_threshold_changed(self, value):
        """Изменение порога температуры"""
        self.temp_threshold = value
        set_user_setting(self.db_conn, 'temp_threshold', str(value))
        self.update_data_view()

    def choose_color(self, color_type):
        """Выбор цвета для элемента"""
        from PyQt6.QtWidgets import QColorDialog
        from PyQt6.QtGui import QColor
        
        current_colors = {
            'hotspot': self.color_hotspot,
            'error': self.color_error,
            'normal': self.color_normal,
            'warning': self.color_warning,
        }
        
        current = current_colors.get(color_type, '#f38ba8')
        qcolor = QColor(current)
        color = QColorDialog.getColor(qcolor, self, f"Выберите цвет для: {color_type}")
        
        if color.isValid():
            hex_color = color.name()
            
            if color_type == 'hotspot':
                self.color_hotspot = hex_color
                self.hotspot_color_btn.setStyleSheet(f"background-color: {hex_color};")
            elif color_type == 'error':
                self.color_error = hex_color
                self.error_color_btn.setStyleSheet(f"background-color: {hex_color};")
            elif color_type == 'normal':
                self.color_normal = hex_color
            elif color_type == 'warning':
                self.color_warning = hex_color
            
            set_user_setting(self.db_conn, f'color_{color_type}', hex_color)
            self.update_data_view()

    def export_table_dialog(self, table, table_type):
        """Экспорт таблицы в Excel"""
        if table.rowCount() == 0:
            self.status_label.setText("Таблица пуста, нечего экспортировать.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Экспортировать таблицу", "", "Excel Files (*.xlsx)")
        if file_path:
            try:
                headers = [table.horizontalHeaderItem(i).text() for i in range(table.columnCount())]
                data = []
                for row in range(table.rowCount()):
                    row_data = [table.item(row, col).text() for col in range(table.columnCount())]
                    data.append(row_data)

                df = pd.DataFrame(data, columns=headers)
                df.to_excel(file_path, index=False)

                self.status_label.setText(f"Таблица экспортирована в {file_path}")
            except Exception as e:
                self.status_label.setText(f"Ошибка экспорта таблицы: {e}")

    def reset_database(self):
        """Сброс базы данных"""
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setText("Вы уверены, что хотите удалить ВСЕ данные из базы?")
        msg_box.setInformativeText("Это действие нельзя отменить!")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)

        reply = msg_box.exec()
        if reply == QMessageBox.StandardButton.Yes:
            cursor = self.db_conn.cursor()
            cursor.execute("DELETE FROM readings")
            self.db_conn.commit()
            self.populate_silo_filter()
            self.update_date_range()
            self.update_data_view()
            self.status_label.setText("✅ База данных очищена")

    def save_graph_dialog(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить график", "", "PNG Images (*.png);;JPEG Images (*.jpg)")
        if file_path:
            try:
                self.plot_widget.save_plot(file_path)
                self.status_label.setText(f"График сохранен в {file_path}")
            except Exception as e:
                self.status_label.setText(f"Ошибка сохранения: {e}")

    def populate_silo_filter(self):
        self.silo_combo.clear()
        self.silo_combo.addItem("Все силосы")
        silos = get_unique_silos(self.db_conn)
        self.silo_combo.addItems(silos)
        self.populate_suspension_filter()

    def populate_suspension_filter(self):
        self.suspension_combo.clear()
        self.suspension_combo.addItem("Все подвески")
        silo = self.silo_combo.currentText()
        if silo != "Все силосы":
            suspensions = get_suspensions_for_silo(self.db_conn, silo)
            self.suspension_combo.addItems([str(s) for s in suspensions])

    def update_date_range(self):
        """Обновить диапазон доступных дат"""
        min_date_str, max_date_str = get_date_range(self.db_conn)

        if min_date_str and max_date_str:
            min_date = QDate.fromString(min_date_str, "yyyy-MM-dd")
            max_date = QDate.fromString(max_date_str, "yyyy-MM-dd")

            self.start_date_edit.setMinimumDate(min_date)
            self.start_date_edit.setMaximumDate(max_date)
            self.end_date_edit.setMinimumDate(min_date)
            self.end_date_edit.setMaximumDate(max_date)

            self.date_range_label.setText(f"📅 Данные: {min_date_str} — {max_date_str}")

            if not self.config.get("start_date"):
                self.start_date_edit.setDate(min_date)
            if not self.config.get("end_date"):
                self.end_date_edit.setDate(max_date)
        else:
            self.date_range_label.setText("📅 Данные: нет данных")

    def update_data_view(self):
        """Обновить отображение данных на вкладке горячих точек"""
        import traceback
        stack = traceback.format_stack()
        logging.debug(f"update_data_view вызван из:\n{''.join(stack[-5:-1])}")
        
        # Не обновлять status_label если активна вкладка "Самые горячие датчики"
        if hasattr(self, 'main_tabs') and self.main_tabs.currentIndex() == 5:
            logging.debug("update_data_view пропущен (активна вкладка 5)")
            return
        
        self.delta_label.setText("ℹ️ Кликните на ячейку в таблице для просмотра тренда")
        silo = self.silo_combo.currentText()
        suspension = self.suspension_combo.currentText()
        plot_type = self.plot_type_combo.currentText()
        threshold = self.temp_threshold_spinbox.value()

        start_date = self.start_date_edit.date().toString("yyyy-MM-dd")
        end_date = self.end_date_edit.date().toString("yyyy-MM-dd")

        # Получаем последнюю дату выбранного периода для отображения горячих точек
        last_date = end_date

        # Обновить информацию о самом горячем датчике
        self.update_hotspot_leader_label(last_date, threshold)

        if silo != "Все силосы":
            if plot_type == "Средняя температура":
                self.hot_spots_table.setRowCount(0)
                plot_series = {}
                if suspension != "Все подвески":
                    susp_num = int(suspension)
                    avg_data = get_average_temp_by_suspension(self.db_conn, silo, susp_num, start_date, end_date)
                    plot_series[f"Средняя t° (подв. {susp_num})"] = avg_data
                    msg = f"График средней t° для силоса {silo}, подвески {susp_num}"
                    logging.debug(f"status_label установлен: '{msg}'")
                    self.status_label.setText(msg)
                else:
                    avg_data = get_average_temp_by_silo(self.db_conn, silo, start_date, end_date)
                    plot_series[f"Средняя t° (силос {silo})"] = avg_data
                    msg = f"График средней t° для силоса {silo}"
                    logging.debug(f"status_label установлен: '{msg}'")
                    self.status_label.setText(msg)
                self.plot_widget.plot_data(plot_series)

            elif suspension != "Все подвески":
                self.hot_spots_table.setRowCount(0)
                susp_num = int(suspension)
                all_sensors_data = get_readings(self.db_conn, silo=silo, start_date=start_date, end_date=end_date)
                plot_series = {}
                for row in all_sensors_data:
                    if row[1] == susp_num:
                        sensor_id = row[2]
                        series_name = f"Датчик {sensor_id}"
                        if series_name not in plot_series:
                            plot_series[series_name] = []
                        plot_series[series_name].append((row[4], row[3]))
                self.plot_widget.plot_data(plot_series)
                self.status_label.setText(f"График для силоса {silo}, подвески {susp_num}")

            else:
                self.populate_hotspots_table(silo, last_date, threshold)
        else:
            self.populate_hotspots_table(None, last_date, threshold)
        
        # Обновить таблицу обрывов
        self.populate_breaks_table(silo if silo != "Все силосы" else None, start_date, end_date)

    def populate_hotspots_table(self, silo, date, threshold):
        """Заполнить таблицу горячими точками за конкретную дату"""
        self.plot_widget.plot_data({})

        # Получаем горячие точки за выбранную дату
        hot_spots = get_hot_spots_for_date(self.db_conn, silo if silo != "Все силосы" else None, date, threshold)

        self.hot_spots_table.setRowCount(0)

        if not hot_spots:
            self.hot_spots_label.setText(f"🔥 Горячих точек: 0 (порог: {threshold}°C)")
            self.status_label.setText(f"Горячих точек не найдено за {date}")
            return

        # Формат даты для отображения
        date_format = "%d.%m.%Y" if self.date_format_with_year else "%d.%m"

        # Получить предыдущую дату для расчёта дельты
        prev_date = get_previous_date_with_data(self.db_conn, date)

        self.hot_spots_table.setRowCount(len(hot_spots))
        for row_idx, row_data in enumerate(hot_spots):
            silo_name = str(row_data[0])
            suspension = int(row_data[1])
            sensor = int(row_data[2])
            temperature = float(row_data[3])
            row_date = row_data[4]

            # Силос
            item = QTableWidgetItem(silo_name)
            self.hot_spots_table.setItem(row_idx, 0, item)
            # Подвеска
            item = QTableWidgetItem(str(suspension))
            self.hot_spots_table.setItem(row_idx, 1, item)
            # Датчик
            item = QTableWidgetItem(str(sensor))
            self.hot_spots_table.setItem(row_idx, 2, item)
            # Температура
            item = QTableWidgetItem(f"{temperature:.1f}°C")
            self.hot_spots_table.setItem(row_idx, 3, item)
            # Дата (форматированная)
            date_obj = datetime.strptime(row_date, "%Y-%m-%d")
            formatted_date = date_obj.strftime(date_format)
            item = QTableWidgetItem(formatted_date)
            self.hot_spots_table.setItem(row_idx, 4, item)

            # Подсветка красным
            self.highlight_row(row_idx, QColor(self.color_hotspot))

            # Всплывающая подсказка с информацией о датчике и дельтой
            tooltip = f"📍 {silo_name}, Подвеска {suspension}, Датчик {sensor}\n"
            tooltip += f"🌡️ Температура: {temperature:.1f}°C\n"
            tooltip += f"📅 Дата: {formatted_date}"
            
            # Добавить дельту если есть предыдущая дата
            if prev_date:
                prev_temp = get_sensor_temperature_on_date(
                    self.db_conn, silo_name, suspension, sensor, prev_date
                )
                if prev_temp is not None and prev_temp != 71.2:
                    delta = temperature - prev_temp
                    delta_sign = "+" if delta > 0 else ""
                    prev_date_obj = datetime.strptime(prev_date, "%Y-%m-%d")
                    prev_date_formatted = prev_date_obj.strftime(date_format)
                    tooltip += f"\n\n📈 Дельта за сутки ({prev_date_formatted}): {delta_sign}{delta:.1f}°C"
                    tooltip += f"\n   Предыдущая t°: {prev_temp:.1f}°C"
            
            item.setToolTip(tooltip)

        msg = f"🔥 Горячих точек: {len(hot_spots)} (порог: {threshold}°C)"
        logging.debug(f"hot_spots_label установлен: '{msg}'")
        self.hot_spots_label.setText(msg)
        
        msg = f"Найдено {len(hot_spots)} горячих точек за {date}"
        logging.debug(f"status_label установлен: '{msg}'")
        self.status_label.setText(msg)

    def highlight_row(self, row_index, color):
        for col in range(self.hot_spots_table.columnCount()):
            item = self.hot_spots_table.item(row_index, col)
            if item:
                item.setBackground(color)

    def update_hotspot_leader_label(self, date, threshold):
        """Обновить информацию о самом горячем датчике с информацией о смене лидера"""
        try:
            leader_info = get_leader_change_info(self.db_conn, date, threshold)
            
            if not leader_info:
                self.hotspot_leader_label.setText("")
                return
            
            current = leader_info['current']
            previous = leader_info['previous']
            changed = leader_info['changed']
            prev_date = leader_info.get('prev_date')
            
            # Формат даты
            date_format = "%d.%m.%Y" if self.date_format_with_year else "%d.%m"
            
            if current:
                current_text = f"🔥 Лидер: Силос {current['silo']}, Подвеска {current['suspension']}, Датчик {current['sensor']} ({current['temperature']:.1f}°C)"
                
                if changed and previous:
                    prev_date_obj = datetime.strptime(prev_date, "%Y-%m-%d")
                    prev_date_formatted = prev_date_obj.strftime(date_format)
                    
                    # Дельта между текущим и предыдущим лидером
                    temp_delta = current['temperature'] - previous['temperature']
                    delta_sign = "+" if temp_delta > 0 else ""
                    
                    change_text = (
                        f" | 📈 Смена лидера: был {previous['silo']}-{previous['suspension']}-{previous['sensor']} "
                        f"({previous['temperature']:.1f}°C, {prev_date_formatted}), "
                        f"дельта: {delta_sign}{temp_delta:.1f}°C"
                    )
                    self.hotspot_leader_label.setText(current_text + change_text)
                else:
                    self.hotspot_leader_label.setText(current_text)
            else:
                self.hotspot_leader_label.setText("")
                
        except Exception as e:
            print(f"Ошибка в update_hotspot_leader_label: {e}")

    def on_hotspot_clicked(self, row, column):
        """Клик по таблице горячих точек"""
        silo_item = self.hot_spots_table.item(row, 0)
        susp_item = self.hot_spots_table.item(row, 1)
        sens_item = self.hot_spots_table.item(row, 2)

        if not (silo_item and susp_item and sens_item):
            return

        silo = silo_item.text()
        suspension = int(susp_item.text())
        sensor = int(sens_item.text())

        start_date = self.start_date_edit.date().toString("yyyy-MM-dd")
        end_date = self.end_date_edit.date().toString("yyyy-MM-dd")

        history_data = get_sensor_history_with_dates(
            self.db_conn, silo, suspension, sensor, start_date, end_date
        )

        self.plot_widget.plot_data({f"Датчик {sensor} (Силос {silo}, Подв. {suspension})": history_data})

        if len(history_data) > 1:
            latest_date_str, latest_temp = history_data[-1]
            latest_date = datetime.strptime(latest_date_str, '%Y-%m-%d')

            temp_1_day_ago = None
            temp_3_days_ago = None

            date_1_day_ago = latest_date - timedelta(days=1)
            date_3_days_ago = latest_date - timedelta(days=3)

            for date_str, temp in reversed(history_data[:-1]):
                current_date = datetime.strptime(date_str, '%Y-%m-%d')
                if current_date == date_1_day_ago:
                    temp_1_day_ago = temp
                if current_date == date_3_days_ago:
                    temp_3_days_ago = temp
                if temp_1_day_ago is not None and temp_3_days_ago is not None:
                    break

            delta_texts = []
            if temp_1_day_ago is not None:
                delta_1 = latest_temp - temp_1_day_ago
                delta_texts.append(f"24ч: {delta_1:+.1f}°C")
            if temp_3_days_ago is not None:
                delta_3 = latest_temp - temp_3_days_ago
                delta_texts.append(f"3 дня: {delta_3:+.1f}°C")

            if delta_texts:
                self.delta_label.setText(f"Тренд для {latest_date_str}: " + " | ".join(delta_texts))
            else:
                self.delta_label.setText("Недостаточно данных для расчета тренда.")
        else:
            self.delta_label.setText("Недостаточно данных для расчета тренда.")

        self.update_color_buttons()

    def populate_breaks_table(self, silo, start_date, end_date):
        """Заполнить таблицу обрывов датчиков"""
        all_data = get_readings(self.db_conn, silo=silo, start_date=None, end_date=None)

        sensor_data = {}
        for row in all_data:
            key = (row[0], row[1], row[2])
            if key not in sensor_data:
                sensor_data[key] = []
            sensor_data[key].append((row[4], row[3]))

        breaks_new = []
        breaks_old = []

        for (silo_name, susp_num, sensor_num), readings in sensor_data.items():
            readings.sort(key=lambda x: x[0])

            has_break = any(temp == 71.2 for _, temp in readings)
            if not has_break:
                continue

            first_break_date = None
            first_break_index = None

            for i, (date_str, temp) in enumerate(readings):
                if temp == 71.2:
                    first_break_date = date_str
                    first_break_index = i
                    break

            if first_break_index == 0:
                breaks_old.append({
                    'silo': silo_name,
                    'suspension': susp_num,
                    'sensor': sensor_num,
                    'first_break': first_break_date,
                    'last_temp': '—',
                    'last_date': '—',
                    'status': 'Всегда в обрыве'
                })
            else:
                last_normal_date, last_normal_temp = readings[first_break_index - 1]
                breaks_new.append({
                    'silo': silo_name,
                    'suspension': susp_num,
                    'sensor': sensor_num,
                    'first_break': first_break_date,
                    'last_temp': f"{last_normal_temp:+.1f}°C",
                    'last_date': last_normal_date,
                    'status': 'Ушёл в обрыв'
                })

        self.breaks_table.setRowCount(0)
        all_breaks = breaks_new + breaks_old

        if not all_breaks:
            self.breaks_label.setText(f"⚠️ Обрывов: 0")
            return

        self.breaks_table.setRowCount(len(all_breaks))
        for row_idx, brk in enumerate(all_breaks):
            self.breaks_table.setItem(row_idx, 0, QTableWidgetItem(str(brk['silo'])))
            self.breaks_table.setItem(row_idx, 1, QTableWidgetItem(str(brk['suspension'])))
            self.breaks_table.setItem(row_idx, 2, QTableWidgetItem(str(brk['sensor'])))
            self.breaks_table.setItem(row_idx, 3, QTableWidgetItem(brk['first_break']))
            self.breaks_table.setItem(row_idx, 4, QTableWidgetItem(str(brk['last_temp'])))
            self.breaks_table.setItem(row_idx, 5, QTableWidgetItem(brk['last_date']))

        total = len(all_breaks)
        new_breaks = len(breaks_new)
        old_breaks = len(breaks_old)
        self.breaks_label.setText(f"⚠️ Обрывов: {total} (ушли: {new_breaks} | всегда: {old_breaks})")

    def on_break_cell_clicked(self, row, column):
        """Клик по таблице обрывов"""
        silo_item = self.breaks_table.item(row, 0)
        susp_item = self.breaks_table.item(row, 1)
        sens_item = self.breaks_table.item(row, 2)

        if not (silo_item and susp_item and sens_item):
            return

        silo = silo_item.text()
        suspension = int(susp_item.text())
        sensor = int(sens_item.text())

        history_data = get_sensor_history(self.db_conn, silo, suspension, sensor)

        self.plot_widget.plot_data({f"Датчик {sensor} (Силос {silo}, Подв. {suspension})": history_data})
        self.delta_label.setText(f"⚠️ Обрыв датчика! Кликните для просмотра истории")
        self.update_color_buttons()

    def update_color_buttons(self):
        """Обновить панель кнопок выбора цвета для серий"""
        if not hasattr(self, 'color_buttons_layout') or self.color_buttons_layout is None:
            return

        # Очистить текущие кнопки
        while self.color_buttons_layout.count():
            item = self.color_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        series_names = list(self.plot_widget.series_colors.keys())

        for series_name in series_names:
            btn = QPushButton(f"■ {series_name[:15]}...")
            btn.setMaximumWidth(100)
            btn.setStyleSheet(f"font-size: 10px; background-color: {self.plot_widget.series_colors[series_name]}; color: #000000; font-weight: bold;")
            btn.clicked.connect(lambda checked, name=series_name: self.change_series_color(name))
            self.color_buttons_layout.addWidget(btn)

    def change_series_color(self, series_name):
        """Изменить цвет серии"""
        from PyQt6.QtWidgets import QColorDialog
        from PyQt6.QtGui import QColor

        current_color = self.plot_widget.series_colors.get(series_name, '#89b4fa')
        qcolor = QColor(current_color)
        color = QColorDialog.getColor(qcolor, self, f"Выберите цвет для: {series_name}")

        if color.isValid():
            hex_color = color.name()
            self.plot_widget.set_series_color(series_name, hex_color)
            self.on_hotspot_clicked(self.hot_spots_table.currentRow(), 0)
            self.update_color_buttons()

    def change_graphic_color(self, element):
        """Изменить цвет элемента графика"""
        from PyQt6.QtWidgets import QColorDialog
        from PyQt6.QtGui import QColor

        current_colors = {
            'background': self.plot_widget.plot_colors['background'],
            'grid': self.plot_widget.plot_colors['grid'],
            'axes': self.plot_widget.plot_colors['axes']
        }

        current_color = current_colors.get(element, '#1e1e2e')
        qcolor = QColor(current_color)
        color = QColorDialog.getColor(qcolor, self, f"Выберите цвет для: {element}")

        if color.isValid():
            hex_color = color.name()

            if element == 'background':
                self.plot_widget.set_color_scheme(background=hex_color)
                self.bg_color_btn.setStyleSheet(f"background-color: {hex_color}; color: white;")
            elif element == 'grid':
                self.plot_widget.set_color_scheme(grid=hex_color)
                self.grid_color_btn.setStyleSheet(f"background-color: {hex_color}; color: white;")
            elif element == 'axes':
                self.plot_widget.set_color_scheme(axes=hex_color)
                self.axes_color_btn.setStyleSheet(f"background-color: {hex_color}; color: white;")

            if self.hot_spots_table.rowCount() > 0:
                self.on_hotspot_clicked(self.hot_spots_table.currentRow(), 0)
            else:
                self.update_data_view()

    def reset_plot_colors(self):
        """Сбросить цвета графика"""
        self.plot_widget.series_colors.clear()
        self.plot_widget.plot_colors = DEFAULT_PLOT_COLORS.copy()
        self.plot_widget.set_color_scheme(
            background=DEFAULT_PLOT_COLORS['background'],
            axes=DEFAULT_PLOT_COLORS['axes'],
            grid=DEFAULT_PLOT_COLORS['grid']
        )

        self.bg_color_btn.setStyleSheet("background-color: #1e1e2e; color: white;")
        self.grid_color_btn.setStyleSheet("background-color: #45475a; color: white;")
        self.axes_color_btn.setStyleSheet("background-color: #313244; color: white;")

        if self.hot_spots_table.rowCount() > 0:
            self.on_hotspot_clicked(self.hot_spots_table.currentRow(), 0)
        else:
            self.update_data_view()

    # === Методы для вкладки графиков по силосам ===

    def build_multi_silo_graph(self):
        """Построить график по выбранным горячим точкам"""
        try:
            if not self.selected_silo or not self.selected_points:
                self.status_label.setText("Выберите силос и горячие точки")
                return

            # Построить график
            plot_series = {}
            for susp, sensor in self.selected_points:
                history_data = get_sensor_history_with_dates(
                    self.db_conn, self.selected_silo, susp, sensor,
                    self.graph_start_date, self.graph_end_date
                )
                # Исключить обрывы датчиков (71.2°C)
                filtered_data = [(d, t) for d, t in history_data if t != 71.2]
                series_name = f"Подв. {susp}, Датчик {sensor}"
                plot_series[series_name] = filtered_data
                print(f"Загружено {len(history_data)} записей, после фильтрации {len(filtered_data)} для {series_name}")

            print(f"Построение графика с {len(plot_series)} сериями")
            self.silo_graph_widget.plot_data(plot_series)
            self.status_label.setText(f"Построен график для {len(self.selected_points)} точек")

            # Сохранить настройки
            set_user_setting(self.db_conn, 'graph_start_date', self.graph_start_date)
            set_user_setting(self.db_conn, 'graph_end_date', self.graph_end_date)
        except Exception as e:
            print(f"Ошибка в build_multi_silo_graph: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Ошибка", f"Ошибка при построении графика: {e}")

    def on_silo_graph_point_selected(self, date, temp, series):
        """Обработка клика по точке на графике силосов"""
        try:
            # Сохранить текущую выбранную точку
            self.current_selected_date = date
            self.current_selected_series = series
            
            # Форматировать дату
            if self.date_format_with_year:
                formatted_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m.%Y")
            else:
                formatted_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m")

            self.point_date_label.setText(f"📍 Дата: {formatted_date}")

            # Обновить состояние кнопок навигации
            all_dates = self.get_all_dates_for_current_series()
            if all_dates and date in all_dates:
                current_idx = all_dates.index(date)
                self.prev_date_btn.setEnabled(current_idx > 0)
                self.next_date_btn.setEnabled(current_idx < len(all_dates) - 1)

            print(f"Выбрана точка: дата={date}, temp={temp}, series={series}")
            print(f"plot_data_cache keys: {list(self.silo_graph_widget.plot_data_cache.keys())}")

            self.update_values_display()

        except Exception as e:
            print(f"Ошибка в on_silo_graph_point_selected: {e}")
            import traceback
            traceback.print_exc()

    def update_values_display(self):
        """Обновить отображение значений с текущими настройками"""
        if not hasattr(self, 'current_selected_date') or not hasattr(self, 'point_values_layout'):
            return

        # Очистить старые значения - удалить все виджеты и layout
        while self.point_values_layout.count():
            item = self.point_values_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                # Рекурсивно удалить виджеты из вложенного layout
                self._clear_layout(item.layout())

        # Получить текущее количество значений в строке
        try:
            values_per_row = int(self.values_per_row_combo.currentText())
        except:
            values_per_row = 6

        # Получить значения всех серий в этой дате
        found_values = []
        for series_name, data in self.silo_graph_widget.plot_data_cache.items():
            if self.current_selected_date in data['dates']:
                idx = data['dates'].index(self.current_selected_date)
                temp_val = data['temperatures'][idx]
                color = data['color']
                found_values.append((series_name, temp_val, color))

        if not found_values:
            no_data_label = QLabel("Значения: —")
            no_data_label.setStyleSheet("font-size: 12px; color: #6c7086;")
            self.point_values_layout.addWidget(no_data_label)
        else:
            # Пометить выбранную точку
            selected_series = self.current_selected_series

            # Разделить на выбранную и остальные
            selected_data = [(name, temp_val, color) for name, temp_val, color in found_values if name == selected_series]
            other_data = [(name, temp_val, color) for name, temp_val, color in found_values if name != selected_series]

            # Все точки в одной сетке - выбранная жирным и первой
            all_items = []

            # Сначала выбранная (жирным)
            for name, temp_val, color in selected_data:
                all_items.append(('selected', name, temp_val, color))

            # Затем остальные
            for name, temp_val, color in other_data:
                all_items.append(('normal', name, temp_val, color))

            # Создаём строки по N элементов
            col = 0
            grid_layout = QHBoxLayout()
            grid_layout.setSpacing(4)
            grid_layout.setContentsMargins(0, 4, 0, 4)

            for i, (item_type, name, temp_val, color) in enumerate(all_items):
                if item_type == 'selected':
                    label = QLabel(f"● <b style='color:{color}; font-size: 13px;'>{name}: {temp_val:.1f}°C</b>")
                    label.setStyleSheet(f"font-size: 13px; color: {color}; padding: 4px; background-color: rgba(255,255,255,0.05); border-radius: 4px;")
                else:
                    label = QLabel(f"○ <span style='color:{color}'>{name}: {temp_val:.1f}°C</span>")
                    label.setStyleSheet(f"font-size: 11px; color: {color}; padding: 2px 4px;")

                label.setWordWrap(True)
                grid_layout.addWidget(label, 1)
                col += 1

                # Перенос на новую строку после каждых N элементов
                if col >= values_per_row and i < len(all_items) - 1:
                    self.point_values_layout.addLayout(grid_layout)
                    grid_layout = QHBoxLayout()
                    grid_layout.setSpacing(4)
                    grid_layout.setContentsMargins(0, 0, 0, 0)
                    col = 0

            # Добавить последнюю строку
            if grid_layout.count() > 0:
                grid_layout.addStretch()
                self.point_values_layout.addLayout(grid_layout)

            self.point_values_layout.addStretch()

    def _clear_layout(self, layout):
        """Рекурсивно удалить все виджеты из layout"""
        if layout is None:
            return
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def scroll_values_up(self):
        """Прокрутка значений вверх на 1 строку"""
        scrollbar = self.point_values_scroll.verticalScrollBar()
        current_value = scrollbar.value()
        page_step = scrollbar.singleStep()
        scrollbar.setValue(current_value - page_step * 3)

    def scroll_values_down(self):
        """Прокрутка значений вниз на 1 строку"""
        scrollbar = self.point_values_scroll.verticalScrollBar()
        current_value = scrollbar.value()
        page_step = scrollbar.singleStep()
        scrollbar.setValue(current_value + page_step * 3)

    def get_all_dates_for_current_series(self):
        """Получить отсортированный список всех дат для текущей выбранной серии"""
        if not hasattr(self, 'current_selected_series') or not self.current_selected_series:
            return []
        
        if self.current_selected_series in self.silo_graph_widget.plot_data_cache:
            data = self.silo_graph_widget.plot_data_cache[self.current_selected_series]
            return sorted(data['dates'])
        return []

    def navigate_to_prev_date(self):
        """Перейти к предыдущей дате"""
        all_dates = self.get_all_dates_for_current_series()
        if not all_dates or not hasattr(self, 'current_selected_date'):
            return
        
        try:
            current_idx = all_dates.index(self.current_selected_date)
            if current_idx > 0:
                prev_date = all_dates[current_idx - 1]
                # Найти температуру для предыдущей даты
                temp = None
                if self.current_selected_series in self.silo_graph_widget.plot_data_cache:
                    data = self.silo_graph_widget.plot_data_cache[self.current_selected_series]
                    if prev_date in data['dates']:
                        temp = data['temperatures'][data['dates'].index(prev_date)]
                
                if temp is not None:
                    self.on_silo_graph_point_selected(prev_date, temp, self.current_selected_series)
        except ValueError:
            pass

    def navigate_to_next_date(self):
        """Перейти к следующей дате"""
        all_dates = self.get_all_dates_for_current_series()
        if not all_dates or not hasattr(self, 'current_selected_date'):
            return
        
        try:
            current_idx = all_dates.index(self.current_selected_date)
            if current_idx < len(all_dates) - 1:
                next_date = all_dates[current_idx + 1]
                # Найти температуру для следующей даты
                temp = None
                if self.current_selected_series in self.silo_graph_widget.plot_data_cache:
                    data = self.silo_graph_widget.plot_data_cache[self.current_selected_series]
                    if next_date in data['dates']:
                        temp = data['temperatures'][data['dates'].index(next_date)]
                
                if temp is not None:
                    self.on_silo_graph_point_selected(next_date, temp, self.current_selected_series)
        except ValueError:
            pass

    # === Методы для вкладки мониторинга ===
    
    def update_monitoring_view(self):
        """Обновить таблицу изменений температуры"""
        try:
            silo = self.silo_combo.currentText()
            start_date = self.start_date_edit.date().toString("yyyy-MM-dd")
            end_date = self.end_date_edit.date().toString("yyyy-MM-dd")
            threshold = self.change_threshold_spinbox.value()

            print(f"Мониторинг: силос={silo}, {start_date} - {end_date}, порог={threshold}")

            changes = get_temperature_changes(
                self.db_conn,
                silo if silo != "Все силосы" else None,
                start_date,
                end_date,
                threshold
            )

            print(f"Найдено изменений: {len(changes) if changes else 0}")

            self.changes_table.setRowCount(0)

            if not changes:
                self.changes_label.setText(f"📊 Изменений > {threshold}°C не найдено")
                return

            date_format = "%d.%m.%Y" if self.date_format_with_year else "%d.%m"

            self.changes_table.setRowCount(len(changes))
            for row_idx, change in enumerate(changes):
                self.changes_table.setItem(row_idx, 0, QTableWidgetItem(change['silo']))
                self.changes_table.setItem(row_idx, 1, QTableWidgetItem(str(change['suspension'])))
                self.changes_table.setItem(row_idx, 2, QTableWidgetItem(str(change['sensor'])))

                last_date_obj = datetime.strptime(change['last_date'], "%Y-%m-%d")
                prev_date_obj = datetime.strptime(change['prev_date'], "%Y-%m-%d")

                self.changes_table.setItem(row_idx, 3, QTableWidgetItem(last_date_obj.strftime(date_format)))
                self.changes_table.setItem(row_idx, 4, QTableWidgetItem(f"{change['prev_temp']:.1f}°C"))
                self.changes_table.setItem(row_idx, 5, QTableWidgetItem(f"{change['last_temp']:.1f}°C"))

                delta_item = QTableWidgetItem(f"{change['delta']:+.1f}°C")
                if change['delta'] > 0:
                    delta_item.setBackground(QColor(self.color_hotspot))
                else:
                    delta_item.setBackground(QColor(self.color_normal))
                self.changes_table.setItem(row_idx, 6, delta_item)

                status = "🔥 Нагрев" if change['delta'] > 0 else "❄️ Охлаждение"
                self.changes_table.setItem(row_idx, 7, QTableWidgetItem(status))

            self.changes_label.setText(f"📊 Найдено {len(changes)} изменений > {threshold}°C")
        except Exception as e:
            print(f"Ошибка в update_monitoring_view: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Ошибка", f"Ошибка мониторинга: {e}")

    # === Drag and Drop и загрузка файлов ===
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        self.load_reports_from_paths(files)

    def load_reports_from_paths(self, paths):
        """Загрузить несколько отчетов"""
        total = len(paths)
        success_count = 0
        skip_count = 0
        error_count = 0

        for idx, path in enumerate(paths):
            if not (path.lower().endswith('.csv') or path.lower().endswith('.xlsx')):
                continue

            self.status_label.setText(f"Обработка {idx + 1}/{total}: {path}")
            QApplication.processEvents()

            report_date, data = parse_thermometry_file(path)

            if not (report_date and data):
                error_count += 1
                self.status_label.setText(f"Ошибка парсинга: {path}")
                continue

            if check_date_exists(self.db_conn, report_date):
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Icon.Question)
                msg_box.setText(f"Отчет за дату {report_date} уже существует.")
                msg_box.setInformativeText("Заменить данные?")
                msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                msg_box.setDefaultButton(QMessageBox.StandardButton.No)
                reply = msg_box.exec()

                if reply == QMessageBox.StandardButton.No:
                    skip_count += 1
                    continue
                else:
                    delete_readings_for_date(self.db_conn, report_date)

            insert_readings(self.db_conn, data)
            success_count += 1

        self.populate_silo_filter()
        self.update_date_range()
        self.update_data_view()
        
        # Обновить погодные данные после загрузки нового отчета
        self.refresh_weather_data()
        
        # Проверить смену лидера за новые даты
        self.check_leader_changes()

        msg = f"✅ Загружено: {success_count}"
        if skip_count > 0:
            msg += f" | Пропущено: {skip_count}"
        if error_count > 0:
            msg += f" | Ошибок: {error_count}"
        self.status_label.setText(msg)

    def load_report_dialog(self):
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Выбрать отчеты",
            "",
            "Файлы термометрии (*.csv *.xlsx);;CSV Files (*.csv);;Excel Files (*.xlsx);;All Files (*)"
        )
        if file_paths:
            self.load_reports_from_paths(file_paths)

    def show_email_menu(self):
        """Показать меню почты"""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtCore import QPoint

        try:
            menu = QMenu(self)
            menu.setStyleSheet("""
                QMenu {
                    background-color: #313244;
                    color: #cdd6f4;
                    border-radius: 8px;
                    padding: 8px;
                }
                QMenu::item {
                    padding: 8px 16px;
                    border-radius: 4px;
                }
                QMenu::item:selected {
                    background-color: #45475a;
                }
            """)

            settings_action = menu.addAction("⚙️ Настройки почты...")
            settings_action.triggered.connect(self.email_settings_dialog)

            download_action = menu.addAction("📥 Загрузить отчеты...")
            download_action.triggered.connect(self.email_download_dialog)

            # Показать меню под кнопкой
            pos = self.email_button.mapToGlobal(QPoint(0, self.email_button.height()))
            menu.exec(pos)
        except Exception as e:
            print(f"Ошибка в show_email_menu: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Ошибка", f"Ошибка меню почты: {e}")

    def show_weather_settings(self):
        """Диалог настройки API ключа OpenWeatherMap"""
        try:
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout
            
            dialog = QDialog(self)
            dialog.setWindowTitle("⚙️ Настройка погоды — OpenWeatherMap API")
            dialog.setMinimumWidth(450)
            
            layout = QVBoxLayout()
            layout.setSpacing(10)
            
            # Заголовок
            title_label = QLabel("🌤️ Настройка погодного API")
            title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #89b4fa;")
            layout.addWidget(title_label)
            
            # Описание
            desc_label = QLabel(
                "Для получения погодных данных необходим API ключ OpenWeatherMap.\n"
                "Зарегистрируйтесь на сайте openweathermap.org и получите бесплатный ключ."
            )
            desc_label.setStyleSheet("font-size: 11px; color: #cdd6f4;")
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)
            
            # Поле ввода API ключа
            key_layout = QHBoxLayout()
            key_layout.addWidget(QLabel("API ключ:"))
            self.weather_api_input = QLineEdit()
            self.weather_api_input.setPlaceholderText("Введите API ключ OpenWeatherMap")
            self.weather_api_input.setText(self.config.get("openweathermap_api_key", ""))
            key_layout.addWidget(self.weather_api_input)
            layout.addLayout(key_layout)
            
            # Ссылка
            link_label = QLabel(
                "🔗 <a href='https://home.openweathermap.org/api_keys' style='color: #89b4fa;'>Получить API ключ</a>"
            )
            link_label.setStyleSheet("font-size: 10px;")
            link_label.setOpenExternalLinks(True)
            layout.addWidget(link_label)
            
            # Кнопки
            btn_layout = QHBoxLayout()
            btn_layout.addStretch()
            
            save_btn = QPushButton("💾 Сохранить")
            save_btn.setStyleSheet("background-color: #a6e3a1; color: #1e1e2e; font-weight: bold; padding: 8px 16px;")
            save_btn.clicked.connect(lambda: self.save_weather_settings(dialog))
            btn_layout.addWidget(save_btn)
            
            cancel_btn = QPushButton("Отмена")
            cancel_btn.setStyleSheet("background-color: #6c7086; color: #1e1e2e; padding: 8px 16px;")
            cancel_btn.clicked.connect(dialog.reject)
            btn_layout.addWidget(cancel_btn)
            
            layout.addLayout(btn_layout)
            dialog.setLayout(layout)
            
            dialog.exec()
            
        except Exception as e:
            print(f"Ошибка в show_weather_settings: {e}")
            import traceback
            traceback.print_exc()

    def save_weather_settings(self, dialog):
        """Сохранить настройки погоды"""
        try:
            api_key = self.weather_api_input.text().strip()
            self.config["openweathermap_api_key"] = api_key
            save_config(self.config)
            
            if api_key:
                # Сразу загрузить погоду
                self.refresh_weather_data()
                QMessageBox.information(
                    self, "Настройки сохранены",
                    "✅ API ключ сохранён!\nПогодные данные загружаются..."
                )
            else:
                self.weather_temp_label.setText("Н/Д")
                self.weather_humidity_label.setText("Н/Д")
                self.weather_status_label.setText("API ключ не указан")
                QMessageBox.information(
                    self, "Настройки сохранены",
                    "⚠️ API ключ удалён.\nПогодные данные не будут загружаться."
                )
            
            dialog.accept()
            
        except Exception as e:
            print(f"Ошибка в save_weather_settings: {e}")
            QMessageBox.critical(self, "Ошибка", f"Ошибка сохранения настроек: {e}")

    def refresh_weather_data(self, force=False):
        """
        Обновить погодные данные.
        
        Параметры:
        - force: принудительная загрузка (игнорировать кэш)
        """
        api_key = self.config.get("openweathermap_api_key", "")
        
        if not api_key:
            self.weather_temp_label.setText("Н/Д")
            self.weather_humidity_label.setText("Н/Д")
            self.weather_status_label.setText("⚠️ Нет API ключа")
            return
        
        # Загрузить погоду
        weather = get_weather_data(api_key)
        
        if weather:
            # Сохранить в конфиг
            self.config["weather_last_data"] = weather
            save_config(self.config)
            
            # Обновить отображение
            display = format_weather_display(weather)
            self.weather_temp_label.setText(display['temp_text'])
            self.weather_temp_label.setStyleSheet(
                f"font-size: 18px; font-weight: bold; color: {display['color']}; padding: 4px;"
            )
            self.weather_humidity_label.setText(display['humidity_text'])
            self.weather_status_label.setText(f"🕐 {weather['timestamp']}")
            
            # Установить tooltip
            self.weather_group.setToolTip(display['tooltip'])
        else:
            # Ошибка загрузки - показать последние данные если есть
            last_data = self.config.get("weather_last_data")
            if last_data:
                display = format_weather_display(last_data)
                self.weather_temp_label.setText(display['temp_text'])
                self.weather_humidity_label.setText(display['humidity_text'])
                self.weather_status_label.setText(f"⚠️ Ошибка загрузки (данные от {last_data.get('timestamp', 'неизвестно')})")
            else:
                self.weather_temp_label.setText("Н/Д")
                self.weather_humidity_label.setText("Н/Д")
                self.weather_status_label.setText("❌ Ошибка загрузки")

    def check_leader_changes(self):
        """
        Проверить смену лидера за все даты.
        Использует кэширование - проверяет только новые даты.
        """
        try:
            # Получить последнюю обработанную дату
            last_processed = get_last_processed_leader_date(self.db_conn)
            
            # Получить диапазон дат в БД
            min_date, max_date = get_date_range(self.db_conn)
            
            if not min_date or not max_date:
                return
            
            # Определить диапазон для проверки
            start_date = last_processed if last_processed else min_date
            # Начать со следующего дня после last_processed
            if start_date:
                from datetime import datetime, timedelta
                start_dt = datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=1)
                start_date = start_dt.strftime("%Y-%m-%d")
            
            # Если новые даты есть - проверить
            if start_date <= max_date:
                logging.info(f"Проверка лидеров за период {start_date} - {max_date}")
                changes_count = check_leader_changes_for_period(
                    self.db_conn, start_date, max_date, self.temp_threshold
                )
                if changes_count > 0:
                    logging.info(f"Найдено {changes_count} смен лидера")
                    self.status_label.setText(f"🔄 Найдено {changes_count} смен лидера")
        except Exception as e:
            logging.error(f"Ошибка в check_leader_changes: {e}")

    def email_settings_dialog(self):
        """Диалог настроек почты"""
        try:
            # Загрузка сохранённых настроек
            settings = {
                'login': self.user_settings.get('email_login', ''),
                'password': self.user_settings.get('email_password', ''),
                'imap_server': self.user_settings.get('email_imap_server', 'imap.yandex.ru'),
                'imap_port': int(self.user_settings.get('email_imap_port', '993')),
                'sender_email': self.user_settings.get('email_sender', 'ams10@aminosib.ru'),
                'days_back': int(self.user_settings.get('email_days_back', '30'))
            }

            dialog = EmailSettingsDialog(self, settings)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_settings = dialog.get_settings()

                # Сохранение настроек (пароль в зашифрованном виде - TODO)
                set_user_setting(self.db_conn, 'email_login', new_settings['login'])
                set_user_setting(self.db_conn, 'email_password', new_settings['password'])
                set_user_setting(self.db_conn, 'email_imap_server', new_settings['imap_server'])
                set_user_setting(self.db_conn, 'email_imap_port', str(new_settings['imap_port']))
                set_user_setting(self.db_conn, 'email_sender', new_settings['sender_email'])
                set_user_setting(self.db_conn, 'email_days_back', str(new_settings['days_back']))

                # Обновление user_settings
                self.user_settings.update({
                    'email_login': new_settings['login'],
                    'email_password': new_settings['password'],
                    'email_imap_server': new_settings['imap_server'],
                    'email_imap_port': str(new_settings['imap_port']),
                    'email_sender': new_settings['sender_email'],
                    'email_days_back': str(new_settings['days_back'])
                })

                QMessageBox.information(self, "Успех", "Настройки почты сохранены!")
        except Exception as e:
            print(f"Ошибка в email_settings_dialog: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Ошибка", f"Ошибка настроек почты: {e}")

    def email_download_dialog(self):
        """Диалог загрузки отчетов с почты"""
        try:
            # Проверка настроек
            if not self.user_settings.get('email_login') or not self.user_settings.get('email_password'):
                QMessageBox.warning(self, "Ошибка", "Сначала настройте подключение к почте (кнопка 'Почта' → Настройки)")
                return

            email_settings = {
                'login': self.user_settings.get('email_login', ''),
                'password': self.user_settings.get('email_password', ''),
                'imap_server': self.user_settings.get('email_imap_server', 'imap.yandex.ru'),
                'imap_port': int(self.user_settings.get('email_imap_port', '993')),
                'sender_email': self.user_settings.get('email_sender', 'ams10@aminosib.ru'),
                'days_back': int(self.user_settings.get('email_days_back', '30'))
            }

            dialog = EmailDownloadDialog(self, email_settings)
            
            # Подключить сигнал обновления дат
            dialog.dates_loaded.connect(self.on_email_dates_loaded)
            
            result = dialog.exec()
                
        except Exception as e:
            print(f"Ошибка в email_download_dialog: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Ошибка", f"Ошибка загрузки почты: {e}\n\nСмотрите консоль для деталей")

    def on_email_dates_loaded(self, dates):
        """Обработка дат, загруженных с почты"""
        # Обновить диапазон дат
        self.update_date_range()
        # Обновить таблицу горячих точек
        self.update_data_view()
        # Проверить смену лидера за новые даты
        self.check_leader_changes()


class FullScreen3DDialog(QDialog):
    """Диалог полноэкранной 3D визуализации силоса"""

    def __init__(self, parent, silo, start_date, end_date):
        super().__init__(parent)
        self.setWindowTitle(f"🏭 3D Модель: {silo}")
        self.setMinimumSize(1200, 800)
        self.showMaximized()  # Открыть на весь экран

        self.silo = silo
        self.start_date = start_date
        self.end_date = end_date
        self.db_conn = parent.db_conn

        self.init_ui()
        self.load_3d_model()

    def init_ui(self):
        """Создать интерфейс диалога"""
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        # Панель управления
        control_layout = QHBoxLayout()

        control_layout.addWidget(QLabel("📊 "))
        self.info_label = QLabel("")
        self.info_label.setStyleSheet("font-size: 14px; color: #89b4fa;")
        control_layout.addWidget(self.info_label)

        control_layout.addStretch()

        # Кнопка закрытия
        close_btn = QPushButton("❌ Закрыть")
        close_btn.setStyleSheet("background-color: #f38ba8; color: #1e1e2e; font-weight: bold; padding: 8px 16px;")
        close_btn.clicked.connect(self.close)
        control_layout.addWidget(close_btn)

        layout.addLayout(control_layout)

        # 3D виджет
        if PLOTLY_AVAILABLE:
            self.plotly_widget = PlotlyWidget()
            self.plotly_widget.setMinimumHeight(600)
            layout.addWidget(self.plotly_widget, 1)
        else:
            from plotly_widget import PlotlyPlaceholder
            self.plotly_widget = PlotlyPlaceholder()
            layout.addWidget(self.plotly_widget, 1)

        self.setLayout(layout)

    def load_3d_model(self):
        """Загрузить 3D модель"""
        try:
            df = get_silo_data_with_errors(self.db_conn, self.silo, self.start_date, self.end_date)

            if df.empty:
                self.info_label.setText(f"⚠️ Нет данных для {self.silo}")
                return

            fig = create_silo_3d(df, self.silo, date=None, suspension_range=None)

            self.plotly_widget.load_plotly_figure(fig)

            self.info_label.setText(
                f"✅ {self.silo} | Записей: {len(df)} | "
                f"Дат: {df['date'].nunique()} | "
                f"Датчиков: {len(df.groupby(['suspension', 'sensor']))}"
            )

        except Exception as e:
            print(f"Ошибка в FullScreen3DDialog: {e}")
            import traceback
            traceback.print_exc()
            self.info_label.setText(f"⚠️ Ошибка: {e}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = ThermometryApp()
    ex.show()
    sys.exit(app.exec())
