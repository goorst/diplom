from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QTextEdit,
    QDialogButtonBox,
    QMessageBox,
)


class ProductDialog(QDialog):

    def __init__(self, parent=None, product=None):
        super().__init__(parent)

        self.product = product or {}

        self.setWindowTitle(
            "Редактирование изделия"
            if product else "Новое изделие"
        )
        self.setMinimumWidth(450)

        self.name_edit = QLineEdit(
            self.product.get("name", "")
        )

        self.part_type_edit = QLineEdit(
            self.product.get("part_type", "")
        )

        self.material_edit = QLineEdit(
            self.product.get("material", "")
        )

        self.drawing_edit = QLineEdit(
            self.product.get("drawing_number", "") or ""
        )

        self.description_edit = QTextEdit(
            self.product.get("description", "") or ""
        )
        self.description_edit.setMaximumHeight(100)

        form = QFormLayout()
        form.addRow("Название изделия:", self.name_edit)
        form.addRow("Тип детали:", self.part_type_edit)
        form.addRow("Материал:", self.material_edit)
        form.addRow("Номер чертежа:", self.drawing_edit)
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

    def validate_and_accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(
                self,
                "Проверка данных",
                "Введите название изделия."
            )
            return

        if not self.part_type_edit.text().strip():
            QMessageBox.warning(
                self,
                "Проверка данных",
                "Введите тип детали."
            )
            return

        if not self.material_edit.text().strip():
            QMessageBox.warning(
                self,
                "Проверка данных",
                "Введите материал."
            )
            return

        self.accept()

    def get_data(self):
        return {
            "name": self.name_edit.text().strip(),
            "part_type": self.part_type_edit.text().strip(),
            "material": self.material_edit.text().strip(),
            "drawing_number": self.drawing_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip(),
        }