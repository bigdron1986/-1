# -*- coding: utf-8 -*-
"""
3D визуализация силоса с температурной картой
Использует Plotly для интерактивного отображения
Силос отображается как цилиндр с датчиками по окружности
"""

import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np


# Цветовая схема для температур
def get_temp_color(temp):
    """Возвращает цвет для температуры"""
    if temp == 71.2:
        return 'rgba(128, 128, 128, 0.5)'  # Серый для обрыва
    elif temp < 0:
        return 'rgba(59, 130, 246, 0.9)'   # Синий для отрицательных
    elif temp < 10:
        return 'rgba(34, 197, 94, 0.9)'    # Зелёный для холодных
    elif temp < 15:
        return 'rgba(134, 239, 172, 0.9)'  # Светло-зелёный для нормы
    elif temp < 20:
        return 'rgba(254, 240, 138, 0.9)'  # Жёлтый для внимания
    elif temp < 25:
        return 'rgba(253, 186, 116, 0.9)'  # Оранжевый для тревоги
    elif temp < 35:
        return 'rgba(248, 113, 113, 1.0)'  # Красный для перегрева
    else:
        return 'rgba(220, 38, 38, 1.0)'    # Тёмно-красный для критического


def get_temp_status(temp):
    """Возвращает статус температуры"""
    if temp == 71.2:
        return "⚠️ Обрыв"
    elif temp < 0:
        return "❄️ Мороз"
    elif temp < 15:
        return "✅ Норма"
    elif temp < 25:
        return "⚠️ Внимание"
    elif temp < 35:
        return "🔥 Перегрев"
    else:
        return "🚨 Критично"


def calculate_cylinder_positions(num_sensors=6, num_suspensions=11, cylinder_radius=5):
    """
    Рассчитать позиции датчиков на поверхности цилиндра

    11 подвесок расположены в 2 контура:
    - Внешний контур (радиус cylinder_radius): 4 → 5 → 6 → 7 → 8 → 9 → 10 → 11 (равномерно по кругу)
    - Внутренний контур (радиус cylinder_radius * 0.4): 1 → 2 → 3
    6 датчиков на каждой подвеске расположены по высоте (1-снизу, 6-сверху)

    Шнек проходит между 4 и 11 (внешний) и между 2 и 3 (внутренний)
    Вид сверху: шнек снизу по центру (-90°)

    Возвращает:
    - dict с координатами для каждого (suspension, sensor)
    """
    positions = {}

    # Датчики: от -10 (низ, датчик 1) до 0 (верх, датчик 6) - 6 датчиков
    sensor_heights = np.linspace(-10, 0, num_sensors)

    # Внешний контур: подвески 4,5,6,7,8,9,10,11 (8 подвесок равномерно по окружности)
    # Шнек между 4 и 11 - шнек снизу (-90°)
    # Угол между подвесками: 360/8 = 45°
    # 4: -67.5°, 5: -22.5°, 6: 22.5°, 7: 67.5°, 8: 112.5°, 9: 157.5°, 10: -157.5°, 11: -112.5°
    outer_angles = [-3*np.pi/8, -np.pi/8, np.pi/8, 3*np.pi/8, 5*np.pi/8, 7*np.pi/8, -7*np.pi/8, -5*np.pi/8]
    outer_suspensions = [4, 5, 6, 7, 8, 9, 10, 11]

    # Внутренний контур: подвески 1,2,3 (3 подвески в центре)
    # Шнек между 2 и 3 - шнек снизу (-90°)
    # 1 - вверху (90°), 2 - справа от шнека (-45°), 3 - слева от шнека (-135°)
    inner_angles = [np.pi/2, -np.pi/4, -3*np.pi/4]  # 1 сверху, 2 справа-снизу, 3 слева-снизу
    inner_suspensions = [1, 2, 3]

    # Внешний контур
    for i, susp_num in enumerate(outer_suspensions):
        angle = outer_angles[i]
        x = cylinder_radius * np.cos(angle)
        z = cylinder_radius * np.sin(angle)
        for sensor_idx, sensor_num in enumerate(range(1, num_sensors + 1)):
            y = sensor_heights[sensor_idx]
            positions[(susp_num, sensor_num)] = (x, y, z)

    # Внутренний контур (радиус 40% от внешнего)
    inner_radius = cylinder_radius * 0.4
    for i, susp_num in enumerate(inner_suspensions):
        angle = inner_angles[i]
        x = inner_radius * np.cos(angle)
        z = inner_radius * np.sin(angle)
        for sensor_idx, sensor_num in enumerate(range(1, num_sensors + 1)):
            y = sensor_heights[sensor_idx]
            positions[(susp_num, sensor_num)] = (x, y, z)

    return positions


