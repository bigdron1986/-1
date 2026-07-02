# -*- coding: utf-8 -*-
"""
Термометрия — Контроль температуры в силосах
Главный файл приложения (точка входа)
"""

import sys
import os
import logging
import traceback
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog,
                             QHBoxLayout, QComboBox, QDateEdit, QTableWidget, QTableWidgetItem,
                             QGroupBox, QFormLayout, QAbstractItemView, QDoubleSpinBox, QSpinBox,
                             QMessageBox, QGridLayout, QSpacerItem, QSizePolicy, QSplitter, QTabWidget,
                             QCheckBox, QScrollArea, QFrame, QToolBar, QDialog)
from PyQt6.QtCore import QDate, Qt, QMimeData, QTimer, QUrl
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent, QAction

from database import (setup_database, get_all_user_settings, set_user_setting)
from plotter import PlotWidget, DEFAULT_PLOT_COLORS
from styles import STYLESHEET
from config import load_config, save_config
from dialogs import ExportDropdownButton

# Импортируем миксины
from app.hotspots_tab import HotspotsTabMixin, AdvancedPlotWidget
from app.silo_graphs_tab import SiloGraphsTabMixin
from app.monitoring_breaks_tab import MonitoringTabMixin, BreaksTabMixin
from app.model_3d_tab import Model3DTabMixin
from app.hottest_sensors_tab import HottestSensorsTabMixin
from app.email_file import EmailFileMixin

# Импортируем FullScreen3DDialog
try:
    from plotly_widget import PlotlyWidget
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


def setup_global_logging():
    """Настроить глобальное логирование до создания приложения"""
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
    """Глобальный обработчик необработанных исключений"""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return

    tb_str = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logging.critical(f"НЕОБРАБОТАННОЕ ИСКЛЮЧЕНИЕ:\n{tb_str}")

    # Показать пользователю
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
    """Перехватчик исключений для слотов PyQt"""
    def __init__(self):
        self._original_hook = None

    def install(self):
        """Установить перехватчик"""
        self._original_hook = sys.excepthook
        sys.excepthook = global_exception_handler


