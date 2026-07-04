# -*- coding: utf-8 -*-
"""Миксин: вкладка 3D Модель"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout,
                             QGroupBox, QComboBox, QDateEdit, QMessageBox, QDialog)
from PyQt6.QtCore import QDate, QUrl
from database import get_unique_silos, get_last_n_dates
from silo_3d import create_silo_3d, get_silo_data_with_errors

try:
    from plotly_widget import PlotlyWidget
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


class FullScreen3DDialog(QDialog):
    def __init__(self, parent, silo, start_date, end_date):
        super().__init__(parent)
        self.setWindowTitle(f"🏭 3D Модель: {silo}")
        self.setMinimumSize(1200, 800)
        self.showMaximized()

        self.silo = silo
        self.start_date = start_date
        self.end_date = end_date
        self.db_conn = parent.ctx.db_conn if hasattr(parent, 'ctx') else parent.db_conn

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


class Model3DTab(QWidget):
    """Вкладка 5: 3D Модель силоса"""

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self._build()

    def _build(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

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

        control_group = QGroupBox("🎛️ Параметры 3D визуализации")
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)

        control_layout.addWidget(QLabel("Силос:"))
        self.silo_3d_combo = QComboBox()
        self.silo_3d_combo.setMinimumWidth(150)
        self.silo_3d_combo.currentTextChanged.connect(self._update_model)
        control_layout.addWidget(self.silo_3d_combo)

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

        self.update_3d_btn = QPushButton("🔄 Обновить")
        self.update_3d_btn.setObjectName("loadButton")
        self.update_3d_btn.clicked.connect(self._update_model)
        control_layout.addWidget(self.update_3d_btn)

        self.fullscreen_3d_btn = QPushButton("🖥️ На весь экран")
        self.fullscreen_3d_btn.setStyleSheet("background-color: #89b4fa; color: #1e1e2e; font-weight: bold; padding: 8px 16px;")
        self.fullscreen_3d_btn.clicked.connect(self.open_3d_fullscreen)
        control_layout.addWidget(self.fullscreen_3d_btn)

        control_layout.addStretch()
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        self.silo_3d_info = QLabel("ℹ️ Выберите силос и нажмите 'Обновить'")
        self.silo_3d_info.setStyleSheet("font-size: 12px; color: #6c7086; padding: 4px;")
        layout.addWidget(self.silo_3d_info)

        if PLOTLY_AVAILABLE:
            self.silo_3d_widget = PlotlyWidget()
            self.silo_3d_widget.setMinimumHeight(500)
            layout.addWidget(self.silo_3d_widget, 1)
        else:
            from plotly_widget import PlotlyPlaceholder
            placeholder = PlotlyPlaceholder()
            layout.addWidget(placeholder, 1)

        self.setLayout(layout)
        self._populate_silo_combo()
        self._set_dates_from_db()
        if self.silo_3d_combo.count() > 0:
            self._update_model()

    def _set_dates_from_db(self):
        try:
            dates = get_last_n_dates(self.ctx.db_conn, 2)
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

    def _populate_silo_combo(self):
        self.silo_3d_combo.clear()
        silos = get_unique_silos(self.ctx.db_conn)
        self.silo_3d_combo.addItems(silos)

    def _update_model(self):
        try:
            silo = self.silo_3d_combo.currentText()
            start_date = self.silo_3d_start_date.date().toString("yyyy-MM-dd")
            end_date = self.silo_3d_end_date.date().toString("yyyy-MM-dd")

            df = get_silo_data_with_errors(self.ctx.db_conn, silo, start_date, end_date)

            if df.empty:
                self.silo_3d_info.setText(f"⚠️ Нет данных для {silo} в выбранном диапазоне")
                return

            fig = create_silo_3d(df, silo, date=None, suspension_range=None)

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
        silo = self.silo_3d_combo.currentText()
        start_date = self.silo_3d_start_date.date().toString("yyyy-MM-dd")
        end_date = self.silo_3d_end_date.date().toString("yyyy-MM-dd")
        dialog = FullScreen3DDialog(self, silo, start_date, end_date)
        dialog.exec()


