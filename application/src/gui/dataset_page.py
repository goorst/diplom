
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QScrollArea,
    QSizePolicy,
    QAbstractScrollArea,
    QAbstractItemView,
    QProgressBar,
)
from PySide6.QtCore import Qt, QThread, Signal

from application.src.core.dataset_builder import DatasetBuilder
from application.src.core.model_trainer import ModelTrainer


class DatasetTrainingWorker(QThread):
    """Подготовка данных и обучение модели в отдельном потоке."""

    completed = Signal(object, object, object, object)
    failed = Signal(str)

    def run(self):
        try:
            # Подготовка датасета.
            builder = DatasetBuilder()
            dataset = builder.build()

            if len(dataset) < 10:
                raise ValueError(
                    "Для обучения необходимо минимум "
                    "10 измерений."
                )

            # Разделение по независимым экспериментам.
            train_rows, test_rows = builder.split_dataset(
                train_ratio=0.8
            )

            # Обучение модели.
            trainer = ModelTrainer()

            metrics = trainer.train(
                train_rows=train_rows,
                test_rows=test_rows,
                feature_names=builder.feature_names,
            )

            self.completed.emit(
                builder,
                dataset,
                trainer,
                metrics,
            )

        except Exception as error:
            self.failed.emit(str(error))


class DatasetPage(QWidget):
    """Подготовка датасета и обучение ML-модели."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.builder = DatasetBuilder()
        self.trainer = ModelTrainer()
        self.dataset = []

        self.training_thread = None

        self.build_ui()

    def build_ui(self):
        page_layout = QVBoxLayout(self)
        page_layout.setContentsMargins(6, 6, 6, 6)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)

        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        content = QWidget()
        root = QVBoxLayout(content)

        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        title = QLabel(
            "Подготовка датасета и обучение модели"
        )

        title.setStyleSheet(
            "font-size: 22px; font-weight: bold; padding: 8px;"
        )

        root.addWidget(title)

        description = QLabel(
            "Формирование экспериментального датасета, "
            "обучение Random Forest и оценка качества диагностики."
        )

        description.setWordWrap(True)
        root.addWidget(description)

        # ======================================
        # ИНФОРМАЦИЯ О ДАТАСЕТЕ
        # ======================================

        info_group = QGroupBox("Состав датасета")
        info_layout = QVBoxLayout(info_group)

        self.total_label = QLabel(
            "Измерений в источнике: 0"
        )

        self.prepared_label = QLabel(
            "Подготовлено записей: 0"
        )

        self.skipped_label = QLabel(
            "Пропущено записей: 0"
        )

        self.features_label = QLabel(
            "Количество признаков: 0"
        )

        self.targets_label = QLabel(
            "Количество целевых меток: 4"
        )

        for label in (
            self.total_label,
            self.prepared_label,
            self.skipped_label,
            self.features_label,
            self.targets_label,
        ):
            info_layout.addWidget(label)

        root.addWidget(info_group)

        # ======================================
        # РАСПРЕДЕЛЕНИЕ КЛАССОВ
        # ======================================

        classes_group = QGroupBox(
            "Распределение классов"
        )

        classes_layout = QVBoxLayout(classes_group)

        self.classes_label = QLabel(
            "Датасет ещё не сформирован."
        )

        self.classes_label.setWordWrap(True)

        self.classes_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        classes_layout.addWidget(self.classes_label)
        root.addWidget(classes_group)

        # ======================================
        # ПОДГОТОВКА ДАТАСЕТА
        # ======================================

        dataset_group = QGroupBox(
            "Подготовка данных"
        )

        dataset_layout = QHBoxLayout(dataset_group)

        self.build_button = QPushButton(
            "Сформировать датасет"
        )

        self.export_button = QPushButton(
            "Экспортировать выборки"
        )

        self.export_button.setEnabled(False)

        self.build_button.clicked.connect(
            self.build_dataset
        )

        self.export_button.clicked.connect(
            self.export_dataset
        )

        dataset_layout.addWidget(self.build_button)
        dataset_layout.addWidget(self.export_button)
        dataset_layout.addStretch()

        root.addWidget(dataset_group)

        # ======================================
        # ОБУЧЕНИЕ МОДЕЛИ
        # ======================================

        training_group = QGroupBox(
            "Обучение модели машинного обучения"
        )

        training_layout = QVBoxLayout(training_group)

        training_buttons = QHBoxLayout()

        self.train_button = QPushButton(
            "Обучить модель Random Forest"
        )

        self.train_button.clicked.connect(
            self.train_model
        )

        self.save_model_button = QPushButton(
            "Сохранить обученную модель"
        )

        self.save_model_button.setEnabled(False)

        self.save_model_button.clicked.connect(
            self.save_model
        )

        training_buttons.addWidget(self.train_button)
        training_buttons.addWidget(self.save_model_button)
        training_buttons.addStretch()

        training_layout.addLayout(training_buttons)

        self.training_status = QLabel(
            "Модель ещё не обучалась."
        )

        self.training_status.setWordWrap(True)

        training_layout.addWidget(
            self.training_status
        )

        # Индикатор выполнения.
        self.training_progress = QProgressBar()
        self.training_progress.setRange(0, 0)
        self.training_progress.setTextVisible(False)
        self.training_progress.hide()

        training_layout.addWidget(
            self.training_progress
        )

        self.metrics_label = QLabel(
            "Метрики качества появятся после обучения."
        )

        self.metrics_label.setWordWrap(True)

        training_layout.addWidget(
            self.metrics_label
        )

        self.metrics_table = QTableWidget()
        self.configure_table(self.metrics_table)

        self.metrics_table.setColumnCount(4)

        self.metrics_table.setHorizontalHeaderLabels([
            "Неисправность",
            "Precision",
            "Recall",
            "F1-score",
        ])

        self.metrics_table.setMaximumHeight(190)
        self.metrics_table.setMinimumHeight(150)

        metrics_header = (
            self.metrics_table.horizontalHeader()
        )

        metrics_header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch
        )

        for column in range(1, 4):
            metrics_header.setSectionResizeMode(
                column,
                QHeaderView.ResizeMode.ResizeToContents
            )

        training_layout.addWidget(
            self.metrics_table
        )

        root.addWidget(training_group)

        # ======================================
        # ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР
        # ======================================

        preview_group = QGroupBox(
            "Предварительный просмотр датасета"
        )

        preview_layout = QVBoxLayout(preview_group)

        preview_info = QLabel(
            "Показаны первые 20 записей. "
            "Для просмотра всех признаков используйте "
            "горизонтальную прокрутку."
        )

        preview_info.setWordWrap(True)

        preview_layout.addWidget(preview_info)

        self.table = QTableWidget()
        self.configure_table(self.table)

        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        self.table.setMinimumHeight(420)

        self.table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        header = self.table.horizontalHeader()

        header.setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

        header.setMinimumSectionSize(110)
        header.setDefaultSectionSize(140)

        self.table.verticalHeader().setDefaultSectionSize(28)

        preview_layout.addWidget(self.table)
        root.addWidget(preview_group)

        self.result_label = QLabel(
            "Ожидание формирования датасета."
        )

        self.result_label.setWordWrap(True)
        root.addWidget(self.result_label)

        root.addStretch()

        self.scroll_area.setWidget(content)
        page_layout.addWidget(self.scroll_area)

    # ==========================================
    # НАСТРОЙКА ТАБЛИЦ
    # ==========================================

    def configure_table(self, table):
        table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        table.setAlternatingRowColors(True)

        table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        table.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents
        )

        table.setWordWrap(False)

        table.setTextElideMode(
            Qt.TextElideMode.ElideNone
        )

        table.setHorizontalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )

        table.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )

    # ==========================================
    # ФОРМИРОВАНИЕ ДАТАСЕТА
    # ==========================================

    def build_dataset(self):
        if self.training_thread is not None:
            return

        self.build_button.setEnabled(False)
        self.train_button.setEnabled(False)

        try:
            self.builder = DatasetBuilder()
            self.dataset = self.builder.build()

            self.update_statistics()
            self.update_table()

            self.export_button.setEnabled(
                len(self.dataset) >= 2
            )

            self.trainer = ModelTrainer()

            self.save_model_button.setEnabled(False)
            self.metrics_table.setRowCount(0)

            self.metrics_label.setText(
                "Обучите модель на сформированном датасете."
            )

            self.training_status.setText(
                "Датасет сформирован. "
                "Модель ещё не обучалась."
            )

            self.result_label.setText(
                "Датасет успешно сформирован."
            )

        except Exception as error:
            self.dataset = []

            self.export_button.setEnabled(False)

            QMessageBox.critical(
                self,
                "Ошибка формирования датасета",
                str(error),
            )

        finally:
            self.build_button.setEnabled(True)
            self.train_button.setEnabled(True)

    # ==========================================
    # СТАТИСТИКА
    # ==========================================

    def update_statistics(self):
        self.total_label.setText(
            "Измерений в источнике: "
            f"{self.builder.total_source_rows}"
        )

        self.prepared_label.setText(
            "Подготовлено записей: "
            f"{len(self.dataset)}"
        )

        self.skipped_label.setText(
            "Пропущено записей: "
            f"{self.builder.skipped_rows}"
        )

        self.features_label.setText(
            "Количество признаков: "
            f"{len(self.builder.feature_names)}"
        )

        distribution = self.builder.class_distribution

        if distribution:
            lines = []

            for label, count in sorted(
                distribution.items(),
                key=lambda item: item[1],
                reverse=True,
            ):
                percentage = (
                    count / len(self.dataset) * 100
                    if self.dataset else 0
                )

                lines.append(
                    f"{label}: {count} ({percentage:.1f}%)"
                )

            self.classes_label.setText(
                "\n".join(lines)
            )

        else:
            self.classes_label.setText("Нет данных.")

    # ==========================================
    # ТАБЛИЦА ДАТАСЕТА
    # ==========================================

    def update_table(self):
        if not self.dataset:
            self.table.clear()
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return

        preview_rows = self.dataset[:20]
        columns = list(self.dataset[0].keys())

        self.table.setUpdatesEnabled(False)

        try:
            self.table.clear()

            self.table.setRowCount(
                len(preview_rows)
            )

            self.table.setColumnCount(
                len(columns)
            )

            self.table.setHorizontalHeaderLabels(
                columns
            )

            for row_index, row in enumerate(preview_rows):
                for column_index, column in enumerate(columns):
                    value = row.get(column)

                    if isinstance(value, float):
                        value_text = f"{value:.3f}"
                    else:
                        value_text = str(value)

                    item = QTableWidgetItem(value_text)

                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter
                    )

                    self.table.setItem(
                        row_index,
                        column_index,
                        item,
                    )

        finally:
            self.table.setUpdatesEnabled(True)
            self.table.viewport().update()

        self.table.resizeColumnsToContents()

        self.table.horizontalHeader().setMinimumSectionSize(
            110
        )

        self.result_label.setText(
            f"Показано {len(preview_rows)} "
            f"из {len(self.dataset)} записей."
        )

    # ==========================================
    # ЭКСПОРТ
    # ==========================================

    def export_dataset(self):
        if self.training_thread is not None:
            return

        if len(self.dataset) < 2:
            QMessageBox.information(
                self,
                "Экспорт",
                "Недостаточно данных для разделения выборок.",
            )
            return

        directory = QFileDialog.getExistingDirectory(
            self,
            "Выбрать папку для экспорта датасета",
        )

        if not directory:
            return

        self.export_button.setEnabled(False)

        try:
            result = self.builder.export_bundle(
                directory
            )

            QMessageBox.information(
                self,
                "Экспорт завершён",
                "Датасет успешно экспортирован.\n\n"
                f"Всего записей: {len(self.dataset)}\n"
                f"Обучающая выборка: {result['train_count']}\n"
                f"Тестовая выборка: {result['test_count']}\n\n"
                f"Полный датасет:\n{result['full']}\n\n"
                f"Обучающая выборка:\n{result['train']}\n\n"
                f"Тестовая выборка:\n{result['test']}",
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Ошибка экспорта",
                str(error),
            )

        finally:
            self.export_button.setEnabled(
                len(self.dataset) >= 2
            )

    # ==========================================
    # ЗАПУСК ОБУЧЕНИЯ В ОТДЕЛЬНОМ ПОТОКЕ
    # ==========================================

    def train_model(self):
        if self.training_thread is not None:
            return

        self.train_button.setEnabled(False)
        self.build_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.save_model_button.setEnabled(False)

        self.training_progress.show()

        self.metrics_table.setRowCount(0)

        self.metrics_label.setText(
            "Подготовка данных и обучение модели..."
        )

        self.training_status.setText(
            "Выполняется подготовка датасета. "
            "Не закрывайте приложение."
        )

        self.result_label.setText(
            "Обучение выполняется в фоновом потоке."
        )

        self.training_thread = DatasetTrainingWorker(self)

        self.training_thread.completed.connect(
            self.on_training_completed
        )

        self.training_thread.failed.connect(
            self.on_training_failed
        )

        self.training_thread.finished.connect(
            self.on_training_thread_finished
        )

        self.training_thread.start()

    # ==========================================
    # УСПЕШНОЕ ЗАВЕРШЕНИЕ ОБУЧЕНИЯ
    # ==========================================

    def on_training_completed(
        self,
        builder,
        dataset,
        trainer,
        metrics,
    ):
        self.builder = builder
        self.dataset = dataset
        self.trainer = trainer

        self.update_statistics()
        self.update_table()
        self.show_metrics(metrics)

        self.save_model_button.setEnabled(True)

        self.training_status.setText(
            "Обучение успешно завершено.\n"
            f"Всего записей: {len(dataset)}"
        )

        self.result_label.setText(
            "Модель обучена и готова к сохранению."
        )

    # ==========================================
    # ОШИБКА ОБУЧЕНИЯ
    # ==========================================

    def on_training_failed(self, error_message):
        self.save_model_button.setEnabled(False)

        self.training_status.setText(
            "Не удалось обучить модель."
        )

        self.result_label.setText(
            "Во время обучения произошла ошибка."
        )

        QMessageBox.critical(
            self,
            "Ошибка обучения",
            error_message,
        )

    # ==========================================
    # ЗАВЕРШЕНИЕ ПОТОКА
    # ==========================================

    def on_training_thread_finished(self):
        self.training_thread = None

        self.training_progress.hide()

        self.train_button.setEnabled(True)
        self.build_button.setEnabled(True)

        self.export_button.setEnabled(
            len(self.dataset) >= 2
        )

        if self.trainer.model is None:
            self.save_model_button.setEnabled(False)

    # ==========================================
    # ОТОБРАЖЕНИЕ МЕТРИК
    # ==========================================

    def show_metrics(self, metrics):
        self.metrics_label.setText(
            "Общие показатели качества:\n"
            f"Accuracy: {metrics['accuracy']:.3f}\n"
            f"Precision (micro): {metrics['precision_micro']:.3f}\n"
            f"Recall (micro): {metrics['recall_micro']:.3f}\n"
            f"F1-score (micro): {metrics['f1_micro']:.3f}\n"
            f"Precision (macro): {metrics['precision_macro']:.3f}\n"
            f"Recall (macro): {metrics['recall_macro']:.3f}\n"
            f"F1-score (macro): {metrics['f1_macro']:.3f}"
        )

        faults = metrics["fault_metrics"]

        self.metrics_table.setRowCount(
            len(faults)
        )

        for row_index, fault_data in enumerate(
            faults.values()
        ):
            values = [
                fault_data["label"],
                f"{fault_data['precision']:.3f}",
                f"{fault_data['recall']:.3f}",
                f"{fault_data['f1']:.3f}",
            ]

            for column_index, value in enumerate(values):
                self.metrics_table.setItem(
                    row_index,
                    column_index,
                    QTableWidgetItem(str(value)),
                )

        self.metrics_table.resizeColumnsToContents()

    # ==========================================
    # СОХРАНЕНИЕ МОДЕЛИ
    # ==========================================

    def save_model(self):
        if self.trainer.model is None:
            QMessageBox.information(
                self,
                "Сохранение модели",
                "Сначала обучите модель.",
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить обученную модель",
            "cnc_fault_detection.joblib",
            "Модель машинного обучения (*.joblib)",
        )

        if not file_path:
            return

        if not file_path.lower().endswith(".joblib"):
            file_path += ".joblib"

        try:
            destination = self.trainer.save_model(
                file_path
            )

            QMessageBox.information(
                self,
                "Модель сохранена",
                f"Обученная модель сохранена:\n{destination}",
            )

        except Exception as error:
            QMessageBox.critical(
                self,
                "Ошибка сохранения",
                str(error),
            )
