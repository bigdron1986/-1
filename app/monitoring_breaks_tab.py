# -*- coding: utf-8 -*-
"""Миксин: вкладки Мониторинг + Обрывы"""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout,
                             QGroupBox, QTableWidget, QTableWidgetItem, QAbstractItemView,
                             QDoubleSpinBox, QMessageBox, QDialog)
from PyQt6.QtGui import QColor
from database import (get_readings, get_sensor_history, get_temperature_changes, get_sensor_history_with_dates)
from plotter import PlotWidget


class MonitoringTab(QWidget):
    """Вкладка 3: Мониторинг изменений"""

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self._build()

    def _build(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)

        control_group = QGroupBox("🎛️ Параметры мониторинга")
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)
        control_layout.addWidget(QLabel("Порог изменения температуры:"))
        self.change_threshold_spinbox = QDoubleSpinBox()
        self.change_threshold_spinbox.setValue(self.ctx.change_threshold)
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

        self.changes_table = QTableWidget()
        self.changes_table.setColumnCount(8)
        self.changes_table.setHorizontalHeaderLabels([
            "Силос", "Подвеска", "Датчик", "Дата", "Пред. t°", "Тек. t°", "Δ t°", "Статус"
        ])
        self.changes_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.changes_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.changes_table.setAlternatingRowColors(True)
        self.changes_table.horizontalHeader().setStretchLastSection(True)
        self.changes_table.cellClicked.connect(self.on_monitoring_cell_clicked)
        layout.addWidget(self.changes_table)

        self.changes_label = QLabel("📊 Изменений не найдено (кликните по строке для графика за неделю от конца периода)")
        self.changes_label.setStyleSheet("font-size: 12px; color: #cdd6f4; padding: 4px;")
        layout.addWidget(self.changes_label)

        self.setLayout(layout)

    def update_monitoring_view(self):
        try:
            silo = self.ctx.silo_combo.currentText()
            start_date = self.ctx.start_date_edit.date().toString("yyyy-MM-dd")
            end_date = self.ctx.end_date_edit.date().toString("yyyy-MM-dd")
            threshold = self.change_threshold_spinbox.value()

            changes = get_temperature_changes(
                self.ctx.db_conn,
                silo if silo != "Все силосы" else None,
                start_date,
                end_date,
                threshold
            )

            self.changes_table.setRowCount(0)
            if not changes:
                self.changes_label.setText(f"📊 Изменений > {threshold}°C не найдено")
                return

            date_format = "%d.%m.%Y" if self.ctx.date_format_with_year else "%d.%m"
            self.changes_table.setRowCount(len(changes))

            for row_idx, change in enumerate(changes):
                self.changes_table.setItem(row_idx, 0, QTableWidgetItem(str(change['silo'])))
                self.changes_table.setItem(row_idx, 1, QTableWidgetItem(str(change['suspension'])))
                self.changes_table.setItem(row_idx, 2, QTableWidgetItem(str(change['sensor'])))

                from datetime import datetime
                last_date_obj = datetime.strptime(change['last_date'], "%Y-%m-%d")
                last_date = last_date_obj.strftime(date_format)
                self.changes_table.setItem(row_idx, 3, QTableWidgetItem(last_date))
                self.changes_table.setItem(row_idx, 4, QTableWidgetItem(f"{change['prev_temp']:.1f}°C"))
                self.changes_table.setItem(row_idx, 5, QTableWidgetItem(f"{change['last_temp']:.1f}°C"))

                delta = change['delta']
                delta_str = f"{delta:+.1f}°C"
                delta_item = QTableWidgetItem(delta_str)

                if delta > 0:
                    delta_item.setBackground(QColor(self.ctx.color_hotspot))
                else:
                    delta_item.setBackground(QColor(self.ctx.color_normal))

                self.changes_table.setItem(row_idx, 6, delta_item)

                status = "🔥 Нагрев" if delta > 0 else "❄️ Охлаждение"
                status_item = QTableWidgetItem(status)
                if delta > 0:
                    status_item.setBackground(QColor(self.ctx.color_hotspot))
                else:
                    status_item.setBackground(QColor(self.ctx.color_normal))
                self.changes_table.setItem(row_idx, 7, status_item)

            self.changes_label.setText(f"📊 Изменений: {len(changes)} (порог: {threshold}°C)")
        except Exception as e:
            print(f"Ошибка в update_monitoring_view: {e}")
            import traceback
            traceback.print_exc()

    def on_monitoring_cell_clicked(self, row, column):
        try:
            silo_item = self.changes_table.item(row, 0)
            susp_item = self.changes_table.item(row, 1)
            sens_item = self.changes_table.item(row, 2)

            if not (silo_item and susp_item and sens_item):
                return

            silo = silo_item.text()
            suspension = int(susp_item.text())
            sensor = int(sens_item.text())

            from datetime import datetime, timedelta
            end_date = self.ctx.end_date_edit.date().toPyDate()
            start_date = end_date - timedelta(days=7)

            start_date_str = start_date.strftime("%Y-%m-%d")
            end_date_str = end_date.strftime("%Y-%m-%d")

            history_data = get_sensor_history_with_dates(
                self.ctx.db_conn, silo, suspension, sensor, start_date_str, end_date_str
            )

            if not history_data:
                QMessageBox.information(
                    self,
                    "Нет данных",
                    f"Нет данных для датчика:\n"
                    f"Силос: {silo}, Подвеска: {suspension}, Датчик: {sensor}\n"
                    f"За период: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
                )
                return

            dialog = SensorWeekDialog(self, silo, suspension, sensor, history_data, start_date_str, end_date_str)
            dialog.exec()

        except Exception as e:
            print(f"Ошибка в on_monitoring_cell_clicked: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Ошибка", f"Ошибка при построении графика:\n{e}")





