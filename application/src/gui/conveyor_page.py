
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QComboBox,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
)

from application.src.quality.quality_checker import QualityChecker
from application.src.simulator.conveyor_simulator import (
    ConveyorSimulator,
)


class ConveyorPage(QWidget):
    """Страница моделирования потока изделий."""

    def __init__(
        self,
        product_manager,
        measurement_logger,
        parent=None,
    ):
        super().__init__(parent)

        self.product_manager = product_manager
        self.measurement_logger = measurement_logger

        self.simulator = None
        self.current_product_id = None

        self.total_count = 0
        self.good_count = 0
        self.defect_count = 0
        self.unknown_count = 0

        # Статистика сравнения ML-прогноза с фактом.
        self.prediction_count = 0
        self.prediction_correct_count = 0
        self.prediction_wrong_count = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.process_next_item)

        self._build_ui()
        self.load_products()

    # ---------------------------------------------------------
    # ИНТЕРФЕЙС
    # ---------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Моделирование потока изделий")
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold; padding: 5px;"
        )
        root.addWidget(title)

        settings_group = QGroupBox("Параметры симуляции")
        settings_layout = QFormLayout(settings_group)

        self.product_combo = QComboBox()

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(200, 30000)
        self.interval_spin.setValue(1500)
        self.interval_spin.setSuffix(" мс")

        self.defect_probability_spin = QSpinBox()
        self.defect_probability_spin.setRange(0, 100)
        self.defect_probability_spin.setValue(50)
        self.defect_probability_spin.setSuffix(" %")

        settings_layout.addRow("Изделие:", self.product_combo)
        settings_layout.addRow(
            "Интервал поступления:",
            self.interval_spin,
        )
        settings_layout.addRow(
            "Вероятность искусственного дефекта:",
            self.defect_probability_spin,
        )

        root.addWidget(settings_group)

        controls_layout = QHBoxLayout()

        self.start_button = QPushButton("Запустить конвейер")
        self.stop_button = QPushButton("Остановить")
        self.reset_button = QPushButton("Сбросить статистику")

        self.stop_button.setEnabled(False)

        controls_layout.addWidget(self.start_button)
        controls_layout.addWidget(self.stop_button)
        controls_layout.addWidget(self.reset_button)

        root.addLayout(controls_layout)

        self.status_label = QLabel("Конвейер остановлен")
        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.status_label.setMinimumHeight(45)
        self.status_label.setStyleSheet(
            "background-color: #424242;"
            "color: white;"
            "font-weight: bold;"
            "border-radius: 5px;"
            "padding: 8px;"
        )

        root.addWidget(self.status_label)

        # Сведения о загруженной модели.
        model_group = QGroupBox("ML-модель")
        model_layout = QVBoxLayout(model_group)

        self.model_status_label = QLabel(
            "Модель будет проверена при запуске конвейера."
        )
        self.model_status_label.setWordWrap(True)

        model_layout.addWidget(self.model_status_label)
        root.addWidget(model_group)

        # Статистика фактического контроля.
        statistics_group = QGroupBox("Фактический контроль качества")
        statistics_layout = QHBoxLayout(statistics_group)

        self.total_label = QLabel("Всего: 0")
        self.good_label = QLabel("Годных: 0")
        self.defect_label = QLabel("Брак: 0")
        self.unknown_label = QLabel("Не определено: 0")

        statistics_layout.addWidget(self.total_label)
        statistics_layout.addWidget(self.good_label)
        statistics_layout.addWidget(self.defect_label)
        statistics_layout.addWidget(self.unknown_label)

        root.addWidget(statistics_group)

        # Статистика прогноза.
        prediction_group = QGroupBox(
            "Сравнение ML-прогноза с фактическим результатом"
        )
        prediction_layout = QHBoxLayout(prediction_group)

        self.prediction_total_label = QLabel(
            "Оценено: 0"
        )
        self.prediction_correct_label = QLabel(
            "Совпадений: 0"
        )
        self.prediction_wrong_label = QLabel(
            "Ошибок: 0"
        )
        self.prediction_accuracy_label = QLabel(
            "Точность: —"
        )

        prediction_layout.addWidget(self.prediction_total_label)
        prediction_layout.addWidget(self.prediction_correct_label)
        prediction_layout.addWidget(self.prediction_wrong_label)
        prediction_layout.addWidget(self.prediction_accuracy_label)

        root.addWidget(prediction_group)

        note_label = QLabel(
            "Точность ML-прогноза рассчитывается только для изделий "
            "без искусственно внесённых дефектов. Прогноз выполняется "
            "до генерации измерений."
        )
        note_label.setWordWrap(True)
        note_label.setStyleSheet(
            "color: #777777; padding: 3px;"
        )
        root.addWidget(note_label)

        # История изделий.
        history_group = QGroupBox(
            "Последние обработанные изделия"
        )
        history_layout = QVBoxLayout(history_group)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(8)

        self.history_table.setHorizontalHeaderLabels([
            "№",
            "Время",
            "Изделие",
            "Прогноз ML",
            "Фактический статус",
            "Сравнение",
            "Количество дефектов",
            "Измерения",
        ])

        self.history_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        self.history_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        self.history_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        self.history_table.setWordWrap(True)

        history_layout.addWidget(self.history_table)
        root.addWidget(history_group, 1)

        # Сигналы.
        self.product_combo.currentIndexChanged.connect(
            self._on_product_changed
        )

        self.start_button.clicked.connect(
            self.start_conveyor
        )

        self.stop_button.clicked.connect(
            self.stop_conveyor
        )

        self.reset_button.clicked.connect(
            self.reset_statistics
        )

    # ---------------------------------------------------------
    # НОМЕНКЛАТУРА
    # ---------------------------------------------------------

    def load_products(self):
        self.product_combo.blockSignals(True)
        self.product_combo.clear()

        products = self.product_manager.get_all_products()

        for product in products:
            self.product_combo.addItem(
                f"{product.get('article', '')} — "
                f"{product.get('name', '')}",
                product["id"],
            )

        self.product_combo.blockSignals(False)

        if self.product_combo.count():
            self._on_product_changed()
        else:
            self.current_product_id = None
            self.start_button.setEnabled(False)

            self.status_label.setText(
                "Сначала добавьте изделие в номенклатуру"
            )

    def _on_product_changed(self):
        if self.timer.isActive():
            self.stop_conveyor()

        self.current_product_id = self.product_combo.currentData()
        self.simulator = None

        self.start_button.setEnabled(
            self.current_product_id is not None
        )

    # ---------------------------------------------------------
    # ЗАПУСК И ОСТАНОВКА
    # ---------------------------------------------------------

    def start_conveyor(self):
        if self.current_product_id is None:
            QMessageBox.warning(
                self,
                "Конвейер",
                "Выберите изделие.",
            )
            return

        try:
            checker = QualityChecker(
                product_manager=self.product_manager
            )

            self.simulator = ConveyorSimulator(
                product_manager=self.product_manager,
                quality_checker=checker,
                measurement_logger=self.measurement_logger,
                defect_probability=(
                    self.defect_probability_spin.value() / 100
                ),
            )

            self.simulator.set_product(
                self.current_product_id
            )

            # Отображение состояния модели.
            model_info = self.simulator.get_model_info()

            if model_info["loaded"]:
                self.model_status_label.setText(
                    f"Модель загружена: {model_info['name']}\n"
                    f"Файл: {model_info['path']}"
                )
                self.model_status_label.setStyleSheet(
                    "color: green; padding: 3px;"
                )
            else:
                self.model_status_label.setText(
                    "ML-модель не загружена.\n"
                    f"Причина: {model_info['error']}\n"
                    "Конвейер сможет выполнять симуляцию, "
                    "но прогноз качества будет недоступен."
                )
                self.model_status_label.setStyleSheet(
                    "color: red; padding: 3px;"
                )

            self.timer.start(
                self.interval_spin.value()
            )

            self._set_running_state(True)

        except Exception as error:
            self.simulator = None

            QMessageBox.critical(
                self,
                "Ошибка запуска",
                str(error),
            )

    def stop_conveyor(self):
        self.timer.stop()
        self._set_running_state(False)

    def _set_running_state(self, running):
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)

        self.product_combo.setEnabled(not running)
        self.interval_spin.setEnabled(not running)
        self.defect_probability_spin.setEnabled(not running)

        if running:
            self.status_label.setText(
                "КОНВЕЙЕР РАБОТАЕТ"
            )
            background = "#1b5e20"
        else:
            self.status_label.setText(
                "КОНВЕЙЕР ОСТАНОВЛЕН"
            )
            background = "#424242"

        self.status_label.setStyleSheet(
            f"background-color: {background};"
            "color: white;"
            "font-weight: bold;"
            "border-radius: 5px;"
            "padding: 8px;"
        )

    # ---------------------------------------------------------
    # ОБРАБОТКА ИЗДЕЛИЙ
    # ---------------------------------------------------------

    def process_next_item(self):
        if self.simulator is None:
            self.stop_conveyor()
            return

        try:
            result = self.simulator.generate_item(
                self.current_product_id
            )

            self.total_count += 1

            actual_status = str(
                result.get("status", "UNKNOWN")
            ).upper()

            if actual_status == "GOOD":
                self.good_count += 1
            elif actual_status == "DEFECT":
                self.defect_count += 1
            else:
                self.unknown_count += 1

            # Учитываем только изделия, пригодные для оценки модели.
            if result.get("prediction_evaluable", False):
                self.prediction_count += 1

                if result.get("prediction_correct") is True:
                    self.prediction_correct_count += 1
                elif result.get("prediction_correct") is False:
                    self.prediction_wrong_count += 1

            self._add_history_row(result)
            self._update_statistics()

        except Exception as error:
            self.stop_conveyor()

            QMessageBox.critical(
                self,
                "Ошибка симуляции",
                str(error),
            )

    # ---------------------------------------------------------
    # ИСТОРИЯ
    # ---------------------------------------------------------

    def _add_history_row(self, result):
        row = self.history_table.rowCount()

        # Не более 200 последних изделий.
        if row >= 200:
            self.history_table.removeRow(0)
            row -= 1

        self.history_table.insertRow(row)

        item_id = result.get("item_id", "")

        generated_at = result.get(
            "generated_at",
            datetime.now().isoformat(timespec="seconds"),
        )

        product_name = self.product_combo.currentText()

        actual_status = str(
            result.get("status", "UNKNOWN")
        ).upper()

        ml_prediction = result.get(
            "ml_prediction",
            {},
        )

        predicted_status = ml_prediction.get(
            "predicted_status",
            "UNAVAILABLE",
        )

        if predicted_status in {"UNAVAILABLE", "ERROR"}:
            prediction_text = "Недоступен"
        else:
            prediction_text = predicted_status

            defect_probability = ml_prediction.get(
                "defect_probability"
            )

            if defect_probability is not None:
                prediction_text += (
                    f" ({defect_probability * 100:.1f}%)"
                )

        if result.get("prediction_evaluable", False):
            if result.get("prediction_correct"):
                comparison_text = "Совпадение"
            else:
                comparison_text = "Ошибка"
        elif result.get("prediction_comparison_available", False):
            comparison_text = "Искусственный дефект"
        else:
            comparison_text = "Не оценивался"

        defects = result.get("defects", [])
        measurements = result.get("measurements", {})

        measurement_text = "; ".join(
            f"{key}: {value}"
            for key, value in measurements.items()
        )

        values = [
            item_id,
            generated_at,
            product_name,
            prediction_text,
            actual_status,
            comparison_text,
            len(defects),
            measurement_text,
        ]

        for column, value in enumerate(values):
            cell = QTableWidgetItem(str(value))

            if column == 3:
                if predicted_status == "GOOD":
                    cell.setForeground(
                        Qt.GlobalColor.darkGreen
                    )
                elif predicted_status == "DEFECT":
                    cell.setForeground(
                        Qt.GlobalColor.red
                    )

            if column == 4:
                if actual_status == "GOOD":
                    cell.setForeground(
                        Qt.GlobalColor.green
                    )
                elif actual_status == "DEFECT":
                    cell.setForeground(
                        Qt.GlobalColor.red
                    )
                else:
                    cell.setForeground(
                        Qt.GlobalColor.darkYellow
                    )

            if column == 5:
                if comparison_text == "Совпадение":
                    cell.setForeground(
                        Qt.GlobalColor.darkGreen
                    )
                elif comparison_text == "Ошибка":
                    cell.setForeground(
                        Qt.GlobalColor.red
                    )

            self.history_table.setItem(
                row,
                column,
                cell,
            )

        self.history_table.scrollToBottom()

    # ---------------------------------------------------------
    # ОБНОВЛЕНИЕ СТАТИСТИКИ
    # ---------------------------------------------------------

    def _update_statistics(self):
        self.total_label.setText(
            f"Всего: {self.total_count}"
        )

        self.good_label.setText(
            f"Годных: {self.good_count}"
        )

        self.defect_label.setText(
            f"Брак: {self.defect_count}"
        )

        self.unknown_label.setText(
            f"Не определено: {self.unknown_count}"
        )

        self.prediction_total_label.setText(
            f"Оценено: {self.prediction_count}"
        )

        self.prediction_correct_label.setText(
            f"Совпадений: {self.prediction_correct_count}"
        )

        self.prediction_wrong_label.setText(
            f"Ошибок: {self.prediction_wrong_count}"
        )

        if self.prediction_count:
            accuracy = (
                self.prediction_correct_count
                / self.prediction_count
                * 100
            )

            accuracy_text = f"{accuracy:.1f}%"
        else:
            accuracy_text = "—"

        self.prediction_accuracy_label.setText(
            f"Точность: {accuracy_text}"
        )

    # ---------------------------------------------------------
    # СБРОС СТАТИСТИКИ
    # ---------------------------------------------------------

    def reset_statistics(self):
        if self.timer.isActive():
            QMessageBox.warning(
                self,
                "Сброс статистики",
                "Сначала остановите конвейер.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Сброс статистики",
            "Очистить статистику и журнал на экране?\n\n"
            "Записи в базе данных останутся.",
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.total_count = 0
        self.good_count = 0
        self.defect_count = 0
        self.unknown_count = 0

        self.prediction_count = 0
        self.prediction_correct_count = 0
        self.prediction_wrong_count = 0

        self.history_table.setRowCount(0)

        if self.simulator is not None:
            self.simulator.reset()

        self._update_statistics()
