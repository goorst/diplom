
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
)

from application.src.quality.dataset_builder import DatasetBuilder


class DatasetPage(QWidget):
    """Страница формирования обучающего и тестового датасетов."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.dataset_builder = DatasetBuilder()
        self.current_result = None

        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # Заголовок
        title = QLabel("Подготовка экспериментального датасета")
        title.setStyleSheet(
            "font-size: 18px; font-weight: bold;"
        )

        description = QLabel(
            "Формирование обучающей и тестовой выборок "
            "на основе результатов контроля качества."
        )
        description.setWordWrap(True)

        main_layout.addWidget(title)
        main_layout.addWidget(description)

        # Управление
        control_group = QGroupBox("Формирование датасета")
        control_layout = QVBoxLayout(control_group)

        self.build_button = QPushButton(
            "Сформировать датасет"
        )
        self.build_button.clicked.connect(
            self.build_dataset
        )

        self.status_label = QLabel(
            "Датасет ещё не сформирован."
        )
        self.status_label.setWordWrap(True)

        control_layout.addWidget(self.build_button)
        control_layout.addWidget(self.status_label)

        main_layout.addWidget(control_group)

        # Статистика
        stats_group = QGroupBox("Статистика датасета")
        stats_layout = QVBoxLayout(stats_group)

        self.total_label = QLabel("Всего записей: —")
        self.train_label = QLabel("Обучающая выборка: —")
        self.test_label = QLabel("Тестовая выборка: —")
        self.experiments_label = QLabel("Экспериментов: —")
        self.products_label = QLabel("Типов изделий: —")
        self.features_label = QLabel("Признаков: —")

        self.good_label = QLabel("GOOD: —")
        self.defect_label = QLabel("DEFECT: —")

        for label in (
            self.total_label,
            self.train_label,
            self.test_label,
            self.experiments_label,
            self.products_label,
            self.features_label,
            self.good_label,
            self.defect_label,
        ):
            stats_layout.addWidget(label)

        main_layout.addWidget(stats_group)

        # Таблица
        table_group = QGroupBox("Предварительный просмотр")
        table_layout = QVBoxLayout(table_group)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

        self.table.horizontalHeader().setStretchLastSection(
            True
        )

        table_layout.addWidget(self.table)

        main_layout.addWidget(table_group, 1)

    def build_dataset(self):
        """Формирует датасет и отображает результат."""
        self.build_button.setEnabled(False)
        self.status_label.setText(
            "Формирование датасета..."
        )

        try:
            result = self.dataset_builder.build_dataset()

            self.current_result = result

            self.update_statistics(result)
            self.update_table(result["dataframe"])

            paths = result["paths"]

            self.status_label.setText(
                "Датасет успешно сформирован.\n"
                f"Сохранён в: {Path(paths['dataset']).parent}"
            )

            QMessageBox.information(
                self,
                "Формирование завершено",
                "Датасет успешно сформирован.\n\n"
                f"Всего записей: {result['total']}\n"
                f"Обучающих: {result['train']}\n"
                f"Тестовых: {result['test']}\n\n"
                f"Файлы сохранены в:\n"
                f"{Path(paths['dataset']).parent}"
            )

        except Exception as error:
            self.status_label.setText(
                "Не удалось сформировать датасет."
            )

            QMessageBox.critical(
                self,
                "Ошибка формирования датасета",
                str(error)
            )

        finally:
            self.build_button.setEnabled(True)

    def update_statistics(self, result):
        """Обновляет статистические показатели."""
        self.total_label.setText(
            f"Всего записей: {result['total']}"
        )

        self.train_label.setText(
            f"Обучающая выборка: {result['train']} "
            f"({result['train_experiments']} экспериментов)"
        )

        self.test_label.setText(
            f"Тестовая выборка: {result['test']} "
            f"({result['test_experiments']} экспериментов)"
        )

        self.experiments_label.setText(
            f"Всего экспериментов: {result['experiments']}"
        )

        self.products_label.setText(
            f"Типов изделий: {result['products']}"
        )

        self.features_label.setText(
            f"Количество признаков: {result['features']}"
        )

        self.good_label.setText(
            f"GOOD: {result['good']}"
        )

        self.defect_label.setText(
            f"DEFECT: {result['defect']}"
        )

    def update_table(self, dataframe):
        """Показывает первые 100 строк датасета."""
        preview = dataframe.head(100)

        self.table.clear()
        self.table.setRowCount(len(preview))
        self.table.setColumnCount(len(preview.columns))

        self.table.setHorizontalHeaderLabels(
            [str(column) for column in preview.columns]
        )

        for row_index, (_, row) in enumerate(
            preview.iterrows()
        ):
            for column_index, value in enumerate(row):
                if value is None:
                    text = ""
                elif isinstance(value, float):
                    text = f"{value:.6f}"
                else:
                    text = str(value)

                self.table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(text)
                )

        self.table.resizeColumnsToContents()
