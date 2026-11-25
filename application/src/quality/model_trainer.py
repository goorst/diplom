
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from sklearn.ensemble import (
    ExtraTreesClassifier,
    GradientBoostingClassifier,
    RandomForestClassifier,
)
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

from application.src.quality.dataset_builder import DatasetBuilder
from application.src.quality.ensemble_model import EnsembleModel


class ModelTrainer:
    """
    Обучение и сравнительная оценка алгоритмов классификации
    качества изделий.

    Сравниваемые модели:
    - Random Forest;
    - Extra Trees;
    - Gradient Boosting;
    - Voting Classifier.

    Обучение и тестирование выполняются на заранее разделённых
    выборках. Разделение по experiment_id обеспечивает DatasetBuilder.

    Дополнительно рассчитываются метрики отдельно по каждому изделию.
    """

    def __init__(
        self,
        dataset_builder=None,
        output_dir=None,
        model_dir=None,
        random_state=42
    ):
        self.dataset_builder = (
            dataset_builder
            if dataset_builder is not None
            else DatasetBuilder(random_state=random_state)
        )

        project_root = Path(__file__).resolve().parents[3]

        self.output_dir = (
            Path(output_dir)
            if output_dir is not None
            else project_root / "data" / "quality"
        )

        self.model_dir = (
            Path(model_dir)
            if model_dir is not None
            else project_root / "data" / "model"
        )

        self.random_state = int(random_state)

        self.ensemble_model = None
        self.individual_models = {}
        self.results = {}
        self.comparison = None

    # =========================================================
    # ПРОВЕРКА ДАТАСЕТА
    # =========================================================

    @staticmethod
    def _validate_dataframe(dataframe, name):
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError(
                f"{name} должен быть pandas DataFrame."
            )

        if dataframe.empty:
            raise ValueError(
                f"{name} не должен быть пустым."
            )

        required_columns = {
            "product_id",
            "target",
            "experiment_id"
        }

        missing = required_columns - set(dataframe.columns)

        if missing:
            raise ValueError(
                f"В {name} отсутствуют колонки: "
                f"{', '.join(sorted(missing))}"
            )

        if dataframe["target"].isna().any():
            raise ValueError(
                f"{name} содержит пустые целевые метки."
            )

        target = set(
            dataframe["target"].astype(int).unique()
        )

        if not target.issubset({0, 1}):
            raise ValueError(
                f"{name}: target должен содержать только 0 и 1."
            )

        if len(target) < 2:
            raise ValueError(
                f"{name} должен содержать оба класса: "
                "GOOD и DEFECT."
            )

    def _load_datasets(self, train_dataframe=None, test_dataframe=None):
        """
        Загружает обучающую и тестовую выборки.

        Если таблицы не переданы, использует DatasetBuilder.
        """

        if train_dataframe is None or test_dataframe is None:
            dataset_info = self.dataset_builder.build_dataset()

            train_dataframe = dataset_info["train_dataframe"]
            test_dataframe = dataset_info["test_dataframe"]

        train_dataframe = train_dataframe.copy()
        test_dataframe = test_dataframe.copy()

        self._validate_dataframe(
            train_dataframe,
            "Обучающая выборка"
        )

        self._validate_dataframe(
            test_dataframe,
            "Тестовая выборка"
        )

        train_experiments = set(
            train_dataframe["experiment_id"].astype(str)
        )

        test_experiments = set(
            test_dataframe["experiment_id"].astype(str)
        )

        intersection = train_experiments & test_experiments

        if intersection:
            raise ValueError(
                "Обнаружена утечка экспериментов между "
                "обучающей и тестовой выборками."
            )

        return train_dataframe, test_dataframe

    # =========================================================
    # ПОДГОТОВКА ПРИЗНАКОВ
    # =========================================================

    def _prepare_features(self, train_dataframe, test_dataframe):
        """
        Подготавливает признаки с использованием правил EnsembleModel.

        Исключаются:
        - experiment_id;
        - run_id;
        - item_id;
        - target;
        - simulated_defect;
        - injected_defects.
        """

        feature_manager = EnsembleModel(
            random_state=self.random_state
        )

        x_train = feature_manager._select_features(
            train_dataframe,
            training=True
        )

        x_test = feature_manager._select_features(
            test_dataframe
        )

        y_train = train_dataframe["target"].astype(int).reset_index(
            drop=True
        )

        y_test = test_dataframe["target"].astype(int).reset_index(
            drop=True
        )

        if y_train.value_counts().min() < 2:
            raise ValueError(
                "В обучающей выборке должно быть минимум "
                "два примера каждого класса."
            )

        if x_train.shape[1] == 0:
            raise ValueError(
                "Не удалось определить признаки для обучения."
            )

        return (
            feature_manager,
            x_train,
            x_test,
            y_train,
            y_test
        )

    # =========================================================
    # СОЗДАНИЕ ОТДЕЛЬНЫХ МОДЕЛЕЙ
    # =========================================================

    def _build_individual_models(self, feature_manager):
        """Создаёт отдельные модели с одинаковой обработкой признаков."""

        random_forest = Pipeline(
            steps=[
                (
                    "preprocessor",
                    feature_manager._build_preprocessor()
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
                    feature_manager._build_preprocessor()
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
                    feature_manager._build_preprocessor()
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

        return {
            "Random Forest": random_forest,
            "Extra Trees": extra_trees,
            "Gradient Boosting": gradient_boosting
        }

    # =========================================================
    # ОБЩАЯ ОЦЕНКА МОДЕЛИ
    # =========================================================

    @staticmethod
    def _evaluate_model(model, x_test, y_test):
        """Рассчитывает общие метрики для одной модели."""

        predictions = model.predict(x_test)
        probabilities = model.predict_proba(x_test)

        classes = {
            int(class_value): index
            for index, class_value in enumerate(model.classes_)
        }

        defect_index = classes.get(1)

        roc_auc = None

        if defect_index is not None and y_test.nunique() == 2:
            roc_auc = float(
                roc_auc_score(
                    y_test,
                    probabilities[:, defect_index]
                )
            )

        matrix = confusion_matrix(
            y_test,
            predictions,
            labels=[0, 1]
        )

        report = classification_report(
            y_test,
            predictions,
            labels=[0, 1],
            target_names=["GOOD", "DEFECT"],
            output_dict=True,
            zero_division=0
        )

        return {
            "accuracy": float(
                accuracy_score(y_test, predictions)
            ),
            "precision": float(
                precision_score(
                    y_test,
                    predictions,
                    pos_label=1,
                    zero_division=0
                )
            ),
            "recall": float(
                recall_score(
                    y_test,
                    predictions,
                    pos_label=1,
                    zero_division=0
                )
            ),
            "f1": float(
                f1_score(
                    y_test,
                    predictions,
                    pos_label=1,
                    zero_division=0
                )
            ),
            "roc_auc": roc_auc,
            "confusion_matrix": matrix.tolist(),
            "classification_report": report,
            "predictions": predictions.astype(int).tolist(),
            "probabilities": probabilities.tolist()
        }

    # =========================================================
    # ОЦЕНКА ПО КАЖДОМУ ИЗДЕЛИЮ
    # =========================================================

    @staticmethod
    def _evaluate_by_product(
        dataframe,
        predictions,
        probabilities
    ):
        """
        Рассчитывает метрики отдельно для каждого изделия.

        Важно:
        оценка проводится на тестовой выборке,
        а не на обучающих данных.

        Класс DEFECT имеет метку 1.
        """

        evaluation_data = pd.DataFrame({
            "product_id": dataframe["product_id"].reset_index(drop=True),
            "target": dataframe["target"].astype(int).reset_index(drop=True),
            "prediction": np.asarray(predictions, dtype=int),
            "defect_probability": np.asarray(probabilities)[:, 1]
        })

        results = {}

        for product_id, group in evaluation_data.groupby(
            "product_id",
            sort=True
        ):
            y_true = group["target"].to_numpy()
            y_pred = group["prediction"].to_numpy()
            y_probability = group["defect_probability"].to_numpy()

            matrix = confusion_matrix(
                y_true,
                y_pred,
                labels=[0, 1]
            )

            roc_auc = None

            # ROC-AUC имеет смысл только при наличии обоих классов.
            if len(np.unique(y_true)) == 2:
                roc_auc = float(
                    roc_auc_score(
                        y_true,
                        y_probability
                    )
                )

            report = classification_report(
                y_true,
                y_pred,
                labels=[0, 1],
                target_names=["GOOD", "DEFECT"],
                output_dict=True,
                zero_division=0
            )

            results[str(product_id)] = {
                "product_id": (
                    product_id.item()
                    if isinstance(product_id, np.generic)
                    else product_id
                ),
                "records": int(len(group)),
                "good_count": int((y_true == 0).sum()),
                "defect_count": int((y_true == 1).sum()),

                "accuracy": float(
                    accuracy_score(y_true, y_pred)
                ),
                "precision": float(
                    precision_score(
                        y_true,
                        y_pred,
                        pos_label=1,
                        zero_division=0
                    )
                ),
                "recall": float(
                    recall_score(
                        y_true,
                        y_pred,
                        pos_label=1,
                        zero_division=0
                    )
                ),
                "f1": float(
                    f1_score(
                        y_true,
                        y_pred,
                        pos_label=1,
                        zero_division=0
                    )
                ),
                "roc_auc": roc_auc,

                "confusion_matrix": matrix.tolist(),
                "classification_report": report
            }

        return results

    # =========================================================
    # СОХРАНЕНИЕ РЕЗУЛЬТАТОВ
    # =========================================================

    def _save_results(self):
        """Сохраняет отчёты и обученные модели."""

        self.output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        self.model_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        report_path = (
            self.output_dir / "model_comparison.json"
        )

        comparison_path = (
            self.output_dir / "model_comparison.csv"
        )

        individual_models_path = (
            self.model_dir / "individual_models.joblib"
        )

        report = {
            "random_state": self.random_state,
            "models": self.results,
            "best_model": (
                self.comparison.iloc[0]["model"]
                if self.comparison is not None
                and not self.comparison.empty
                else None
            )
        }

        with open(
            report_path,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                report,
                file,
                ensure_ascii=False,
                indent=4,
                allow_nan=False
            )

        self.comparison.to_csv(
            comparison_path,
            index=False,
            encoding="utf-8-sig"
        )

        joblib.dump(
            self.individual_models,
            individual_models_path
        )

        ensemble_path = self.ensemble_model.save()

        return {
            "report": str(report_path),
            "comparison": str(comparison_path),
            "individual_models": str(individual_models_path),
            "ensemble_model": ensemble_path
        }

    # =========================================================
    # ОСНОВНОЙ ЦИКЛ ОБУЧЕНИЯ
    # =========================================================

    def train(self, train_dataframe=None, test_dataframe=None):
        """
        Полный цикл обучения и сравнения моделей.

        Параметры:
            train_dataframe — обучающая выборка.
            test_dataframe — тестовая выборка.

        Если выборки не переданы, они формируются через DatasetBuilder.
        """

        train_dataframe, test_dataframe = self._load_datasets(
            train_dataframe,
            test_dataframe
        )

        (
            feature_manager,
            x_train,
            x_test,
            y_train,
            y_test
        ) = self._prepare_features(
            train_dataframe,
            test_dataframe
        )

        self.results = {}
        self.individual_models = {}

        # -----------------------------------------------------
        # 1. Обучение отдельных алгоритмов
        # -----------------------------------------------------

        individual_models = self._build_individual_models(
            feature_manager
        )

        for model_name, model in individual_models.items():
            print(
                f"\nОбучение модели: {model_name}"
            )

            model.fit(
                x_train,
                y_train
            )

            self.individual_models[model_name] = model

            self.results[model_name] = self._evaluate_model(
                model,
                x_test,
                y_test
            )

        # -----------------------------------------------------
        # 2. Обучение ансамбля
        # -----------------------------------------------------

        print("\nОбучение ансамблевой модели...")

        self.ensemble_model = EnsembleModel(
            random_state=self.random_state
        )

        self.ensemble_model.fit(
            train_dataframe
        )

        self.results["Voting Classifier"] = (
            self.ensemble_model.evaluate(test_dataframe)
        )

        # -----------------------------------------------------
        # 3. Оценка моделей отдельно по изделиям
        # -----------------------------------------------------

        for model_name, model in self.individual_models.items():
            predictions = self.results[model_name]["predictions"]
            probabilities = self.results[model_name]["probabilities"]

            self.results[model_name]["per_product"] = (
                self._evaluate_by_product(
                    test_dataframe,
                    predictions,
                    probabilities
                )
            )

        ensemble_result = self.results["Voting Classifier"]

        self.results["Voting Classifier"]["per_product"] = (
            self._evaluate_by_product(
                test_dataframe,
                ensemble_result["predictions"],
                ensemble_result["probabilities"]
            )
        )

        # -----------------------------------------------------
        # 4. Формирование сравнительной таблицы
        # -----------------------------------------------------

        comparison_rows = []

        for model_name, metrics in self.results.items():
            comparison_rows.append(
                {
                    "model": model_name,
                    "accuracy": metrics["accuracy"],
                    "precision": metrics["precision"],
                    "recall": metrics["recall"],
                    "f1": metrics["f1"],
                    "roc_auc": metrics["roc_auc"]
                }
            )

        self.comparison = pd.DataFrame(
            comparison_rows
        )

        self.comparison = self.comparison.sort_values(
            by=["f1", "roc_auc", "accuracy"],
            ascending=False,
            na_position="last"
        ).reset_index(drop=True)

        # -----------------------------------------------------
        # 5. Вывод результатов по изделиям
        # -----------------------------------------------------

        print("\n======= ОЦЕНКА ПО ИЗДЕЛИЯМ =======")

        for model_name, metrics in self.results.items():
            print(f"\nМодель: {model_name}")

            for product_id, product_metrics in (
                metrics["per_product"].items()
            ):
                print(
                    f"\nИзделие {product_id}:"
                )

                print(
                    f"  Записей: {product_metrics['records']}"
                )

                print(
                    f"  GOOD: {product_metrics['good_count']}"
                )

                print(
                    f"  DEFECT: {product_metrics['defect_count']}"
                )

                print(
                    f"  Accuracy: {product_metrics['accuracy']:.4f}"
                )

                print(
                    f"  Precision: {product_metrics['precision']:.4f}"
                )

                print(
                    f"  Recall: {product_metrics['recall']:.4f}"
                )

                print(
                    f"  F1: {product_metrics['f1']:.4f}"
                )

                auc = product_metrics["roc_auc"]

                print(
                    f"  ROC-AUC: "
                    f"{auc:.4f}" if auc is not None
                    else "  ROC-AUC: невозможно рассчитать"
                )

        # -----------------------------------------------------
        # 6. Сохранение результатов
        # -----------------------------------------------------

        paths = self._save_results()

        return {
            "comparison": self.comparison,
            "results": self.results,
            "best_model": self.comparison.iloc[0]["model"],

            "train_records": len(train_dataframe),
            "test_records": len(test_dataframe),

            "train_experiments": train_dataframe[
                "experiment_id"
            ].nunique(),

            "test_experiments": test_dataframe[
                "experiment_id"
            ].nunique(),

            "train_products": train_dataframe[
                "product_id"
            ].nunique(),

            "test_products": test_dataframe[
                "product_id"
            ].nunique(),

            "paths": paths
        }
