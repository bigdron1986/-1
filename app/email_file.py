# -*- coding: utf-8 -*-
"""Миксин: Email + File loading + Shared utilities"""

import os
import logging
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout,
                             QGroupBox, QSpinBox, QMessageBox, QFileDialog, QDialog,
                             QLineEdit, QTextEdit, QProgressBar, QFormLayout, QCheckBox)
from PyQt6.QtCore import QDate, Qt, QTimer
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from database import (get_unique_silos, get_suspensions_for_silo, get_date_range,
                      get_available_dates, insert_readings, check_date_exists,
                      delete_readings_for_date, get_all_dates, set_user_setting,
                      get_last_processed_leader_date, check_leader_changes_for_period)
from data_parser import parse_thermometry_file
from config import load_config, save_config
from email_dialogs import EmailSettingsDialog, EmailDownloadDialog


class EmailFileService:
    """Сервис: Email, Загрузка файлов, Общие утилиты (composition-based)"""

    def __init__(self, ctx):
        self.ctx = ctx

    def populate_silo_filter(self):
        self.ctx.silo_combo.clear()
        self.ctx.silo_combo.addItem("Все силосы")
        silos = get_unique_silos(self.ctx.db_conn)
        self.ctx.silo_combo.addItems(silos)
        self.populate_suspension_filter()

    def populate_suspension_filter(self):
        self.ctx.suspension_combo.clear()
        self.ctx.suspension_combo.addItem("Все подвески")
        silo = self.ctx.silo_combo.currentText()
        if silo != "Все силосы":
            suspensions = get_suspensions_for_silo(self.ctx.db_conn, silo)
            self.ctx.suspension_combo.addItems([str(s) for s in suspensions])

    def update_date_range(self):
        min_date_str, max_date_str = get_date_range(self.ctx.db_conn)

        if min_date_str and max_date_str:
            min_date = QDate.fromString(min_date_str, "yyyy-MM-dd")
            max_date = QDate.fromString(max_date_str, "yyyy-MM-dd")

            self.ctx.start_date_edit.setMinimumDate(min_date)
            self.ctx.start_date_edit.setMaximumDate(max_date)
            self.ctx.end_date_edit.setMinimumDate(min_date)
            self.ctx.end_date_edit.setMaximumDate(max_date)

            self.ctx.date_range_label.setText(f"📅 Данные: {min_date_str} — {max_date_str}")

            if not self.ctx.config.get("start_date"):
                self.ctx.start_date_edit.setDate(min_date)
            if not self.ctx.config.get("end_date"):
                self.ctx.end_date_edit.setDate(max_date)
        else:
            self.ctx.date_range_label.setText("📅 Данные: нет данных")

    def set_period(self, days):
        for btn in self.ctx.period_buttons:
            btn.setChecked(False)

        today = QDate.currentDate()

        if days == 0:
            all_data = get_readings(self.ctx.db_conn)
            if all_data:
                dates = [row[4] for row in all_data if row[4]]
                if dates:
                    min_date = QDate.fromString(min(dates), "yyyy-MM-dd")
                    self.ctx.start_date_edit.setDate(min_date)
                else:
                    self.ctx.start_date_edit.setDate(today.addYears(-1))
            else:
                self.ctx.start_date_edit.setDate(today.addYears(-1))
            self.ctx.end_date_edit.setDate(today)
        else:
            self.ctx.start_date_edit.setDate(today.addDays(-days + 1))
            self.ctx.end_date_edit.setDate(today)

        self.ctx.hotspots_tab.update_data_view()

    # === File Loading ===

    def load_reports_from_paths(self, file_paths):
        success_count = 0
        skip_count = 0
        error_count = 0

        for file_path in file_paths:
            try:
                report_date, readings = parse_thermometry_file(file_path)

                if not readings:
                    error_count += 1
                    continue

                if check_date_exists(self.ctx.db_conn, report_date):
                    logging.info(f"Дата {report_date} уже существует, замена...")
                    delete_readings_for_date(self.ctx.db_conn, report_date)

                insert_readings(self.ctx.db_conn, readings)
                success_count += 1

            except Exception as e:
                logging.error(f"Ошибка загрузки {file_path}: {e}")
                error_count += 1

        self.populate_silo_filter()
        self.update_date_range()
        self.ctx.hotspots_tab.update_data_view()

        self.ctx.hottest_sensors_tab.check_leader_changes()

        msg = f"✅ Загружено: {success_count}"
        if skip_count > 0:
            msg += f" | Пропущено: {skip_count}"
        if error_count > 0:
            msg += f" | Ошибок: {error_count}"
        self.ctx.status_label.setText(msg)

    def load_report_dialog(self):
        parent = self.ctx.hotspots_tab if self.ctx.hotspots_tab else self.ctx.status_label.parent()
        file_paths, _ = QFileDialog.getOpenFileNames(
            parent,
            "Выбрать отчеты",
            "",
            "Файлы термометрии (*.csv *.xlsx);;CSV Files (*.csv);;Excel Files (*.xlsx);;All Files (*)"
        )
        if file_paths:
            self.load_reports_from_paths(file_paths)

    # === Email ===

    def show_email_menu(self):
        from PyQt6.QtWidgets import QMenu
        parent = self.ctx.hotspots_tab if self.ctx.hotspots_tab else self.ctx.status_label.parent()
        menu = QMenu(parent)
        settings_action = menu.addAction("⚙️ Настройки почты")
        download_action = menu.addAction("📥 Загрузить отчеты")
        settings_action.triggered.connect(self.email_settings_dialog)
        download_action.triggered.connect(self.email_download_dialog)
        menu.exec(self.ctx.email_button.mapToGlobal(self.ctx.email_button.rect().bottomLeft()))

    def email_settings_dialog(self):
        try:
            settings = {
                'login': self.ctx.user_settings.get('email_login', ''),
                'password': self.ctx.user_settings.get('email_password', ''),
                'imap_server': self.ctx.user_settings.get('email_imap_server', 'imap.yandex.ru'),
                'imap_port': int(self.ctx.user_settings.get('email_imap_port', '993')),
                'sender_email': self.ctx.user_settings.get('email_sender', 'ams10@aminosib.ru'),
                'days_back': int(self.ctx.user_settings.get('email_days_back', '365'))
            }

            parent = self.ctx.hotspots_tab if self.ctx.hotspots_tab else self.ctx.status_label.parent()
            dialog = EmailSettingsDialog(parent, settings)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                new_settings = dialog.get_settings()

                set_user_setting(self.ctx.db_conn, 'email_login', new_settings['login'])
                set_user_setting(self.ctx.db_conn, 'email_password', new_settings['password'])
                set_user_setting(self.ctx.db_conn, 'email_imap_server', new_settings['imap_server'])
                set_user_setting(self.ctx.db_conn, 'email_imap_port', str(new_settings['imap_port']))
                set_user_setting(self.ctx.db_conn, 'email_sender', new_settings['sender_email'])
                set_user_setting(self.ctx.db_conn, 'email_days_back', str(new_settings['days_back']))
                set_user_setting(self.ctx.db_conn, 'email_sender', new_settings['sender_email'])

                self.ctx.user_settings.update({
                    'email_login': new_settings['login'],
                    'email_password': new_settings['password'],
                    'email_imap_server': new_settings['imap_server'],
                    'email_imap_port': str(new_settings['imap_port']),
                    'email_sender': new_settings['sender_email'],
                    'email_days_back': str(new_settings['days_back'])
                })

                QMessageBox.information(parent, "Успех", "Настройки почты сохранены!")
        except Exception as e:
            print(f"Ошибка в email_settings_dialog: {e}")

    def email_download_dialog(self):
        try:
            email_settings = {
                'login': self.ctx.user_settings.get('email_login', ''),
                'password': self.ctx.user_settings.get('email_password', ''),
                'imap_server': self.ctx.user_settings.get('email_imap_server', 'imap.yandex.ru'),
                'imap_port': int(self.ctx.user_settings.get('email_imap_port', '993')),
                'sender_email': self.ctx.user_settings.get('email_sender', 'ams10@aminosib.ru'),
                'days_back': int(self.ctx.user_settings.get('email_days_back', '365'))
            }

            parent = self.ctx.hotspots_tab if self.ctx.hotspots_tab else self.ctx.status_label.parent()
            dialog = EmailDownloadDialog(parent, email_settings)
            dialog.dates_loaded.connect(self.on_email_dates_loaded)
            dialog.exec()
        except Exception as e:
            print(f"Ошибка в email_download_dialog: {e}")

    def on_email_dates_loaded(self, dates):
        self.update_date_range()
        self.ctx.hotspots_tab.update_data_view()
        self.ctx.hottest_sensors_tab.check_leader_changes()

    def handle_export(self, export_type):
        if not self.ctx.hotspots_tab:
            return
        if export_type == 'graph':
            self.ctx.hotspots_tab.save_graph_dialog()
        elif export_type == 'hotspots':
            self.ctx.hotspots_tab.export_table_dialog(self.ctx.hotspots_tab.hot_spots_table, "hot_spots")
        elif export_type == 'breaks':
            self.ctx.hotspots_tab.export_table_dialog(self.ctx.breaks_tab.breaks_table, "breaks")
        elif export_type == 'changes':
            self.ctx.hotspots_tab.export_table_dialog(self.ctx.monitoring_tab.changes_table, "changes")

    def on_tab_changed(self, index):
        print(f"on_tab_changed: индекс {index}")

        if hasattr(self.ctx, 'tabs_combo') and self.ctx.tabs_combo:
            self.ctx.tabs_combo.blockSignals(True)
            self.ctx.tabs_combo.setCurrentIndex(index)
            self.ctx.tabs_combo.blockSignals(False)

        if hasattr(self.ctx, 'filter_group') and self.ctx.filter_group:
            if index == 5:
                self.ctx.filter_group.setVisible(False)
            else:
                self.ctx.filter_group.setVisible(True)

        if index == 5:
            print("Переключение на вкладку 'Самые горячие датчики'")
            logging.info("Переключение на вкладку 'Самые горячие датчики'")
            self.ctx.status_label.setText("")
            logging.debug(f"status_label очищен: '{self.ctx.status_label.text()}'")
            if self.ctx.hottest_sensors_tab:
                QTimer.singleShot(100, self.ctx.hottest_sensors_tab.update_hottest_sensors_view)

    def on_tabs_combo_changed(self, index):
        if hasattr(self.ctx, 'main_tabs') and self.ctx.main_tabs:
            self.ctx.main_tabs.setCurrentIndex(index)


