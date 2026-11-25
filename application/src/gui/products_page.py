
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QPushButton,
    QLabel,
    QLineEdit,
    QTextEdit,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QScrollArea,
    QFrame,
)

from application.src.products.product_manager import ProductManager
from application.src.products.document_manager import DocumentManager
from application.src.products.document_parser import DocumentParser


DARK_STYLE = """
QWidget {
    background-color: #202124;
    color: #e8eaed;
    font-size: 10pt;
}

QTabWidget::pane {
    border: 1px solid #45474b;
    background: #202124;
}

QTabBar::tab {
    background: #303134;
    color: #bdc1c6;
    padding: 9px 15px;
    border: 1px solid #45474b;
    border-bottom: none;
    margin-right: 2px;
}

QTabBar::tab:selected {
    background: #202124;
    color: #8ab4f8;
    font-weight: bold;
}

QLineEdit, QTextEdit, QComboBox {
    background: #292a2d;
    color: #e8eaed;
    border: 1px solid #5f6368;
    border-radius: 4px;
    padding: 6px;
    selection-background-color: #3c78c5;
}

QTableWidget {
    background: #292a2d;
    alternate-background-color: #303134;
    color: #e8eaed;
    gridline-color: #45474b;
    border: 1px solid #45474b;
    selection-background-color: #3c78c5;
    selection-color: white;
}

QHeaderView::section {
    background: #35363a;
    color: #e8eaed;
    padding: 8px;
    border: 1px solid #45474b;
    font-weight: bold;
}

QPushButton {
    background: #3c4043;
    color: #e8eaed;
    border: 1px solid #5f6368;
    border-radius: 4px;
    padding: 8px 12px;
}

QPushButton:hover {
    background: #4a4d51;
}

QPushButton:pressed {
    background: #303134;
}

QPushButton:disabled {
    color: #777777;
    background: #292a2d;
}

QLabel {
    color: #e8eaed;
}

QScrollArea {
    border: 1px solid #45474b;
    background: #292a2d;
}

QFrame {
    border-color: #45474b;
}
"""


def make_table(headers):
    table = QTableWidget()

    table.setColumnCount(len(headers))
    table.setHorizontalHeaderLabels(headers)

    table.setSelectionBehavior(
        QTableWidget.SelectionBehavior.SelectRows
    )

    table.setSelectionMode(
        QTableWidget.SelectionMode.SingleSelection
    )

    table.setEditTriggers(
        QTableWidget.EditTrigger.NoEditTriggers
    )

    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)

    header = table.horizontalHeader()

    # Пользователь может самостоятельно менять ширину столбцов.
    header.setSectionResizeMode(
        QHeaderView.ResizeMode.Interactive
    )

    header.setStretchLastSection(True)

    return table


def set_cell(table, row, column, value):
    item = QTableWidgetItem(
        "" if value is None else str(value)
    )

    item.setFlags(
        item.flags() & ~Qt.ItemFlag.ItemIsEditable
    )

    table.setItem(row, column, item)


def selected_id(table):
    row = table.currentRow()

    if row < 0:
        return None

    item = table.item(row, 0)

    if item is None:
        return None

    return item.data(Qt.ItemDataRole.UserRole)


# =============================================================
# ДИАЛОГ ИЗДЕЛИЯ
# =============================================================

