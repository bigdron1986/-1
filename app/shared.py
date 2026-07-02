class TabContext:
    """Общее состояние, разделяемое между вкладками"""
    def __init__(self, db_conn, config, user_settings):
        self.db_conn = db_conn
        self.config = config
        self.user_settings = user_settings

        # Shared widget references (set by main window after creation)
        self.silo_combo = None
        self.suspension_combo = None
        self.plot_type_combo = None
        self.temp_threshold_spinbox = None
        self.start_date_edit = None
        self.end_date_edit = None
        self.date_range_label = None
        self.status_label = None
        self.period_buttons = []
        self.filter_group = None
        self.main_tabs = None
        self.tabs_combo = None
        self.email_button = None
        self.load_button = None
        self.export_button = None
        self.main_splitter = None
        self.show_year_check = None

        # Settings (synced from user_settings)
        self.temp_threshold = float(user_settings.get('temp_threshold', '15.0'))
        self.change_threshold = float(user_settings.get('change_threshold', '3.0'))
        self.date_format_with_year = user_settings.get('date_format_with_year', 'false') == 'true'
        self.color_hotspot = user_settings.get('color_hotspot', '#f38ba8')
        self.color_error = user_settings.get('color_error', '#fab387')
        self.color_normal = user_settings.get('color_normal', '#a6e3a1')
        self.color_warning = user_settings.get('color_warning', '#f9e2af')

        # Tab instance references (set after creation, for cross-tab calls)
        self.hotspots_tab = None
        self.silo_graphs_tab = None
        self.monitoring_tab = None
        self.breaks_tab = None
        self.model_3d_tab = None
        self.hottest_sensors_tab = None
        self.email_file_mixin = None

    def update_settings_from_db(self):
        """Sync settings from user_settings dict"""
        self.temp_threshold = float(self.user_settings.get('temp_threshold', '15.0'))
        self.change_threshold = float(self.user_settings.get('change_threshold', '3.0'))
        self.date_format_with_year = self.user_settings.get('date_format_with_year', 'false') == 'true'
        self.color_hotspot = self.user_settings.get('color_hotspot', '#f38ba8')
        self.color_error = self.user_settings.get('color_error', '#fab387')
        self.color_normal = self.user_settings.get('color_normal', '#a6e3a1')
        self.color_warning = self.user_settings.get('color_warning', '#f9e2af')
