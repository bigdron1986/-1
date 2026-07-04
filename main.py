# -*- coding: utf-8 -*-
"""
Термометрия — Контроль температуры в силосах
Главный файл приложения (точка входа)
"""

import sys
import os
import logging
import traceback
from datetime import datetime

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog,
                             QHBoxLayout, QComboBox, QDateEdit, QTableWidget, QTableWidgetItem,
                             QGroupBox, QFormLayout, QAbstractItemView, QDoubleSpinBox, QSpinBox,
                             QMessageBox, QGridLayout, QSpacerItem, QSizePolicy, QSplitter, QTabWidget,
                              QCheckBox, QScrollArea, QFrame, QToolBar)
from PyQt6.QtCore import QDate, Qt, QMimeData, QTimer
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent, QAction

from database import (setup_database, get_all_user_settings, set_user_setting)
from plotter import PlotWidget, DEFAULT_PLOT_COLORS
from styles import STYLESHEET
from config import load_config, save_config
from dialogs import ExportDropdownButton

from app.shared import TabContext
from app.hotspots_tab import HotspotsTab, AdvancedPlotWidget
from app.silo_graphs_tab import SiloGraphsTab
from app.monitoring_breaks_tab import MonitoringTab, BreaksTab
from app.model_3d_tab import Model3DTab
from app.hottest_sensors_tab import HottestSensorsTab
from app.email_file import EmailFileService

try:
    from plotly_widget import PlotlyWidget
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


def setup_global_logging():
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f'app_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    logging.info(f"=== Запуск приложения ===")
    logging.info(f"Лог файл: {log_file}")
    logging.info(f"Python: {sys.version}")
    logging.info(f"Рабочая директория: {os.getcwd()}")
    return log_file


