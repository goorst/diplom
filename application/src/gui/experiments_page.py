
import csv
import json

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QFileDialog,
    QMessageBox,
    QHeaderView,
    QTabWidget,
)

from application.src.core.measurement_logger import MeasurementLogger


class AnalyticsChart(QWidget):
    """Компактный график для аналитики экспериментальных данных."""

    def __init__(self, title, unit="", chart_type="line", parent=None):
        super().__init__(parent)

        self.title = title
        self.unit = unit
        self.chart_type = chart_type

        self.labels = []
        self.values = []

        self.setMinimumHeight(210)

    def set_data(self, labels, values):
        self.labels = list(labels)
        self.values = list(values)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.fillRect(self.rect(), QColor("#303030"))

        painter.setPen(QColor("#ffffff"))
        painter.drawText(12, 22, self.title)

        chart_rect = self.rect().adjusted(
            48, 38, -15, -38
        )

        valid_values = [
            float(value)
            for value in self.values
            if value is not None
        ]

        if not valid_values:
            painter.setPen(QColor("#aaaaaa"))
            painter.drawText(
                chart_rect,
                Qt.AlignmentFlag.AlignCenter,
                "Нет данных для отображения"
            )
            return

        maximum = max(valid_values)
        minimum = min(valid_values)

        if self.chart_type == "bar":
            minimum = 0

        if maximum - minimum < 0.001:
            maximum += 1

        if self.chart_type == "line":
            padding = (maximum - minimum) * 0.12
            minimum -= padding
            maximum += padding

        if self.chart_type == "bar":
            maximum *= 1.15

        if maximum == minimum:
            maximum += 1

        # Горизонтальная сетка
        painter.setPen(QPen(QColor("#555555"), 1))

        for i in range(5):
            y = chart_rect.top() + (
                chart_rect.height() * i / 4
            )

            painter.drawLine(
                chart_rect.left(),
                int(y),
                chart_rect.right(),
                int(y)
            )

        # Подписи шкалы
        painter.setPen(QColor("#aaaaaa"))

        for i in range(5):
            value = maximum - (
                (maximum - minimum) * i / 4
            )

            y = chart_rect.top() + (
                chart_rect.height() * i / 4
            )

            painter.drawText(
                2,
                int(y) + 4,
                f"{value:.1f}"
            )

        if self.chart_type == "bar":
            self.draw_bars(
                painter,
                chart_rect,
                minimum,
                maximum
            )
        else:
            self.draw_line(
                painter,
                chart_rect,
                minimum,
                maximum
            )

        if self.unit:
            painter.setPen(QColor("#aaaaaa"))
            painter.drawText(
                chart_rect.left(),
                self.height() - 8,
                self.unit
            )

    def draw_line(
        self,
        painter,
        chart_rect,
        minimum,
        maximum
    ):
        if len(self.values) < 2:
            return

        points = [
            float(value)
            for value in self.values
            if value is not None
        ]

        if len(points) < 2:
            return

        painter.setPen(
            QPen(QColor("#35b7ff"), 2)
        )

        for i in range(1, len(points)):
            x1 = chart_rect.left() + (
                chart_rect.width() * (i - 1)
                / (len(points) - 1)
            )

            x2 = chart_rect.left() + (
                chart_rect.width() * i
                / (len(points) - 1)
            )

            y1 = chart_rect.bottom() - (
                (points[i - 1] - minimum)
                / (maximum - minimum)
                * chart_rect.height()
            )

            y2 = chart_rect.bottom() - (
                (points[i] - minimum)
                / (maximum - minimum)
                * chart_rect.height()
            )

            painter.drawLine(
                int(x1), int(y1),
                int(x2), int(y2)
            )

        # Подписи времени: начало, середина, конец
        if self.labels:
            painter.setPen(QColor("#aaaaaa"))

            indexes = sorted({
                0,
                len(self.labels) // 2,
                len(self.labels) - 1
            })

            for index in indexes:
                if index >= len(self.labels):
                    continue

                x = chart_rect.left() + (
                    chart_rect.width() * index
                    / max(1, len(self.labels) - 1)
                )

                label = str(self.labels[index])

                if len(label) > 16:
                    label = label[-8:]

                painter.drawText(
                    int(x) - 20,
                    self.height() - 8,
                    label
                )

    def draw_bars(
        self,
        painter,
        chart_rect,
        minimum,
        maximum
    ):
        values = [
            float(value) if value is not None else 0
            for value in self.values
        ]

        if not values:
            return

        count = len(values)
        slot_width = chart_rect.width() / count
        bar_width = max(4, slot_width * 0.55)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#35b7ff"))

        for index, value in enumerate(values):
            height = (
                (value - minimum)
                / (maximum - minimum)
                * chart_rect.height()
            )

            x = (
                chart_rect.left()
                + index * slot_width
                + (slot_width - bar_width) / 2
            )

            y = chart_rect.bottom() - height

            painter.drawRect(
                int(x),
                int(y),
                int(bar_width),
                max(1, int(height))
            )

            painter.setPen(QColor("#ffffff"))
            painter.drawText(
                int(x - 8),
                int(y) - 5,
                f"{value:.1f}"
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#35b7ff"))

            if index < len(self.labels):
                label = str(self.labels[index])

                if len(label) > 12:
                    label = label[:10] + ".."

                painter.setPen(QColor("#aaaaaa"))
                painter.drawText(
                    int(x - 15),
                    chart_rect.bottom() + 17,
                    label
                )
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#35b7ff"))


class ExperimentsPage(QWidget):
    """Просмотр и анализ экспериментальных измерений."""

    MAX_DISPLAY_ROWS = 1000
    MAX_CHART_POINTS = 300
    MAX_COMPARISON_ITEMS = 8

    def __init__(self, parent=None):
        super().__init__(parent)

        self.logger = MeasurementLogger()

        self.all_rows = []
        self.filtered_rows = []

        self.columns = [
            ("timestamp", "Дата и время"),
            ("product_id", "ID изделия"),
            ("part_type", "Тип детали"),
            ("material", "Материал"),
            ("operation", "Операция"),
            ("tool_id", "Инструмент"),
            ("spindle_speed", "Обороты"),
            ("feed_rate", "Подача"),
            ("cutting_depth", "Глубина"),
            ("temperature", "Температура"),
            ("vibration", "Вибрация"),
            ("spindle_load", "Нагрузка"),
            ("tool_wear", "Износ"),
            ("diagnosis_status", "Диагностика"),
            ("active_faults", "Неисправности"),
        ]

        self.build_ui()
        self.refresh_data()

    # ==========================================
    # СОЗДАНИЕ ИНТЕРФЕЙСА
    # ==========================================

    def build_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Экспериментальные данные")
        title.setStyleSheet(
            "font-size: 22px; font-weight: bold; padding: 8px;"
        )
        root.addWidget(title)

        description = QLabel(
            "Просмотр, фильтрация и анализ измерений "
            "виртуального станка."
        )
        root.addWidget(description)

        # Статистика
        statistics_group = QGroupBox("Общая статистика")
        statistics_layout = QGridLayout(statistics_group)

        self.total_label = QLabel("Всего измерений: 0")
        self.average_temperature_label = QLabel(
            "Средняя температура: --"
        )
        self.max_vibration_label = QLabel(
            "Максимальная вибрация: --"
        )
        self.warning_label = QLabel("Предупреждений: 0")
        self.critical_label = QLabel(
            "Критических состояний: 0"
        )
        self.critical_percent_label = QLabel(
            "Доля критических состояний: 0%"
        )

        statistics_layout.addWidget(
            self.total_label, 0, 0
        )
        statistics_layout.addWidget(
            self.average_temperature_label, 0, 1
        )
        statistics_layout.addWidget(
            self.max_vibration_label, 0, 2
        )
        statistics_layout.addWidget(
            self.warning_label, 1, 0
        )
        statistics_layout.addWidget(
            self.critical_label, 1, 1
        )
        statistics_layout.addWidget(
            self.critical_percent_label, 1, 2
        )

        root.addWidget(statistics_group)

        # Фильтры
        filters_group = QGroupBox("Фильтрация данных")
        filters_layout = QGridLayout(filters_group)

        self.product_filter = QComboBox()
        self.material_filter = QComboBox()
        self.operation_filter = QComboBox()
        self.status_filter = QComboBox()

        filters_layout.addWidget(
            QLabel("Изделие:"), 0, 0
        )
        filters_layout.addWidget(
            self.product_filter, 0, 1
        )

        filters_layout.addWidget(
            QLabel("Материал:"), 0, 2
        )
        filters_layout.addWidget(
            self.material_filter, 0, 3
        )

        filters_layout.addWidget(
            QLabel("Операция:"), 1, 0
        )
        filters_layout.addWidget(
            self.operation_filter, 1, 1
        )

        filters_layout.addWidget(
            QLabel("Диагностика:"), 1, 2
        )
        filters_layout.addWidget(
            self.status_filter, 1, 3
        )

        root.addWidget(filters_group)

        # Кнопки
        buttons_layout = QHBoxLayout()

        self.refresh_button = QPushButton("Обновить данные")
        self.export_button = QPushButton("Экспортировать CSV")
        self.reset_filters_button = QPushButton(
            "Сбросить фильтры"
        )

        self.refresh_button.clicked.connect(self.refresh_data)
        self.export_button.clicked.connect(self.export_csv)
        self.reset_filters_button.clicked.connect(
            self.reset_filters
        )

        buttons_layout.addWidget(self.refresh_button)
        buttons_layout.addWidget(self.export_button)
        buttons_layout.addWidget(self.reset_filters_button)
        buttons_layout.addStretch()

        root.addLayout(buttons_layout)

        # Вкладки журнала и аналитики
        self.content_tabs = QTabWidget()

        self.build_table_tab()
        self.build_trends_tab()
        self.build_summary_tab()

        root.addWidget(self.content_tabs, 1)

        self.result_label = QLabel(
            "Отображено записей: 0"
        )
        root.addWidget(self.result_label)

        # События фильтров
        self.product_filter.currentIndexChanged.connect(
            self.apply_filters
        )
        self.material_filter.currentIndexChanged.connect(
            self.apply_filters
        )
        self.operation_filter.currentIndexChanged.connect(
            self.apply_filters
        )
        self.status_filter.currentIndexChanged.connect(
            self.apply_filters
        )

    def build_table_tab(self):
        table_tab = QWidget()
        layout = QVBoxLayout(table_tab)

        table_group = QGroupBox("Журнал измерений")
        table_layout = QVBoxLayout(table_group)

        self.table = QTableWidget()

        self.table.setColumnCount(len(self.columns))
        self.table.setHorizontalHeaderLabels(
            [title for _, title in self.columns]
        )

        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)

        header = self.table.horizontalHeader()

        header.setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )

        header.setDefaultSectionSize(120)
        header.setMinimumSectionSize(80)
        header.setStretchLastSection(True)

        self.table.setColumnWidth(0, 155)
        self.table.setColumnWidth(1, 110)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 110)
        self.table.setColumnWidth(4, 140)
        self.table.setColumnWidth(14, 180)

        table_layout.addWidget(self.table)
        layout.addWidget(table_group)

        self.content_tabs.addTab(
            table_tab,
            "Журнал измерений"
        )

    def build_trends_tab(self):
        trends_tab = QWidget()
        layout = QVBoxLayout(trends_tab)

        description = QLabel(
            "Изменение показаний датчиков во времени. "
            "На графиках отображаются последние 300 измерений "
            "из текущей выборки."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        charts_group = QGroupBox("Динамика параметров")
        charts_layout = QGridLayout(charts_group)

        self.temperature_chart = AnalyticsChart(
            "Температура",
            "°C"
        )

        self.vibration_chart = AnalyticsChart(
            "Вибрация",
            "мм/с"
        )

        self.spindle_load_chart = AnalyticsChart(
            "Нагрузка шпинделя",
            "%"
        )

        self.tool_wear_chart = AnalyticsChart(
            "Износ инструмента",
            "%"
        )

        charts_layout.addWidget(
            self.temperature_chart, 0, 0
        )
        charts_layout.addWidget(
            self.vibration_chart, 0, 1
        )
        charts_layout.addWidget(
            self.spindle_load_chart, 1, 0
        )
        charts_layout.addWidget(
            self.tool_wear_chart, 1, 1
        )

        layout.addWidget(charts_group)
        layout.addStretch()

        self.content_tabs.addTab(
            trends_tab,
            "Динамика параметров"
        )

    def build_summary_tab(self):
        summary_tab = QWidget()
        layout = QVBoxLayout(summary_tab)

        description = QLabel(
            "Сводные показатели рассчитываются по всем "
            "записям, прошедшим текущую фильтрацию."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        charts_group = QGroupBox("Сравнительная аналитика")
        charts_layout = QGridLayout(charts_group)

        self.status_chart = AnalyticsChart(
            "Распределение технических состояний",
            "Количество измерений",
            "bar"
        )

        self.product_chart = AnalyticsChart(
            "Средняя температура по изделиям",
            "°C",
            "bar"
        )

        self.fault_chart = AnalyticsChart(
            "Средняя нагрузка шпинделя по неисправностям",
            "%",
            "bar"
        )

        charts_layout.addWidget(
            self.status_chart, 0, 0
        )
        charts_layout.addWidget(
            self.product_chart, 0, 1
        )
        charts_layout.addWidget(
            self.fault_chart, 1, 0, 1, 2
        )

        layout.addWidget(charts_group)
        layout.addStretch()

        self.content_tabs.addTab(
            summary_tab,
            "Сводная аналитика"
        )

    # ==========================================
    # ЗАГРУЗКА ДАННЫХ
    # ==========================================

    def refresh_data(self):
        try:
            self.all_rows = self.logger.list_measurements()

            self.populate_filters()
            self.apply_filters()

        except Exception as error:
            QMessageBox.critical(
                self,
                "Ошибка загрузки",
                str(error)
            )

    def populate_filters(self):
        filters = [
            self.product_filter,
            self.material_filter,
            self.operation_filter,
            self.status_filter,
        ]

        previous_block_states = [
            combo.blockSignals(True)
            for combo in filters
        ]

        try:
            for combo in filters:
                combo.clear()

            self.product_filter.addItem(
                "Все изделия", None
            )

            products = {}

            for row in self.all_rows:
                product_id = row.get("product_id")

                if product_id is not None and product_id != "":
                    products[product_id] = row.get(
                        "part_type", ""
                    )

            for product_id, part_type in sorted(
                products.items(),
                key=lambda item: str(item[0])
            ):
                label = f"{product_id} — {part_type}"

                self.product_filter.addItem(
                    label, product_id
                )

            self.material_filter.addItem(
                "Все материалы", ""
            )

            materials = sorted({
                row.get("material")
                for row in self.all_rows
                if row.get("material")
            })

            for material in materials:
                self.material_filter.addItem(
                    str(material), material
                )

            self.operation_filter.addItem(
                "Все операции", ""
            )

            operations = sorted({
                row.get("operation")
                for row in self.all_rows
                if row.get("operation")
            })

            for operation in operations:
                self.operation_filter.addItem(
                    str(operation), operation
                )

            self.status_filter.addItem(
                "Все состояния", ""
            )

            statuses = sorted({
                row.get("diagnosis_status")
                for row in self.all_rows
                if row.get("diagnosis_status")
            })

            for status in statuses:
                self.status_filter.addItem(
                    str(status), status
                )

        finally:
            for combo, previous_state in zip(
                filters,
                previous_block_states
            ):
                combo.blockSignals(previous_state)

    # ==========================================
    # ФИЛЬТРАЦИЯ
    # ==========================================

    def apply_filters(self):
        product_id = self.product_filter.currentData()
        material = self.material_filter.currentData()
        operation = self.operation_filter.currentData()
        status = self.status_filter.currentData()

        self.filtered_rows = [
            row
            for row in self.all_rows
            if (
                (product_id is None or row.get("product_id") == product_id)
                and (not material or row.get("material") == material)
                and (not operation or row.get("operation") == operation)
                and (not status or row.get("diagnosis_status") == status)
            )
        ]

        self.update_table()
        self.update_statistics()
        self.update_analytics()

    def reset_filters(self):
        combos = [
            self.product_filter,
            self.material_filter,
            self.operation_filter,
            self.status_filter,
        ]

        previous_block_states = [
            combo.blockSignals(True)
            for combo in combos
        ]

        try:
            for combo in combos:
                combo.setCurrentIndex(0)

        finally:
            for combo, previous_state in zip(
                combos,
                previous_block_states
            ):
                combo.blockSignals(previous_state)

        self.apply_filters()

    # ==========================================
    # ФОРМАТИРОВАНИЕ
    # ==========================================

    @staticmethod
    def format_value(value):
        if value is None:
            return ""

        if isinstance(value, float):
            return f"{value:.2f}"

        if isinstance(value, (dict, list)):
            return json.dumps(
                value,
                ensure_ascii=False
            )

        return str(value)

    @staticmethod
    def format_faults(value):
        if not value:
            return ""

        try:
            faults = json.loads(value)

            if isinstance(faults, list):
                return ", ".join(
                    str(item) for item in faults
                )

        except (TypeError, json.JSONDecodeError):
            pass

        return str(value)

    @staticmethod
    def to_number(value):
        try:
            if value is None:
                return None

            return float(value)

        except (TypeError, ValueError):
            return None

    @staticmethod
    def parse_faults(value):
        if not value:
            return []

        if isinstance(value, list):
            return value

        if isinstance(value, dict):
            return list(value.keys())

        try:
            result = json.loads(value)

            if isinstance(result, list):
                return result

            if isinstance(result, dict):
                return list(result.keys())

        except (TypeError, json.JSONDecodeError):
            pass

        return [str(value)]

    # ==========================================
    # ОБНОВЛЕНИЕ ТАБЛИЦЫ
    # ==========================================

    def update_table(self):
        display_rows = self.filtered_rows[
            :self.MAX_DISPLAY_ROWS
        ]

        self.table.setUpdatesEnabled(False)

        try:
            self.table.clearContents()
            self.table.setRowCount(len(display_rows))

            for row_index, row in enumerate(display_rows):
                for column_index, (key, _) in enumerate(
                    self.columns
                ):
                    value = row.get(key)

                    if key == "active_faults":
                        text = self.format_faults(value)
                    else:
                        text = self.format_value(value)

                    item = QTableWidgetItem(text)

                    if key in (
                        "spindle_speed",
                        "feed_rate",
                        "cutting_depth",
                        "temperature",
                        "vibration",
                        "spindle_load",
                        "tool_wear",
                    ):
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignCenter
                        )

                    self.table.setItem(
                        row_index,
                        column_index,
                        item
                    )

        finally:
            self.table.setUpdatesEnabled(True)
            self.table.viewport().update()

        displayed_count = len(display_rows)
        total_filtered = len(self.filtered_rows)

        self.result_label.setText(
            f"Отображено в таблице: {displayed_count} "
            f"из {total_filtered} отфильтрованных записей "
            f"(всего в базе: {len(self.all_rows)})"
        )

    # ==========================================
    # СТАТИСТИКА
    # ==========================================

    def update_statistics(self):
        rows = self.filtered_rows

        total = len(rows)

        self.total_label.setText(
            f"Всего измерений: {total}"
        )

        temperatures = [
            number
            for row in rows
            if (
                number := self.to_number(
                    row.get("temperature")
                )
            ) is not None
        ]

        vibrations = [
            number
            for row in rows
            if (
                number := self.to_number(
                    row.get("vibration")
                )
            ) is not None
        ]

        if temperatures:
            average_temperature = (
                sum(temperatures) / len(temperatures)
            )

            self.average_temperature_label.setText(
                f"Средняя температура: "
                f"{average_temperature:.2f} °C"
            )
        else:
            self.average_temperature_label.setText(
                "Средняя температура: --"
            )

        if vibrations:
            self.max_vibration_label.setText(
                f"Максимальная вибрация: "
                f"{max(vibrations):.2f} мм/с"
            )
        else:
            self.max_vibration_label.setText(
                "Максимальная вибрация: --"
            )

        warning_count = sum(
            1
            for row in rows
            if "ПРЕДУПРЕЖДЕНИЕ"
            in str(row.get("diagnosis_status", "")).upper()
        )

        critical_count = sum(
            1
            for row in rows
            if "КРИТИЧЕСКОЕ"
            in str(row.get("diagnosis_status", "")).upper()
        )

        self.warning_label.setText(
            f"Предупреждений: {warning_count}"
        )

        self.critical_label.setText(
            f"Критических состояний: {critical_count}"
        )

        critical_percent = (
            critical_count / total * 100
            if total else 0
        )

        self.critical_percent_label.setText(
            f"Доля критических состояний: "
            f"{critical_percent:.1f}%"
        )

    # ==========================================
    # АНАЛИТИКА
    # ==========================================

    def update_analytics(self):
        self.update_trend_charts()
        self.update_status_chart()
        self.update_product_chart()
        self.update_fault_chart()

    def update_trend_charts(self):
        # Сортируем по времени для правильного направления графика.
        rows = sorted(
            self.filtered_rows,
            key=lambda row: str(row.get("timestamp", ""))
        )

        rows = rows[-self.MAX_CHART_POINTS:]

        labels = [
            str(row.get("timestamp", ""))
            for row in rows
        ]

        chart_definitions = [
            (
                self.temperature_chart,
                "temperature"
            ),
            (
                self.vibration_chart,
                "vibration"
            ),
            (
                self.spindle_load_chart,
                "spindle_load"
            ),
            (
                self.tool_wear_chart,
                "tool_wear"
            ),
        ]

        for chart, key in chart_definitions:
            values = [
                self.to_number(row.get(key))
                for row in rows
            ]

            chart.set_data(labels, values)

    def update_status_chart(self):
        status_counts = {}

        for row in self.filtered_rows:
            status = str(
                row.get("diagnosis_status") or "Не определено"
            )

            status_counts[status] = (
                status_counts.get(status, 0) + 1
            )

        labels = list(status_counts.keys())
        values = list(status_counts.values())

        self.status_chart.set_data(
            labels,
            values
        )

    def update_product_chart(self):
        product_data = {}

        for row in self.filtered_rows:
            temperature = self.to_number(
                row.get("temperature")
            )

            if temperature is None:
                continue

            product_id = row.get("product_id", "Без ID")
            part_type = row.get("part_type", "")

            label = f"{product_id} {part_type}".strip()

            if not label:
                label = "Неизвестное изделие"

            if label not in product_data:
                product_data[label] = {
                    "sum": 0.0,
                    "count": 0
                }

            product_data[label]["sum"] += temperature
            product_data[label]["count"] += 1

        averages = []

        for label, values in product_data.items():
            average = (
                values["sum"] / values["count"]
            )

            averages.append((label, average))

        averages.sort(
            key=lambda item: item[1],
            reverse=True
        )

        averages = averages[:self.MAX_COMPARISON_ITEMS]

        self.product_chart.set_data(
            [item[0] for item in averages],
            [item[1] for item in averages]
        )

    def update_fault_chart(self):
        fault_data = {}

        for row in self.filtered_rows:
            load = self.to_number(
                row.get("spindle_load")
            )

            if load is None:
                continue

            faults = self.parse_faults(
                row.get("active_faults")
            )

            if faults:
                label = ", ".join(
                    str(fault) for fault in faults
                )
            else:
                label = "Без неисправностей"

            if label not in fault_data:
                fault_data[label] = {
                    "sum": 0.0,
                    "count": 0
                }

            fault_data[label]["sum"] += load
            fault_data[label]["count"] += 1

        averages = []

        for label, values in fault_data.items():
            average = (
                values["sum"] / values["count"]
            )

            averages.append((label, average))

        averages.sort(
            key=lambda item: item[1],
            reverse=True
        )

        averages = averages[:self.MAX_COMPARISON_ITEMS]

        self.fault_chart.set_data(
            [item[0] for item in averages],
            [item[1] for item in averages]
        )

    # ==========================================
    # ЭКСПОРТ CSV
    # ==========================================

    def export_csv(self):
        if not self.filtered_rows:
            QMessageBox.information(
                self,
                "Экспорт",
                "Нет данных для экспорта."
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить экспериментальные данные",
            "experimental_data.csv",
            "CSV-файлы (*.csv)"
        )

        if not file_path:
            return

        if Path(file_path).suffix.lower() != ".csv":
            file_path += ".csv"

        try:
            columns = list(self.filtered_rows[0].keys())

            with open(
                file_path,
                "w",
                newline="",
                encoding="utf-8-sig"
            ) as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=columns,
                    delimiter=";"
                )

                writer.writeheader()
                writer.writerows(self.filtered_rows)

            QMessageBox.information(
                self,
                "Экспорт завершён",
                f"Экспортировано записей: "
                f"{len(self.filtered_rows)}\n\n"
                f"Файл:\n{file_path}"
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Ошибка экспорта",
                str(error)
            )