def create_silo_3d(df, silo_name, date=None, suspension_range=None, cylinder_radius=5):
    """
    Создать 3D визуализацию силоса в форме цилиндра
    
    Параметры:
    - df: DataFrame с колонками [suspension, sensor, temperature, date]
    - silo_name: название силоса
    - date: конкретная дата (None = все даты, будет анимация)
    - suspension_range: диапазон подвесок для фильтрации
    - cylinder_radius: радиус цилиндра для визуализации
    
    Возвращает:
    - Plotly figure
    """
    
    # Фильтрация по дате
    if date:
        df_filtered = df[df['date'] == date].copy()
        dates = [date]
    else:
        df_filtered = df.copy()
        dates = sorted(df_filtered['date'].unique())
    
    # Фильтрация по подвескам
    if suspension_range:
        df_filtered = df_filtered[
            (df_filtered['suspension'] >= suspension_range[0]) & 
            (df_filtered['suspension'] <= suspension_range[1])
        ]
    
    # Определить количество подвесок и датчиков из данных
    num_suspensions = df_filtered['suspension'].nunique()
    num_sensors = df_filtered['sensor'].nunique()
    
    # Если данных нет, использовать значения по умолчанию
    if num_suspensions == 0:
        num_suspensions = 11
    if num_sensors == 0:
        num_sensors = 6
    
    # Рассчитать позиции на цилиндре
    positions = calculate_cylinder_positions(
        num_sensors=num_sensors, 
        num_suspensions=num_suspensions,
        cylinder_radius=cylinder_radius
    )
    
    # Создадим фреймы для анимации
    frames = []
    
    for d in dates:
        df_date = df_filtered[df_filtered['date'] == d]
        
        # Получить координаты для каждой точки
        x_coords = []
        y_coords = []
        z_coords = []
        temps = []
        colors = []
        hover_texts = []
        
        for _, row in df_date.iterrows():
            susp = row['suspension']
            sensor = row['sensor']
            temp = row['temperature']
            
            if (susp, sensor) in positions:
                x, y, z = positions[(susp, sensor)]
                x_coords.append(x)
                y_coords.append(y)
                z_coords.append(z)
                temps.append(temp)
                colors.append(get_temp_color(temp))
                
                status = get_temp_status(temp)
                hover_texts.append(
                    f"Подвеска: {susp}<br>"
                    f"Датчик: {sensor}<br>"
                    f"Температура: {temp:.1f}°C<br>"
                    f"Статус: {status}<br>"
                    f"Дата: {d}"
                )
        
        frame = go.Frame(
            name=str(d),
            data=[go.Scatter3d(
                x=x_coords, y=y_coords, z=z_coords,
                mode='markers+text',
                marker=dict(
                    size=10,
                    color=colors,
                    opacity=0.95,
                    line=dict(color='white', width=0.5),
                ),
                text=[f"{t:.0f}°" if t != 71.2 else "X" for t in temps],
                textposition="top center",
                textfont=dict(size=8, color='white'),
                hovertext=hover_texts,
                hoverinfo='text'
            )]
        )
        frames.append(frame)
    
    # Начальные данные (первый кадр) — с явным hovertext
    if len(frames) > 0:
        initial_data = frames[0].data[0]
    else:
        initial_data = go.Scatter3d(x=[], y=[], z=[], mode='markers', marker=dict(size=0))
    
    # Создание фигуры
    fig = make_subplots(specs=[[{'type': 'scatter3d'}]])
    
    # Добавить начальные данные с hovertext
    fig.add_trace(go.Scatter3d(
        x=initial_data.x,
        y=initial_data.y,
        z=initial_data.z,
        mode='markers+text',
        marker=dict(
            size=12,
            color=initial_data.marker.color if hasattr(initial_data.marker, 'color') else [],
            opacity=0.95,
            line=dict(color='white', width=0.5),
        ),
        text=initial_data.text if hasattr(initial_data, 'text') else [],
        textposition="top center",
        textfont=dict(size=9, color='white'),
        hovertext=initial_data.hovertext if hasattr(initial_data, 'hovertext') else [],
        hoverinfo='text',
        hoverlabel=dict(
            bgcolor='rgba(30, 30, 46, 0.95)',
            bordercolor='#89b4fa',
            font=dict(size=13, color='#cdd6f4', family='Consolas')
        )
    ))
    
    # Добавить фреймы
    fig.frames = frames
    
    # Каркас цилиндра (вертикальные линии + горизонтальные кольца)
    # Вертикальные линии
    for angle_deg in range(0, 360, 30):
        angle = np.radians(angle_deg)
        x_line = cylinder_radius * np.cos(angle)
        z_line = cylinder_radius * np.sin(angle)
        fig.add_trace(go.Scatter3d(
            x=[x_line, x_line], y=[0, -11], z=[z_line, z_line],
            mode='lines',
            line=dict(color='rgba(100,100,120,0.2)', width=1),
            hoverinfo='skip',
            showlegend=False
        ))

    # Горизонтальные кольца цилиндра
    for y_level in np.linspace(0, -11, 12):
        ring_theta = np.linspace(0, 2*np.pi, 60)
        ring_x = cylinder_radius * np.cos(ring_theta)
        ring_z = cylinder_radius * np.sin(ring_theta)
        fig.add_trace(go.Scatter3d(
            x=ring_x, y=[y_level]*len(ring_x), z=ring_z,
            mode='lines',
            line=dict(color='rgba(100,100,120,0.15)', width=1),
            hoverinfo='skip',
            showlegend=False
        ))

    # Плоское дно силоса (кольцо + радиальные линии)
    for angle_deg in range(0, 360, 30):
        angle = np.radians(angle_deg)
        x_line = cylinder_radius * np.cos(angle)
        z_line = cylinder_radius * np.sin(angle)
        fig.add_trace(go.Scatter3d(
            x=[0, x_line], y=[-11, -11], z=[0, z_line],
            mode='lines',
            line=dict(color='rgba(100,100,120,0.2)', width=1),
            hoverinfo='skip',
            showlegend=False
        ))
    # Кольцо дна
    bottom_theta = np.linspace(0, 2*np.pi, 60)
    fig.add_trace(go.Scatter3d(
        x=cylinder_radius * np.cos(bottom_theta),
        y=[-11]*60,
        z=cylinder_radius * np.sin(bottom_theta),
        mode='lines',
        line=dict(color='rgba(100,100,120,0.25)', width=1),
        hoverinfo='skip',
        showlegend=False
    ))

    # Крыша силоса (конус - wireframe)
    roof_height = 2
    for angle_deg in range(0, 360, 30):
        angle = np.radians(angle_deg)
        x_line = cylinder_radius * np.cos(angle)
        z_line = cylinder_radius * np.sin(angle)
        fig.add_trace(go.Scatter3d(
            x=[0, x_line], y=[roof_height, 0], z=[0, z_line],
            mode='lines',
            line=dict(color='rgba(100,100,120,0.15)', width=1),
            hoverinfo='skip',
            showlegend=False
        ))
    # Кольцо крыши
    roof_theta = np.linspace(0, 2*np.pi, 60)
    fig.add_trace(go.Scatter3d(
        x=cylinder_radius * np.cos(roof_theta),
        y=[0]*60,
        z=cylinder_radius * np.sin(roof_theta),
        mode='lines',
        line=dict(color='rgba(100,100,120,0.2)', width=1),
        hoverinfo='skip',
        showlegend=False
    ))

    # Кольца подвесок (горизонтальные линии на уровне каждой подвески)
    sensor_heights = np.linspace(-10, 0, df_filtered['sensor'].nunique() if len(df_filtered) > 0 else 6)
    for h_idx, h in enumerate(sensor_heights):
        ring_theta = np.linspace(0, 2*np.pi, 60)
        ring_x = cylinder_radius * np.cos(ring_theta)
        ring_z = cylinder_radius * np.sin(ring_theta)
        fig.add_trace(go.Scatter3d(
            x=ring_x, y=[h]*len(ring_x), z=ring_z,
            mode='lines',
            line=dict(color='rgba(100,100,120,0.12)', width=1),
            hoverinfo='skip',
            showlegend=False
        ))

    # Добавить шнек в центре (горизонтальный цилиндр вдоль оси Z, снизу по центру)
    # Шнек идёт от края (между 4 и 11) к центру (между 2 и 3)
    # Повёрнут на 90° по часовой стрелке
    shnek_radius = cylinder_radius * 0.15  # Радиус шнека ~15% от радиуса силоса
    shnek_length = 6  # Длина шнека от края до центра
    theta_shnek = np.linspace(0, 2*np.pi, 30)
    z_shnek = np.linspace(-shnek_length, 0, 50)  # От края (Z=-6) до центра (Z=0)
    theta_shnek_grid, z_shnek_grid = np.meshgrid(theta_shnek, z_shnek)
    x_shnek = shnek_radius * np.cos(theta_shnek_grid)
    y_shnek = shnek_radius * np.sin(theta_shnek_grid) - 10  # На уровне 1 датчика (Y=-10)

    fig.add_trace(go.Surface(
        x=x_shnek, y=y_shnek, z=z_shnek_grid,
        opacity=0.9,
        showscale=False,
        colorscale=[[0, 'rgba(100,100,100,0.9)'], [1, 'rgba(120,120,120,0.9)']],
        hoverinfo='skip',
        name='Шнек'
    ))

    # Настройка сцены
    fig.update_layout(
        scene=dict(
            xaxis=dict(
                title='',
                showticklabels=False,
                showbackground=False,
                showgrid=False,
                zeroline=False,
                showline=False
            ),
            yaxis=dict(
                title='',
                showticklabels=False,
                showbackground=False,
                showgrid=False,
                zeroline=False,
                showline=False
            ),
            zaxis=dict(
                title='',
                showticklabels=False,
                showbackground=False,
                showgrid=False,
                zeroline=False,
                showline=False
            ),
            camera=dict(
                eye=dict(x=2.5, y=2, z=2.5),
                up=dict(x=0, y=1, z=0),
                center=dict(x=0, y=0, z=0)
            ),
            aspectmode='manual',
            aspectratio=dict(x=1.3, y=1, z=1.3)
        ),
        title=dict(
            text=f"🏭 3D Модель: {silo_name} (подвески по окружности)",
            x=0.5,
            font=dict(size=16, color='#89b4fa')
        ),
        margin=dict(l=0, r=0, t=60, b=60),
        paper_bgcolor='rgba(30,30,46,1)',
        plot_bgcolor='rgba(30,30,46,1)',
        updatemenus=[{
            'buttons': [
                {
                    'args': [None, {
                        'frame': {'duration': 500, 'redraw': True},
                        'fromcurrent': True,
                        'transition': {'duration': 300}
                    }],
                    'label': '▶️ Старт',
                    'method': 'animate'
                },
                {
                    'args': [[None], {
                        'frame': {'duration': 0, 'redraw': True},
                        'mode': 'immediate',
                        'transition': {'duration': 0}
                    }],
                    'label': '⏸️ Стоп',
                    'method': 'animate'
                }
            ],
            'direction': 'left',
            'pad': {'r': 10, 't': 10},
            'showactive': True,
            'type': 'buttons',
            'x': 0.1,
            'xanchor': 'right',
            'y': 0,
            'yanchor': 'top'
        },
        {
            'buttons': [
                {
                    'args': [{'scene.camera.eye': {'x': 0, 'y': 3, 'z': 0}}],
                    'label': '🔼 Вид сверху',
                    'method': 'relayout'
                },
                {
                    'args': [{'scene.camera': {'eye': {'x': 2.5, 'y': 2, 'z': 2.5}, 'center': {'x': 0, 'y': 0, 'z': 0}, 'up': {'x': 0, 'y': 1, 'z': 0}}}],
                    'label': '🔙 Сброс',
                    'method': 'relayout'
                }
            ],
            'direction': 'down',
            'pad': {'r': 10, 't': 10},
            'showactive': True,
            'type': 'buttons',
            'x': 0.35,
            'xanchor': 'left',
            'y': 0,
            'yanchor': 'top'
        },
        {
            'buttons': [
                {
                    'args': [{'scene.camera.eye': {'x': 0.5, 'y': 1, 'z': 2.8}}],
                    'label': '↻ +15° (по часовой)',
                    'method': 'relayout'
                },
                {
                    'args': [{'scene.camera.eye': {'x': -0.5, 'y': 1, 'z': 2.8}}],
                    'label': '↺ -15° (против)',
                    'method': 'relayout'
                },
                {
                    'args': [{'scene.camera.eye': {'x': 0, 'y': 2.5, 'z': 1.5}}],
                    'label': '⬆ Кверху +15°',
                    'method': 'relayout'
                },
                {
                    'args': [{'scene.camera.eye': {'x': 0, 'y': 0.5, 'z': 2.8}}],
                    'label': '⬇ Книзу -15°',
                    'method': 'relayout'
                }
            ],
            'direction': 'down',
            'pad': {'r': 10, 't': 10},
            'showactive': True,
            'type': 'buttons',
            'x': 0.55,
            'xanchor': 'left',
            'y': 0,
            'yanchor': 'top'
        }]
    )
    
    # Слайдер для дат
    sliders_dict = {
        'active': 0,
        'yanchor': 'top',
        'xanchor': 'left',
        'currentvalue': {
            'font': {'size': 14, 'color': '#cdd6f4'},
            'prefix': '📅 Дата: ',
            'visible': True,
            'xanchor': 'right'
        },
        'transition': {'duration': 300},
        'pad': {'b': 10, 't': 10},
        'len': 0.9,
        'x': 0.1,
        'y': 0,
        'steps': [
            {
                'args': [[str(d)], {
                    'frame': {'duration': 300, 'redraw': True},
                    'mode': 'immediate',
                    'transition': {'duration': 300}
                }],
                'label': str(d),
                'method': 'animate'
            }
            for d in dates
        ]
    }
    
    fig.update_layout(sliders=[sliders_dict])

    return fig


