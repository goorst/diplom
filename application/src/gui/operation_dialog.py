from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QSpinBox,
    QDialogButtonBox,
    QMessageBox,
)


class OperationDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Добавление операции")
        self.setMinimumWidth(420)

        self.name_edit = QLineEdit()

        self.sequence_spin = QSpinBox()
        self.sequence_spin.setMinimum(1)
        self.sequence_spin.setMaximum(9999)

        self.speed_edit = QLineEdit()
        self.feed_edit = QLineEdit()
        self.depth_edit = QLineEdit()
        self.tool_edit = QLineEdit()

        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)

        form = QFormLayout()
        form.addRow("Название операции:", self.name_edit)
        form.addRow("Номер операции:", self.sequence_spin)
        form.addRow("Обороты шпинделя:", self.speed_edit)
        form.addRow("Подача:", self.feed_edit)
        form.addRow("Глубина резания:", self.depth_edit)
        form.addRow("Номер инструмента:", self.tool_edit)
        form.addRow("Описание:", self.description_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(self.validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    @staticmethod
    def parse_optional_number(value, field_name):
        value = value.strip()

        if not value:
            return None

        try:
            number = float(value.replace(",", "."))
        except ValueError:
            raise ValueError(
                f"Поле «{field_name}» должно содержать число."
            )

        if number <= 0:
            raise ValueError(
                f"Поле «{field_name}» должно быть больше нуля."
            )

        return number

    def validate_and_accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(
                self,
                "Проверка данных",
                "Введите название операции."
            )
            return

        try:
            self.parse_optional_number(
                self.speed_edit.text(),
                "Обороты шпинделя"
            )
            self.parse_optional_number(
                self.feed_edit.text(),
                "Подача"
            )
            self.parse_optional_number(
                self.depth_edit.text(),
                "Глубина резания"
            )
        except ValueError as error:
            QMessageBox.warning(
                self,
                "Проверка данных",
                str(error)
            )
            return

        self.accept()

    def get_data(self):
        return {
            "operation_name": self.name_edit.text().strip(),
            "sequence_number": self.sequence_spin.value(),
            "spindle_speed": self.parse_optional_number(
                self.speed_edit.text(),
                "Обороты шпинделя"
            ),
            "feed_rate": self.parse_optional_number(
                self.feed_edit.text(),
                "Подача"
            ),
            "cutting_depth": self.parse_optional_number(
                self.depth_edit.text(),
                "Глубина резания"
            ),
            "tool_id": self.tool_edit.text().strip() or None,
            "description": self.description_edit.toPlainText().strip(),
        }