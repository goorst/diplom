
import json
import math
import random
from pathlib import Path

import pandas as pd

from application.src.core.measurement_logger import MeasurementLogger


class DatasetBuilder:
    """
    Формирование датасета для обучения модели контроля качества.

    Особенности:
    - поддержка нескольких типов изделий;
    - автоматическое определение измеряемых характеристик;
    - исключение UNKNOWN;
    - групповое разделение по experiment_id;
    - стратификация экспериментов по изделиям;
    - балансировка классов GOOD/DEFECT;
    - исключение искусственных меток из признаков.
    """

    def __init__(
        self,
        measurement_logger=None,
        output_dir=None,
        test_size=0.2,
        random_state=42,
        split_candidates=500
    ):
        self.measurement_logger = (
            measurement_logger
            if measurement_logger is not None
            else MeasurementLogger()
        )

        project_root = Path(__file__).resolve().parents[3]

        self.output_dir = (
            Path(output_dir)
            if output_dir is not None
            else project_root / "data" / "quality"
        )

        self.test_size = float(test_size)
        self.random_state = int(random_state)
        self.split_candidates = int(split_candidates)

        if not 0 < self.test_size < 1:
            raise ValueError(
                "test_size должен находиться между 0 и 1."
            )

        if self.split_candidates < 1:
            raise ValueError(
                "split_candidates должен быть больше 0."
            )

        self.dataset = None
        self.train_dataset = None
        self.test_dataset = None

    @staticmethod
    def _parse_json(value):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return {}

        if isinstance(value, dict):
            return value

        return {}

    @staticmethod
    def _get_numeric_measurements(measurements):
        result = {}

        if not isinstance(measurements, dict):
            return result

        for name, value in measurements.items():
            try:
                number = float(value)

                if math.isfinite(number):
                    result[f"measurement__{name}"] = number

            except (TypeError, ValueError):
                continue

        return result

    def load_records(self):
        records = self.measurement_logger.get_all_records(
            limit=1000000
        )

        return records or []

    def prepare_dataset(self, records):
        rows = []

        for record in records:
            if not isinstance(record, dict):
                continue

            nested_result = self._parse_json(
                record.get("result")
            )

            measurements = record.get("measurements")

            if not isinstance(measurements, dict):
                measurements = nested_result.get(
                    "measurements",
                    {}
                )

            measurements = self._parse_json(measurements)

            status = (
                record.get("status")
                or nested_result.get("status")
                or "UNKNOWN"
            )

            status = str(status).upper()

            if status not in ("GOOD", "DEFECT"):
                continue

            experiment_id = (
                record.get("experiment_id")
                or nested_result.get("experiment_id")
            )

            if not experiment_id:
                continue

            product_id = (
                record.get("product_id")
                or nested_result.get("product_id")
            )

            if product_id is None:
                continue

            product_name = (
                nested_result.get("product_name")
                or record.get("product_name")
                or str(product_id)
            )

            row = {
                "experiment_id": str(experiment_id),
                "run_id": (
                    record.get("run_id")
                    or nested_result.get("run_id")
                    or ""
                ),
                "item_id": (
                    record.get("item_id")
                    or nested_result.get("item_id")
                    or ""
                ),
                "product_id": str(product_id),
                "product_name": str(product_name),
            }

            row.update(
                self._get_numeric_measurements(measurements)
            )

            row["target"] = (
                0 if status == "GOOD" else 1
            )

            rows.append(row)

        if not rows:
            raise ValueError(
                "Не удалось сформировать датасет. "
                "Проверьте наличие записей GOOD/DEFECT, "
                "измерений и experiment_id."
            )

        dataframe = pd.DataFrame(rows)

        measurement_columns = [
            column
            for column in dataframe.columns
            if column.startswith("measurement__")
        ]

        if not measurement_columns:
            raise ValueError(
                "В записях не обнаружены числовые измерения."
            )

        dataframe = dataframe.dropna(
            subset=measurement_columns,
            how="all"
        ).copy()

        if dataframe.empty:
            raise ValueError(
                "После удаления пустых измерений датасет пуст."
            )

        return dataframe

    @staticmethod
    def _get_product_statistics(dataframe):
        """
        Статистика по количеству экспериментов и классов
        для каждого изделия.
        """
        result = {}

        for product_id, group in dataframe.groupby("product_id"):
            result[str(product_id)] = {
                "experiments": int(
                    group["experiment_id"].nunique()
                ),
                "records": int(len(group)),
                "good": int(
                    (group["target"] == 0).sum()
                ),
                "defect": int(
                    (group["target"] == 1).sum()
                )
            }

        return result

    @staticmethod
    def _get_test_experiment_count(total_experiments, test_size):
        """
        Определяет количество экспериментов изделия,
        направляемых в тестовую выборку.

        Для изделий с достаточным количеством групп
        старается выделить минимум три тестовых эксперимента.
        При этом минимум один эксперимент остаётся в train.
        """
        if total_experiments < 2:
            return 0

        desired_count = round(
            total_experiments * test_size
        )

        minimum_count = min(
            3,
            total_experiments - 1
        )

        test_count = max(
            desired_count,
            minimum_count
        )

        return min(
            test_count,
            total_experiments - 1
        )

    def _evaluate_split(self, dataframe, train, test):
        """
        Оценивает качество конкретного разделения.

        Меньшее значение означает более удачное разделение.
        """
        score = 0.0

        if train.empty or test.empty:
            return float("inf")

        total_records = len(dataframe)

        actual_test_ratio = (
            len(test) / total_records
        )

        score += abs(
            actual_test_ratio - self.test_size
        ) * 5

        all_products = sorted(
            dataframe["product_id"].unique()
        )

        for product_id in all_products:
            original = dataframe[
                dataframe["product_id"] == product_id
            ]

            train_product = train[
                train["product_id"] == product_id
            ]

            test_product = test[
                test["product_id"] == product_id
            ]

            if train_product.empty:
                score += 100

            if (
                original["experiment_id"].nunique() >= 2
                and test_product.empty
            ):
                score += 100

            # Сравнение распределения классов по изделию.
            original_distribution = (
                original["target"].value_counts(normalize=True)
            )

            for subset in (train_product, test_product):
                if subset.empty:
                    continue

                subset_distribution = (
                    subset["target"].value_counts(normalize=True)
                )

                for class_value in (0, 1):
                    original_ratio = float(
                        original_distribution.get(
                            class_value,
                            0
                        )
                    )

                    subset_ratio = float(
                        subset_distribution.get(
                            class_value,
                            0
                        )
                    )

                    score += abs(
                        original_ratio - subset_ratio
                    )

                    # Штраф за отсутствие класса,
                    # если он присутствует в исходном изделии.
                    if (
                        original_ratio > 0
                        and subset_ratio == 0
                    ):
                        score += 2

        return score

    def split_dataset(self, dataframe):
        """
        Стратифицированное групповое разделение.

        Эксперименты распределяются отдельно для каждого изделия.
        Один experiment_id целиком относится либо к train,
        либо к test.
        """
        if dataframe.empty:
            raise ValueError(
                "Нельзя разделить пустой датасет."
            )

        # Проверяем, что один эксперимент не содержит
        # записи разных изделий.
        products_per_experiment = (
            dataframe.groupby("experiment_id")["product_id"]
            .nunique()
        )

        mixed_experiments = (
            products_per_experiment[
                products_per_experiment > 1
            ]
        )

        if not mixed_experiments.empty:
            raise ValueError(
                "Обнаружены experiment_id, содержащие записи "
                "нескольких изделий. Нельзя независимо "
                "стратифицировать такие эксперименты по изделиям. "
                "Проблемные ID: "
                + ", ".join(
                    mixed_experiments.index.astype(str).tolist()[:10]
                )
            )

        product_statistics = self._get_product_statistics(
            dataframe
        )

        print("\n======= ЭКСПЕРИМЕНТЫ ПО ИЗДЕЛИЯМ =======")

        for product_id, stats in product_statistics.items():
            print(
                f"Изделие {product_id}: "
                f"экспериментов {stats['experiments']}, "
                f"записей {stats['records']}, "
                f"GOOD {stats['good']}, "
                f"DEFECT {stats['defect']}"
            )

        rng = random.Random(self.random_state)

        product_groups = {}

        for product_id, group in dataframe.groupby("product_id"):
            experiments = (
                group["experiment_id"]
                .drop_duplicates()
                .tolist()
            )

            product_groups[str(product_id)] = experiments

        best_split = None
        best_score = float("inf")

        # Многократно пробуем разные комбинации групп.
        for _ in range(self.split_candidates):
            selected_test_experiments = set()

            for product_id, experiments in product_groups.items():
                total_experiments = len(experiments)

                test_count = self._get_test_experiment_count(
                    total_experiments,
                    self.test_size
                )

                if test_count == 0:
                    continue

                shuffled = experiments.copy()
                rng.shuffle(shuffled)

                selected = shuffled[:test_count]

                selected_test_experiments.update(
                    selected
                )

            if not selected_test_experiments:
                continue

            test_mask = dataframe["experiment_id"].isin(
                selected_test_experiments
            )

            test = dataframe[test_mask].copy()
            train = dataframe[~test_mask].copy()

            train_experiments = set(
                train["experiment_id"]
            )

            test_experiments = set(
                test["experiment_id"]
            )

            if train_experiments & test_experiments:
                continue

            score = self._evaluate_split(
                dataframe,
                train,
                test
            )

            if score < best_score:
                best_score = score
                best_split = (
                    train.copy(),
                    test.copy()
                )

        if best_split is None:
            raise ValueError(
                "Не удалось сформировать разделение датасета. "
                "Проверьте количество независимых экспериментов."
            )

        train, test = best_split

        train_experiments = set(
            train["experiment_id"]
        )

        test_experiments = set(
            test["experiment_id"]
        )

        if train_experiments & test_experiments:
            raise RuntimeError(
                "Обнаружена утечка экспериментов между train и test."
            )

        print("\n======= РЕЗУЛЬТАТ РАЗДЕЛЕНИЯ =======")

        print(
            f"Train: {len(train)} записей, "
            f"{train['experiment_id'].nunique()} экспериментов"
        )

        print(
            f"Test: {len(test)} записей, "
            f"{test['experiment_id'].nunique()} экспериментов"
        )

        print(
            f"Оценка разделения: {best_score:.4f}"
        )

        print("\n======= РАСПРЕДЕЛЕНИЕ TRAIN =======")

        print(
            pd.crosstab(
                train["product_id"],
                train["target"]
            ).rename(
                columns={
                    0: "GOOD",
                    1: "DEFECT"
                }
            )
        )

        print("\n======= РАСПРЕДЕЛЕНИЕ TEST =======")

        print(
            pd.crosstab(
                test["product_id"],
                test["target"]
            ).rename(
                columns={
                    0: "GOOD",
                    1: "DEFECT"
                }
            )
        )

        print("\n======= ЭКСПЕРИМЕНТЫ ПО ИЗДЕЛИЯМ =======")

        for product_id, experiments in product_groups.items():
            train_count = train[
                train["product_id"] == product_id
            ]["experiment_id"].nunique()

            test_count = test[
                test["product_id"] == product_id
            ]["experiment_id"].nunique()

            print(
                f"Изделие {product_id}: "
                f"train — {train_count}, "
                f"test — {test_count}, "
                f"всего — {len(experiments)}"
            )

            if len(experiments) == 1:
                print(
                    "  ВНИМАНИЕ: только один эксперимент. "
                    "Изделие невозможно представить "
                    "одновременно в train и test."
                )

        return train, test

    def save_dataset(self, dataframe, train, test):
        self.output_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        dataset_path = self.output_dir / "dataset.csv"
        train_path = self.output_dir / "train.csv"
        test_path = self.output_dir / "test.csv"
        info_path = self.output_dir / "split_info.json"

        dataframe.to_csv(
            dataset_path,
            index=False,
            encoding="utf-8-sig"
        )

        train.to_csv(
            train_path,
            index=False,
            encoding="utf-8-sig"
        )

        test.to_csv(
            test_path,
            index=False,
            encoding="utf-8-sig"
        )

        measurement_columns = [
            column
            for column in dataframe.columns
            if column.startswith("measurement__")
        ]

        train_experiments = sorted(
            train["experiment_id"].unique().tolist()
        )

        test_experiments = sorted(
            test["experiment_id"].unique().tolist()
        )

        info = {
            "total_records": len(dataframe),
            "train_records": len(train),
            "test_records": len(test),

            "train_experiments": train_experiments,
            "test_experiments": test_experiments,

            "product_statistics": (
                self._get_product_statistics(dataframe)
            ),

            "train_products": sorted(
                train["product_id"].unique().tolist()
            ),

            "test_products": sorted(
                test["product_id"].unique().tolist()
            ),

            "measurement_features": measurement_columns,

            "feature_columns": (
                ["product_id"] + measurement_columns
            ),

            "target_column": "target",

            "target_classes": {
                "GOOD": 0,
                "DEFECT": 1
            },

            "class_distribution": {
                str(key): int(value)
                for key, value in dataframe["target"]
                .value_counts()
                .sort_index()
                .items()
            },

            "test_size": self.test_size,
            "random_state": self.random_state,
            "split_candidates": self.split_candidates,

            "split_method": (
                "Stratified group split by product_id "
                "and experiment_id with class balancing"
            )
        }

        with open(
            info_path,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                info,
                file,
                ensure_ascii=False,
                indent=4
            )

        return {
            "dataset": str(dataset_path),
            "train": str(train_path),
            "test": str(test_path),
            "info": str(info_path)
        }

    def build_dataset(self, records=None):
        """
        Полный цикл формирования датасета.
        """
        if records is None:
            records = self.load_records()

        if not records:
            raise ValueError(
                "В базе данных пока нет записей контроля."
            )

        dataframe = self.prepare_dataset(records)

        train, test = self.split_dataset(dataframe)

        paths = self.save_dataset(
            dataframe,
            train,
            test
        )

        self.dataset = dataframe
        self.train_dataset = train
        self.test_dataset = test

        measurement_columns = [
            column
            for column in dataframe.columns
            if column.startswith("measurement__")
        ]

        return {
            "total": len(dataframe),
            "train": len(train),
            "test": len(test),

            "experiments": (
                dataframe["experiment_id"].nunique()
            ),

            "train_experiments": (
                train["experiment_id"].nunique()
            ),

            "test_experiments": (
                test["experiment_id"].nunique()
            ),

            "products": (
                dataframe["product_id"].nunique()
            ),

            "features": len(measurement_columns) + 1,

            "good": int(
                (dataframe["target"] == 0).sum()
            ),

            "defect": int(
                (dataframe["target"] == 1).sum()
            ),

            "train_good": int(
                (train["target"] == 0).sum()
            ),

            "train_defect": int(
                (train["target"] == 1).sum()
            ),

            "test_good": int(
                (test["target"] == 0).sum()
            ),

            "test_defect": int(
                (test["target"] == 1).sum()
            ),

            "paths": paths,

            "dataframe": dataframe,
            "train_dataframe": train,
            "test_dataframe": test
        }
