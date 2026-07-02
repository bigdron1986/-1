# -*- coding: utf-8 -*-
"""Миксин: вкладка Горячие точки + общие методы обновления данных"""

import logging
import pandas as pd
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QFileDialog,
                             QHBoxLayout, QComboBox, QDateEdit, QTableWidget, QTableWidgetItem,
                             QGroupBox, QFormLayout, QAbstractItemView, QDoubleSpinBox, QSpinBox,
                             QMessageBox, QGridLayout, QSpacerItem, QSizePolicy, QSplitter, QTabWidget,
                             QCheckBox, QScrollArea, QFrame, QToolBar, QDialog, QColorDialog)
from PyQt6.QtCore import QDate, Qt, QMimeData
from PyQt6.QtGui import QColor, QDragEnterEvent, QDropEvent, QAction
from database import (get_readings, get_sensor_history, get_sensor_history_with_dates,
                      get_suspensions_for_silo, get_average_temp_by_silo,
                      get_average_temp_by_suspension, get_date_range, get_available_dates,
                      get_user_setting, set_user_setting, get_all_user_settings,
                      get_hot_spots_for_date, get_temperature_changes, get_silo_list,
                      get_hot_spots_for_silo, get_hottest_sensors_by_silo, get_all_sensors_for_silo,
                      get_all_silos_delta_for_date, get_date_range_for_slider, get_last_n_dates,
                      get_hottest_sensor_for_date, get_hottest_sensor_for_silo_date, get_all_silos_leaders_for_date,
                      get_previous_date_with_data, get_sensor_temperature_on_date,
                      get_leader_change_info, has_comment, has_any_comment, get_comment,
                      get_unique_silos, insert_readings, check_date_exists, delete_readings_for_date)
from plotter import PlotWidget, DEFAULT_PLOT_COLORS
from dialogs import SiloHotspotsDialog, ExportDropdownButton


