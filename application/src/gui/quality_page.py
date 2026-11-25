from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QSplitter,
)

from application.src.quality.quality_checker import QualityChecker


class QualityPage(QWidget):
    """Страница ручного контроля качества изделий."""

    def __init__(
        self,
        product_manager,
        measurement_logger,
        parent=None,
    ):
        super().__init__(parent)

        self.product_manager = product_manager
        self.measurement_logger = measurement_logger

        self.checker = QualityChecker(
            product_manager=self.product_manager
        )

        self.current_product_id = None
        self.parameter_inputs = {}

        self._build_ui()
        self.load_products()

    def _build_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Контроль качества изделий")
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold; padding: 5px;"
        )
        root.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Левая часть — выбор изделия и измерения.
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)

        product_group = QGroupBox("Выбор изделия")
        product_form = QFormLayout(product_group)

        self.product_combo = QComboBox()
        product_form.addRow("Изделие:", self.product_combo)

        left_layout.addWidget(product_group)

        self.parameters_group = QGroupBox(
            "Измеренные характеристики"
        )
        self.parameters_layout = QFormLayout(
            self.parameters_group
        )

        left_layout.addWidget(self.parameters_group)

        buttons_layout = QHBoxLayout()

        self.check_button = QPushButton("Проверить")
        self.clear_button = QPushButton("Очистить")

        buttons_layout.addWidget(self.check_button)
        buttons_layout.addWidget(self.clear_button)

        left_layout.addLayout(buttons_layout)
        left_layout.addStretch()

        # Правая часть — результат проверки.
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)

        result_group = QGroupBox("Результат контроля")
        result_layout = QVBoxLayout(result_group)

        self.result_label = QLabel(
            "Ожидание результатов контроля"
        )
        self.result_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.result_label.setMinimumHeight(65)
        self.result_label.setStyleSheet(
            "font-size: 15px; font-weight: bold;"
            "background-color: #424242; color: white;"
            "border-radius: 5px; padding: 8px;"
        )

        result_layout.addWidget(self.result_label)

        self.result_details = QLabel(
            "Выберите изделие и введите измерения."
        )
        self.result_details.setWordWrap(True)

        result_layout.addWidget(self.result_details)

        right_layout.addWidget(result_group)

        defects_group = QGroupBox("Обнаруженные дефекты")
        defects_layout = QVBoxLayout(defects_group)

        self.defects_table = QTableWidget()
        self.defects_table.setColumnCount(5)
        self.defects_table.setHorizontalHeaderLabels([
            "Характеристика",
            "Измерение",
            "Допуск",
            "Отклонение",
            "Тип дефекта",
        ])

        self.defects_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.defects_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        defects_layout.addWidget(self.defects_table)
        right_layout.addWidget(defects_group, 1)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([400, 700])

        root.addWidget(splitter, 1)

        statistics_group = QGroupBox("Статистика контроля")
        statistics_layout = QHBoxLayout(statistics_group)

        self.total_label = QLabel("Всего проверено: 0")
        self.good_label = QLabel("Годных: 0")
        self.defect_label = QLabel("Бракованных: 0")
        self.unknown_label = QLabel("Не определено: 0")

        statistics_layout.addWidget(self.total_label)
        statistics_layout.addWidget(self.good_label)
        statistics_layout.addWidget(self.defect_label)
        statistics_layout.addWidget(self.unknown_label)

        root.addWidget(statistics_group)

        self.product_combo.currentIndexChanged.connect(
            self._on_product_changed
        )
        self.check_button.clicked.connect(self.check_quality)
        self.clear_button.clicked.connect(self.clear_inputs)

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
            self._clear_parameter_widgets()
            self.result_label.setText(
                "НЕТ ИЗДЕЛИЙ В НОМЕНКЛАТУРЕ"
            )

    def _clear_parameter_widgets(self):
        while self.parameters_layout.count():
            item = self.parameters_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        self.parameter_inputs.clear()

    def _on_product_changed(self):
        self.current_product_id = self.product_combo.currentData()

        self._clear_parameter_widgets()
        self.defects_table.setRowCount(0)

        if self.current_product_id is None:
            return

        parameters = self.product_manager.get_product_parameters(
            self.current_product_id
        )

        for parameter in parameters:
            code = parameter.get("code") or parameter.get("name")

            if not code:
                continue

            name = parameter.get("name", code)
            unit = parameter.get("unit", "")

            edit = QLineEdit()
            edit.setPlaceholderText("Введите измеренное значение")

            nominal = parameter.get("nominal")
            if nominal is not None:
                edit.setText(str(nominal))

            label = name
            if unit:
                label += f" ({unit})"

            self.parameters_layout.addRow(label, edit)
            self.parameter_inputs[code] = edit

        self.result_label.setText(
            "ОЖИДАНИЕ КОНТРОЛЯ"
        )
        self.result_details.setText(
            "Введите фактические измерения характеристик."
        )

    def clear_inputs(self):
        for edit in self.parameter_inputs.values():
            edit.clear()

        self.defects_table.setRowCount(0)

        self.result_label.setText("ПОЛЯ ОЧИЩЕНЫ")
        self.result_details.setText(
            "Введите новые измерения."
        )

    def _collect_measurements(self):
        measurements = {}

        for code, edit in self.parameter_inputs.items():
            raw_value = edit.text().strip()

            if not raw_value:
                continue

            try:
                value = float(raw_value.replace(",", "."))
            except ValueError:
                raise ValueError(
                    f"Некорректное значение характеристики: {code}"
                )

            measurements[code] = value

        if not measurements:
            raise ValueError(
                "Не введено ни одного измерения."
            )

        return measurements

    def check_quality(self):
        if self.current_product_id is None:
            QMessageBox.warning(
                self,
                "Контроль качества",
                "Сначала выберите изделие.",
            )
            return

        try:
            measurements = self._collect_measurements()

            result = self.checker.check_measurements(
                self.current_product_id,
                measurements,
            )

            result["measurements"] = measurements

            self._display_result(result)

            # Сохраняем результат, включая UNKNOWN.
            # Такие записи можно будет учитывать отдельно.
            self.measurement_logger.log_result(result)

            self.update_statistics()

        except ValueError as error:
            QMessageBox.warning(
                self,
                "Ошибка ввода",
                str(error),
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Ошибка контроля",
                str(error),
            )

    def _display_result(self, result):
        status = str(result.get("status", "UNKNOWN")).upper()
        defects = result.get("defects", [])

        if status == "GOOD":
            self.result_label.setText("ИЗДЕЛИЕ ГОДНО")
            background = "#1b5e20"

        elif status == "DEFECT":
            self.result_label.setText("ОБНАРУЖЕН БРАК")
            background = "#8e2424"

        else:
            self.result_label.setText("РЕЗУЛЬТАТ НЕ ОПРЕДЕЛЁН")
            background = "#8a641c"

        self.result_label.setStyleSheet(
            f"font-size: 15px; font-weight: bold;"
            f"background-color: {background}; color: white;"
            "border-radius: 5px; padding: 8px;"
        )

        checked = result.get("checked_parameters", [])
        skipped = result.get("skipped_parameters", [])

        self.result_details.setText(
            f"Проверено характеристик: {len(checked)}\n"
            f"Пропущено характеристик: {len(skipped)}\n"
            f"Количество дефектов: {len(defects)}"
        )

        self.defects_table.setRowCount(0)

        for defect in defects:
            row = self.defects_table.rowCount()
            self.defects_table.insertRow(row)

            name = defect.get(
                "parameter",
                defect.get("name", ""),
            )

            measured = defect.get(
                "measured",
                defect.get("measured_value", ""),
            )

            minimum = defect.get("min_value")
            maximum = defect.get("max_value")
            unit = defect.get("unit", "")

            if minimum is not None or maximum is not None:
                limit = (
                    f"{minimum if minimum is not None else '—'}"
                    f" … "
                    f"{maximum if maximum is not None else '—'}"
                )
            else:
                limit = "Не задан"

            deviation = defect.get(
                "deviation",
                "",
            )

            defect_type = defect.get(
                "defect_type",
                defect.get("message", ""),
            )

            values = [
                name,
                f"{measured} {unit}".strip(),
                f"{limit} {unit}".strip(),
                deviation,
                defect_type,
            ]

            for column, value in enumerate(values):
                self.defects_table.setItem(
                    row,
                    column,
                    QTableWidgetItem(str(value)),
                )

    def update_statistics(self):
        records = self.measurement_logger.get_all_records(
            product_id=self.current_product_id,
        )

        total = len(records)
        good = 0
        defect = 0
        unknown = 0

        for record in records:
            status = str(record.get("status", "")).upper()

            if status == "GOOD":
                good += 1
            elif status == "DEFECT":
                defect += 1
            else:
                unknown += 1

        self.total_label.setText(f"Всего проверено: {total}")
        self.good_label.setText(f"Годных: {good}")
        self.defect_label.setText(f"Бракованных: {defect}")
        self.unknown_label.setText(f"Не определено: {unknown}")