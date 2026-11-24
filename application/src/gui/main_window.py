
from PySide6.QtWidgets import (
    QMainWindow,
    QTabWidget,
)

from .products_page import ProductsPage
from .simulator_page import SimulatorPage
from .experiments_page import ExperimentsPage
from .dataset_page import DatasetPage


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Интеллектуальная система управления процессом ЧПУ"
        )

        self.resize(1500, 950)

        self.tabs = QTabWidget()

        self.products_page = ProductsPage()
        self.simulator_page = SimulatorPage()
        self.experiments_page = ExperimentsPage()
        self.dataset_page = DatasetPage()

        self.tabs.addTab(
            self.products_page,
            "Номенклатура"
        )

        self.tabs.addTab(
            self.simulator_page,
            "Симулятор ЧПУ"
        )

        self.tabs.addTab(
            self.experiments_page,
            "Экспериментальные данные"
        )

        self.tabs.addTab(
            self.dataset_page,
            "Подготовка ML-датасета"
        )

        self.setCentralWidget(self.tabs)
