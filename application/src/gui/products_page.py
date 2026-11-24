from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QLabel,
    QTabWidget,
    QMessageBox,
    QFileDialog,
    QInputDialog,
    QHeaderView,
    QAbstractItemView,
)

from application.src.products import ProductManager, DocumentManager
from .product_dialog import ProductDialog
from .operation_dialog import OperationDialog


class ProductsPage(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.product_manager = ProductManager()
        self.document_manager = DocumentManager(
            self.product_manager
        )

        self.selected_product_id = None

        self.build_ui()
        self.load_products()

    def build_ui(self):
        root = QVBoxLayout(self)

        title = QLabel("Номенклатура изделий")
        title.setStyleSheet(
            "font-size: 22px; font-weight: bold; padding: 8px;"
        )
        root.addWidget(title)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Левая часть: список изделий
        left = QWidget()
        left_layout = QVBoxLayout(left)

        product_buttons = QHBoxLayout()

        add_button = QPushButton("Добавить")
        edit_button = QPushButton("Изменить")
        delete_button = QPushButton("Удалить")

        add_button.clicked.connect(self.add_product)
        edit_button.clicked.connect(self.edit_product)
        delete_button.clicked.connect(self.delete_product)

        product_buttons.addWidget(add_button)
        product_buttons.addWidget(edit_button)
        product_buttons.addWidget(delete_button)

        left_layout.addLayout(product_buttons)

        self.products_table = QTableWidget(0, 5)
        self.products_table.setHorizontalHeaderLabels([
            "Название",
            "Тип детали",
            "Материал",
            "Чертёж",
            "ID",
        ])

        self.products_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.products_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.products_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.products_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        self.products_table.itemSelectionChanged.connect(
            self.on_product_selected
        )

        left_layout.addWidget(self.products_table)

        # Правая часть: карточка, операции, документы
        right = QWidget()
        right_layout = QVBoxLayout(right)

        self.product_info = QLabel(
            "Выберите изделие из списка."
        )
        self.product_info.setWordWrap(True)
        self.product_info.setMinimumHeight(90)
        self.product_info.setStyleSheet("""
            QLabel {
                color: #202124;
                background-color: #f0f0f0;
                border: 1px solid #cccccc;
                padding: 10px;
            }
        """)

        right_layout.addWidget(self.product_info)

        self.tabs = QTabWidget()

        self.operations_table = QTableWidget(0, 6)
        self.operations_table.setHorizontalHeaderLabels([
            "№",
            "Операция",
            "Обороты",
            "Подача",
            "Глубина",
            "Инструмент",
        ])
        self.configure_table(self.operations_table)

        operations_widget = QWidget()
        operations_layout = QVBoxLayout(operations_widget)

        operation_buttons = QHBoxLayout()

        add_operation_button = QPushButton("Добавить операцию")
        delete_operation_button = QPushButton("Удалить операцию")

        add_operation_button.clicked.connect(
            self.add_operation
        )
        delete_operation_button.clicked.connect(
            self.delete_operation
        )

        operation_buttons.addWidget(add_operation_button)
        operation_buttons.addWidget(delete_operation_button)

        operations_layout.addLayout(operation_buttons)
        operations_layout.addWidget(self.operations_table)

        self.tabs.addTab(
            operations_widget,
            "Технологические операции"
        )

        self.documents_table = QTableWidget(0, 4)
        self.documents_table.setHorizontalHeaderLabels([
            "Название файла",
            "Формат",
            "Категория",
            "Дата добавления",
        ])
        self.configure_table(self.documents_table)

        documents_widget = QWidget()
        documents_layout = QVBoxLayout(documents_widget)

        document_buttons = QHBoxLayout()

        attach_button = QPushButton("Прикрепить документ")
        open_button = QPushButton("Открыть документ")
        delete_document_button = QPushButton("Удалить документ")

        attach_button.clicked.connect(self.attach_document)
        open_button.clicked.connect(self.open_document)
        delete_document_button.clicked.connect(
            self.delete_document
        )

        document_buttons.addWidget(attach_button)
        document_buttons.addWidget(open_button)
        document_buttons.addWidget(delete_document_button)

        documents_layout.addLayout(document_buttons)
        documents_layout.addWidget(self.documents_table)

        self.tabs.addTab(
            documents_widget,
            "Технические документы"
        )

        right_layout.addWidget(self.tabs)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([550, 750])

        root.addWidget(splitter)

    @staticmethod
    def configure_table(table):
        table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

    def show_error(self, error):
        QMessageBox.critical(
            self,
            "Ошибка",
            str(error)
        )

    def current_product(self):
        if not self.selected_product_id:
            QMessageBox.information(
                self,
                "Номенклатура",
                "Сначала выберите изделие."
            )
            return None

        return self.product_manager.get_product(
            self.selected_product_id
        )

    def load_products(self, select_id=None):
        products = self.product_manager.list_products()

        self.products_table.setRowCount(0)
        self.selected_product_id = None

        selected_row = None

        for row, product in enumerate(products):
            self.products_table.insertRow(row)

            values = [
                product["name"],
                product["part_type"],
                product["material"],
                product["drawing_number"] or "",
                product["product_id"],
            ]

            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(
                    Qt.ItemDataRole.UserRole,
                    product["product_id"]
                )
                self.products_table.setItem(
                    row,
                    column,
                    item
                )

            if product["product_id"] == select_id:
                selected_row = row

        if selected_row is not None:
            self.products_table.selectRow(selected_row)
        elif products:
            self.products_table.selectRow(0)
        else:
            self.clear_details()

    def clear_details(self):
        self.selected_product_id = None
        self.product_info.setText(
            "Выберите изделие из списка."
        )
        self.operations_table.setRowCount(0)
        self.documents_table.setRowCount(0)

    def on_product_selected(self):
        row = self.products_table.currentRow()

        if row < 0:
            return

        item = self.products_table.item(row, 0)

        if item is None:
            return

        product_id = item.data(Qt.ItemDataRole.UserRole)

        self.selected_product_id = product_id

        self.load_product_details()

    def load_product_details(self):
        product = self.current_product()

        if not product:
            self.clear_details()
            return

        self.product_info.setText(
            f"<b>{product['name']}</b><br>"
            f"ID: {product['product_id']}<br>"
            f"Тип детали: {product['part_type']}<br>"
            f"Материал: {product['material']}<br>"
            f"Номер чертежа: {product['drawing_number'] or '—'}<br>"
            f"Описание: {product['description'] or '—'}"
        )

        self.load_operations()
        self.load_documents()

    def add_product(self):
        dialog = ProductDialog(self)

        if dialog.exec():
            try:
                data = dialog.get_data()

                product_id = self.product_manager.add_product(
                    **data
                )

                self.load_products(select_id=product_id)

            except Exception as error:
                self.show_error(error)

    def edit_product(self):
        product = self.current_product()

        if not product:
            return

        dialog = ProductDialog(
            self,
            product=product
        )

        if dialog.exec():
            try:
                self.product_manager.update_product(
                    product["product_id"],
                    **dialog.get_data()
                )

                self.load_products(
                    select_id=product["product_id"]
                )

            except Exception as error:
                self.show_error(error)

    def delete_product(self):
        product = self.current_product()

        if not product:
            return

        answer = QMessageBox.question(
            self,
            "Удаление изделия",
            (
                f"Удалить изделие «{product['name']}»?\n\n"
                "Связанные операции и записи документов "
                "также будут удалены из базы данных."
            )
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.product_manager.delete_product(
                product["product_id"]
            )

            self.load_products()

        except Exception as error:
            self.show_error(error)

    def load_operations(self):
        self.operations_table.setRowCount(0)

        operations = self.product_manager.list_operations(
            self.selected_product_id
        )

        for row, operation in enumerate(operations):
            self.operations_table.insertRow(row)

            values = [
                operation["sequence_number"],
                operation["operation_name"],
                operation["spindle_speed"],
                operation["feed_rate"],
                operation["cutting_depth"],
                operation["tool_id"],
            ]

            item = QTableWidgetItem(
                str(operation["operation_id"])
            )
            item.setData(
                Qt.ItemDataRole.UserRole,
                operation["operation_id"]
            )

            for column, value in enumerate(values):
                self.operations_table.setItem(
                    row,
                    column,
                    QTableWidgetItem(
                        "" if value is None else str(value)
                    )
                )

            self.operations_table.item(
                row, 0
            ).setData(
                Qt.ItemDataRole.UserRole,
                operation["operation_id"]
            )

    def add_operation(self):
        if not self.current_product():
            return

        dialog = OperationDialog(self)

        if dialog.exec():
            try:
                data = dialog.get_data()

                self.product_manager.add_operation(
                    product_id=self.selected_product_id,
                    **data
                )

                self.load_operations()

            except Exception as error:
                self.show_error(error)

    def delete_operation(self):
        if not self.current_product():
            return

        row = self.operations_table.currentRow()

        if row < 0:
            QMessageBox.information(
                self,
                "Операции",
                "Выберите операцию."
            )
            return

        operation_id = self.operations_table.item(
            row, 0
        ).data(Qt.ItemDataRole.UserRole)

        answer = QMessageBox.question(
            self,
            "Удаление операции",
            "Удалить выбранную технологическую операцию?"
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.product_manager.delete_operation(
                operation_id
            )
            self.load_operations()

        except Exception as error:
            self.show_error(error)

    def load_documents(self):
        self.documents_table.setRowCount(0)

        documents = self.document_manager.list_documents(
            self.selected_product_id
        )

        for row, document in enumerate(documents):
            self.documents_table.insertRow(row)

            values = [
                document["original_name"],
                document["extension"],
                document["category"] or "",
                document["uploaded_at"],
            ]

            for column, value in enumerate(values):
                self.documents_table.setItem(
                    row,
                    column,
                    QTableWidgetItem(str(value or ""))
                )

            self.documents_table.item(
                row, 0
            ).setData(
                Qt.ItemDataRole.UserRole,
                document["document_id"]
            )

    def attach_document(self):
        if not self.current_product():
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите технический документ",
            "",
            (
                "Поддерживаемые файлы "
                "(*.pdf *.dxf *.step *.stp *.dwg "
                "*.png *.jpg *.jpeg *.xlsx *.docx)"
            )
        )

        if not file_path:
            return

        category, accepted = QInputDialog.getText(
            self,
            "Категория документа",
            "Введите категорию:",
            text="Техническая документация"
        )

        if not accepted:
            return

        description, accepted = QInputDialog.getText(
            self,
            "Описание документа",
            "Введите описание:"
        )

        if not accepted:
            return

        try:
            self.document_manager.add_document(
                product_id=self.selected_product_id,
                file_path=file_path,
                category=category.strip() or "Техническая документация",
                description=description.strip()
            )

            self.load_documents()

        except Exception as error:
            self.show_error(error)

    def selected_document_id(self):
        row = self.documents_table.currentRow()

        if row < 0:
            QMessageBox.information(
                self,
                "Документы",
                "Выберите документ."
            )
            return None

        item = self.documents_table.item(row, 0)

        return item.data(Qt.ItemDataRole.UserRole)

    def open_document(self):
        if not self.current_product():
            return

        document_id = self.selected_document_id()

        if not document_id:
            return

        try:
            path = self.document_manager.get_document_path(
                document_id
            )

            QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(path))
            )

        except Exception as error:
            self.show_error(error)

    def delete_document(self):
        if not self.current_product():
            return

        document_id = self.selected_document_id()

        if not document_id:
            return

        answer = QMessageBox.question(
            self,
            "Удаление документа",
            "Удалить выбранный документ и его сохранённую копию?"
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            self.document_manager.delete_document(
                document_id
            )

            self.load_documents()

        except Exception as error:
            self.show_error(error)