class SensorWeekDialog(QDialog):
    """Диалог показа графика датчика за неделю"""
    
    def __init__(self, parent, silo, suspension, sensor, history_data, start_date, end_date):
        super().__init__(parent)
        self.silo = silo
        self.suspension = suspension
        self.sensor = sensor
        self.history_data = history_data
        self.start_date = start_date
        self.end_date = end_date
        
        self.initUI()
    
    def initUI(self):
        self.setWindowTitle(f"📈 Датчик: Силос {self.silo}, Подв. {self.suspension}, Датчик {self.sensor}")
        self.setMinimumSize(900, 600)
        self.setModal(True)
        
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Заголовок
        title = QLabel(f"📊 Динамика температуры за последнюю неделю")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #89b4fa; padding: 8px;")
        layout.addWidget(title)
        
        # Информация о датчике
        info = QLabel(
            f"Силос: {self.silo} | Подвеска: {self.suspension} | Датчик: {self.sensor}\n"
            f"Период: {self.start_date} - {self.end_date} | Записей: {len(self.history_data)}"
        )
        info.setStyleSheet("font-size: 12px; color: #cdd6f4; padding: 6px; background-color: #313244; border-radius: 4px;")
        layout.addWidget(info)
        
        # График
        self.plot_widget = PlotWidget()
        layout.addWidget(self.plot_widget, 1)
        
        # Кнопка закрытия
        close_btn = QPushButton("Закрыть")
        close_btn.setStyleSheet("background-color: #45475a; padding: 10px 20px; font-size: 14px;")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)
        
        # Построить график
        series_name = f"Датчик {self.sensor} (Подв. {self.suspension})"
        self.plot_widget.plot_data({series_name: self.history_data})


class BreaksTab(QWidget):
    """Вкладка 4: Обрывы датчиков"""

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self._build()

    def _build(self):
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

        self.setLayout(layout)

    def populate_breaks_table(self, silo, start_date, end_date):
        all_data = get_readings(self.ctx.db_conn, silo=silo, start_date=start_date, end_date=end_date)

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
                    'silo': silo_name, 'suspension': susp_num, 'sensor': sensor_num,
                    'first_break': first_break_date, 'last_temp': '—', 'last_date': '—',
                    'status': 'Всегда в обрыве'
                })
            else:
                last_normal_date, last_normal_temp = readings[first_break_index - 1]
                breaks_new.append({
                    'silo': silo_name, 'suspension': susp_num, 'sensor': sensor_num,
                    'first_break': first_break_date, 'last_temp': f"{last_normal_temp:+.1f}°C",
                    'last_date': last_normal_date, 'status': 'Ушёл в обрыв'
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
        silo_item = self.breaks_table.item(row, 0)
        susp_item = self.breaks_table.item(row, 1)
        sens_item = self.breaks_table.item(row, 2)
        if not (silo_item and susp_item and sens_item):
            return

        silo = silo_item.text()
        suspension = int(susp_item.text())
        sensor = int(sens_item.text())

        history_data = get_sensor_history(self.ctx.db_conn, silo, suspension, sensor)
        self.ctx.hotspots_tab.plot_widget.plot_data({f"Датчик {sensor} (Силос {silo}, Подв. {suspension})": history_data})
        self.ctx.hotspots_tab.delta_label.setText(f"⚠️ Обрыв датчика! Кликните для просмотра истории")
        self.ctx.hotspots_tab.update_color_buttons()