def create_silo_3d_with_highlight(df, silo_name, date=None, suspension_range=None, 
                                   cylinder_radius=5, highlight_suspension=None, 
                                   highlight_sensor=None):
    """
    Создать 3D визуализацию силоса с подсветкой горячего датчика
    
    Параметры:
    - df: DataFrame с колонками [suspension, sensor, temperature, date]
    - silo_name: название силоса
    - date: конкретная дата
    - suspension_range: диапазон подвесок
    - cylinder_radius: радиус цилиндра
    - highlight_suspension: номер подвески для подсветки
    - highlight_sensor: номер датчика для подсветки
    
    Возвращает:
    - Plotly figure
    """
    # Создать базовую фигуру
    fig = create_silo_3d(df, silo_name, date, suspension_range, cylinder_radius)
    
    # Если указаны датчики для подсветки, обновить цвета
    if highlight_suspension is not None and highlight_sensor is not None:
        for trace in fig.data:
            if hasattr(trace, 'hovertext') and trace.hovertext:
                new_colors = []
                new_sizes = []
                
                for i, hover_text in enumerate(trace.hovertext):
                    # Проверить, является ли это горячим датчиком
                    if (f"Подвеска: {highlight_suspension}" in hover_text and 
                        f"Датчик: {highlight_sensor}" in hover_text):
                        new_colors.append('rgba(255, 0, 0, 1.0)')  # Ярко-красный
                        new_sizes.append(15)  # Увеличенный размер
                    else:
                        # Оставить оригинальный цвет
                        if hasattr(trace.marker, 'color') and isinstance(trace.marker.color, list):
                            new_colors.append(trace.marker.color[i] if i < len(trace.marker.color) else 'rgba(200, 200, 200, 0.5)')
                        else:
                            new_colors.append('rgba(200, 200, 200, 0.5)')
                        new_sizes.append(10)
                
                # Обновить маркер
                trace.marker.color = new_colors
                trace.marker.size = new_sizes
    
    # Обновить заголовок
    if highlight_suspension and highlight_sensor:
        current_title = fig.layout.title.text if fig.layout.title else ""
        fig.update_layout(
            title=dict(
                text=f"{current_title} 🔥 Подсветка: П{highlight_suspension}/Д{highlight_sensor}",
                x=0.5
            )
        )
    
    return fig


