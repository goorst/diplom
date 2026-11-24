
import math
from pathlib import Path

import joblib

from sklearn.ensemble import RandomForestClassifier
from sklearn.multioutput import MultiOutputClassifier

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)


class ModelTrainer:
    """Обучение, сохранение и применение ML-модели диагностики."""

    FAULTS = [
        "overheating",
        "high_vibration",
        "overload",
        "tool_wear",
    ]

    FAULT_LABELS = {
        "overheating": "Перегрев",
        "high_vibration": "Повышенная вибрация",
        "overload": "Перегрузка шпинделя",
        "tool_wear": "Износ инструмента",
    }

    NUMERIC_FEATURES = [
        "spindle_speed",
        "feed_rate",
        "cutting_depth",
        "temperature",
        "vibration",
        "spindle_load",
        "tool_wear",
    ]

    CATEGORICAL_FEATURES = [
        "part_type",
        "material",
        "operation",
        "tool_id",
    ]

    def __init__(self):
        self.model = None
        self.feature_names = []
        self.metrics = {}
        self.model_path = None

    # ==========================================
    # ПРОВЕРКА ЧИСЛОВЫХ ДАННЫХ
    # ==========================================

    @staticmethod
    def _number(value, feature_name):
        try:
            result = float(value)

        except (TypeError, ValueError):
            raise ValueError(
                f"Некорректное числовое значение признака "
                f"'{feature_name}': {value}"
            )

        if not math.isfinite(result):
            raise ValueError(
                f"Признак '{feature_name}' должен быть "
                "конечным числом."
            )

        return result

    # ==========================================
    # ПОДГОТОВКА ПРИЗНАКОВ
    # ==========================================

    def _make_feature_vector(self, measurement):
        """Формирует вектор признаков для одного измерения."""

        if not self.feature_names:
            raise RuntimeError(
                "Список признаков модели не загружен."
            )

        values = []

        for feature_name in self.feature_names:

            if feature_name in self.NUMERIC_FEATURES:
                value = self._number(
                    measurement.get(feature_name),
                    feature_name,
                )

            else:
                value = 0

                for category_feature in self.CATEGORICAL_FEATURES:
                    prefix = f"{category_feature}__"

                    if feature_name.startswith(prefix):
                        category_value = measurement.get(
                            category_feature
                        )

                        if category_value is None:
                            category_value = "Не указано"

                        category_value = str(
                            category_value
                        ).strip()

                        expected_category = feature_name[
                            len(prefix):
                        ]

                        value = int(
                            category_value == expected_category
                        )

                        break

            values.append(value)

        return [values]

    # ==========================================
    # ПОДГОТОВКА ОБУЧАЮЩИХ ДАННЫХ
    # ==========================================

    def _make_x(self, rows):
        result = []

        for row in rows:
            values = []

            for feature_name in self.feature_names:
                values.append(
                    self._number(
                        row.get(feature_name),
                        feature_name,
                    )
                )

            result.append(values)

        return result

    def _make_y(self, rows):
        target_names = [
            f"target_{fault}"
            for fault in self.FAULTS
        ]

        result = []

        for row in rows:
            values = []

            for target_name in target_names:
                value = int(row.get(target_name, 0))

                if value not in (0, 1):
                    raise ValueError(
                        f"Целевая метка {target_name} "
                        "должна иметь значение 0 или 1."
                    )

                values.append(value)

            result.append(values)

        return result

    # ==========================================
    # ОБУЧЕНИЕ
    # ==========================================

    def train(
        self,
        train_rows,
        test_rows,
        feature_names,
    ):
        if not train_rows:
            raise ValueError(
                "Обучающая выборка пуста."
            )

        if not test_rows:
            raise ValueError(
                "Тестовая выборка пуста."
            )

        if not feature_names:
            raise ValueError(
                "Список признаков пуст."
            )

        self.model = None
        self.metrics = {}

        self.feature_names = list(feature_names)

        # Подготовка матриц признаков и целевых меток.
        x_train = self._make_x(train_rows)
        y_train = self._make_y(train_rows)

        x_test = self._make_x(test_rows)
        y_test = self._make_y(test_rows)

        # Проверка наличия обоих классов
        # для каждой неисправности.
        for index, fault in enumerate(self.FAULTS):
            train_classes = {
                row[index] for row in y_train
            }

            test_classes = {
                row[index] for row in y_test
            }

            if len(train_classes) < 2:
                raise ValueError(
                    f"В обучающей выборке для неисправности "
                    f"'{self.FAULT_LABELS[fault]}' отсутствует "
                    "один из классов (0 или 1)."
                )

            if len(test_classes) < 2:
                raise ValueError(
                    f"В тестовой выборке для неисправности "
                    f"'{self.FAULT_LABELS[fault]}' отсутствует "
                    "один из классов (0 или 1)."
                )

        # Random Forest.
        base_model = RandomForestClassifier(
            n_estimators=200,
            max_features="sqrt",
            min_samples_leaf=2,
            class_weight="balanced_subsample",
            random_state=42,
            n_jobs=-1,
        )

        self.model = MultiOutputClassifier(
            base_model,
            n_jobs=1,
        )

        # Основная вычислительно затратная операция.
        self.model.fit(
            x_train,
            y_train,
        )

        # Прогноз.
        predictions = self.model.predict(
            x_test
        )

        # ======================================
        # ОБЩИЕ МЕТРИКИ
        # ======================================

        self.metrics = {
            "accuracy": accuracy_score(
                y_test,
                predictions,
            ),

            "precision_micro": precision_score(
                y_test,
                predictions,
                average="micro",
                zero_division=0,
            ),

            "recall_micro": recall_score(
                y_test,
                predictions,
                average="micro",
                zero_division=0,
            ),

            "f1_micro": f1_score(
                y_test,
                predictions,
                average="micro",
                zero_division=0,
            ),

            "precision_macro": precision_score(
                y_test,
                predictions,
                average="macro",
                zero_division=0,
            ),

            "recall_macro": recall_score(
                y_test,
                predictions,
                average="macro",
                zero_division=0,
            ),

            "f1_macro": f1_score(
                y_test,
                predictions,
                average="macro",
                zero_division=0,
            ),

            "fault_metrics": {},
        }

        # ======================================
        # МЕТРИКИ ПО КАЖДОЙ НЕИСПРАВНОСТИ
        # ======================================

        for index, fault in enumerate(self.FAULTS):
            true_values = [
                row[index]
                for row in y_test
            ]

            predicted_values = [
                row[index]
                for row in predictions
            ]

            self.metrics["fault_metrics"][fault] = {
                "label": self.FAULT_LABELS[fault],

                "precision": precision_score(
                    true_values,
                    predicted_values,
                    zero_division=0,
                ),

                "recall": recall_score(
                    true_values,
                    predicted_values,
                    zero_division=0,
                ),

                "f1": f1_score(
                    true_values,
                    predicted_values,
                    zero_division=0,
                ),

                "confusion_matrix": confusion_matrix(
                    true_values,
                    predicted_values,
                    labels=[0, 1],
                ).tolist(),

                "test_positive": sum(true_values),
                "test_negative": len(true_values) - sum(true_values),
            }

        return self.metrics

    # ==========================================
    # СОХРАНЕНИЕ МОДЕЛИ
    # ==========================================

    def save_model(self, file_path):
        if self.model is None:
            raise RuntimeError(
                "Сначала необходимо обучить модель."
            )

        destination = Path(file_path)

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        bundle = {
            "model": self.model,
            "feature_names": self.feature_names,
            "faults": self.FAULTS,
            "fault_labels": self.FAULT_LABELS,
            "metrics": self.metrics,
            "version": 2,
        }

        joblib.dump(
            bundle,
            destination,
        )

        self.model_path = destination

        return destination

    # ==========================================
    # ЗАГРУЗКА МОДЕЛИ
    # ==========================================

    def load_model(self, file_path):
        source = Path(file_path)

        if not source.exists():
            raise FileNotFoundError(
                f"Файл модели не найден:\n{source}"
            )

        bundle = joblib.load(source)

        if not isinstance(bundle, dict):
            raise ValueError(
                "Файл не содержит корректный пакет ML-модели."
            )

        required_keys = {
            "model",
            "feature_names",
            "faults",
        }

        missing_keys = required_keys.difference(
            bundle.keys()
        )

        if missing_keys:
            raise ValueError(
                "В файле модели отсутствуют поля: "
                + ", ".join(sorted(missing_keys))
            )

        if list(bundle["faults"]) != self.FAULTS:
            raise ValueError(
                "Модель обучена для другого набора неисправностей."
            )

        feature_names = bundle["feature_names"]

        if not isinstance(feature_names, (list, tuple)):
            raise ValueError(
                "Некорректный список признаков модели."
            )

        if not feature_names:
            raise ValueError(
                "В модели отсутствуют признаки."
            )

        model = bundle["model"]

        if not hasattr(model, "estimators_"):
            raise ValueError(
                "Загруженный объект не является "
                "обученной MultiOutputClassifier."
            )

        if len(model.estimators_) != len(self.FAULTS):
            raise ValueError(
                "Количество выходов модели не соответствует "
                "количеству диагностируемых неисправностей."
            )

        self.model = model
        self.feature_names = list(feature_names)
        self.metrics = bundle.get("metrics", {})
        self.model_path = source

        return {
            "path": str(source),
            "feature_count": len(self.feature_names),
            "metrics": self.metrics,
        }

    # ==========================================
    # ПРОГНОЗ ВЕРОЯТНОСТЕЙ
    # ==========================================

    def predict_proba(self, measurement):
        """Возвращает вероятность каждой неисправности."""

        if self.model is None:
            raise RuntimeError(
                "ML-модель не загружена."
            )

        features = self._make_feature_vector(
            measurement
        )

        probabilities = self.model.predict_proba(
            features
        )

        result = {}

        for index, fault in enumerate(self.FAULTS):
            estimator_classes = (
                self.model.estimators_[index].classes_
            )

            class_probabilities = probabilities[index][0]

            probability_of_fault = 0.0

            for class_index, class_value in enumerate(
                estimator_classes
            ):
                if int(class_value) == 1:
                    probability_of_fault = float(
                        class_probabilities[class_index]
                    )
                    break

            result[fault] = max(
                0.0,
                min(1.0, probability_of_fault),
            )

        return result

    # ==========================================
    # БИНАРНЫЙ ПРОГНОЗ
    # ==========================================

    def predict(self, measurement, threshold=0.5):
        probabilities = self.predict_proba(
            measurement
        )

        return {
            fault: probability >= threshold
            for fault, probability in probabilities.items()
        }

    # ==========================================
    # ИНТЕРПРЕТАЦИЯ ВЕРОЯТНОСТИ
    # ==========================================

    @staticmethod
    def get_probability_level(probability):
        percentage = probability * 100

        if percentage < 30:
            return "Низкая"

        if percentage < 60:
            return "Средняя"

        return "Высокая"