def global_exception_handler(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    tb_str = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logging.critical(f"НЕОБРАБОТАННОЕ ИСКЛЮЧЕНИЕ:\n{tb_str}")

    try:
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle("Критическая ошибка")
        msg.setText(f"Произошла непредвиденная ошибка:\n{exc_type.__name__}")
        msg.setInformativeText(str(exc_value))
        msg.setDetailedText(tb_str)
        msg.exec()
    except:
        pass


class PyQtExceptionHandler:
    def __init__(self):
        self._original_hook = None

    def install(self):
        self._original_hook = sys.excepthook
        sys.excepthook = global_exception_handler


class ThermometryApp(QWidget):
    """Главное приложение термометрии"""

    def __init__(self):
        super().__init__()
        logging.info("Инициализация ThermometryApp...")
        try:
            db_conn = setup_database("temperatures.db")
            logging.info("База данных подключена")
        except Exception as e:
            logging.critical(f"Ошибка подключения к БД: {e}")
            raise

        try:
            config = load_config()
            user_settings = get_all_user_settings(db_conn)
            logging.info("Конфигурация загружена")
        except Exception as e:
            logging.critical(f"Ошибка загрузки конфигурации: {e}")
            raise

        self.ctx = TabContext(db_conn, config, user_settings)

        self.setWindowTitle("🌡️ Термометрия — Контроль температуры в силосах")
        self.setGeometry(100, 100, config.get("window_width", 1400), config.get("window_height", 1000))
        self.setMinimumSize(1400, 900)
        self.setAcceptDrops(True)

        logging.info("Настройки загружены, создаю UI...")
        try:
            self.initUI()
            logging.info("UI создан")
        except Exception as e:
            logging.critical(f"Ошибка создания UI: {e}")
            logging.critical(traceback.format_exc())
            raise

        try:
            self.email_service.populate_silo_filter()
            self.email_service.update_date_range()
            self.ctx.hotspots_tab.update_data_view()
            logging.info("Данные загружены")
        except Exception as e:
            logging.error(f"Ошибка загрузки данных: {e}")
            logging.error(traceback.format_exc())

        QTimer.singleShot(1000, self.ctx.hottest_sensors_tab.check_leader_changes)
        self.showMaximized()
        logging.info("Приложение запущено")

    def closeEvent(self, event):
        try:
            self.ctx.config["window_width"] = self.width()
            self.ctx.config["window_height"] = self.height()
            self.ctx.config["start_date"] = self.ctx.start_date_edit.date().toString("yyyy-MM-dd")
            self.ctx.config["end_date"] = self.ctx.end_date_edit.date().toString("yyyy-MM-dd")
            self.ctx.config["active_tab"] = self.ctx.main_tabs.currentIndex()
            self.ctx.config["splitter_sizes"] = self.ctx.main_splitter.sizes()
            save_config(self.ctx.config)

            if self.ctx.temp_threshold_spinbox:
                set_user_setting(self.ctx.db_conn, 'temp_threshold', str(self.ctx.temp_threshold_spinbox.value()))
            if self.ctx.show_year_check:
                set_user_setting(self.ctx.db_conn, 'date_format_with_year', 'true' if self.ctx.show_year_check.isChecked() else 'false')
            if self.ctx.silo_graphs_tab and hasattr(self.ctx.silo_graphs_tab, 'graph_start_date'):
                set_user_setting(self.ctx.db_conn, 'graph_start_date', self.ctx.silo_graphs_tab.graph_start_date)
                set_user_setting(self.ctx.db_conn, 'graph_end_date', self.ctx.silo_graphs_tab.graph_end_date)
            set_user_setting(self.ctx.db_conn, 'color_hotspot', self.ctx.color_hotspot)
            set_user_setting(self.ctx.db_conn, 'color_error', self.ctx.color_error)
            set_user_setting(self.ctx.db_conn, 'color_normal', self.ctx.color_normal)
            set_user_setting(self.ctx.db_conn, 'color_warning', self.ctx.color_warning)

            if self.ctx.db_conn:
                self.ctx.db_conn.close()
                self.ctx.db_conn = None
        except Exception as e:
            logging.error(f"closeEvent error: {e}")
        finally:
            event.accept()
            os._exit(0)

    def initUI(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # === Верхняя панель ===
        top_bar = QHBoxLayout()
        top_bar.setSpacing(15)

        title_label = QLabel("🌡️ Термометрия силосов")
        title_label.setStyleSheet("font-size: 20px; font-weight: bold; color: #89b4fa; padding: 8px;")
        top_bar.addWidget(title_label)
        top_bar.addStretch()

        self.ctx.tabs_combo = QComboBox()
        self.ctx.tabs_combo.addItems([
            "🔥 Горячие точки",
            "📈 Графики по силосам",
            "📊 Мониторинг изменений",
            "⚠️ Обрывы",
            "🏭 3D Модель",
            "🔥 Самые горячие датчики"
        ])
        self.ctx.tabs_combo.setMaximumWidth(250)
        self.ctx.tabs_combo.currentIndexChanged.connect(self._on_tabs_combo_changed)
        self.ctx.tabs_combo.setStyleSheet("""
            QComboBox {
                background-color: #89b4fa;
                color: #1e1e2e;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
        """)
        top_bar.addWidget(self.ctx.tabs_combo)

        # Создаём сервис email/file (должен быть до виджетов, которые его используют)
        self.email_service = EmailFileService(self.ctx)
        self.ctx.email_file_mixin = self.email_service

        self.ctx.export_button = ExportDropdownButton(on_export_callback=self.email_service.handle_export)
        top_bar.addWidget(self.ctx.export_button)

        self.ctx.email_button = QPushButton("📧 Почта ▼")
        self.ctx.email_button.setStyleSheet("""
            QPushButton {
                background-color: #f38ba8;
                color: #1e1e2e;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
        """)
        self.ctx.email_button.setMinimumHeight(32)
        self.ctx.email_button.clicked.connect(self.email_service.show_email_menu)
        top_bar.addWidget(self.ctx.email_button)

        self.ctx.load_button = QPushButton("📂 Загрузить отчеты")
        self.ctx.load_button.setObjectName("loadButton")
        self.ctx.load_button.setMinimumHeight(32)
        self.ctx.load_button.clicked.connect(self.email_service.load_report_dialog)
        top_bar.addWidget(self.ctx.load_button)

        main_layout.addLayout(top_bar)

        # === Панель фильтров ===
        self.ctx.filter_group = QGroupBox("📊 Фильтры данных")
        filter_layout = QVBoxLayout()
        filter_layout.setSpacing(8)

        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(10)

        self.ctx.silo_combo = QComboBox()
        self.ctx.silo_combo.setMinimumWidth(180)
        self.ctx.silo_combo.currentIndexChanged.connect(self.email_service.populate_suspension_filter)

        self.ctx.suspension_combo = QComboBox()
        self.ctx.suspension_combo.setMinimumWidth(140)

        self.ctx.plot_type_combo = QComboBox()
        self.ctx.plot_type_combo.addItems(["По датчикам", "Средняя температура"])
        self.ctx.plot_type_combo.setMinimumWidth(160)

        self.ctx.temp_threshold_spinbox = QDoubleSpinBox()
        self.ctx.temp_threshold_spinbox.setValue(self.ctx.temp_threshold)
        self.ctx.temp_threshold_spinbox.setSuffix(" °C")
        self.ctx.temp_threshold_spinbox.setRange(0, 100)
        self.ctx.temp_threshold_spinbox.setMinimumWidth(90)
        self.ctx.temp_threshold_spinbox.valueChanged.connect(self._on_threshold_changed)

        row1_layout.addWidget(QLabel("Силос:"))
        row1_layout.addWidget(self.ctx.silo_combo)
        row1_layout.addWidget(QLabel("Подвеска:"))
        row1_layout.addWidget(self.ctx.suspension_combo)
        row1_layout.addWidget(QLabel("Тип графика:"))
        row1_layout.addWidget(self.ctx.plot_type_combo)
        row1_layout.addWidget(QLabel("Порог t°:"))
        row1_layout.addWidget(self.ctx.temp_threshold_spinbox)
        row1_layout.addStretch()

        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(10)

        self.ctx.start_date_edit = QDateEdit(calendarPopup=True)
        self.ctx.start_date_edit.setDate(QDate.currentDate().addMonths(-1))
        self.ctx.start_date_edit.setCalendarPopup(True)
        self.ctx.start_date_edit.setMinimumWidth(120)

        self.ctx.end_date_edit = QDateEdit(calendarPopup=True)
        self.ctx.end_date_edit.setDate(QDate.currentDate())
        self.ctx.end_date_edit.setCalendarPopup(True)
        self.ctx.end_date_edit.setMinimumWidth(120)

        if self.ctx.config.get("start_date"):
            self.ctx.start_date_edit.setDate(QDate.fromString(self.ctx.config["start_date"], "yyyy-MM-dd"))
        if self.ctx.config.get("end_date"):
            self.ctx.end_date_edit.setDate(QDate.fromString(self.ctx.config["end_date"], "yyyy-MM-dd"))

        self.ctx.apply_button = QPushButton("✅ Применить фильтры")
        self.ctx.apply_button.setMinimumWidth(160)
        self.ctx.apply_button.setStyleSheet("font-weight: bold; background-color: #a6e3a1; color: #1e1e2e;")
        self.ctx.apply_button.clicked.connect(self.ctx.hotspots_tab.update_data_view)

        row2_layout.addWidget(QLabel("С:"))
        row2_layout.addWidget(self.ctx.start_date_edit)
        row2_layout.addWidget(QLabel("По:"))
        row2_layout.addWidget(self.ctx.end_date_edit)
        row2_layout.addWidget(QLabel("Период:"))

        self.ctx.date_range_label = QLabel("📅 Данные: —")
        self.ctx.date_range_label.setStyleSheet("font-size: 11px; color: #6c7086; padding: 4px;")
        row2_layout.addWidget(self.ctx.date_range_label)

        period_layout = QHBoxLayout()
        period_layout.setSpacing(6)
        self.ctx.period_buttons = []
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
            btn.clicked.connect(lambda checked, d=days: self.email_service.set_period(d))
            period_layout.addWidget(btn)
            self.ctx.period_buttons.append(btn)

        row2_layout.addLayout(period_layout)
        row2_layout.addStretch()
        row2_layout.addWidget(self.ctx.apply_button)

        filter_layout.addLayout(row1_layout)
        filter_layout.addLayout(row2_layout)
        self.ctx.filter_group.setLayout(filter_layout)
        main_layout.addWidget(self.ctx.filter_group)

        # === Статус бар ===
        self.ctx.status_label = QLabel("✅ Готово")
        self.ctx.status_label.setObjectName("statusLabel")
        self.ctx.status_label.setStyleSheet("font-size: 12px; padding: 4px; color: #a6e3a1;")
        main_layout.addWidget(self.ctx.status_label)

        # === Создание вкладок ===
        self.ctx.main_tabs = QTabWidget()

        # Создаём вкладки
        tab_defs = [
            ("🔥 Горячие точки", HotspotsTab, "hotspots_tab"),
            ("📈 Графики по силосам", SiloGraphsTab, "silo_graphs_tab"),
            ("📊 Мониторинг изменений", MonitoringTab, "monitoring_tab"),
            ("⚠️ Обрывы", BreaksTab, "breaks_tab"),
            ("🏭 3D Модель", Model3DTab, "model_3d_tab"),
            ("🔥 Самые горячие датчики", HottestSensorsTab, "hottest_sensors_tab"),
        ]

        for tab_name, tab_cls, ctx_key in tab_defs:
            try:
                logging.info(f"Создание вкладки: {tab_name}")
                tab = tab_cls(self.ctx)
                setattr(self.ctx, ctx_key, tab)
                self.ctx.main_tabs.addTab(tab, tab_name)
                logging.info(f"Вкладка {tab_name} создана успешно")
            except Exception as e:
                logging.error(f"Ошибка создания вкладки {tab_name}: {e}")
                logging.error(traceback.format_exc())
                err_widget = QWidget()
                err_layout = QVBoxLayout()
                err_layout.addWidget(QLabel(f"⚠️ Ошибка загрузки вкладки: {e}"))
                err_widget.setLayout(err_layout)
                self.ctx.main_tabs.addTab(err_widget, tab_name)

        self.ctx.main_tabs.currentChanged.connect(self._on_tab_changed)
        self.ctx.main_tabs.tabBar().setVisible(False)
        main_layout.addWidget(self.ctx.main_tabs, 1)

        if self.ctx.config.get("active_tab"):
            self.ctx.main_tabs.setCurrentIndex(self.ctx.config["active_tab"])
        else:
            self._on_tab_changed(0)

        self.setStyleSheet(STYLESHEET)
        self.setLayout(main_layout)

    def _on_tab_changed(self, index):
        self.ctx.filter_group.setVisible(index != 4)

    def _on_tabs_combo_changed(self, index):
        if self.ctx.main_tabs:
            self.ctx.main_tabs.setCurrentIndex(index)

    def _on_threshold_changed(self, value):
        self.ctx.hotspots_tab.update_data_view()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        file_paths = [url.toLocalFile() for url in event.mimeData().urls()]
        if file_paths:
            self.email_service.load_reports_from_paths(file_paths)

if __name__ == '__main__':
    log_file = setup_global_logging()

    try:
        logging.info("Создание QApplication...")
        app = QApplication(sys.argv)

        exc_handler = PyQtExceptionHandler()
        exc_handler.install()

        logging.info("Создание ThermometryApp...")
        window = ThermometryApp()
        logging.info("Запуск event loop...")
        exit_code = app.exec()
        logging.info(f"Приложение завершено с кодом {exit_code}")
        sys.exit(exit_code)
    except Exception as e:
        logging.critical(f"Фатальная ошибка при запуске: {e}")
        logging.critical(traceback.format_exc())
        sys.exit(1)