class ThermometryApp(
    HotspotsTabMixin,
    SiloGraphsTabMixin,
    MonitoringTabMixin,
    BreaksTabMixin,
    Model3DTabMixin,
    HottestSensorsTabMixin,
    EmailFileMixin,
    QWidget
):
    """Главное приложение термометрии"""
    
    def __init__(self):
        super().__init__()
        logging.info("Инициализация ThermometryApp...")
        try:
            self.db_conn = setup_database("temperatures.db")
            logging.info("База данных подключена")
        except Exception as e:
            logging.critical(f"Ошибка подключения к БД: {e}")
            raise

        try:
            self.config = load_config()
            self.user_settings = get_all_user_settings(self.db_conn)
            logging.info("Конфигурация загружена")
        except Exception as e:
            logging.critical(f"Ошибка загрузки конфигурации: {e}")
            raise
        
        self.setWindowTitle("🌡️ Термометрия — Контроль температуры в силосах")
        self.setGeometry(100, 100, self.config.get("window_width", 1400), self.config.get("window_height", 1000))
        self.setMinimumSize(1400, 900)
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
        
        logging.info("Настройки загружены, создаю UI...")
        try:
            self.initUI()
            logging.info("UI создан")
        except Exception as e:
            logging.critical(f"Ошибка создания UI: {e}")
            logging.critical(traceback.format_exc())
            raise

        try:
            self.populate_silo_filter()
            self.update_date_range()
            self.update_data_view()
            logging.info("Данные загружены")
        except Exception as e:
            logging.error(f"Ошибка загрузки данных: {e}")
            logging.error(traceback.format_exc())
        
        QTimer.singleShot(1000, self.check_leader_changes)
        self.showMaximized()
        logging.info("Приложение запущено")

    def closeEvent(self, event):
        """Сохранение настроек при закрытии"""
        try:
            self.config["window_width"] = self.width()
            self.config["window_height"] = self.height()
            self.config["start_date"] = self.start_date_edit.date().toString("yyyy-MM-dd")
            self.config["end_date"] = self.end_date_edit.date().toString("yyyy-MM-dd")
            self.config["active_tab"] = self.main_tabs.currentIndex()
            self.config["splitter_sizes"] = self.main_splitter.sizes()
            save_config(self.config)

            if hasattr(self, 'temp_threshold_spinbox'):
                set_user_setting(self.db_conn, 'temp_threshold', str(self.temp_threshold_spinbox.value()))
            if hasattr(self, 'change_threshold_spinbox'):
                set_user_setting(self.db_conn, 'change_threshold', str(self.change_threshold_spinbox.value()))
            if hasattr(self, 'show_year_check'):
                set_user_setting(self.db_conn, 'date_format_with_year', 'true' if self.show_year_check.isChecked() else 'false')
            if hasattr(self, 'graph_start_date') and self.graph_start_date:
                set_user_setting(self.db_conn, 'graph_start_date', self.graph_start_date)
            if hasattr(self, 'graph_end_date') and self.graph_end_date:
                set_user_setting(self.db_conn, 'graph_end_date', self.graph_end_date)
            if hasattr(self, 'color_hotspot'):
                set_user_setting(self.db_conn, 'color_hotspot', self.color_hotspot)
                set_user_setting(self.db_conn, 'color_error', self.color_error)
                set_user_setting(self.db_conn, 'color_normal', self.color_normal)
                set_user_setting(self.db_conn, 'color_warning', self.color_warning)

            if self.db_conn:
                self.db_conn.close()
                self.db_conn = None
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
        """)
        top_bar.addWidget(self.tabs_combo)

        self.export_button = ExportDropdownButton(on_export_callback=self.handle_export)
        top_bar.addWidget(self.export_button)

        self.email_button = QPushButton("📧 Почта ▼")
        self.email_button.setStyleSheet("""
            QPushButton {
                background-color: #f38ba8;
                color: #1e1e2e;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
            }
        """)
        self.email_button.setMinimumHeight(32)
        self.email_button.clicked.connect(self.show_email_menu)
        top_bar.addWidget(self.email_button)

        self.load_button = QPushButton("📂 Загрузить отчеты")
        self.load_button.setObjectName("loadButton")
        self.load_button.setMinimumHeight(32)
        self.load_button.clicked.connect(self.load_report_dialog)
        top_bar.addWidget(self.load_button)

        main_layout.addLayout(top_bar)

        # === Панель фильтров ===
        self.filter_group = QGroupBox("📊 Фильтры данных")
        filter_layout = QVBoxLayout()
        filter_layout.setSpacing(8)

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

        self.date_range_label = QLabel("📅 Данные: —")
        self.date_range_label.setStyleSheet("font-size: 11px; color: #6c7086; padding: 4px;")
        row2_layout.addWidget(self.date_range_label)

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

        # === Основные вкладки ===
        self.main_tabs = QTabWidget()

        tab_creators = [
            ("🔥 Горячие точки", self.create_hotspots_tab),
            ("📈 Графики по силосам", self.create_silo_graphs_tab),
            ("📊 Мониторинг изменений", self.create_monitoring_tab),
            ("⚠️ Обрывы", self.create_breaks_tab),
            ("🏭 3D Модель", self.create_3d_model_tab),
            ("🔥 Самые горячие датчики", self.create_hottest_sensors_tab),
        ]

        for tab_name, creator in tab_creators:
            try:
                logging.info(f"Создание вкладки: {tab_name}")
                self.main_tabs.addTab(creator(), tab_name)
                logging.info(f"Вкладка {tab_name} создана успешно")
            except Exception as e:
                logging.error(f"Ошибка создания вкладки {tab_name}: {e}")
                logging.error(traceback.format_exc())
                # Создать заглушку
                err_widget = QWidget()
                err_layout = QVBoxLayout()
                err_layout.addWidget(QLabel(f"⚠️ Ошибка загрузки вкладки: {e}"))
                err_widget.setLayout(err_layout)
                self.main_tabs.addTab(err_widget, tab_name)

        self.main_tabs.currentChanged.connect(self.on_tab_changed)
        self.main_tabs.tabBar().setVisible(False)
        main_layout.addWidget(self.main_tabs, 1)

        if self.config.get("active_tab"):
            self.main_tabs.setCurrentIndex(self.config["active_tab"])
        else:
            self.on_tab_changed(0)

        self.setStyleSheet(STYLESHEET)
        self.setLayout(main_layout)

    def on_tab_changed(self, index):
        """Скрыть фильтры на вкладке 3D (индекс 4)"""
        if hasattr(self, 'filter_group'):
            self.filter_group.setVisible(index != 4)


# === FullScreen3DDialog (нужен для model_3d_tab) ===

class FullScreen3DDialog(QDialog):
    """Диалог полноэкранной 3D визуализации силоса"""

    def __init__(self, parent, silo, start_date, end_date):
        super().__init__(parent)
        self.setWindowTitle(f"🏭 3D Модель: {silo}")
        self.setMinimumSize(1200, 800)
        self.showMaximized()

        self.silo = silo
        self.start_date = start_date
        self.end_date = end_date
        self.db_conn = parent.db_conn

        self.init_ui()
        self.load_3d_model()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)

        self.info_label = QLabel(f"Загрузка 3D модели: {self.silo}...")
        self.info_label.setStyleSheet("font-size: 14px; color: #89b4fa; padding: 8px;")
        layout.addWidget(self.info_label)

        if PLOTLY_AVAILABLE:
            self.plotly_widget = PlotlyWidget()
            layout.addWidget(self.plotly_widget, 1)
        else:
            from plotly_widget import PlotlyPlaceholder
            layout.addWidget(PlotlyPlaceholder())

        close_btn = QPushButton("Закрыть")
        close_btn.setStyleSheet("background-color: #45475a; padding: 10px 20px; font-size: 14px;")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

        self.setLayout(layout)

    def load_3d_model(self):
        from silo_3d import create_silo_3d, get_silo_data_with_errors
        try:
            df = get_silo_data_with_errors(self.db_conn, self.silo, self.start_date, self.end_date)
            if df.empty:
                self.info_label.setText(f"⚠️ Нет данных для {self.silo}")
                return

            fig = create_silo_3d(df, self.silo, date=None, suspension_range=None)
            if PLOTLY_AVAILABLE:
                self.plotly_widget.load_plotly_figure(fig)
            self.info_label.setText(f"✅ {self.silo} | {len(df)} записей | {df['date'].nunique()} дат")
        except Exception as e:
            self.info_label.setText(f"⚠️ Ошибка: {e}")

    def closeEvent(self, event):
        """Быстрое закрытие 3D диалога"""
        if hasattr(self, 'plotly_widget') and self.plotly_widget:
            if hasattr(self.plotly_widget, 'cleanup'):
                self.plotly_widget.cleanup()
            if hasattr(self.plotly_widget, 'browser'):
                browser = self.plotly_widget.browser
                browser.blockSignals(True)
                browser.setUrl(QUrl('about:blank'))
                if browser.page():
                    browser.page().deleteLater()
                browser.deleteLater()
        event.accept()


if __name__ == '__main__':
    # Настроить логирование ДО создания приложения
    log_file = setup_global_logging()

    try:
        logging.info("Создание QApplication...")
        app = QApplication(sys.argv)

        # Установить глобальный обработчик исключений (после создания QApplication)
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
