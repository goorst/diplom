
import sys

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QMessageBox,
)

from application.src.products.product_manager import ProductManager
from application.src.products.document_manager import DocumentManager

from application.src.core.measurement_logger import MeasurementLogger

from application.src.gui.products_page import ProductsPage
from application.src.gui.quality_page import QualityPage
from application.src.gui.conveyor_page import ConveyorPage


DARK_THEME = """
QMainWindow, QWidget {
    background-color: #202124;
    color: #e8eaed;
    font-family: Segoe UI;
    font-size: 13px;
}

QLabel {
    color: #e8eaed;
}

QGroupBox {
    color: #e8eaed;
    background-color: #292a2d;
    border: 1px solid #45474b;
    border-radius: 7px;
    margin-top: 12px;
    padding: 12px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}

QPushButton {
    background-color: #3c4043;
    color: #f1f3f4;
    border: 1px solid #5f6368;
    border-radius: 5px;
    padding: 8px 12px;
}

QPushButton:hover {
    background-color: #505459;
    border-color: #8ab4f8;
}

QPushButton:pressed {
    background-color: #303134;
}

QPushButton:disabled {
    color: #77797c;
    background-color: #292a2d;
    border-color: #3c4043;
}

QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #292a2d;
    color: #e8eaed;
    border: 1px solid #5f6368;
    border-radius: 4px;
    padding: 6px;
    selection-background-color: #3c65a0;
}

QLineEdit:focus, QTextEdit:focus {
    border: 1px solid #8ab4f8;
}

QTableWidget, QTableView {
    background-color: #292a2d;
    alternate-background-color: #303134;
    color: #e8eaed;
    gridline-color: #45474b;
    border: 1px solid #45474b;
    selection-background-color: #3c65a0;
    selection-color: white;
}

QHeaderView::section {
    background-color: #35363a;
    color: #e8eaed;
    border: 1px solid #45474b;
    padding: 7px;
    font-weight: bold;
}

QTabWidget::pane {
    background-color: #292a2d;
    border: 1px solid #45474b;
}

QTabBar::tab {
    background-color: #303134;
    color: #bdc1c6;
    padding: 10px 16px;
    margin-right: 2px;
    border: 1px solid #45474b;
    border-bottom: none;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
}

QTabBar::tab:selected {
    background-color: #292a2d;
    color: #8ab4f8;
    font-weight: bold;
}

QTabBar::tab:hover {
    color: white;
    background-color: #3c4043;
}

QComboBox {
    background-color: #292a2d;
    color: #e8eaed;
    border: 1px solid #5f6368;
    border-radius: 4px;
    padding: 6px;
}

QComboBox QAbstractItemView {
    background-color: #292a2d;
    color: #e8eaed;
    selection-background-color: #3c65a0;
}

QScrollBar:vertical {
    background-color: #202124;
    width: 12px;
}

QScrollBar::handle:vertical {
    background-color: #5f6368;
    border-radius: 5px;
    min-height: 25px;
}

QScrollBar:horizontal {
    background-color: #202124;
    height: 12px;
}

QScrollBar::handle:horizontal {
    background-color: #5f6368;
    border-radius: 5px;
    min-width: 25px;
}

QSplitter::handle {
    background-color: #45474b;
}

QStatusBar {
    background-color: #292a2d;
    color: #bdc1c6;
    border-top: 1px solid #45474b;
}

QMessageBox {
    background-color: #292a2d;
    color: #e8eaed;
}

QDialog {
    background-color: #202124;
    color: #e8eaed;
}
"""


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Система автоматического контроля качества изделий"
        )

        self.resize(1400, 850)
        self.setMinimumSize(1000, 650)

        # Общие менеджеры данных.
        self.product_manager = ProductManager()
        self.document_manager = DocumentManager()
        self.measurement_logger = MeasurementLogger()

        self.init_ui()

    def init_ui(self):

        self.tabs = QTabWidget()

        # 1. Номенклатура изделий.
        self.products_page = ProductsPage()

        self.tabs.addTab(
            self.products_page,
            "Номенклатура изделий"
        )

        # 2. Контроль качества.
        self.quality_page = QualityPage(
            product_manager=self.product_manager,
            measurement_logger=self.measurement_logger,
        )

        self.tabs.addTab(
            self.quality_page,
            "Контроль качества"
        )

        # 3. Конвейер.
        self.conveyor_page = ConveyorPage(
            product_manager=self.product_manager,
            measurement_logger=self.measurement_logger,
        )

        self.tabs.addTab(
            self.conveyor_page,
            "Конвейер"
        )

        self.setCentralWidget(self.tabs)

        self.statusBar().showMessage(
            "Система готова к работе"
        )

    def closeEvent(self, event):
        # Останавливаем конвейер перед закрытием приложения.
        if hasattr(self, "conveyor_page"):
            if self.conveyor_page.timer.isActive():
                self.conveyor_page.stop_conveyor()

        event.accept()


def main():

    app = QApplication(sys.argv)

    app.setApplicationName(
        "Система автоматического контроля качества"
    )

    app.setStyleSheet(DARK_THEME)

    try:
        window = MainWindow()
        window.show()

        sys.exit(app.exec())

    except Exception as error:

        QMessageBox.critical(
            None,
            "Ошибка запуска",
            f"Не удалось запустить приложение:\n\n{error}"
        )

        sys.exit(1)


if __name__ == "__main__":
    main()
