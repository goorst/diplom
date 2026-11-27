
import json
import math
import random

from pathlib import Path

import pandas as pd

from application.src.core.measurement_logger import MeasurementLogger


class DatasetBuilder:
    """
    Формирование датасета для предиктивного контроля качества.

    ML-модель прогнозирует качество изделия по технологическим
    параметрам до получения результатов измерений.

    Используемые признаки:
    - product_id;
    - process__cutting_speed;
    - process__feed_rate;
    - process__depth_of_cut;
    - process__tool_wear;
    - process__vibration.

    Измеренные характеристики не используются как признаки,
    поскольку по ним непосредственно определяется целевая метка.

    Особенности:
    - поддержка нескольких типов изделий;
    - исключение UNKNOWN;
    - исключение старых записей без технологических параметров;
    - исключение записей с искусственно внесенными дефектами;
    - групповое разделение по experiment_id;
    - стратификация экспериментов по изделиям;
    - сохранение статистики и состава признаков.
    """

    def __init__(
        self,
        measurement_logger=None,
        output_dir=None,
        test_size=0.2,
        validation_size=0.15,
        random_state=42,
        split_candidates=1000,
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
        self.validation_size = float(validation_size)
        self.random_state = int(random_state)
        self.split_candidates = int(split_candidates)

        if not 0 < self.test_size < 1:
            raise ValueError(
                "test_size должен находиться между 0 и 1."
            )

        if not 0 < self.validation_size < 1:
            raise ValueError(
                "validation_size должен находиться между 0 и 1."
            )

        if self.test_size + self.validation_size >= 1:
            raise ValueError(
                "Сумма validation_size и test_size должна быть меньше 1."
            )

        if self.split_candidates < 1:
            raise ValueError(
                "split_candidates должен быть больше 0."
            )

        self.dataset = None
        self.train_dataset = None
        self.validation_dataset = None
        self.test_dataset = None

    # ---------------------------------------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ---------------------------------------------------------

    @staticmethod
    def _parse_json(value):
        if isinstance(value, str):
            try:
                parsed = json.loads(value)

                if isinstance(parsed, dict):
                    return parsed

                return {}

            except (json.JSONDecodeError, TypeError):
                return {}

        if isinstance(value, dict):
            return value

        return {}

    @staticmethod
    def _to_float(value):
        if value is None or isinstance(value, bool):
            return None

        try:
            number = float(
                str(value).strip().replace(",", ".")
            )

            if math.isfinite(number):
                return number

        except (ValueError, TypeError):
            pass

        return None

    @staticmethod
    def _get_numeric_process_parameters(process_parameters):
        """
        Преобразует технологические параметры в ML-признаки.

        Например:
        cutting_speed -> process__cutting_speed
        feed_rate     -> process__feed_rate
        """

        result = {}

        if not isinstance(process_parameters, dict):
            return result

        for name, value in process_parameters.items():
            number = DatasetBuilder._to_float(value)

            if number is None:
                continue

            feature_name = f"process__{name}"

            result[feature_name] = number

        return result

    def load_records(self):
        records = self.measurement_logger.get_all_records(
            limit=1000000
        )

        return records or []

    # ---------------------------------------------------------
    # ФОРМИРОВАНИЕ ДАТАСЕТА
    # ---------------------------------------------------------

    def prepare_dataset(self, records):
        """
        Формирует датасет только из записей,
        содержащих технологические параметры.

        Не использует измеренные характеристики как признаки.
        """

        rows = []

        counters = {
            "total": 0,
            "unknown": 0,
            "without_experiment_id": 0,
            "without_product_id": 0,
            "without_process_parameters": 0,
            "simulated_defects": 0,
            "accepted": 0,
        }

        for record in records:
            counters["total"] += 1

            if not isinstance(record, dict):
                continue

            nested_result = self._parse_json(
                record.get("result")
            )

            # -------------------------------------------------
            # 1. Получение статуса контроля
            # -------------------------------------------------

            status = (
                record.get("status")
                or nested_result.get("status")
                or "UNKNOWN"
            )

            status = str(status).strip().upper()

            if status not in ("GOOD", "DEFECT"):
                counters["unknown"] += 1
                continue

            # -------------------------------------------------
            # 2. Исключение искусственно внесенных дефектов
            # -------------------------------------------------

            simulated_defect = record.get(
                "simulated_defect",
                nested_result.get("simulated_defect", False),
            )

            if isinstance(simulated_defect, str):
                simulated_defect = (
                    simulated_defect.strip().lower()
                    in ("1", "true", "yes")
                )

            if bool(simulated_defect):
                counters["simulated_defects"] += 1
                continue

            # -------------------------------------------------
            # 3. Идентификатор эксперимента
            # -------------------------------------------------

            experiment_id = (
                record.get("experiment_id")
                or nested_result.get("experiment_id")
            )

            if not experiment_id:
                counters["without_experiment_id"] += 1
                continue

            # -------------------------------------------------
            # 4. Идентификатор изделия
            # -------------------------------------------------

            product_id = (
                record.get("product_id")
                or nested_result.get("product_id")
            )

            if product_id is None:
                counters["without_product_id"] += 1
                continue

            # -------------------------------------------------
            # 5. Технологические параметры
            # -------------------------------------------------

            process_parameters = nested_result.get(
                "process_parameters",
                record.get("process_parameters", {}),
            )

            process_parameters = self._parse_json(
                process_parameters
            )

            process_features = (
                self._get_numeric_process_parameters(
                    process_parameters
                )
            )

            if not process_features:
                counters["without_process_parameters"] += 1
                continue

            # -------------------------------------------------
            # 6. Формирование строки датасета
            # -------------------------------------------------

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

            # Добавляем только технологические параметры.
            row.update(process_features)

            # GOOD = 0, DEFECT = 1.
            row["target"] = (
                0 if status == "GOOD" else 1
            )

            rows.append(row)
            counters["accepted"] += 1

        print("\n======= ФИЛЬТРАЦИЯ ЗАПИСЕЙ =======")

        print(
            f"Всего записей: {counters['total']}"
        )

        print(
            f"Принято записей: {counters['accepted']}"
        )

        print(
            f"UNKNOWN: {counters['unknown']}"
        )

        print(
            f"Без experiment_id: "
            f"{counters['without_experiment_id']}"
        )

        print(
            f"Без product_id: "
            f"{counters['without_product_id']}"
        )

        print(
            f"Без технологических параметров: "
            f"{counters['without_process_parameters']}"
        )

        print(
            f"С искусственными дефектами: "
            f"{counters['simulated_defects']}"
        )

        if not rows:
            raise ValueError(
                "Не удалось сформировать датасет. "
                "Не найдены записи GOOD/DEFECT с технологическими "
                "параметрами и без искусственно внесенных дефектов. "
                "Создайте новые эксперименты после обновления "
                "ProductGenerator и ConveyorSimulator."
            )

        dataframe = pd.DataFrame(rows)

        process_columns = [
            column
            for column in dataframe.columns
            if column.startswith("process__")
        ]

        if not process_columns:
            raise ValueError(
                "В датасете отсутствуют технологические признаки."
            )

        # Удаляем записи, у которых все процессные признаки пустые.
        dataframe = dataframe.dropna(
            subset=process_columns,
            how="all",
        ).copy()

        if dataframe.empty:
            raise ValueError(
                "После проверки технологических параметров "
                "датасет оказался пустым."
            )

        # Проверяем наличие хотя бы двух классов.
        if dataframe["target"].nunique() < 2:
            raise ValueError(
                "В датасете присутствует только один класс. "
                "Для обучения классификатора необходимы "
                "как GOOD, так и DEFECT."
            )

        print("\n======= СОСТАВ ПРИЗНАКОВ =======")

        for column in process_columns:
            print(column)

        print(
            f"\nВсего технологических признаков: "
            f"{len(process_columns)}"
        )

        return dataframe

    # ---------------------------------------------------------
    # СТАТИСТИКА И РАЗДЕЛЕНИЕ ПО ГРУППАМ
    # ---------------------------------------------------------

    @staticmethod
    def _get_product_statistics(dataframe):
        result = {}
        for product_id, group in dataframe.groupby("product_id"):
            result[str(product_id)] = {
                "experiments": int(group["experiment_id"].nunique()),
                "records": int(len(group)),
                "good": int((group["target"] == 0).sum()),
                "defect": int((group["target"] == 1).sum()),
            }
        return result

    def _evaluate_three_way_split(self, dataframe, train, validation, test):
        """Оценивает близость размеров и распределений классов к исходным."""
        if train.empty or validation.empty or test.empty:
            return float("inf")

        score = 0.0
        total = len(dataframe)
        desired = {
            "train": 1.0 - self.validation_size - self.test_size,
            "validation": self.validation_size,
            "test": self.test_size,
        }
        subsets = {"train": train, "validation": validation, "test": test}

        for name, subset in subsets.items():
            ratio = len(subset) / total
            score += abs(ratio - desired[name]) * 5
            distribution = subset["target"].value_counts(normalize=True)
            original = dataframe["target"].value_counts(normalize=True)
            for class_value in (0, 1):
                score += abs(
                    float(distribution.get(class_value, 0))
                    - float(original.get(class_value, 0))
                )
                if name == "train" and float(distribution.get(class_value, 0)) == 0:
                    score += 100
                elif name in ("validation", "test") and float(distribution.get(class_value, 0)) == 0:
                    score += 2

        # Штрафуем отсутствие изделия в обучении. В validation/test оно
        # может отсутствовать, если для изделия накоплено менее трёх групп.
        for product_id, original_group in dataframe.groupby("product_id"):
            train_group = train[train["product_id"] == product_id]
            if train_group.empty:
                score += 100
            group_count = original_group["experiment_id"].nunique()
            if group_count >= 3:
                for subset in (validation, test):
                    if subset[subset["product_id"] == product_id].empty:
                        score += 10
        return score

    def split_dataset(self, dataframe):
        """Групповое разделение Train/Validation/Test по experiment_id."""
        if dataframe.empty:
            raise ValueError("Нельзя разделить пустой датасет.")

        products_per_experiment = dataframe.groupby("experiment_id")["product_id"].nunique()
        mixed = products_per_experiment[products_per_experiment > 1]
        if not mixed.empty:
            raise ValueError(
                "Обнаружены experiment_id, содержащие записи нескольких изделий: "
                + ", ".join(mixed.index.astype(str).tolist()[:10])
            )

        statistics = self._get_product_statistics(dataframe)
        print("\n======= НЕЗАВИСИМЫЕ ЭКСПЕРИМЕНТЫ ПО ИЗДЕЛИЯМ =======")
        for product_id, stats in statistics.items():
            print(
                f"Изделие {product_id}: экспериментов {stats['experiments']}, "
                f"записей {stats['records']}, GOOD {stats['good']}, "
                f"DEFECT {stats['defect']}"
            )
            if stats["experiments"] < 3:
                print(
                    f"  ВНИМАНИЕ: для изделия {product_id} недостаточно "
                    "независимых экспериментов, чтобы представить его "
                    "во всех трёх выборках."
                )

        product_groups = {
            str(product_id): group["experiment_id"].drop_duplicates().tolist()
            for product_id, group in dataframe.groupby("product_id")
        }
        rng = random.Random(self.random_state)
        best = None
        best_score = float("inf")

        for _ in range(self.split_candidates):
            assignment = {"train": set(), "validation": set(), "test": set()}
            for experiments in product_groups.values():
                shuffled = list(experiments)
                rng.shuffle(shuffled)
                count = len(shuffled)

                if count >= 3:
                    validation_count = max(1, round(count * self.validation_size))
                    test_count = max(1, round(count * self.test_size))
                    while validation_count + test_count >= count:
                        if validation_count >= test_count and validation_count > 1:
                            validation_count -= 1
                        elif test_count > 1:
                            test_count -= 1
                        else:
                            break
                    assignment["validation"].update(shuffled[:validation_count])
                    assignment["test"].update(
                        shuffled[validation_count:validation_count + test_count]
                    )
                    assignment["train"].update(
                        shuffled[validation_count + test_count:]
                    )
                elif count == 2:
                    # Один эксперимент оставляем для обучения, второй случайно
                    # направляем либо в validation, либо в test.
                    assignment["train"].add(shuffled[0])
                    destination = "validation" if rng.random() < 0.5 else "test"
                    assignment[destination].add(shuffled[1])
                else:
                    assignment["train"].update(shuffled)

            masks = {
                name: dataframe["experiment_id"].isin(ids)
                for name, ids in assignment.items()
            }
            train = dataframe[masks["train"]].copy()
            validation = dataframe[masks["validation"]].copy()
            test = dataframe[masks["test"]].copy()

            if train.empty or validation.empty or test.empty:
                continue
            if train["target"].nunique() < 2:
                continue

            sets = [set(assignment[name]) for name in ("train", "validation", "test")]
            if (sets[0] & sets[1]) or (sets[0] & sets[2]) or (sets[1] & sets[2]):
                continue

            score = self._evaluate_three_way_split(
                dataframe, train, validation, test
            )
            if score < best_score:
                best_score = score
                best = (train, validation, test)

        if best is None:
            raise ValueError(
                "Не удалось сформировать три непустые выборки с обоими "
                "классами в Train. Увеличьте число независимых экспериментов."
            )

        train, validation, test = best
        group_sets = [
            set(train["experiment_id"].astype(str)),
            set(validation["experiment_id"].astype(str)),
            set(test["experiment_id"].astype(str)),
        ]
        if (group_sets[0] & group_sets[1]) or (group_sets[0] & group_sets[2]) or (group_sets[1] & group_sets[2]):
            raise RuntimeError("Обнаружена утечка experiment_id между выборками.")

        print("\n======= РЕЗУЛЬТАТ РАЗДЕЛЕНИЯ =======")
        for name, subset in (("Train", train), ("Validation", validation), ("Test", test)):
            print(
                f"{name}: {len(subset)} записей, "
                f"{subset['experiment_id'].nunique()} экспериментов, "
                f"GOOD {(subset['target'] == 0).sum()}, "
                f"DEFECT {(subset['target'] == 1).sum()}"
            )
            print(pd.crosstab(subset["product_id"], subset["target"]).rename(
                columns={0: "GOOD", 1: "DEFECT"}
            ))

        print(f"Оценка разделения: {best_score:.4f}")
        return train, validation, test

    # ---------------------------------------------------------
    # СОХРАНЕНИЕ ДАТАСЕТА
    # ---------------------------------------------------------

    def save_dataset(self, dataframe, train, validation, test):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "dataset": self.output_dir / "dataset.csv",
            "train": self.output_dir / "train.csv",
            "validation": self.output_dir / "validation.csv",
            "test": self.output_dir / "test.csv",
            "info": self.output_dir / "split_info.json",
        }
        for key, subset in (("dataset", dataframe), ("train", train),
                            ("validation", validation), ("test", test)):
            subset.to_csv(paths[key], index=False, encoding="utf-8-sig")

        process_columns = [c for c in dataframe.columns if c.startswith("process__")]
        info = {
            "dataset_type": "predictive_process_parameters",
            "prediction_description": (
                "Прогнозирование качества изделия по технологическим параметрам до измерения"
            ),
            "total_records": len(dataframe),
            "train_records": len(train),
            "validation_records": len(validation),
            "test_records": len(test),
            "train_experiments": sorted(train["experiment_id"].astype(str).unique().tolist()),
            "validation_experiments": sorted(validation["experiment_id"].astype(str).unique().tolist()),
            "test_experiments": sorted(test["experiment_id"].astype(str).unique().tolist()),
            "product_statistics": self._get_product_statistics(dataframe),
            "process_features": process_columns,
            "feature_columns": ["product_id"] + process_columns,
            "excluded_features": [
                "measurement__*", "simulated_defect", "simulated_defective_parameters",
                "injected_defects", "experiment_id", "run_id", "item_id"
            ],
            "target_column": "target",
            "target_classes": {"GOOD": 0, "DEFECT": 1},
            "class_distribution": {
                str(k): int(v) for k, v in dataframe["target"].value_counts().sort_index().items()
            },
            "validation_size": self.validation_size,
            "test_size": self.test_size,
            "random_state": self.random_state,
            "split_candidates": self.split_candidates,
            "split_method": "Group split by experiment_id with approximate class balancing",
        }
        with open(paths["info"], "w", encoding="utf-8") as file:
            json.dump(info, file, ensure_ascii=False, indent=4)
        return {key: str(value) for key, value in paths.items()}

    # ---------------------------------------------------------
    # ПОЛНЫЙ ЦИКЛ
    # ---------------------------------------------------------

    def build_dataset(self, records=None):
        """Полный цикл формирования датасета и трёх выборок."""
        if records is None:
            records = self.load_records()
        if not records:
            raise ValueError("В базе данных пока нет записей контроля.")

        dataframe = self.prepare_dataset(records)
        train, validation, test = self.split_dataset(dataframe)
        paths = self.save_dataset(dataframe, train, validation, test)

        self.dataset = dataframe
        self.train_dataset = train
        self.validation_dataset = validation
        self.test_dataset = test
        process_columns = [c for c in dataframe.columns if c.startswith("process__")]

        return {
            "total": len(dataframe),
            "train": len(train),
            "validation": len(validation),
            "test": len(test),
            "experiments": dataframe["experiment_id"].nunique(),
            "train_experiments": train["experiment_id"].nunique(),
            "validation_experiments": validation["experiment_id"].nunique(),
            "test_experiments": test["experiment_id"].nunique(),
            "products": dataframe["product_id"].nunique(),
            "features": len(process_columns) + 1,
            "process_features": process_columns,
            "good": int((dataframe["target"] == 0).sum()),
            "defect": int((dataframe["target"] == 1).sum()),
            "train_good": int((train["target"] == 0).sum()),
            "train_defect": int((train["target"] == 1).sum()),
            "validation_good": int((validation["target"] == 0).sum()),
            "validation_defect": int((validation["target"] == 1).sum()),
            "test_good": int((test["target"] == 0).sum()),
            "test_defect": int((test["target"] == 1).sum()),
            "paths": paths,
            "dataframe": dataframe,
            "train_dataframe": train,
            "validation_dataframe": validation,
            "test_dataframe": test,
        }
