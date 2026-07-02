# plotter.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QColorDialog
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Circle
from datetime import datetime

# Цвета по умолчанию в стиле Catppuccin Mocha
DEFAULT_PLOT_COLORS = {
    'background': '#1e1e2e',
    'axes': '#313244',
    'grid': '#45475a',
    'text': '#cdd6f4',
    'lines': ['#89b4fa', '#f38ba8', '#a6e3a1', '#fab387', '#cba6f7', '#94e2d5', '#f9e2af', '#74c7ec']
}

class PlotWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Текущие цвета графика
        self.plot_colors = DEFAULT_PLOT_COLORS.copy()
        self.series_colors = {}
        
        # Данные для клика по точкам
        self.plot_data_cache = {}
        self.point_lines = []  # Линии для выбранных точек

        self.figure = Figure(figsize=(5, 3), facecolor=self.plot_colors['background'])
        self.canvas = FigureCanvas(self.figure)

        layout = QVBoxLayout()
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        self.ax = self.figure.add_subplot(111)
        self.setup_axes()
        
        # Подключение события клика
        self.cid = self.canvas.mpl_connect('button_press_event', self.on_click)

    def setup_axes(self):
        """Настройка стиля осей"""
        self.ax.set_facecolor(self.plot_colors['axes'])
        self.ax.tick_params(colors=self.plot_colors['text'])
        self.ax.spines['bottom'].set_color(self.plot_colors['text'])
        self.ax.spines['top'].set_color(self.plot_colors['text'])
        self.ax.spines['left'].set_color(self.plot_colors['text'])
        self.ax.spines['right'].set_color(self.plot_colors['text'])
        self.ax.xaxis.label.set_color(self.plot_colors['text'])
        self.ax.yaxis.label.set_color(self.plot_colors['text'])
        self.ax.title.set_color(self.plot_colors['text'])
        self.ax.grid(True, linestyle='--', alpha=0.3, color=self.plot_colors['grid'])

    def plot_data(self, data_series):
        """
        Plots one or more data series.
        'data_series' should be a dictionary where keys are series names
        and values are lists of (date, temperature) tuples.
        """
        self.ax.clear()
        self.setup_axes()

        # Очистить кэш данных
        self.plot_data_cache = {}

        if not data_series:
            self.ax.set_title("Нет данных для отображения")
            self.canvas.draw()
            return

        # Циклически используем цвета для линий
        for idx, (name, data) in enumerate(data_series.items()):
            if data:
                # Сортировка по датам (строки YYYY-MM-DD)
                data.sort(key=lambda x: x[0])
                
                # Конвертация строк дат в datetime объекты для правильного отображения
                dates_dt = [datetime.strptime(item[0], "%Y-%m-%d") for item in data]
                temperatures = [item[1] for item in data]

                # Используем сохранённый цвет или берём из палитры
                if name not in self.series_colors:
                    self.series_colors[name] = DEFAULT_PLOT_COLORS['lines'][idx % len(DEFAULT_PLOT_COLORS['lines'])]

                color = self.series_colors[name]
                line, = self.ax.plot(dates_dt, temperatures, marker='o', linestyle='-', label=name,
                            color=color, linewidth=2, markersize=6,
                            markerfacecolor=color, markeredgecolor='white', markeredgewidth=1)

                # Сохранить данные для клика (строки для простоты сравнения)
                self.plot_data_cache[name] = {
                    'dates': [item[0] for item in data],  # Строки YYYY-MM-DD
                    'temperatures': temperatures,
                    'color': color
                }

        self.ax.set_title("Динамика температуры")
        self.ax.set_xlabel("Дата")
        self.ax.set_ylabel("Температура (°C)")
        self.ax.legend(loc='upper left', facecolor=self.plot_colors['axes'], labelcolor=self.plot_colors['text'])
        
        # Форматирование оси дат
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        self.figure.autofmt_xdate(rotation=45, ha='right')
        self.ax.grid(True, linestyle='--', alpha=0.3, color=self.plot_colors['grid'])
        self.canvas.draw()

    def on_click(self, event):
        """Обработка клика по графику"""
        if event.inaxes != self.ax:
            return

        # Удалить предыдущие маркеры
        for line in self.point_lines:
            try:
                line.remove()
            except NotImplementedError:
                pass  # Некоторые художники не могут быть удалены
        self.point_lines = []

        # Найти ближайшую точку
        min_dist = float('inf')
        selected_point = None
        selected_series = None

        for series_name, data in self.plot_data_cache.items():
            for i, (date_str, temp) in enumerate(zip(data['dates'], data['temperatures'])):
                # Конвертировать строку даты в datetime объект
                date_dt = datetime.strptime(date_str, "%Y-%m-%d")
                
                # Преобразовать дату в координаты
                x = mdates.date2num(date_dt)
                y = temp

                dist = (event.xdata - x)**2 + (event.ydata - y)**2
                if dist < min_dist and dist < 0.5:  # Порог расстояния
                    min_dist = dist
                    selected_point = (date_str, temp)  # Возвращаем строку для совместимости
                    selected_series = series_name

        if selected_point:
            # Нарисовать маркер на выбранной точке
            date_dt = datetime.strptime(selected_point[0], "%Y-%m-%d")
            x = mdates.date2num(date_dt)
            y = selected_point[1]

            circle = Circle((x, y), radius=0.02, color='yellow', fill=True, zorder=10)
            self.ax.add_patch(circle)
            self.point_lines.append(circle)

            # Сигнал о выбранной точке (через callback)
            if hasattr(self, 'on_point_selected'):
                self.on_point_selected(selected_point[0], selected_point[1], selected_series)

            self.canvas.draw()

    def set_series_color(self, series_name, color):
        """Установить цвет для конкретной серии"""
        self.series_colors[series_name] = color

    def clear_colors(self):
        """Очистить сохранённые цвета"""
        self.series_colors.clear()

    def set_color_scheme(self, background=None, axes=None, grid=None, text=None):
        """Установить цвета элементов графика"""
        if background:
            self.plot_colors['background'] = background
            self.figure.set_facecolor(background)
        if axes:
            self.plot_colors['axes'] = axes
        if grid:
            self.plot_colors['grid'] = grid
        if text:
            self.plot_colors['text'] = text
        self.setup_axes()

    def save_plot(self, file_path):
        """ Saves the current plot to a file. """
        self.figure.savefig(file_path, dpi=300, facecolor=self.plot_colors['background'])


if __name__ == '__main__':
    from PyQt6.QtWidgets import QApplication
    import sys

    app = QApplication(sys.argv)

    main_window = QWidget()
    main_window.setWindowTitle("Тест плоттера")
    layout = QVBoxLayout()

    plot_widget = PlotWidget()
    
    # Тест callback
    def on_point_selected(date, temp, series):
        print(f"Выбрана точка: {date}, {temp}°C, {series}")
    
    plot_widget.on_point_selected = on_point_selected
    
    layout.addWidget(plot_widget)
    main_window.setLayout(layout)

    dummy_series = {
        'Датчик 1': [
            ('2026-03-01', 15.2), ('2026-03-02', 15.8), ('2026-03-03', 16.1)
        ],
        'Датчик 2': [
            ('2026-03-01', 14.8), ('2026-03-02', 15.1), ('2026-03-03', 15.5)
        ]
    }

    plot_widget.plot_data(dummy_series)

    main_window.show()
    sys.exit(app.exec())
