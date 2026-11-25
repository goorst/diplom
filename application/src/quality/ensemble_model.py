
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import (
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    RandomForestClassifier,
    VotingClassifier,
)
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


class EnsembleModel:
    """
    Ансамблевая модель классификации качества изделий.

    Используемые алгоритмы:
    - Random Forest;
    - Extra Trees;
    - Gradient Boosting.

    Итоговый прогноз формируется методом мягкого голосования.
    """

    def __init__(
        self,
        random_state=42,
        voting_weights=(2, 2, 1)
    ):
        self.random_state = random_state
        self.voting_weights = voting_weights

        self.model = None
        self.feature_columns = None
        self.numeric_features = None
        self.categorical_features = None
        self.classes_ = None

        self._build_model()

    def _build_preprocessor(self):
        """Создаёт обработчик числовых и категориальных признаков."""

        numeric_pipeline = Pipeline(
            steps=[
                (
                    "imputer",
                    SimpleImputer(strategy="median")
                ),
                (
                    "scaler",
                    StandardScaler()
                )
            ]
        )

        categorical_pipeline = Pipeline(
            steps=[
                (
                    "imputer",
                    SimpleImputer(strategy="most_frequent")
                ),
                (
                    "encoder",
                    OneHotEncoder(handle_unknown="ignore")
                )
            ]
        )

        transformers = []

        if self.numeric_features:
            transformers.append(
                (
                    "numeric",
                    numeric_pipeline,
                    self.numeric_features
                )
            )

        if self.categorical_features:
            transformers.append(
                (
                    "categorical",
                    categorical_pipeline,
                    self.categorical_features
                )
            )

        return ColumnTransformer(
            transformers=transformers,
            remainder="drop"
        )


    def _build_model(self):
        """Создаёт три алгоритма и объединяет их в ансамбль."""

        random_forest = Pipeline(
            steps=[
                (
                    "preprocessor",
                    self._build_preprocessor()
                ),
                (
                    "classifier",
                    RandomForestClassifier(
                        n_estimators=200,
                        max_depth=None,
                        min_samples_split=2,
                        min_samples_leaf=1,
                        class_weight="balanced",
                        random_state=self.random_state,
                        n_jobs=-1
                    )
                )
            ]
        )

        extra_trees = Pipeline(
            steps=[
                (
                    "preprocessor",
                    self._build_preprocessor()
                ),
                (
                    "classifier",
                    ExtraTreesClassifier(
                        n_estimators=200,
                        max_depth=None,
                        min_samples_split=2,
                        min_samples_leaf=1,
                        class_weight="balanced",
                        random_state=self.random_state,
                        n_jobs=-1
                    )
                )
            ]
        )

        gradient_boosting = Pipeline(
            steps=[
                (
                    "preprocessor",
                    self._build_preprocessor()
                ),
                (
                    "classifier",
                    GradientBoostingClassifier(
                        n_estimators=100,
                        learning_rate=0.05,
                        max_depth=3,
                        min_samples_split=2,
                        min_samples_leaf=1,
                        subsample=0.9,
                        random_state=self.random_state
                    )
                )
            ]
        )

        self.model = VotingClassifier(
            estimators=[
                ("random_forest", random_forest),
                ("extra_trees", extra_trees),
                ("gradient_boosting", gradient_boosting)
            ],
            voting="soft",
            weights=list(self.voting_weights),
            n_jobs=1
        )

    @staticmethod
    def _validate_dataframe(dataframe):
        """Проверяет входную таблицу."""

        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError(
                "Ожидается pandas DataFrame."
            )

        if dataframe.empty:
            raise ValueError(
                "Передана пустая таблица."
            )

    def _select_features(self, dataframe, training=False):
        """
        Выбирает только допустимые признаки.

        Не используются:
        - experiment_id;
        - run_id;
        - item_id;
        - target;
        - simulated_defect;
        - injected_defects.
        """

        self._validate_dataframe(dataframe)

        if training:
            measurement_columns = [
                column
                for column in dataframe.columns
                if column.startswith("measurement__")
            ]

            if "product_id" not in dataframe.columns:
                raise ValueError(
                    "В датасете отсутствует product_id."
                )

            if not measurement_columns:
                raise ValueError(
                    "Не найдены признаки measurement__."
                )

            self.numeric_features = measurement_columns
            self.categorical_features = ["product_id"]

            self.feature_columns = (
                self.categorical_features
                + self.numeric_features
            )

        if not self.feature_columns:
            raise RuntimeError(
                "Сначала необходимо обучить модель."
            )

        features = dataframe.copy()

        for column in self.feature_columns:
            if column not in features.columns:
                features[column] = np.nan

        features = features[self.feature_columns].copy()

        for column in self.numeric_features:
            features[column] = pd.to_numeric(
                features[column],
                errors="coerce"
            )

        for column in self.categorical_features:
            features[column] = (
                features[column]
                .astype("string")
            )

        return features

    def fit(self, dataframe, target=None):
        """
        Обучает ансамблевую модель.

        dataframe:
            Таблица с product_id и измерениями.

        target:
            Целевая переменная 0/1.
            Если не передана, берётся из колонки target.
        """

        self._validate_dataframe(dataframe)

        if target is None:
            if "target" not in dataframe.columns:
                raise ValueError(
                    "Не найдена целевая колонка target."
                )

            target = dataframe["target"]

        target = pd.Series(target).reset_index(drop=True)

        features = self._select_features(
            dataframe,
            training=True
        )

        if len(features) != len(target):
            raise ValueError(
                "Количество признаков не совпадает "
                "с количеством целевых меток."
            )

        if target.isna().any():
            raise ValueError(
                "Целевая переменная содержит пропуски."
            )

        target = target.astype(int)

        if not set(target.unique()).issubset({0, 1}):
            raise ValueError(
                "Целевая переменная должна содержать "
                "только классы 0 и 1."
            )

        if target.nunique() < 2:
            raise ValueError(
                "Для обучения необходимы оба класса: "
                "GOOD (0) и DEFECT (1)."
            )

        if target.value_counts().min() < 2:
            raise ValueError(
                "Для каждого класса необходимо минимум "
                "два обучающих примера."
            )

        self._build_model()

        self.model.fit(
            features,
            target
        )

        self.classes_ = self.model.classes_

        return self

    def predict(self, dataframe):
        """Возвращает предсказанные классы качества."""

        features = self._select_features(dataframe)

        return self.model.predict(features)

    def predict_proba(self, dataframe):
        """Возвращает вероятности принадлежности к классам."""

        features = self._select_features(dataframe)

        return self.model.predict_proba(features)

    def predict_quality(self, dataframe):
        """
        Возвращает подробный прогноз качества.

        Для каждой записи:
        - предсказанный класс;
        - вероятность GOOD;
        - вероятность DEFECT.
        """

        features = self._select_features(dataframe)

        predictions = self.model.predict(features)
        probabilities = self.model.predict_proba(features)

        class_indices = {
            int(class_value): index
            for index, class_value in enumerate(
                self.model.classes_
            )
        }

        good_index = class_indices.get(0)
        defect_index = class_indices.get(1)

        results = []

        for index, prediction in enumerate(predictions):
            good_probability = (
                float(probabilities[index][good_index])
                if good_index is not None
                else 0.0
            )

            defect_probability = (
                float(probabilities[index][defect_index])
                if defect_index is not None
                else 0.0
            )

            results.append(
                {
                    "predicted_class": int(prediction),
                    "predicted_status": (
                        "GOOD"
                        if prediction == 0
                        else "DEFECT"
                    ),
                    "good_probability": good_probability,
                    "defect_probability": defect_probability
                }
            )

        return results

    def evaluate(self, dataframe, target=None):
        """
        Оценивает качество модели на тестовой выборке.
        """

        if target is None:
            if "target" not in dataframe.columns:
                raise ValueError(
                    "Не найдена целевая колонка target."
                )

            target = dataframe["target"]

        target = pd.Series(target).reset_index(drop=True)

        if target.isna().any():
            raise ValueError(
                "Тестовые метки содержат пропуски."
            )

        target = target.astype(int)

        predictions = self.predict(dataframe)
        probabilities = self.predict_proba(dataframe)

        class_indices = {
            int(class_value): index
            for index, class_value in enumerate(
                self.model.classes_
            )
        }

        defect_index = class_indices.get(1)

        roc_auc = None

        if (
            target.nunique() == 2
            and defect_index is not None
        ):
            roc_auc = float(
                roc_auc_score(
                    target,
                    probabilities[:, defect_index]
                )
            )

        matrix = confusion_matrix(
            target,
            predictions,
            labels=[0, 1]
        )

        report = classification_report(
            target,
            predictions,
            labels=[0, 1],
            target_names=["GOOD", "DEFECT"],
            output_dict=True,
            zero_division=0
        )

        return {
            "accuracy": float(
                accuracy_score(target, predictions)
            ),
            "precision": float(
                precision_score(
                    target,
                    predictions,
                    pos_label=1,
                    zero_division=0
                )
            ),
            "recall": float(
                recall_score(
                    target,
                    predictions,
                    pos_label=1,
                    zero_division=0
                )
            ),
            "f1": float(
                f1_score(
                    target,
                    predictions,
                    pos_label=1,
                    zero_division=0
                )
            ),
            "roc_auc": roc_auc,
            "confusion_matrix": matrix.tolist(),
            "classification_report": report,
            "predictions": predictions.tolist(),
            "probabilities": probabilities.tolist()
        }

    def save(self, path=None):
        """Сохраняет обученную модель."""

        if self.model is None or not hasattr(
            self.model,
            "classes_"
        ):
            raise RuntimeError(
                "Нельзя сохранить необученную модель."
            )

        if path is None:
            project_root = Path(__file__).resolve().parents[3]

            path = (
                project_root
                / "data"
                / "model"
                / "ensemble_model.joblib"
            )

        path = Path(path)
        path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        model_data = {
            "model": self.model,
            "feature_columns": self.feature_columns,
            "numeric_features": self.numeric_features,
            "categorical_features": self.categorical_features,
            "classes": self.classes_,
            "random_state": self.random_state,
            "voting_weights": self.voting_weights
        }

        joblib.dump(
            model_data,
            path
        )

        return str(path)

    def load(self, path=None):
        """Загружает ранее обученную модель."""

        if path is None:
            project_root = Path(__file__).resolve().parents[3]

            path = (
                project_root
                / "data"
                / "model"
                / "ensemble_model.joblib"
            )

        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(
                f"Файл модели не найден: {path}"
            )

        model_data = joblib.load(path)

        self.model = model_data["model"]
        self.feature_columns = model_data["feature_columns"]
        self.numeric_features = model_data["numeric_features"]
        self.categorical_features = model_data["categorical_features"]
        self.classes_ = model_data["classes"]
        self.random_state = model_data["random_state"]
        self.voting_weights = model_data["voting_weights"]

        return self