def get_silo_data(conn, silo, start_date, end_date):
    """
    Получить данные для 3D визуализации из базы
    
    Параметры:
    - conn: соединение с БД
    - silo: название силоса
    - start_date: начальная дата
    - end_date: конечная дата
    
    Возвращает:
    - DataFrame с данными
    """
    query = """
        SELECT suspension, sensor, temperature, date
        FROM readings
        WHERE silo = ? AND date >= ? AND date <= ?
        AND temperature != 71.2
        ORDER BY suspension, sensor, date
    """
    
    df = pd.read_sql_query(query, conn, params=[silo, start_date, end_date])
    return df


def get_silo_data_with_errors(conn, silo, start_date, end_date):
    """
    Получить данные для 3D визуализации из базы (включая обрывы 71.2)
    """
    query = """
        SELECT suspension, sensor, temperature, date
        FROM readings
        WHERE silo = ? AND date >= ? AND date <= ?
        ORDER BY suspension, sensor, date
    """
    
    df = pd.read_sql_query(query, conn, params=[silo, start_date, end_date])
    return df


if __name__ == '__main__':
    # Тест
    from database import setup_database
    
    conn = setup_database('temperatures.db')
    
    # Получить данные
    df = get_silo_data(conn, '3а', '2026-03-04', '2026-03-07')
    print(f"Загружено {len(df)} записей")
    print(df.head())
    
    # Создать визуализацию
    fig = create_silo_3d(df, '3а')
    
    # Сохранить в HTML
    fig.write_html('3d_silo_test.html')
    print("Сохранено в 3d_silo_test.html")
    
    conn.close()