class AdvancedPlotWidget(PlotWidget):
    """Расширенный виджет графика с поддержкой зума и панели значений"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.zoom_level = 1.0
        self.selected_point_info = None
        
    def enable_zoom(self, zoom_in=True):
        if zoom_in:
            self.zoom_level = min(2.0, self.zoom_level * 1.2)
        else:
            self.zoom_level = max(0.5, self.zoom_level / 1.2)
        self.figure.set_size_inches(
            self.figure.get_figwidth() * (1.2 if zoom_in else 0.83),
            self.figure.get_figheight() * (1.2 if zoom_in else 0.83)
        )
        self.canvas.draw()
    
    def reset_zoom(self):
        self.zoom_level = 1.0
        self.figure.set_size_inches(5, 3)
        self.canvas.draw()


class HotspotsTabMixin:
    """Методы вкладки 1: Горячие точки"""

    def create_hotspots_tab(self):
        """Создать вкладку горячих точек"""
        widget = QWidget()
        layout = QHBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setSpacing(0)
        left_layout.setContentsMargins(0, 0, 0, 0)

        settings_layout = QHBoxLayout()
        self.show_year_check = QCheckBox("Показывать год в дате")
        self.show_year_check.setChecked(self.date_format_with_year)
        self.show_year_check.stateChanged.connect(self.update_data_view)
        settings_layout.addWidget(self.show_year_check)

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

        graph_group = QGroupBox("📈 График динамики температур")
        graph_layout = QVBoxLayout()
        graph_layout.setSpacing(5)

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

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.main_splitter.setObjectName("mainSplitter")
        self.main_splitter.addWidget(left_widget)
        self.main_splitter.addWidget(graph_group)
        self.main_splitter.setSizes([490, 910])
        self.main_splitter.setHandleWidth(6)
        self.main_splitter.setStyleSheet("QSplitter::handle { background-color: #45475a; border-radius: 2px; }")

        layout.addWidget(self.main_splitter)
        widget.setLayout(layout)

        if self.config.get("splitter_sizes"):
            self.main_splitter.setSizes(self.config["splitter_sizes"])

        return widget

    def update_data_view(self):
        """Обновить отображение данных на вкладке горячих точек"""
        try:
            import traceback
            stack = traceback.format_stack()
            logging.debug(f"update_data_view вызван из:\n{''.join(stack[-5:-1])}")

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
            last_date = end_date

            self.update_hotspot_leader_label(last_date, threshold)

            if silo != "Все силосы":
                if plot_type == "Средняя температура":
                    self.hot_spots_table.setRowCount(0)
                    plot_series = {}
                    if suspension != "Все подвески":
                        susp_num = int(suspension)
                        avg_data = get_average_temp_by_suspension(self.db_conn, silo, susp_num, start_date, end_date)
                        plot_series[f"Средняя t° (подв. {susp_num})"] = avg_data
                        self.status_label.setText(f"График средней t° для силоса {silo}, подвески {susp_num}")
                    else:
                        avg_data = get_average_temp_by_silo(self.db_conn, silo, start_date, end_date)
                        plot_series[f"Средняя t° (силос {silo})"] = avg_data
                        self.status_label.setText(f"График средней t° для силоса {silo}")
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

            self.populate_breaks_table(silo if silo != "Все силосы" else None, start_date, end_date)
        except Exception as e:
            logging.error(f"Ошибка в update_data_view: {e}")
            logging.error(traceback.format_exc())

    def populate_hotspots_table(self, silo, date, threshold):
        """Заполнить таблицу горячими точками за конкретную дату"""
        self.plot_widget.plot_data({})
        hot_spots = get_hot_spots_for_date(self.db_conn, silo if silo != "Все силосы" else None, date, threshold)
        self.hot_spots_table.setRowCount(0)

        if not hot_spots:
            self.hot_spots_label.setText(f"🔥 Горячих точек: 0 (порог: {threshold}°C)")
            self.status_label.setText(f"Горячих точек не найдено за {date}")
            return

        date_format = "%d.%m.%Y" if self.date_format_with_year else "%d.%m"
        prev_date = get_previous_date_with_data(self.db_conn, date)

        self.hot_spots_table.setRowCount(len(hot_spots))
        for row_idx, row_data in enumerate(hot_spots):
            silo_name = str(row_data[0])
            suspension = int(row_data[1])
            sensor = int(row_data[2])
            temperature = float(row_data[3])
            row_date = row_data[4]

            self.hot_spots_table.setItem(row_idx, 0, QTableWidgetItem(silo_name))
            self.hot_spots_table.setItem(row_idx, 1, QTableWidgetItem(str(suspension)))
            self.hot_spots_table.setItem(row_idx, 2, QTableWidgetItem(str(sensor)))
            self.hot_spots_table.setItem(row_idx, 3, QTableWidgetItem(f"{temperature:.1f}°C"))

            date_obj = datetime.strptime(row_date, "%Y-%m-%d")
            formatted_date = date_obj.strftime(date_format)
            item = QTableWidgetItem(formatted_date)
            self.hot_spots_table.setItem(row_idx, 4, item)
            self.highlight_row(row_idx, QColor(self.color_hotspot))

            tooltip = f"📍 {silo_name}, Подвеска {suspension}, Датчик {sensor}\n"
            tooltip += f"🌡️ Температура: {temperature:.1f}°C\n"
            tooltip += f"📅 Дата: {formatted_date}"

            if prev_date:
                prev_temp = get_sensor_temperature_on_date(self.db_conn, silo_name, suspension, sensor, prev_date)
                if prev_temp is not None and prev_temp != 71.2:
                    delta = temperature - prev_temp
                    delta_sign = "+" if delta > 0 else ""
                    prev_date_obj = datetime.strptime(prev_date, "%Y-%m-%d")
                    prev_date_formatted = prev_date_obj.strftime(date_format)
                    tooltip += f"\n\n📈 Дельта за сутки ({prev_date_formatted}): {delta_sign}{delta:.1f}°C"
                    tooltip += f"\n   Предыдущая t°: {prev_temp:.1f}°C"

            item.setToolTip(tooltip)

        self.hot_spots_label.setText(f"🔥 Горячих точек: {len(hot_spots)} (порог: {threshold}°C)")
        self.status_label.setText(f"Найдено {len(hot_spots)} горячих точек за {date}")

    def highlight_row(self, row_index, color):
        for col in range(self.hot_spots_table.columnCount()):
            item = self.hot_spots_table.item(row_index, col)
            if item:
                item.setBackground(color)

    def update_hotspot_leader_label(self, date, threshold):
        """Обновить информацию о самом горячем датчике"""
        try:
            leader_info = get_leader_change_info(self.db_conn, date, threshold)
            if not leader_info:
                self.hotspot_leader_label.setText("")
                return

            current = leader_info['current']
            previous = leader_info['previous']
            changed = leader_info['changed']
            prev_date = leader_info.get('prev_date')
            date_format = "%d.%m.%Y" if self.date_format_with_year else "%d.%m"

            if current:
                current_text = f"🔥 Лидер: Силос {current['silo']}, Подвеска {current['suspension']}, Датчик {current['sensor']} ({current['temperature']:.1f}°C)"
                if changed and previous:
                    prev_date_obj = datetime.strptime(prev_date, "%Y-%m-%d")
                    prev_date_formatted = prev_date_obj.strftime(date_format)
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

        history_data = get_sensor_history_with_dates(self.db_conn, silo, suspension, sensor, start_date, end_date)
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

    def on_threshold_changed(self, value):
        self.temp_threshold = value
        set_user_setting(self.db_conn, 'temp_threshold', str(value))
        self.update_data_view()

    def choose_color(self, color_type):
        current_colors = {
            'hotspot': self.color_hotspot, 'error': self.color_error,
            'normal': self.color_normal, 'warning': self.color_warning,
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

    def update_color_buttons(self):
        """Обновить панель кнопок выбора цвета для серий"""
        if not hasattr(self, 'color_buttons_layout') or self.color_buttons_layout is None:
            return
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
        current_color = self.plot_widget.series_colors.get(series_name, '#89b4fa')
        qcolor = QColor(current_color)
        color = QColorDialog.getColor(qcolor, self, f"Выберите цвет для: {series_name}")
        if color.isValid():
            hex_color = color.name()
            self.plot_widget.set_series_color(series_name, hex_color)
            self.on_hotspot_clicked(self.hot_spots_table.currentRow(), 0)
            self.update_color_buttons()

    def change_graphic_color(self, element):
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

    def save_graph_dialog(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Сохранить график", "", "PNG Images (*.png);;JPEG Images (*.jpg)")
        if file_path:
            try:
                self.plot_widget.save_plot(file_path)
                self.status_label.setText(f"График сохранен в {file_path}")
            except Exception as e:
                self.status_label.setText(f"Ошибка сохранения: {e}")

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