class ProductDialog(QDialog):

    def __init__(self, parent=None, product=None):
        super().__init__(parent)

        self.setWindowTitle("Изделие")
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.article_edit = QLineEdit()
        self.type_edit = QLineEdit()
        self.material_edit = QLineEdit()

        self.description_edit = QTextEdit()
        self.description_edit.setMinimumHeight(90)

        form.addRow("Наименование:", self.name_edit)
        form.addRow("Артикул:", self.article_edit)
        form.addRow("Тип изделия:", self.type_edit)
        form.addRow("Материал:", self.material_edit)
        form.addRow("Описание:", self.description_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

        if product:
            self.name_edit.setText(
                product.get("name", "")
            )

            self.article_edit.setText(
                product.get("article", "")
            )

            self.type_edit.setText(
                product.get("product_type", "")
            )

            self.material_edit.setText(
                product.get("material", "")
            )

            self.description_edit.setPlainText(
                product.get("description", "")
            )

    def get_data(self):
        name = self.name_edit.text().strip()
        article = self.article_edit.text().strip()

        if not name:
            raise ValueError(
                "Введите наименование изделия"
            )

        if not article:
            raise ValueError(
                "Введите артикул изделия"
            )

        return {
            "name": name,
            "article": article,
            "product_type": self.type_edit.text().strip(),
            "material": self.material_edit.text().strip(),
            "description": self.description_edit.toPlainText().strip(),
        }

    def _validate_and_accept(self):
        try:
            self.get_data()
            self.accept()

        except ValueError as error:
            QMessageBox.warning(
                self,
                "Проверка данных",
                str(error),
            )


# =============================================================
# ДИАЛОГ ХАРАКТЕРИСТИКИ
# =============================================================

class ParameterDialog(QDialog):

    def __init__(self, parent=None, parameter=None):
        super().__init__(parent)

        self.setWindowTitle("Контролируемая характеристика")
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit()
        self.code_edit = QLineEdit()
        self.nominal_edit = QLineEdit()
        self.min_edit = QLineEdit()
        self.max_edit = QLineEdit()
        self.unit_edit = QLineEdit()

        self.source_combo = QComboBox()

        self.source_combo.addItem("Вручную", "manual")
        self.source_combo.addItem("Из документа", "document")
        self.source_combo.addItem("Копирование", "copy")

        self.note_edit = QLineEdit()

        form.addRow("Название:", self.name_edit)
        form.addRow("Код:", self.code_edit)
        form.addRow("Номинал:", self.nominal_edit)
        form.addRow("Минимум:", self.min_edit)
        form.addRow("Максимум:", self.max_edit)
        form.addRow("Единица измерения:", self.unit_edit)
        form.addRow("Источник:", self.source_combo)
        form.addRow("Примечание:", self.note_edit)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

        if parameter:
            self.name_edit.setText(
                parameter.get("name", "")
            )

            self.code_edit.setText(
                parameter.get("code", "")
            )

            self.nominal_edit.setText(
                self._number_text(parameter.get("nominal"))
            )

            self.min_edit.setText(
                self._number_text(parameter.get("min_value"))
            )

            self.max_edit.setText(
                self._number_text(parameter.get("max_value"))
            )

            self.unit_edit.setText(
                parameter.get("unit", "")
            )

            self.note_edit.setText(
                parameter.get("note", "")
            )

            source = parameter.get("source", "manual")

            index = self.source_combo.findData(source)

            if index >= 0:
                self.source_combo.setCurrentIndex(index)

    @staticmethod
    def _number_text(value):
        return "" if value is None else str(value)

    @staticmethod
    def _parse_number(text, field_name):
        text = text.strip().replace(",", ".")

        if not text:
            return None

        try:
            return float(text)

        except ValueError:
            raise ValueError(
                f"Поле «{field_name}» должно содержать число"
            )

    def get_data(self):
        name = self.name_edit.text().strip()

        if not name:
            raise ValueError(
                "Введите название характеристики"
            )

        nominal = self._parse_number(
            self.nominal_edit.text(),
            "Номинал",
        )

        minimum = self._parse_number(
            self.min_edit.text(),
            "Минимум",
        )

        maximum = self._parse_number(
            self.max_edit.text(),
            "Максимум",
        )

        if (
            minimum is not None
            and maximum is not None
            and minimum > maximum
        ):
            raise ValueError(
                "Минимум не может быть больше максимума"
            )

        return {
            "name": name,
            "code": self.code_edit.text().strip(),
            "nominal": nominal,
            "min_value": minimum,
            "max_value": maximum,
            "unit": self.unit_edit.text().strip(),
            "source": self.source_combo.currentData(),
            "note": self.note_edit.text().strip(),
        }

    def _validate_and_accept(self):
        try:
            self.get_data()
            self.accept()

        except ValueError as error:
            QMessageBox.warning(
                self,
                "Проверка данных",
                str(error),
            )


# =============================================================
# ГЛАВНАЯ СТРАНИЦА НОМЕНКЛАТУРЫ
# =============================================================

class ProductsPage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.product_manager = ProductManager()
        self.document_manager = DocumentManager()
        self.document_parser = DocumentParser()

        self.current_product_id = None
        self.current_document_id = None
        self.preview_path = None

        self.setStyleSheet(DARK_STYLE)

        self._build_ui()
        self.load_products()

    # ---------------------------------------------------------
    # ОСНОВНАЯ КОМПОНОВКА
    # ---------------------------------------------------------

    def _build_ui(self):
        root_layout = QVBoxLayout(self)

        root_layout.setContentsMargins(5, 5, 5, 5)
        root_layout.setSpacing(4)

        self.main_splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        self.main_splitter.setChildrenCollapsible(False)

        # Левая часть: номенклатура и характеристики.
        self.left_panel = QWidget()

        left_layout = QVBoxLayout(self.left_panel)

        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.setSpacing(5)

        self.tabs = QTabWidget()

        left_layout.addWidget(self.tabs)

        self._build_products_tab()
        self._build_basic_tab()
        self._build_parameters_tab()
        self._build_documents_tab()
        self._build_history_tab()

        # Правая часть: просмотр документа.
        self.preview_panel = self._build_preview_panel()

        self.main_splitter.addWidget(self.left_panel)
        self.main_splitter.addWidget(self.preview_panel)

        self.main_splitter.setStretchFactor(0, 1)
        self.main_splitter.setStretchFactor(1, 1)

        self.main_splitter.setSizes([700, 700])

        root_layout.addWidget(self.main_splitter)

        self.tabs.currentChanged.connect(
            self._on_tab_changed
        )

    # ---------------------------------------------------------
    # ВКЛАДКА ИЗДЕЛИЙ
    # ---------------------------------------------------------

    def _build_products_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        search_form = QFormLayout()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "Наименование или артикул..."
        )

        self.type_filter_edit = QLineEdit()
        self.type_filter_edit.setPlaceholderText(
            "Тип изделия"
        )

        self.material_filter_edit = QLineEdit()
        self.material_filter_edit.setPlaceholderText(
            "Материал"
        )

        search_form.addRow("Поиск:", self.search_edit)
        search_form.addRow("Тип:", self.type_filter_edit)
        search_form.addRow("Материал:", self.material_filter_edit)

        layout.addLayout(search_form)

        self.products_table = make_table([
            "Артикул",
            "Наименование",
            "Тип",
            "Характеристик",
        ])

        self.products_table.setColumnWidth(0, 120)
        self.products_table.setColumnWidth(1, 180)
        self.products_table.setColumnWidth(2, 130)

        layout.addWidget(self.products_table, 1)

        buttons = QHBoxLayout()

        self.add_product_button = QPushButton("Добавить")
        self.edit_product_button = QPushButton("Изменить")
        self.copy_product_button = QPushButton("Копировать")
        self.delete_product_button = QPushButton("Удалить")

        buttons.addWidget(self.add_product_button)
        buttons.addWidget(self.edit_product_button)
        buttons.addWidget(self.copy_product_button)
        buttons.addWidget(self.delete_product_button)

        layout.addLayout(buttons)

        self.tabs.addTab(page, "Изделия")

        self.search_edit.textChanged.connect(
            self.load_products
        )

        self.type_filter_edit.textChanged.connect(
            self.load_products
        )

        self.material_filter_edit.textChanged.connect(
            self.load_products
        )

        self.products_table.itemSelectionChanged.connect(
            self._on_product_selected
        )

        self.add_product_button.clicked.connect(
            self.add_product
        )

        self.edit_product_button.clicked.connect(
            self.edit_product
        )

        self.copy_product_button.clicked.connect(
            self.copy_product
        )

        self.delete_product_button.clicked.connect(
            self.delete_product
        )

    # ---------------------------------------------------------
    # ОСНОВНЫЕ ДАННЫЕ
    # ---------------------------------------------------------

    def _build_basic_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        self.basic_info = QTextEdit()
        self.basic_info.setReadOnly(True)

        self.basic_info.setPlaceholderText(
            "Выберите изделие во вкладке «Изделия»."
        )

        layout.addWidget(self.basic_info)

        self.tabs.addTab(page, "Основные данные")

    # ---------------------------------------------------------
    # ХАРАКТЕРИСТИКИ
    # ---------------------------------------------------------

    def _build_parameters_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        self.parameters_table = make_table([
            "Название",
            "Код",
            "Номинал",
            "Минимум",
            "Максимум",
            "Ед.",
            "Источник",
        ])

        self.parameters_table.setColumnWidth(0, 170)
        self.parameters_table.setColumnWidth(1, 80)
        self.parameters_table.setColumnWidth(2, 85)
        self.parameters_table.setColumnWidth(3, 85)
        self.parameters_table.setColumnWidth(4, 85)

        layout.addWidget(self.parameters_table, 1)

        buttons = QHBoxLayout()

        self.add_parameter_button = QPushButton(
            "Добавить характеристику"
        )

        self.edit_parameter_button = QPushButton("Изменить")
        self.delete_parameter_button = QPushButton("Удалить")

        buttons.addWidget(self.add_parameter_button)
        buttons.addWidget(self.edit_parameter_button)
        buttons.addWidget(self.delete_parameter_button)

        layout.addLayout(buttons)

        self.tabs.addTab(page, "Характеристики")

        self.add_parameter_button.clicked.connect(
            self.add_parameter
        )

        self.edit_parameter_button.clicked.connect(
            self.edit_parameter
        )

        self.delete_parameter_button.clicked.connect(
            self.delete_parameter
        )

    # ---------------------------------------------------------
    # ДОКУМЕНТАЦИЯ
    # ---------------------------------------------------------

    def _build_documents_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        hint = QLabel(
            "Выберите документ, чтобы увидеть его оригинал справа."
        )

        hint.setWordWrap(True)

        layout.addWidget(hint)

        self.documents_table = make_table([
            "Документ",
            "Формат",
            "Размер",
            "Дата загрузки",
        ])

        self.documents_table.setColumnWidth(0, 220)
        self.documents_table.setColumnWidth(1, 80)
        self.documents_table.setColumnWidth(2, 100)

        layout.addWidget(self.documents_table, 1)

        buttons = QHBoxLayout()

        self.add_document_button = QPushButton(
            "Добавить документ"
        )

        self.extract_button = QPushButton(
            "Извлечь характеристики"
        )

        self.delete_document_button = QPushButton(
            "Удалить документ"
        )

        buttons.addWidget(self.add_document_button)
        buttons.addWidget(self.extract_button)
        buttons.addWidget(self.delete_document_button)

        layout.addLayout(buttons)

        self.tabs.addTab(page, "Документация")

        self.documents_table.itemSelectionChanged.connect(
            self._on_document_selected
        )

        self.add_document_button.clicked.connect(
            self.add_document
        )

        self.extract_button.clicked.connect(
            self.extract_parameters
        )

        self.delete_document_button.clicked.connect(
            self.delete_document
        )

    # ---------------------------------------------------------
    # ИСТОРИЯ
    # ---------------------------------------------------------

    def _build_history_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)

        self.history_table = make_table([
            "Дата",
            "Действие",
            "Описание",
        ])

        self.history_table.setColumnWidth(0, 160)
        self.history_table.setColumnWidth(1, 190)

        layout.addWidget(self.history_table)

        self.tabs.addTab(page, "История")

    # ---------------------------------------------------------
    # ПАНЕЛЬ ПРОСМОТРА ДОКУМЕНТА
    # ---------------------------------------------------------

    def _build_preview_panel(self):
        panel = QWidget()

        layout = QVBoxLayout(panel)

        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        title = QLabel("Просмотр документа")

        title.setStyleSheet(
            "font-size: 12pt; font-weight: bold;"
        )

        layout.addWidget(title)

        self.preview_filename = QLabel(
            "Документ не выбран"
        )

        self.preview_filename.setWordWrap(True)

        self.preview_filename.setStyleSheet(
            "background: #292a2d; padding: 7px; font-weight: bold;"
        )

        layout.addWidget(self.preview_filename)

        self.preview_scroll = QScrollArea()

        self.preview_scroll.setWidgetResizable(True)

        self.preview_scroll.setAlignment(
            Qt.AlignmentFlag.AlignHCenter
        )

        self.preview_content = QWidget()

        self.preview_layout = QVBoxLayout(
            self.preview_content
        )

        self.preview_layout.setAlignment(
            Qt.AlignmentFlag.AlignHCenter
        )

        self.preview_layout.setContentsMargins(
            8, 8, 8, 8
        )

        self.preview_scroll.setWidget(
            self.preview_content
        )

        layout.addWidget(self.preview_scroll, 1)

        self.preview_message = QLabel(
            "Выберите изделие и документ во вкладке «Документация»."
        )

        self.preview_message.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.preview_message.setWordWrap(True)

        self.preview_layout.addWidget(
            self.preview_message
        )

        self.open_external_button = QPushButton(
            "Открыть во внешней программе"
        )

        self.open_external_button.setEnabled(False)

        self.open_external_button.clicked.connect(
            self.open_document_external
        )

        layout.addWidget(self.open_external_button)

        return panel

    # ---------------------------------------------------------
    # ЗАГРУЗКА ИЗДЕЛИЙ
    # ---------------------------------------------------------

    def load_products(self):
        try:
            products = self.product_manager.search_products(
                search_text=self.search_edit.text().strip(),
                product_type=self.type_filter_edit.text().strip(),
                material=self.material_filter_edit.text().strip(),
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось загрузить изделия:\n{error}",
            )
            return

        previous_id = self.current_product_id

        self.products_table.setRowCount(0)

        for product in products:
            row = self.products_table.rowCount()

            self.products_table.insertRow(row)

            set_cell(
                self.products_table,
                row,
                0,
                product.get("article"),
            )

            set_cell(
                self.products_table,
                row,
                1,
                product.get("name"),
            )

            set_cell(
                self.products_table,
                row,
                2,
                product.get("product_type"),
            )

            set_cell(
                self.products_table,
                row,
                3,
                product.get("parameter_count", 0),
            )

            self.products_table.item(row, 0).setData(
                Qt.ItemDataRole.UserRole,
                product["id"],
            )

            if product["id"] == previous_id:
                self.products_table.selectRow(row)

        if self.products_table.rowCount() == 0:
            self.current_product_id = None
            self.clear_product_details()

    def _on_product_selected(self):
        product_id = selected_id(
            self.products_table
        )

        if product_id is None:
            return

        self.current_product_id = product_id

        self.load_product_details()

    def load_product_details(self):
        if self.current_product_id is None:
            self.clear_product_details()
            return

        product = self.product_manager.get_product(
            self.current_product_id
        )

        if not product:
            self.clear_product_details()
            return

        self.basic_info.setPlainText(
            f"Наименование: {product.get('name', '')}\n"
            f"Артикул: {product.get('article', '')}\n"
            f"Тип изделия: {product.get('product_type', '')}\n"
            f"Материал: {product.get('material', '')}\n\n"
            f"Описание:\n{product.get('description', '')}"
        )

        self.load_parameters()
        self.load_documents()
        self.load_history()

    def clear_product_details(self):
        self.basic_info.clear()

        self.parameters_table.setRowCount(0)
        self.documents_table.setRowCount(0)
        self.history_table.setRowCount(0)

        self.current_document_id = None
        self.preview_path = None

        self.show_preview_message(
            "Выберите изделие и документ во вкладке «Документация»."
        )

    # ---------------------------------------------------------
    # CRUD ИЗДЕЛИЙ
    # ---------------------------------------------------------

    def add_product(self):
        dialog = ProductDialog(self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            data = dialog.get_data()

            if self.product_manager.article_exists(
                data["article"]
            ):
                raise ValueError(
                    "Изделие с таким артикулом уже существует"
                )

            self.current_product_id = (
                self.product_manager.add_product(data)
            )

            self.load_products()
            self.load_product_details()

        except Exception as error:
            QMessageBox.warning(
                self,
                "Ошибка",
                str(error),
            )

    def edit_product(self):
        if self.current_product_id is None:
            QMessageBox.information(
                self,
                "Изменение",
                "Выберите изделие.",
            )
            return

        product = self.product_manager.get_product(
            self.current_product_id
        )

        dialog = ProductDialog(self, product)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            data = dialog.get_data()

            if self.product_manager.article_exists(
                data["article"],
                exclude_id=self.current_product_id,
            ):
                raise ValueError(
                    "Такой артикул уже используется"
                )

            self.product_manager.update_product(
                self.current_product_id,
                data,
            )

            self.load_products()
            self.load_product_details()

        except Exception as error:
            QMessageBox.warning(
                self,
                "Ошибка",
                str(error),
            )

    def copy_product(self):
        if self.current_product_id is None:
            QMessageBox.information(
                self,
                "Копирование",
                "Выберите изделие.",
            )
            return

        try:
            new_id = self.product_manager.duplicate_product(
                self.current_product_id
            )

            self.current_product_id = new_id

            self.load_products()
            self.load_product_details()

        except Exception as error:
            QMessageBox.warning(
                self,
                "Ошибка",
                str(error),
            )

    def delete_product(self):
        if self.current_product_id is None:
            QMessageBox.information(
                self,
                "Удаление",
                "Выберите изделие.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Удаление изделия",
            "Удалить выбранное изделие и связанные с ним данные?",
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.product_manager.delete_product(
                self.current_product_id
            )

            self.current_product_id = None

            self.load_products()
            self.clear_product_details()

        except Exception as error:
            QMessageBox.warning(
                self,
                "Ошибка",
                str(error),
            )

    # ---------------------------------------------------------
    # ХАРАКТЕРИСТИКИ
    # ---------------------------------------------------------

    def load_parameters(self):
        self.parameters_table.setRowCount(0)

        if self.current_product_id is None:
            return

        parameters = self.product_manager.get_product_parameters(
            self.current_product_id
        )

        for parameter in parameters:
            row = self.parameters_table.rowCount()

            self.parameters_table.insertRow(row)

            values = [
                parameter.get("name"),
                parameter.get("code"),
                parameter.get("nominal"),
                parameter.get("min_value"),
                parameter.get("max_value"),
                parameter.get("unit"),
                parameter.get("source"),
            ]

            for column, value in enumerate(values):
                set_cell(
                    self.parameters_table,
                    row,
                    column,
                    value,
                )

            self.parameters_table.item(row, 0).setData(
                Qt.ItemDataRole.UserRole,
                parameter["id"],
            )

    def add_parameter(self):
        if self.current_product_id is None:
            QMessageBox.information(
                self,
                "Характеристики",
                "Выберите изделие.",
            )
            return

        dialog = ParameterDialog(self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            self.product_manager.add_parameter(
                self.current_product_id,
                dialog.get_data(),
            )

            self.load_parameters()
            self.load_products()
            self.load_history()

        except Exception as error:
            QMessageBox.warning(
                self,
                "Ошибка",
                str(error),
            )

    def edit_parameter(self):
        parameter_id = selected_id(
            self.parameters_table
        )

        if parameter_id is None:
            QMessageBox.information(
                self,
                "Характеристики",
                "Выберите характеристику.",
            )
            return

        parameters = self.product_manager.get_product_parameters(
            self.current_product_id
        )

        parameter = next(
            (
                item for item in parameters
                if item["id"] == parameter_id
            ),
            None,
        )

        if not parameter:
            return

        dialog = ParameterDialog(
            self,
            parameter,
        )

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        try:
            self.product_manager.update_parameter(
                parameter_id,
                dialog.get_data(),
            )

            self.load_parameters()
            self.load_history()

        except Exception as error:
            QMessageBox.warning(
                self,
                "Ошибка",
                str(error),
            )

    def delete_parameter(self):
        parameter_id = selected_id(
            self.parameters_table
        )

        if parameter_id is None:
            QMessageBox.information(
                self,
                "Характеристики",
                "Выберите характеристику.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Удаление характеристики",
            "Удалить выбранную характеристику?",
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.product_manager.delete_parameter(
                parameter_id
            )

            self.load_parameters()
            self.load_products()
            self.load_history()

        except Exception as error:
            QMessageBox.warning(
                self,
                "Ошибка",
                str(error),
            )

    # ---------------------------------------------------------
    # ДОКУМЕНТЫ
    # ---------------------------------------------------------

    def load_documents(self):
        self.documents_table.setRowCount(0)

        self.current_document_id = None
        self.preview_path = None

        self.show_preview_message(
            "Выберите документ, чтобы просмотреть его оригинал."
        )

        if self.current_product_id is None:
            return

        documents = self.document_manager.get_product_documents(
            self.current_product_id
        )

        for document in documents:
            row = self.documents_table.rowCount()

            self.documents_table.insertRow(row)

            set_cell(
                self.documents_table,
                row,
                0,
                document.get("original_name"),
            )

            set_cell(
                self.documents_table,
                row,
                1,
                document.get("extension", "").upper().replace(".", ""),
            )

            set_cell(
                self.documents_table,
                row,
                2,
                self.document_manager.format_file_size(
                    document.get("file_size", 0)
                ),
            )

            set_cell(
                self.documents_table,
                row,
                3,
                document.get("uploaded_at"),
            )

            self.documents_table.item(row, 0).setData(
                Qt.ItemDataRole.UserRole,
                document["id"],
            )

    def add_document(self):
        if self.current_product_id is None:
            QMessageBox.information(
                self,
                "Документация",
                "Выберите изделие.",
            )
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите техническую документацию",
            "",
            (
                "Документы (*.pdf *.docx *.doc *.xlsx *.xls "
                "*.png *.jpg *.jpeg *.tif *.tiff);;"
                "Все файлы (*.*)"
            ),
        )

        if not file_path:
            return

        try:
            document_id = self.document_manager.add_document(
                self.current_product_id,
                file_path,
            )

            # Извлечение текста используется для последующего
            # автоматического определения характеристик.
            try:
                extracted_text = self.document_parser.extract_text(
                    file_path
                )

                self.document_manager.save_extracted_text(
                    document_id,
                    extracted_text,
                )

            except Exception:
                # Документ сохраняется даже при ошибке распознавания.
                pass

            self.load_documents()

            for row in range(self.documents_table.rowCount()):
                item = self.documents_table.item(row, 0)

                if (
                    item
                    and item.data(Qt.ItemDataRole.UserRole) == document_id
                ):
                    self.documents_table.selectRow(row)
                    break

        except Exception as error:
            QMessageBox.critical(
                self,
                "Ошибка загрузки",
                str(error),
            )

    def _on_document_selected(self):
        document_id = selected_id(
            self.documents_table
        )

        if document_id is None:
            return

        self.current_document_id = document_id

        try:
            document = self.document_manager.get_document(
                document_id
            )

            if not document:
                self.show_preview_message(
                    "Документ не найден в базе данных."
                )
                return

            path = self.document_manager.get_document_path(
                document_id
            )

            self.preview_path = Path(path)

            self.preview_filename.setText(
                document.get(
                    "original_name",
                    self.preview_path.name,
                )
            )

            self.open_external_button.setEnabled(
                self.preview_path.exists()
            )

            if not self.preview_path.exists():
                self.show_preview_message(
                    "Файл документа отсутствует на диске."
                )
                return

            self.show_document_preview(
                self.preview_path
            )

        except Exception as error:
            self.show_preview_message(
                f"Не удалось открыть документ:\n{error}"
            )

    def delete_document(self):
        if self.current_document_id is None:
            QMessageBox.information(
                self,
                "Документация",
                "Выберите документ.",
            )
            return

        answer = QMessageBox.question(
            self,
            "Удаление документа",
            "Удалить выбранный документ?",
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.document_manager.delete_document(
                self.current_document_id
            )

            self.current_document_id = None
            self.preview_path = None

            self.load_documents()

        except Exception as error:
            QMessageBox.warning(
                self,
                "Ошибка",
                str(error),
            )

    # ---------------------------------------------------------
    # ИЗВЛЕЧЕНИЕ ХАРАКТЕРИСТИК
    # ---------------------------------------------------------

    def extract_parameters(self):
        if self.current_document_id is None:
            QMessageBox.information(
                self,
                "Извлечение характеристик",
                "Сначала выберите документ.",
            )
            return

        try:
            document = self.document_manager.get_document(
                self.current_document_id
            )

            text = (
                document.get("extracted_text", "")
                if document else ""
            )

            if not text:
                path = self.document_manager.get_document_path(
                    self.current_document_id
                )

                text = self.document_parser.extract_text(
                    path
                )

                self.document_manager.save_extracted_text(
                    self.current_document_id,
                    text,
                )

            suggestions = self.document_parser.suggest_parameters(
                text
            )

            if not suggestions:
                QMessageBox.information(
                    self,
                    "Результат",
                    "Не удалось автоматически определить характеристики.\n"
                    "Добавьте их вручную или проверьте документ.",
                )
                return

            self._show_parameter_import_dialog(
                suggestions
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "Ошибка извлечения",
                str(error),
            )


    def _show_parameter_import_dialog(self, suggestions):
        dialog = QDialog(self)

        dialog.setWindowTitle(
            "Импорт характеристик из документа"
        )

        dialog.resize(950, 480)

        layout = QVBoxLayout(dialog)

        hint = QLabel(
            "Проверьте извлечённые характеристики. "
            "В столбцы «Минимум» и «Максимум» можно вручную "
            "ввести допустимые границы из чертежа или нормативной документации. "
            "Пустые значения означают, что допуск не задан."
        )
        hint.setWordWrap(True)

        layout.addWidget(hint)

        table = QTableWidget()

        headers = [
            "Название",
            "Код",
            "Номинал",
            "Минимум",
            "Максимум",
            "Ед.",
            "Примечание",
        ]

        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setRowCount(len(suggestions))

        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)

        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive
        )

        table.horizontalHeader().setStretchLastSection(True)

        for row, parameter in enumerate(suggestions):
            values = [
                parameter.get("name", ""),
                parameter.get("code", ""),
                parameter.get("nominal"),
                parameter.get("min_value"),
                parameter.get("max_value"),
                parameter.get("unit", ""),
                parameter.get("note", ""),
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(
                    "" if value is None else str(value)
                )

                table.setItem(row, column, item)

        table.setColumnWidth(0, 190)
        table.setColumnWidth(1, 80)
        table.setColumnWidth(2, 95)
        table.setColumnWidth(3, 95)
        table.setColumnWidth(4, 95)
        table.setColumnWidth(5, 65)

        layout.addWidget(table, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )

        layout.addWidget(buttons)

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        def cell(row, column):
            item = table.item(row, column)

            return item.text().strip() if item else ""

        def number(row, column, field_name):
            value = cell(row, column).replace(",", ".")

            if not value:
                return None

            try:
                return float(value)

            except ValueError:
                raise ValueError(
                    f"Строка {row + 1}: поле «{field_name}» "
                    f"должно содержать число."
                )

        try:
            parameters = self.product_manager.get_product_parameters(
                self.current_product_id
            )

            for row in range(table.rowCount()):
                name = cell(row, 0)
                code = cell(row, 1)

                if not name:
                    continue

                nominal = number(row, 2, "Номинал")
                minimum = number(row, 3, "Минимум")
                maximum = number(row, 4, "Максимум")

                if (
                    minimum is not None
                    and maximum is not None
                    and minimum > maximum
                ):
                    raise ValueError(
                        f"Строка {row + 1}: минимум не может "
                        "быть больше максимума."
                    )

                data = {
                    "name": name,
                    "code": code,
                    "nominal": nominal,
                    "min_value": minimum,
                    "max_value": maximum,
                    "unit": cell(row, 5),
                    "source": "document",
                    "note": cell(row, 6),
                }

                # Ищем уже существующую характеристику.
                existing = next(
                    (
                        parameter
                        for parameter in parameters
                        if (
                            code
                            and parameter.get("code", "").lower()
                            == code.lower()
                        )
                        or (
                            not code
                            and parameter.get("name", "").lower()
                            == name.lower()
                        )
                    ),
                    None,
                )

                if existing:
                    self.product_manager.update_parameter(
                        existing["id"],
                        data,
                    )
                else:
                    self.product_manager.add_parameter(
                        self.current_product_id,
                        data,
                    )

            self.load_parameters()
            self.load_products()
            self.load_history()

            QMessageBox.information(
                self,
                "Импорт завершён",
                "Характеристики сохранены в номенклатуре.\n"
                "Введённые минимальные и максимальные значения "
                "будут использоваться при контроле качества.",
            )

        except Exception as error:
            QMessageBox.warning(
                self,
                "Ошибка импорта",
                str(error),
            )

    # ---------------------------------------------------------
    # ПРОСМОТР ОРИГИНАЛА ДОКУМЕНТА
    # ---------------------------------------------------------

    def clear_preview(self):
        while self.preview_layout.count():
            item = self.preview_layout.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

    def show_preview_message(self, message):
        self.clear_preview()

        label = QLabel(message)

        label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        label.setWordWrap(True)

        self.preview_layout.addWidget(label)

        self.preview_filename.setText(
            "Документ не выбран"
        )

        self.open_external_button.setEnabled(False)

    def show_document_preview(self, path):
        self.clear_preview()

        suffix = path.suffix.lower()

        if suffix == ".pdf":
            self._show_pdf(path)
            return

        if suffix in (
            ".png",
            ".jpg",
            ".jpeg",
            ".bmp",
            ".tif",
            ".tiff",
        ):
            self._show_image(path)
            return

        label = QLabel(
            "Предварительный просмотр для этого формата "
            "не поддерживается.\n\n"
            "Нажмите «Открыть во внешней программе», "
            "чтобы просмотреть документ."
        )

        label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        label.setWordWrap(True)

        self.preview_layout.addWidget(label)

    def _show_pdf(self, path):
        try:
            import fitz

            pdf = fitz.open(str(path))

            if pdf.page_count == 0:
                raise ValueError(
                    "PDF-документ не содержит страниц"
                )

            available_width = max(
                400,
                self.preview_scroll.viewport().width() - 35,
            )

            for page_number in range(pdf.page_count):
                page = pdf.load_page(page_number)

                original_width = page.rect.width

                scale = available_width / original_width

                # Не увеличиваем маленькие страницы чрезмерно.
                scale = min(scale, 2.0)

                pix = page.get_pixmap(
                    matrix=fitz.Matrix(scale, scale),
                    alpha=False,
                )

                image = QPixmap()

                image.loadFromData(
                    pix.tobytes("png")
                )

                page_label = QLabel()

                page_label.setAlignment(
                    Qt.AlignmentFlag.AlignHCenter
                )

                page_label.setPixmap(image)

                page_label.setToolTip(
                    f"Страница {page_number + 1} "
                    f"из {pdf.page_count}"
                )

                self.preview_layout.addWidget(
                    page_label
                )

                separator = QFrame()

                separator.setFrameShape(
                    QFrame.Shape.HLine
                )

                separator.setStyleSheet(
                    "color: #5f6368; "
                    "margin-top: 8px; "
                    "margin-bottom: 8px;"
                )

                self.preview_layout.addWidget(
                    separator
                )

            pdf.close()

        except ImportError:
            label = QLabel(
                "Для встроенного просмотра PDF установите PyMuPDF:\n"
                "python -m pip install PyMuPDF\n\n"
                "Документ можно открыть во внешней программе."
            )

            label.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            label.setWordWrap(True)

            self.preview_layout.addWidget(label)

        except Exception as error:
            label = QLabel(
                f"Не удалось отобразить PDF:\n{error}\n\n"
                "Попробуйте открыть файл во внешней программе."
            )

            label.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            label.setWordWrap(True)

            self.preview_layout.addWidget(label)

    def _show_image(self, path):
        pixmap = QPixmap(str(path))

        if pixmap.isNull():
            self.show_preview_message(
                "Не удалось загрузить изображение."
            )
            return

        available_width = max(
            300,
            self.preview_scroll.viewport().width() - 35,
        )

        scaled = pixmap.scaledToWidth(
            available_width,
            Qt.TransformationMode.SmoothTransformation,
        )

        label = QLabel()

        label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        label.setPixmap(scaled)

        self.preview_layout.addWidget(label)

    def open_document_external(self):
        if (
            self.preview_path is None
            or not self.preview_path.exists()
        ):
            QMessageBox.warning(
                self,
                "Открытие документа",
                "Файл документа не найден.",
            )
            return

        QDesktopServices.openUrl(
            QUrl.fromLocalFile(
                str(self.preview_path.resolve())
            )
        )

    # ---------------------------------------------------------
    # ИСТОРИЯ
    # ---------------------------------------------------------

    def load_history(self):
        self.history_table.setRowCount(0)

        if self.current_product_id is None:
            return

        history = self.product_manager.get_product_history(
            self.current_product_id
        )

        for record in history:
            row = self.history_table.rowCount()

            self.history_table.insertRow(row)

            set_cell(
                self.history_table,
                row,
                0,
                record.get("created_at"),
            )

            set_cell(
                self.history_table,
                row,
                1,
                record.get("action"),
            )

            set_cell(
                self.history_table,
                row,
                2,
                record.get("details"),
            )

    # ---------------------------------------------------------
    # ПЕРЕКЛЮЧЕНИЕ ВКЛАДОК
    # ---------------------------------------------------------

    def _on_tab_changed(self, index):
        if self.current_product_id is None:
            return

        tab_name = self.tabs.tabText(index)

        if tab_name == "Документация":
            self.load_documents()

        elif tab_name == "Характеристики":
            self.load_parameters()

        elif tab_name == "История":
            self.load_history()
