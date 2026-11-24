
from collections import deque
import time
import uuid

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QCheckBox,
    QMessageBox,
    QFrame,
    QScrollArea,
    QFileDialog,
)

from application.src.products import ProductManager
from application.src.simulator import MachineSimulator
from application.src.core.condition_monitor import ConditionMonitor
from application.src.core.measurement_logger import MeasurementLogger
from application.src.core.model_trainer import ModelTrainer
from application.src.core.background_workers import (
    MeasurementWriter,
    MLPredictionWorker,
)


class SensorChart(QWidget):

    def __init__(self, title, unit, parent=None):
        super().__init__(parent)

        self.title = title
        self.unit = unit
        self.values = deque(maxlen=60)

        self.setMinimumHeight(145)

    def add_value(self, value):
        self.values.append(float(value))
        self.update()

    def clear(self):
        self.values.clear()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#303030"))

        painter.setPen(QColor("#ffffff"))
        painter.drawText(
            12, 22,
            f"{self.title} ({self.unit})"
        )

        chart_rect = self.rect().adjusted(
            38, 35, -12, -24
        )

        if len(self.values) < 2:
            painter.setPen(QColor("#aaaaaa"))
            painter.drawText(
                chart_rect,
                Qt.AlignmentFlag.AlignCenter,
                "Ожидание измерений"
            )
            return

        minimum = min(self.values)
        maximum = max(self.values)

        if maximum - minimum < 0.001:
            minimum -= 1
            maximum += 1
        else:
            padding = (maximum - minimum) * 0.12
            minimum -= padding
            maximum += padding

        painter.setPen(QPen(QColor("#666666"), 1))

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

        painter.setPen(QColor("#aaaaaa"))
        painter.drawText(
            3, chart_rect.top() + 5,
            f"{maximum:.1f}"
        )
        painter.drawText(
            3, chart_rect.bottom(),
            f"{minimum:.1f}"
        )

        points = list(self.values)
        painter.setPen(QPen(QColor("#35b7ff"), 2))

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


