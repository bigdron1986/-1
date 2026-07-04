# -*- coding: utf-8 -*-
"""
Виджет для отображения Plotly графиков в PyQt6
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, Qt
import tempfile
import os
import logging

logger = logging.getLogger(__name__)


class PlotlyWidget(QWidget):
    """Виджет для отображения интерактивных Plotly графиков"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.temp_html_path = None
        self.cam_x = 2.5
        self.cam_y = 2.0
        self.cam_z = 2.5
        self.page_loaded = False

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.browser = QWebEngineView()
        self.browser.loadFinished.connect(self._on_load_finished)
        layout.addWidget(self.browser, 1)

        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(10, 5, 10, 5)
        btn_layout.setSpacing(6)

        btn_style = """
            QPushButton {
                background-color: #89b4fa;
                color: #1e1e2e;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #74c7ec;
            }
        """

        self.btn_left = QPushButton("↺ Влево")
        self.btn_left.setStyleSheet(btn_style)
        self.btn_left.clicked.connect(self.rotate_left)

        self.btn_right = QPushButton("↻ Вправо")
        self.btn_right.setStyleSheet(btn_style)
        self.btn_right.clicked.connect(self.rotate_right)

        self.btn_up = QPushButton("⬆ Вверх")
        self.btn_up.setStyleSheet(btn_style)
        self.btn_up.clicked.connect(self.rotate_up)

        self.btn_down = QPushButton("⬇ Вниз")
        self.btn_down.setStyleSheet(btn_style)
        self.btn_down.clicked.connect(self.rotate_down)

        self.btn_top = QPushButton("🔼 Сверху")
        self.btn_top.setStyleSheet(btn_style.replace("#89b4fa", "#a6e3a1"))
        self.btn_top.clicked.connect(self.top_view)

        self.btn_reset = QPushButton("🔙 Сброс")
        self.btn_reset.setStyleSheet(btn_style.replace("#89b4fa", "#f38ba8"))
        self.btn_reset.clicked.connect(self.reset_camera)

        btn_layout.addWidget(self.btn_left)
        btn_layout.addWidget(self.btn_right)
        btn_layout.addWidget(self.btn_up)
        btn_layout.addWidget(self.btn_down)
        btn_layout.addWidget(self.btn_top)
        btn_layout.addWidget(self.btn_reset)
        btn_layout.addStretch()

        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def _on_load_finished(self, ok):
        self.page_loaded = ok
        if ok:
            logger.debug("Plotly HTML страница загружена")

    def _run_js(self, js):
        """Выполнить JavaScript в браузере"""
        page = self.browser.page()
        if page:
            page.runJavaScript(js, 0, lambda result: None)

    def _update_camera(self):
        if not self.page_loaded:
            logger.warning("Страница ещё не загружена")
            return
        js = f"""
        (function() {{
            try {{
                var plotDiv = document.querySelector('.js-plotly-plot') || document.querySelector('.plotly');
                if (!plotDiv) {{
                    console.log('Plot div not found');
                    return;
                }}
                if (typeof Plotly === 'undefined') {{
                    console.log('Plotly not available');
                    return;
                }}
                Plotly.relayout(plotDiv, {{
                    'scene.camera.eye.x': {self.cam_x},
                    'scene.camera.eye.y': {self.cam_y},
                    'scene.camera.eye.z': {self.cam_z}
                }}).catch(function(err) {{
                    console.log('relayout error: ' + err);
                }});
            }} catch(e) {{
                console.log('Camera update error: ' + e);
            }}
        }})();
        """
        self._run_js(js)

    def _update_camera(self):
        if not self.page_loaded:
            logger.warning("Страница ещё не загружена")
            return
        js = f"""
        (function() {{
            try {{
                var plotDiv = document.querySelector('.js-plotly-plot') || document.querySelector('.plotly');
                if (!plotDiv) {{
                    console.log('Plot div not found');
                    return;
                }}
                if (typeof Plotly === 'undefined') {{
                    console.log('Plotly not available');
                    return;
                }}
                Plotly.relayout(plotDiv, {{
                    'scene.camera.eye.x': {self.cam_x},
                    'scene.camera.eye.y': {self.cam_y},
                    'scene.camera.eye.z': {self.cam_z}
                }}).catch(function(err) {{
                    console.log('relayout error: ' + err);
                }});
            }} catch(e) {{
                console.log('Camera update error: ' + e);
            }}
        }})();
        """
        self._run_js(js)

    def _rotate_camera(self, axis, angle_deg):
        """Вращать камеру через JS, сохраняя текущий масштаб"""
        if not self.page_loaded:
            return
        js = f"""
        (function() {{
            try {{
                var plotDiv = document.querySelector('.js-plotly-plot') || document.querySelector('.plotly');
                if (!plotDiv || !plotDiv.layout || !plotDiv.layout.scene || !plotDiv.layout.scene.camera) return;
                var eye = plotDiv.layout.scene.camera.eye;
                var x = eye.x, y = eye.y, z = eye.z;
                var angle = {angle_deg} * Math.PI / 180;
                var cosA = Math.cos(angle), sinA = Math.sin(angle);
                var nx, ny, nz;
                if ('{axis}' === 'y') {{
                    nx = x * cosA + z * sinA;
                    ny = y;
                    nz = -x * sinA + z * cosA;
                }} else if ('{axis}' === 'x') {{
                    nx = x;
                    ny = y * cosA - z * sinA;
                    nz = y * sinA + z * cosA;
                }}
                Plotly.relayout(plotDiv, {{
                    'scene.camera.eye.x': nx,
                    'scene.camera.eye.y': ny,
                    'scene.camera.eye.z': nz
                }});
            }} catch(e) {{
                console.log('Rotate error: ' + e);
            }}
        }})();
        """
        self._run_js(js)

    def _set_camera_view(self, view_type):
        """Установить вид камеры через JS"""
        if not self.page_loaded:
            return
        js = f"""
        (function() {{
            try {{
                var plotDiv = document.querySelector('.js-plotly-plot') || document.querySelector('.plotly');
                if (!plotDiv || !plotDiv.layout || !plotDiv.layout.scene || !plotDiv.layout.scene.camera) return;
                var eye = plotDiv.layout.scene.camera.eye;
                var x = eye.x, y = eye.y, z = eye.z;
                var dist = Math.sqrt(x*x + y*y + z*z);
                var target;
                if ('{view_type}' === 'top') {{
                    target = {{x: 0.01, y: dist * 0.98, z: 0.01}};
                }} else if ('{view_type}' === 'reset') {{
                    target = {{x: 2.5, y: 2.0, z: 2.5}};
                }}
                if (target) {{
                    Plotly.relayout(plotDiv, {{
                        'scene.camera.eye.x': target.x,
                        'scene.camera.eye.y': target.y,
                        'scene.camera.eye.z': target.z
                    }});
                }}
            }} catch(e) {{
                console.log('Set view error: ' + e);
            }}
        }})();
        """
        self._run_js(js)

    def rotate_left(self):
        self._rotate_camera('y', 15)

    def rotate_right(self):
        self._rotate_camera('y', -15)

    def rotate_up(self):
        self._rotate_camera('x', -15)

    def rotate_down(self):
        self._rotate_camera('x', 15)

    def top_view(self):
        self._set_camera_view('top')

    def reset_camera(self):
        self._set_camera_view('reset')

    def on_url_changed(self, url):
        pass

    def load_plotly_figure(self, fig):
        """
        Загрузить Plotly фигуру в виджет

        Параметры:
        - fig: Plotly figure object
        """
        temp_dir = tempfile.gettempdir()
        self.temp_html_path = os.path.join(temp_dir, 'plotly_silo_3d.html')

        fig.write_html(
            self.temp_html_path,
            include_plotlyjs=True,
            full_html=True,
            config={'responsive': True}
        )

        self.page_loaded = False
        self.browser.setUrl(QUrl.fromLocalFile(self.temp_html_path))

    def load_html(self, html_content):
        """Загрузить HTML строку напрямую"""
        self.page_loaded = False
        self.browser.setHtml(html_content)

    def cleanup(self):
        """Удалить временный файл"""
        if self.temp_html_path and os.path.exists(self.temp_html_path):
            try:
                os.remove(self.temp_html_path)
            except:
                pass


class PlotlyPlaceholder(QWidget):
    """Заглушка, если QtWebEngine не доступен"""

    def __init__(self, message="3D визуализация требует PyQt6.QtWebEngineWidgets", parent=None):
        super().__init__(parent)
        layout = QVBoxLayout()

        label = QLabel(f"⚠️ {message}\n\nУстановите: pip install PyQt6-WebEngine")
        label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                color: #f38ba8;
                background-color: #313244;
                padding: 20px;
                border-radius: 8px;
            }
        """)
        label.setWordWrap(True)
        layout.addWidget(label)

        self.setLayout(layout)
