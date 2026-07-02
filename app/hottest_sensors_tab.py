# -*- coding: utf-8 -*-
"""Миксин: вкладка Самые горячие датчики + Лидеры"""

import logging
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout,
                             QGroupBox, QSpinBox, QMessageBox)
from PyQt6.QtCore import QTimer
from database import (get_available_dates, get_all_silos_delta_for_date,
                      get_date_range_for_slider, get_previous_date_with_data,
                      get_all_silos_leaders_for_date, has_any_comment,
                      get_last_processed_leader_date, check_leader_changes_for_period,
                      get_date_range)
from silo_2d_widget import SilosOverviewWidget
from timeline_slider import DateSliderWidget
from comment_dialog import SiloCommentDialog


class HottestSensorsTabMixin:
    """Методы вкладки 6: Самые горячие датчики"""

    def create_hottest_sensors_tab(self):
        """Создать вкладку самых горячих датчиков (2D схема с дельтой)"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)

        control_group = QGroupBox("Параметры отображения")
        control_layout = QHBoxLayout()
        control_layout.setSpacing(15)

        control_layout.addWidget(QLabel("Период на шкале:"))
        self.timeline_days_spinbox = QSpinBox()
        self.timeline_days_spinbox.setValue(7)
        self.timeline_days_spinbox.setSuffix(" дн.")
        self.timeline_days_spinbox.setRange(1, 60)
        self.timeline_days_spinbox.setMinimumWidth(70)
        self.timeline_days_spinbox.valueChanged.connect(
            lambda: self.update_hottest_sensors_view(refresh_timeline=True)
        )
        control_layout.addWidget(self.timeline_days_spinbox)

        self.refresh_silos_btn = QPushButton("🔄 Обновить силоса")
        self.refresh_silos_btn.setObjectName("loadButton")
        self.refresh_silos_btn.clicked.connect(self.force_refresh_silos)
        control_layout.addWidget(self.refresh_silos_btn)

        self.reset_leader_history_btn = QPushButton("🗑️ Сброс истории лидеров")
        self.reset_leader_history_btn.setStyleSheet("background-color: #f38ba8; color: #1e1e2e; font-weight: bold; padding: 8px 16px;")
        self.reset_leader_history_btn.setToolTip("Очистить таблицу истории лидеров для повторной проверки")
        self.reset_leader_history_btn.clicked.connect(self.reset_leader_history)
        control_layout.addWidget(self.reset_leader_history_btn)

        self.reset_db_btn = QPushButton("☢️ Сброс ВСЕЙ базы")
        self.reset_db_btn.setStyleSheet("background-color: #930000; color: #ffffff; font-weight: bold; padding: 8px 16px;")
        self.reset_db_btn.setToolTip("Полностью удалить базу данных (все показания, комментарии, историю)")
        self.reset_db_btn.clicked.connect(self.reset_database_full)
        control_layout.addWidget(self.reset_db_btn)

        control_layout.addStretch()
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        self.silos_overview = SilosOverviewWidget()
        self.silos_overview.silo_clicked.connect(self.on_silo_clicked)
        layout.addWidget(self.silos_overview, 1)

        self.timeline_slider = DateSliderWidget()
        self.timeline_slider.date_selected.connect(self.on_timeline_date_selected)
        self.timeline_slider.setMinimumHeight(80)
        layout.addWidget(self.timeline_slider)

        widget.setLayout(layout)
        QTimer.singleShot(200, self.update_hottest_sensors_view)
        QTimer.singleShot(300, lambda: self.update_hottest_sensors_view(refresh_timeline=True))
        return widget

    def on_timeline_date_selected(self, date):
        """Обработка выбора даты на шкале"""
        self.update_hottest_sensors_view(selected_date=date, refresh_timeline=False)

    def on_silo_clicked(self, silo_name, date):
        """Обработка клика по силосу"""
        dialog = SiloCommentDialog(self, silo_name, date, self.db_conn)
        if dialog.exec() == dialog.DialogCode.Accepted:
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
                    self.db_conn.close()
                    import os
                    db_path = "temperatures.db"
                    if os.path.exists(db_path):
                        os.remove(db_path)
                        logging.info(f"База данных {db_path} удалена")

                    self.db_conn = setup_database(db_path)
                    logging.info("База данных создана заново")
                    self.status_label.setText("🗑️ База данных сброшена")

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
            threshold = 1.0
            timeline_days = self.timeline_days_spinbox.value() if hasattr(self, 'timeline_days_spinbox') else 7

            if not selected_date:
                all_dates = get_available_dates(self.db_conn)
                if not all_dates:
                    self.silos_overview.update_silos({})
                    return
                selected_date = all_dates[-1]

            if refresh_timeline and hasattr(self, 'timeline_slider'):
                all_dates = get_available_dates(self.db_conn)
                try:
                    end_dt = datetime.strptime(selected_date, "%Y-%m-%d")
                    start_dt = end_dt - timedelta(days=timeline_days)
                    start_date_str = start_dt.strftime("%Y-%m-%d")
                    dates_range = get_date_range_for_slider(self.db_conn, start_date_str, selected_date)
                    self.timeline_slider.set_dates(dates_range, selected_date)
                except:
                    self.timeline_slider.set_dates(all_dates, selected_date)
            elif hasattr(self, 'timeline_slider'):
                self.timeline_slider.update_selection(selected_date)

            print(f"Дельта температур: дата={selected_date}, порог={threshold}, период={timeline_days} дн.")

            silos_delta_data = get_all_silos_delta_for_date(self.db_conn, selected_date)

            print(f"Получено данных по силосам: {len(silos_delta_data) if silos_delta_data else 0}")
            if silos_delta_data:
                print(f"Силоса: {list(silos_delta_data.keys())}")

            if not silos_delta_data:
                self.silos_overview.update_silos({})
                return

            comments = {}
            for silo in silos_delta_data.keys():
                comments[silo] = has_any_comment(self.db_conn, silo)

            print(f"Комментарии: {comments}")

            current_leaders = get_all_silos_leaders_for_date(self.db_conn, selected_date, threshold)
            prev_date = get_previous_date_with_data(self.db_conn, selected_date)
            previous_leaders = {}
            if prev_date:
                previous_leaders = get_all_silos_leaders_for_date(self.db_conn, prev_date, threshold)

            print(f"Лидеры по силосам: {list(current_leaders.keys())}")

            self.silos_overview.delta_threshold = threshold
            self.silos_overview.update_silos(silos_delta_data, date=selected_date, comments=comments, previous_leaders=previous_leaders, current_leaders=current_leaders)

        except Exception as e:
            print(f"Ошибка в update_hottest_sensors_view: {e}")
            import traceback
            traceback.print_exc()

    def check_leader_changes(self):
        """
        Проверить смену лидера за все даты.
        Использует кэширование - проверяет только новые даты.
        """
        try:
            last_processed = get_last_processed_leader_date(self.db_conn)
            min_date, max_date = get_date_range(self.db_conn)

            if not min_date or not max_date:
                return

            start_date = last_processed if last_processed else min_date
            if start_date:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=1)
                start_date = start_dt.strftime("%Y-%m-%d")

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
