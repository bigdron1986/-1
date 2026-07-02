# -*- coding: utf-8 -*-
"""Миксин: вкладка Графики по силосам"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout,
                             QGroupBox, QComboBox, QScrollArea, QMessageBox, QDialog)
from PyQt6.QtCore import Qt
from datetime import datetime
from database import (get_sensor_history_with_dates, get_suspensions_for_silo,
                      set_user_setting)
from dialogs import SiloHotspotsDialog
from app.hotspots_tab import AdvancedPlotWidget


class SiloGraphsTabMixin:
    """Методы вкладки 2: Графики по силосам"""

    def create_silo_graphs_tab(self):
        """Создать вкладку графиков по нескольким силосам"""
        widget = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(8, 8, 8, 8)

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

        self.silo_graph_widget = AdvancedPlotWidget()
        self.silo_graph_widget.on_point_selected = self.on_silo_graph_point_selected
        layout.addWidget(self.silo_graph_widget, 1)

        info_layout = QHBoxLayout()
        self.silo_graph_info = QLabel("Данные не выбраны. Нажмите кнопку выше для выбора.")
        self.silo_graph_info.setStyleSheet("font-size: 11px; color: #6c7086; padding: 4px;")
        info_layout.addWidget(self.silo_graph_info, 1)
        layout.addLayout(info_layout)

        self.point_info_group = QGroupBox("📍 Значения в точке")
        point_info_layout = QVBoxLayout()
        point_info_layout.setSpacing(8)

        date_row_layout = QHBoxLayout()
        self.prev_date_btn = QPushButton("◀")
        self.prev_date_btn.setMaximumWidth(30)
        self.prev_date_btn.setStyleSheet("font-size: 12px; font-weight: bold; padding: 4px;")
        self.prev_date_btn.clicked.connect(self.navigate_to_prev_date)
        self.prev_date_btn.setEnabled(False)
        date_row_layout.addWidget(self.prev_date_btn)

        self.point_date_label = QLabel("📍 Дата: —")
        self.point_date_label.setStyleSheet("font-size: 12px; color: #cdd6f4; font-weight: bold;")
        self.point_date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        date_row_layout.addWidget(self.point_date_label, 1)

        self.next_date_btn = QPushButton("▶")
        self.next_date_btn.setMaximumWidth(30)
        self.next_date_btn.setStyleSheet("font-size: 12px; font-weight: bold; padding: 4px;")
        self.next_date_btn.clicked.connect(self.navigate_to_next_date)
        self.next_date_btn.setEnabled(False)
        date_row_layout.addWidget(self.next_date_btn)
        date_row_layout.addStretch()
        point_info_layout.addLayout(date_row_layout)

        scroll_controls_layout = QHBoxLayout()
        scroll_controls_layout.setSpacing(4)

        self.scroll_up_btn = QPushButton("▲")
        self.scroll_up_btn.setMaximumWidth(30)
        self.scroll_up_btn.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px;")
        self.scroll_up_btn.clicked.connect(self.scroll_values_up)
        scroll_controls_layout.addWidget(self.scroll_up_btn)

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
        scroll_controls_layout.addWidget(self.point_values_scroll, 1)

        self.scroll_down_btn = QPushButton("▼")
        self.scroll_down_btn.setMaximumWidth(30)
        self.scroll_down_btn.setStyleSheet("font-size: 14px; font-weight: bold; padding: 4px;")
        self.scroll_down_btn.clicked.connect(self.scroll_values_down)
        scroll_controls_layout.addWidget(self.scroll_down_btn)
        point_info_layout.addLayout(scroll_controls_layout)

        values_per_row_layout = QHBoxLayout()
        values_per_row_layout.addWidget(QLabel("Значений в строке:"))
        self.values_per_row_combo = QComboBox()
        self.values_per_row_combo.addItems(["3", "6", "9"])
        self.values_per_row_combo.setCurrentText("6")
        self.values_per_row_combo.setMaximumWidth(60)
        self.values_per_row_combo.currentTextChanged.connect(self.update_values_display)
        values_per_row_layout.addWidget(self.values_per_row_combo)
        values_per_row_layout.addStretch()
        point_info_layout.addLayout(values_per_row_layout)

        hint_label = QLabel("💡 Кликните на точку графика для просмотра значений")
        hint_label.setStyleSheet("font-size: 11px; color: #6c7086;")
        point_info_layout.addWidget(hint_label)

        self.point_info_group.setLayout(point_info_layout)
        layout.addWidget(self.point_info_group)

        self.selected_silo = None
        self.selected_points = []
        self.graph_start_date = None
        self.graph_end_date = None

        widget.setLayout(layout)
        return widget

    def show_silo_select_dialog(self):
        """Показать диалог выбора силоса и горячих точек"""
        try:
            dialog = SiloHotspotsDialog(
                self.db_conn,
                self,
                self.temp_threshold_spinbox.value(),
                last_silo=self.selected_silo,
                last_points=self.selected_points
            )
            dialog.start_date.setDate(self.start_date_edit.date())
            dialog.end_date.setDate(self.end_date_edit.date())

            result = dialog.exec()
            if result == QDialog.DialogCode.Accepted:
                data = dialog.get_data()
                self.selected_silo = data['silo']
                self.selected_points = data['points']
                self.graph_start_date = data['start_date']
                self.graph_end_date = data['end_date']

                self.silo_graph_info.setText(
                    f"✅ Силос: {self.selected_silo} | Точек: {len(self.selected_points)} | "
                    f"Период: {self.graph_start_date} — {self.graph_end_date}"
                )
                self.build_multi_silo_graph()
        except Exception as e:
            print(f"Ошибка в show_silo_select_dialog: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Ошибка", f"Произошла ошибка: {e}")

    def build_multi_silo_graph(self):
        """Построить график по выбранным горячим точкам"""
        try:
            if not self.selected_silo or not self.selected_points:
                self.status_label.setText("Выберите силос и горячие точки")
                return

            plot_series = {}
            for susp, sensor in self.selected_points:
                history_data = get_sensor_history_with_dates(
                    self.db_conn, self.selected_silo, susp, sensor,
                    self.graph_start_date, self.graph_end_date
                )
                filtered_data = [(d, t) for d, t in history_data if t != 71.2]
                series_name = f"Подв. {susp}, Датчик {sensor}"
                plot_series[series_name] = filtered_data

            self.silo_graph_widget.plot_data(plot_series)
            self.status_label.setText(f"Построен график для {len(self.selected_points)} точек")

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
            self.current_selected_date = date
            self.current_selected_series = series

            if self.date_format_with_year:
                formatted_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m.%Y")
            else:
                formatted_date = datetime.strptime(date, "%Y-%m-%d").strftime("%d.%m")

            self.point_date_label.setText(f"📍 Дата: {formatted_date}")

            all_dates = self.get_all_dates_for_current_series()
            if all_dates and date in all_dates:
                current_idx = all_dates.index(date)
                self.prev_date_btn.setEnabled(current_idx > 0)
                self.next_date_btn.setEnabled(current_idx < len(all_dates) - 1)

            self.update_values_display()
        except Exception as e:
            print(f"Ошибка в on_silo_graph_point_selected: {e}")
            import traceback
            traceback.print_exc()

    def update_values_display(self):
        """Обновить отображение значений с текущими настройками"""
        if not hasattr(self, 'current_selected_date') or not hasattr(self, 'point_values_layout'):
            return

        while self.point_values_layout.count():
            item = self.point_values_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        try:
            values_per_row = int(self.values_per_row_combo.currentText())
        except:
            values_per_row = 6

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
            selected_data = [(name, temp_val, color) for name, temp_val, color in found_values if name == self.current_selected_series]
            other_data = [(name, temp_val, color) for name, temp_val, color in found_values if name != self.current_selected_series]
            all_items = []
            for name, temp_val, color in selected_data:
                all_items.append(('selected', name, temp_val, color))
            for name, temp_val, color in other_data:
                all_items.append(('normal', name, temp_val, color))

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

                if col >= values_per_row and i < len(all_items) - 1:
                    self.point_values_layout.addLayout(grid_layout)
                    grid_layout = QHBoxLayout()
                    grid_layout.setSpacing(4)
                    grid_layout.setContentsMargins(0, 0, 0, 0)
                    col = 0

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
        scrollbar = self.point_values_scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() - scrollbar.singleStep() * 3)

    def scroll_values_down(self):
        scrollbar = self.point_values_scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() + scrollbar.singleStep() * 3)

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
                temp = None
                if self.current_selected_series in self.silo_graph_widget.plot_data_cache:
                    data = self.silo_graph_widget.plot_data_cache[self.current_selected_series]
                    if next_date in data['dates']:
                        temp = data['temperatures'][data['dates'].index(next_date)]
                if temp is not None:
                    self.on_silo_graph_point_selected(next_date, temp, self.current_selected_series)
        except ValueError:
            pass