class SimulatorPage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.product_manager = ProductManager()
        self.measurement_logger = MeasurementLogger()
        self.model_trainer = ModelTrainer()

        self.measurement_writer = MeasurementWriter(
            logger=self.measurement_logger,
            batch_size=25,
            flush_interval=0.5,
        )
        self.measurement_writer.error_occurred.connect(
            self.on_writer_error
        )
        self.measurement_writer.start()

        self.ml_worker = None
        self._last_chart_update = 0.0

        self.machine = MachineSimulator(interval=1000)

        self.current_product = None
        self.current_operation = None

        self.active_faults = []
        self.session_measurement_count = 0
        self.logging_failed = False
        self.current_experiment_id = None

        self.ml_model_loaded = False

        self.machine.measurement_ready.connect(
            self.update_measurements
        )
        self.machine.status_changed.connect(
            self.update_status
        )
        self.machine.error_occurred.connect(
            self.show_simulator_error
        )

        self.build_ui()
        self.load_products()

    # ==========================================
    # ПОСТРОЕНИЕ ИНТЕРФЕЙСА
    # ==========================================

    def build_ui(self):
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        content_widget = QWidget()
        root = QVBoxLayout(content_widget)

        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        # Заголовок
        title = QLabel(
            "Симулятор технологического процесса ЧПУ"
        )
        title.setStyleSheet(
            "font-size: 22px; font-weight: bold; padding: 8px;"
        )
        root.addWidget(title)

        # Выбор изделия и операции
        selection_group = QGroupBox("Объект моделирования")
        selection_layout = QFormLayout(selection_group)

        self.product_combo = QComboBox()
        self.operation_combo = QComboBox()

        selection_layout.addRow(
            "Изделие:", self.product_combo
        )
        selection_layout.addRow(
            "Технологическая операция:", self.operation_combo
        )

        root.addWidget(selection_group)

        # Параметры обработки
        parameters_group = QGroupBox("Режимы обработки")
        parameters_layout = QGridLayout(parameters_group)

        self.speed_spin = self.create_double_spin(
            100, 30000, 1800, 0
        )
        self.feed_spin = self.create_double_spin(
            0.1, 10000, 200, 1
        )
        self.depth_spin = self.create_double_spin(
            0.01, 100, 1.5, 2
        )

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(100, 10000)
        self.interval_spin.setValue(300)
        self.interval_spin.setSuffix(" мс")

        fields = [
            ("Обороты шпинделя, об/мин:", self.speed_spin, 0, 0),
            ("Подача:", self.feed_spin, 0, 2),
            ("Глубина резания, мм:", self.depth_spin, 1, 0),
            ("Интервал измерений:", self.interval_spin, 1, 2),
        ]

        for label, widget, row, column in fields:
            parameters_layout.addWidget(
                QLabel(label), row, column
            )
            parameters_layout.addWidget(
                widget, row, column + 1
            )

        root.addWidget(parameters_group)

        # Неисправности
        faults_group = QGroupBox("Имитация неисправностей")
        faults_layout = QHBoxLayout(faults_group)

        self.fault_checks = {}

        fault_names = {
            "overheating": "Перегрев",
            "high_vibration": "Повышенная вибрация",
            "overload": "Перегрузка шпинделя",
            "tool_wear": "Износ инструмента",
            "combined": "Комплексная неисправность",
        }

        for code, name in fault_names.items():
            checkbox = QCheckBox(name)
            self.fault_checks[code] = checkbox
            faults_layout.addWidget(checkbox)

        root.addWidget(faults_group)

        # Управление симуляцией
        controls_layout = QHBoxLayout()

        self.start_button = QPushButton(
            "Запустить симуляцию"
        )
        self.stop_button = QPushButton("Остановить")
        self.reset_button = QPushButton(
            "Сбросить износ инструмента"
        )

        self.stop_button.setEnabled(False)

        self.start_button.clicked.connect(
            self.start_simulation
        )
        self.stop_button.clicked.connect(
            self.stop_simulation
        )
        self.reset_button.clicked.connect(
            self.reset_tool
        )

        controls_layout.addWidget(self.start_button)
        controls_layout.addWidget(self.stop_button)
        controls_layout.addWidget(self.reset_button)

        root.addLayout(controls_layout)

        # Состояние эмулятора
        status_group = QGroupBox("Состояние эмулятора")
        status_layout = QHBoxLayout(status_group)

        self.status_label = QLabel("Эмулятор остановлен")
        self.status_label.setStyleSheet(
            "font-weight: bold; color: #ff7777;"
        )

        self.measurement_label = QLabel(
            "Измерений за запуск: 0"
        )

        status_layout.addWidget(QLabel("Статус:"))
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.measurement_label)

        root.addWidget(status_group)

        # Диагностика
        diagnosis_group = QGroupBox(
            "Автоматическая оценка технического состояния"
        )
        diagnosis_layout = QVBoxLayout(diagnosis_group)

        self.diagnosis_label = QLabel(
            "Ожидание данных датчиков"
        )
        self.diagnosis_label.setStyleSheet(
            "font-size: 18px; font-weight: bold; "
            "color: #aaaaaa; padding: 5px;"
        )

        self.reasons_label = QLabel(
            "Причины отклонений появятся после начала измерений."
        )
        self.reasons_label.setWordWrap(True)

        self.recommendations_label = QLabel("")
        self.recommendations_label.setWordWrap(True)

        diagnosis_layout.addWidget(self.diagnosis_label)
        diagnosis_layout.addWidget(self.reasons_label)
        diagnosis_layout.addWidget(
            self.recommendations_label
        )

        # ML-диагностика
        ml_separator = QFrame()
        ml_separator.setFrameShape(QFrame.Shape.HLine)
        ml_separator.setFrameShadow(QFrame.Shadow.Sunken)

        diagnosis_layout.addWidget(ml_separator)

        ml_title = QLabel("Диагностика с использованием ML-модели")
        ml_title.setStyleSheet(
            "font-size: 16px; font-weight: bold; padding-top: 5px;"
        )
        diagnosis_layout.addWidget(ml_title)

        self.ml_load_button = QPushButton(
            "Загрузить ML-модель"
        )
        self.ml_load_button.clicked.connect(
            self.load_ml_model
        )

        self.ml_status_label = QLabel(
            "ML-модель не загружена"
        )
        self.ml_status_label.setStyleSheet(
            "font-weight: bold; color: #aaaaaa; padding: 5px;"
        )

        self.ml_results_label = QLabel(
            "Результаты прогнозирования появятся после загрузки модели."
        )
        self.ml_results_label.setWordWrap(True)
        self.ml_results_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        diagnosis_layout.addWidget(self.ml_load_button)
        diagnosis_layout.addWidget(self.ml_status_label)
        diagnosis_layout.addWidget(self.ml_results_label)

        root.addWidget(diagnosis_group)

        # Показания датчиков
        sensors_group = QGroupBox("Показания датчиков")
        sensors_layout = QGridLayout(sensors_group)

        self.sensor_labels = {}

        sensor_definitions = [
            ("temperature", "Температура", "°C"),
            ("vibration", "Вибрация", "мм/с"),
            ("spindle_load", "Нагрузка шпинделя", "%"),
            ("tool_wear", "Износ инструмента", "%"),
        ]

        for index, (key, name, unit) in enumerate(
            sensor_definitions
        ):
            card = QFrame()
            card.setFrameShape(QFrame.Shape.StyledPanel)
            card.setStyleSheet("""
                QFrame {
                    background-color: #383838;
                    border: 1px solid #555555;
                    border-radius: 5px;
                }
            """)

            card_layout = QVBoxLayout(card)

            name_label = QLabel(name)
            value_label = QLabel("--")
            value_label.setStyleSheet(
                "font-size: 24px; font-weight: bold;"
            )

            unit_label = QLabel(unit)

            card_layout.addWidget(name_label)
            card_layout.addWidget(value_label)
            card_layout.addWidget(unit_label)

            sensors_layout.addWidget(card, 0, index)
            self.sensor_labels[key] = value_label

        root.addWidget(sensors_group)

        # Графики
        charts_group = QGroupBox(
            "Изменение параметров во времени"
        )
        charts_layout = QGridLayout(charts_group)

        self.charts = {
            "temperature": SensorChart("Температура", "°C"),
            "vibration": SensorChart("Вибрация", "мм/с"),
            "spindle_load": SensorChart("Нагрузка шпинделя", "%"),
            "tool_wear": SensorChart("Износ инструмента", "%"),
        }

        positions = [
            (0, 0, "temperature"),
            (0, 1, "vibration"),
            (1, 0, "spindle_load"),
            (1, 1, "tool_wear"),
        ]

        for row, column, key in positions:
            charts_layout.addWidget(
                self.charts[key], row, column
            )

        root.addWidget(charts_group)

        self.scroll_area.setWidget(content_widget)
        outer_layout.addWidget(self.scroll_area)

        # События фильтров
        self.product_combo.currentIndexChanged.connect(
            self.on_product_changed
        )
        self.operation_combo.currentIndexChanged.connect(
            self.on_operation_changed
        )

    @staticmethod
    def create_double_spin(minimum, maximum, value, decimals):
        spin = QDoubleSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        spin.setDecimals(decimals)
        spin.setSingleStep(
            1 if decimals == 0 else 0.1
        )
        return spin

    # ==========================================
    # ЗАГРУЗКА ИЗДЕЛИЙ И ОПЕРАЦИЙ
    # ==========================================

    def load_products(self):
        self.product_combo.clear()

        products = self.product_manager.list_products()

        for product in products:
            self.product_combo.addItem(
                product["name"],
                product
            )

        if not products:
            self.operation_combo.clear()
            self.current_product = None

    def on_product_changed(self, index):
        if index < 0:
            self.current_product = None
            self.operation_combo.clear()
            return

        self.current_product = (
            self.product_combo.itemData(index)
        )

        self.load_operations()

    def load_operations(self):
        self.operation_combo.blockSignals(True)
        self.operation_combo.clear()

        operations = self.product_manager.list_operations(
            self.current_product["product_id"]
        )

        for operation in operations:
            self.operation_combo.addItem(
                (
                    f"{operation['sequence_number']}. "
                    f"{operation['operation_name']}"
                ),
                operation
            )

        self.operation_combo.blockSignals(False)

        if operations:
            self.operation_combo.setCurrentIndex(0)
            self.on_operation_changed(0)
        else:
            self.current_operation = None

    def on_operation_changed(self, index):
        if index < 0:
            self.current_operation = None
            return

        self.current_operation = (
            self.operation_combo.itemData(index)
        )

        operation = self.current_operation

        if operation.get("spindle_speed") is not None:
            self.speed_spin.setValue(
                operation["spindle_speed"]
            )

        if operation.get("feed_rate") is not None:
            self.feed_spin.setValue(
                operation["feed_rate"]
            )

        if operation.get("cutting_depth") is not None:
            self.depth_spin.setValue(
                operation["cutting_depth"]
            )

    # ==========================================
    # НАСТРОЙКА СИМУЛЯТОРА
    # ==========================================

    def apply_configuration(self):
        if not self.current_product:
            raise ValueError(
                "В базе нет выбранного изделия."
            )

        operation = self.current_operation or {}

        product_data = {
            "product_id": self.current_product["product_id"],
            "part_type": self.current_product["part_type"],
            "material": self.current_product["material"],
            "operation": operation.get(
                "operation_name", "Обработка"
            ),
            "tool_id": operation.get("tool_id") or "TOOL-001",
        }

        parameters = {
            "spindle_speed": self.speed_spin.value(),
            "feed_rate": self.feed_spin.value(),
            "cutting_depth": self.depth_spin.value(),
        }

        self.active_faults = [
            code
            for code, checkbox in self.fault_checks.items()
            if checkbox.isChecked()
        ]

        self.machine.set_product(product_data)
        self.machine.set_parameters(parameters)
        self.machine.set_faults(self.active_faults)
        self.machine.set_interval(
            self.interval_spin.value()
        )

    # ==========================================
    # ЗАПУСК И ОСТАНОВКА
    # ==========================================

    def start_simulation(self):
        try:
            self.apply_configuration()
            self.current_experiment_id = str(uuid.uuid4())

            print(
                "\nНовый эксперимент:",
                self.current_experiment_id
            )

            self.session_measurement_count = 0
            self.logging_failed = False
            self._last_chart_update = 0.0

            self.measurement_label.setText(
                "Измерений за запуск: 0"
            )

            for chart in self.charts.values():
                chart.clear()

            self.diagnosis_label.setText(
                "Ожидание первого измерения..."
            )
            self.reasons_label.setText("")
            self.recommendations_label.setText("")

            self.ml_results_label.setText(
                "Ожидание измерений..."
                if self.ml_model_loaded
                else "ML-модель не загружена."
            )

            self.machine.start_simulation()

            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)

        except Exception as error:
            self.show_error(error)

    def stop_simulation(self):
        self.machine.stop_simulation()

        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)

    def reset_tool(self):
        self.machine.reset_tool()

        self.sensor_labels["tool_wear"].setText("0.0")
        self.charts["tool_wear"].clear()

    # ==========================================
    # ОБНОВЛЕНИЕ ПОКАЗАНИЙ И СОХРАНЕНИЕ
    # ==========================================

    def update_measurements(self, data):
        if self.logging_failed:
            return

        try:
            values = {
                "temperature": data["temperature"],
                "vibration": data["vibration"],
                "spindle_load": data["spindle_load"],
                "tool_wear": data["tool_wear"],
            }

            for key, value in values.items():
                self.sensor_labels[key].setText(f"{value:.2f}")

            # Перерисовка графиков не чаще двух раз в секунду.
            now = time.monotonic()
            if now - self._last_chart_update >= 0.5:
                for key, value in values.items():
                    self.charts[key].add_value(value)
                self._last_chart_update = now

            diagnosis = self.update_diagnosis(data)

            if self.ml_worker is not None:
                self.ml_worker.submit(data)

            self.measurement_writer.enqueue(
                measurement=data,
                diagnosis=diagnosis,
                active_faults=self.active_faults,
                experiment_id=self.current_experiment_id,
            )

            self.session_measurement_count += 1
            self.measurement_label.setText(
                "Измерений за запуск: "
                f"{self.session_measurement_count}"
            )

        except Exception as error:
            self.logging_failed = True
            self.stop_simulation()
            self.show_error(
                "Ошибка обработки измерения:\n\n"
                f"{error}"
            )

    # ПОРОГОВАЯ ДИАГНОСТИКА
    # ==========================================

    def update_diagnosis(self, data):
        result = ConditionMonitor.evaluate(data)

        self.diagnosis_label.setText(
            result["status"]
        )
        self.diagnosis_label.setStyleSheet(
            f"font-size: 18px; font-weight: bold; "
            f"color: {result['color']}; padding: 5px;"
        )

        self.reasons_label.setText(
            "Контролируемые отклонения:\n"
            + "\n".join(
                f"• {reason}"
                for reason in result["reasons"]
            )
        )

        self.recommendations_label.setText(
            "Рекомендации системы:\n"
            + "\n".join(
                f"• {item}"
                for item in result["recommendations"]
            )
        )

        return result

    # ==========================================
    # ЗАГРУЗКА ML-МОДЕЛИ
    # ==========================================

    def load_ml_model(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выбор обученной ML-модели",
            "",
            "Файлы ML-моделей (*.joblib);;Все файлы (*.*)"
        )

        if not file_path:
            return

        try:
            info = self.model_trainer.load_model(file_path)
            self.ml_model_loaded = True

            if self.ml_worker is not None:
                self.ml_worker.stop_worker()

            self.ml_worker = MLPredictionWorker(
                self.model_trainer
            )
            self.ml_worker.prediction_ready.connect(
                self.show_ml_prediction
            )
            self.ml_worker.prediction_error.connect(
                self.show_ml_error
            )
            self.ml_worker.start()

            self.ml_status_label.setText(
                "ML-модель загружена"
            )
            self.ml_status_label.setStyleSheet(
                "font-weight: bold; color: #65d982; padding: 5px;"
            )

            self.ml_results_label.setText(
                f"Файл: {file_path}\n"
                f"Количество признаков: {info['feature_count']}\n"
                "Ожидание измерений..."
            )

        except Exception as error:
            self.ml_model_loaded = False

            self.ml_status_label.setText(
                "Ошибка загрузки ML-модели"
            )
            self.ml_status_label.setStyleSheet(
                "font-weight: bold; color: #ff7777; padding: 5px;"
            )

            self.ml_results_label.setText(
                "Не удалось загрузить ML-модель."
            )

            QMessageBox.critical(
                self,
                "Ошибка загрузки модели",
                str(error)
            )

    # ==========================================
    # ML-ДИАГНОСТИКА
    # ==========================================

    def show_ml_prediction(self, probabilities):
        lines = ["Прогноз ML-модели:", ""]

        for fault in self.model_trainer.FAULTS:
            probability = probabilities[fault]
            percentage = probability * 100
            level = self.model_trainer.get_probability_level(
                probability
            )
            label = self.model_trainer.FAULT_LABELS[fault]
            lines.append(
                f"{label}: {percentage:.1f}% "
                f"({level} вероятность)"
            )

        detected = [
            self.model_trainer.FAULT_LABELS[fault]
            for fault, probability in probabilities.items()
            if probability >= 0.5
        ]

        lines.extend(["", "Итог ML-прогноза:"])
        if detected:
            lines.extend(f"• {fault}" for fault in detected)
        else:
            lines.append(
                "Неисправности не выявлены "
                "с порогом вероятности 50%."
            )

        self.ml_results_label.setText("\\n".join(lines))

    def show_ml_error(self, error):
        self.ml_results_label.setText(
            f"Ошибка ML-прогнозирования:\\n{error}"
        )

    def on_writer_error(self, error):
        self.logging_failed = True
        self.machine.stop_simulation()
        self.show_error(
            "Ошибка пакетной записи измерений в базу данных:\\n\\n"
            f"{error}"
        )

    # СТАТУС И ОШИБКИ
    # ==========================================

    def update_status(self, status):
        self.status_label.setText(status)

        if status == "Эмулятор запущен":
            self.status_label.setStyleSheet(
                "font-weight: bold; color: #65d982;"
            )
        else:
            self.status_label.setStyleSheet(
                "font-weight: bold; color: #ff7777;"
            )
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)

    def show_simulator_error(self, message):
        self.show_error(message)

    def show_error(self, error):
        QMessageBox.critical(
            self,
            "Ошибка симулятора",
            str(error)
        )

    def closeEvent(self, event):
        self.machine.stop_simulation()

        if self.ml_worker is not None:
            self.ml_worker.stop_worker()

        self.measurement_writer.stop_and_flush()
        super().closeEvent(event)
