
import csv
import json
import math
import random

from collections import defaultdict
from pathlib import Path

from application.src.core.measurement_logger import MeasurementLogger
from application.src.core.condition_monitor import ConditionMonitor


class DatasetBuilder:
    """Формирование датасета для обучения ML-модели."""

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

    FAULTS = [
        "overheating",
        "high_vibration",
        "overload",
        "tool_wear",
    ]

    FAULT_MEASUREMENTS = {
        "overheating": "temperature",
        "high_vibration": "vibration",
        "overload": "spindle_load",
        "tool_wear": "tool_wear",
    }

    FAULT_LABELS = {
        "overheating": "Перегрев",
        "high_vibration": "Повышенная вибрация",
        "overload": "Перегрузка шпинделя",
        "tool_wear": "Износ инструмента",
    }

    def __init__(self, logger=None):
        self.logger = logger or MeasurementLogger()

        self.dataset = []
        self.feature_names = []
        self.class_distribution = {}

        self.total_source_rows = 0
        self.skipped_rows = 0
        self.legacy_rows = 0

    # ==========================================
    # ЧТЕНИЕ НЕИСПРАВНОСТЕЙ
    # ==========================================

    @staticmethod
    def parse_faults(value):
        if not value:
            return []

        if isinstance(value, list):
            return value

        if isinstance(value, dict):
            return list(value.keys())

        try:
            result = json.loads(value)

            if isinstance(result, list):
                return result

            if isinstance(result, dict):
                return list(result.keys())

        except (TypeError, json.JSONDecodeError):
            pass

        return [str(value)]

    def normalize_faults(self, value):
        faults = set(self.parse_faults(value))

        if "combined" in faults:
            return set(self.FAULTS)

        return faults.intersection(self.FAULTS)

    # ==========================================
    # ПОДГОТОВКА ПРИЗНАКОВ
    # ==========================================

    @staticmethod
    def safe_number(value):
        try:
            if value is None:
                return None

            number = float(value)

            if not math.isfinite(number):
                return None

            return number

        except (TypeError, ValueError):
            return None

    @staticmethod
    def normalize_category(value):
        if value is None or str(value).strip() == "":
            return "Не указано"

        return str(value).strip()

    def prepare_numeric_features(self, row):
        result = {}

        for feature in self.NUMERIC_FEATURES:
            value = self.safe_number(row.get(feature))

            if value is None:
                return None

            result[feature] = value

        return result

    def prepare_categories(self, row):
        return {
            feature: self.normalize_category(row.get(feature))
            for feature in self.CATEGORICAL_FEATURES
        }

    # ==========================================
    # ЦЕЛЕВЫЕ МЕТКИ
    # ==========================================

    def detect_faults_from_measurement(self, numeric):
        """Определяет целевые метки по показаниям датчиков."""

        detected_faults = set()

        for fault, measurement_key in self.FAULT_MEASUREMENTS.items():
            limits = ConditionMonitor.LIMITS[measurement_key]
            value = numeric.get(measurement_key)

            if value is not None and value >= limits["warning"]:
                detected_faults.add(fault)

        return detected_faults

    def determine_class(self, normalized_faults):
        """Определяет общий класс состояния."""

        if not normalized_faults:
            return "normal"

        if len(normalized_faults) == 1:
            return next(iter(normalized_faults))

        return "multiple_faults"

    def prepare_targets(self, faults):
        return {
            f"target_{fault}": int(fault in faults)
            for fault in self.FAULTS
        }

    # ==========================================
    # ФОРМИРОВАНИЕ ДАТАСЕТА
    # ==========================================

    def build(self):
        source_rows = self.logger.list_measurements()

        source_rows.sort(
            key=lambda row: row.get("id", 0)
        )

        self.total_source_rows = len(source_rows)
        self.skipped_rows = 0
        self.legacy_rows = 0

        if not source_rows:
            self.dataset = []
            self.feature_names = []
            self.class_distribution = {}

            raise ValueError(
                "В базе данных пока нет измерений."
            )

        categories = {
            feature: set()
            for feature in self.CATEGORICAL_FEATURES
        }

        prepared_rows = []

        for row in source_rows:
            numeric = self.prepare_numeric_features(row)

            if numeric is None:
                self.skipped_rows += 1
                continue

            categorical = self.prepare_categories(row)

            for feature, value in categorical.items():
                categories[feature].add(value)

            # Фактически обнаруженные состояния по датчикам.
            detected_faults = self.detect_faults_from_measurement(
                numeric
            )

            fault_class = self.determine_class(detected_faults)

            # Неисправности, принудительно активированные
            # в конкретном эксперименте.
            active_faults = self.normalize_faults(
                row.get("active_faults")
            )

            experiment_mode = (
                "+".join(sorted(active_faults))
                if active_faults
                else "normal"
            )

            experiment_id = row.get("experiment_id")

            if not experiment_id:
                self.legacy_rows += 1

            prepared_rows.append({
                "source_id": row.get("id"),
                "timestamp": row.get("timestamp"),
                "experiment_id": experiment_id,
                "experiment_mode": experiment_mode,
                "numeric": numeric,
                "categorical": categorical,
                "fault_class": fault_class,
                "targets": self.prepare_targets(
                    detected_faults
                )
            })

        if not prepared_rows:
            self.dataset = []
            self.feature_names = []
            self.class_distribution = {}

            raise ValueError(
                "Не удалось сформировать датасет: "
                "нет измерений с полным набором числовых признаков."
            )

        # Формирование списка признаков модели.
        self.feature_names = list(self.NUMERIC_FEATURES)

        for feature in self.CATEGORICAL_FEATURES:
            for value in sorted(categories[feature]):
                self.feature_names.append(
                    f"{feature}__{value}"
                )

        self.dataset = []

        for prepared in prepared_rows:
            result = {
                "source_id": prepared["source_id"],
                "timestamp": prepared["timestamp"],
                "experiment_id": prepared["experiment_id"],
                "experiment_mode": prepared["experiment_mode"],
            }

            result.update(prepared["numeric"])

            for feature in self.CATEGORICAL_FEATURES:
                current_value = prepared["categorical"][feature]

                for category in sorted(categories[feature]):
                    result[
                        f"{feature}__{category}"
                    ] = int(current_value == category)

            result["fault_class"] = prepared["fault_class"]
            result.update(prepared["targets"])

            self.dataset.append(result)

        self.class_distribution = {}

        for row in self.dataset:
            label = row["fault_class"]

            self.class_distribution[label] = (
                self.class_distribution.get(label, 0) + 1
            )

        return self.dataset

    # ==========================================
    # РАЗДЕЛЕНИЕ ПО ЭКСПЕРИМЕНТАМ
    # ==========================================


    def split_dataset(self, train_ratio=0.8):
        if not 0 < train_ratio < 1:
            raise ValueError(
                "train_ratio должен быть больше 0 и меньше 1."
            )

        if not self.dataset:
            raise ValueError(
                "Датасет пуст. Сначала выполните build()."
            )

        groups = defaultdict(list)

        for row in self.dataset:
            experiment_id = row.get("experiment_id")

            if experiment_id:
                groups[str(experiment_id)].append(row)

        experiment_ids = list(groups.keys())

        if len(experiment_ids) < 2:
            raise ValueError(
                "Для независимого обучения необходимо минимум "
                "два экспериментальных запуска с experiment_id.\n\n"
                f"Найдено запусков: {len(experiment_ids)}\n"
                f"Измерений без ID запуска: {self.legacy_rows}"
            )

        target_names = [
            f"target_{fault}" for fault in self.FAULTS
        ]

        total_rows = sum(
            len(rows) for rows in groups.values()
        )

        test_ratio = 1 - train_ratio

        rng = random.Random(42)

        # ==========================================
        # ПРЕДВАРИТЕЛЬНАЯ СТАТИСТИКА ЭКСПЕРИМЕНТОВ
        # ==========================================

        group_stats = {}

        total_modes = defaultdict(int)

        for experiment_id, rows in groups.items():
            positive_counts = [
                sum(int(row[target]) for row in rows)
                for target in target_names
            ]

            mode = rows[0].get(
                "experiment_mode",
                "unknown"
            )

            group_stats[experiment_id] = {
                "row_count": len(rows),
                "positive_counts": positive_counts,
                "mode": mode,
            }

            total_modes[mode] += len(rows)

        modes = list(total_modes.keys())

        # ==========================================
        # ПОДБОР РАЗДЕЛЕНИЯ
        # ==========================================

        best_test_ids = None
        best_score = float("inf")

        attempts = min(
            20000,
            max(5000, len(experiment_ids) * 500)
        )

        for _ in range(attempts):
            shuffled_ids = experiment_ids.copy()
            rng.shuffle(shuffled_ids)

            candidate_test_ids = {
                experiment_id
                for experiment_id in shuffled_ids
                if rng.random() < test_ratio
            }

            if (
                not candidate_test_ids
                or len(candidate_test_ids) == len(experiment_ids)
            ):
                continue

            candidate_train_ids = (
                set(experiment_ids) - candidate_test_ids
            )

            # Считаем статистику только по группам.
            train_count = 0
            test_count = 0

            train_positive = [0] * len(target_names)
            test_positive = [0] * len(target_names)

            train_modes = defaultdict(int)
            test_modes = defaultdict(int)

            for experiment_id in candidate_train_ids:
                stats = group_stats[experiment_id]

                train_count += stats["row_count"]

                for index, count in enumerate(
                    stats["positive_counts"]
                ):
                    train_positive[index] += count

                train_modes[stats["mode"]] += stats["row_count"]

            for experiment_id in candidate_test_ids:
                stats = group_stats[experiment_id]

                test_count += stats["row_count"]

                for index, count in enumerate(
                    stats["positive_counts"]
                ):
                    test_positive[index] += count

                test_modes[stats["mode"]] += stats["row_count"]

            if train_count == 0 or test_count == 0:
                continue

            # Проверяем наличие обоих классов
            # для каждой неисправности в обеих выборках.
            valid = True

            for index in range(len(target_names)):
                train_negative = (
                    train_count - train_positive[index]
                )

                test_negative = (
                    test_count - test_positive[index]
                )

                if (
                    train_positive[index] == 0
                    or test_positive[index] == 0
                    or train_negative == 0
                    or test_negative == 0
                ):
                    valid = False
                    break

            if not valid:
                continue

            # 1. Баланс размеров выборок.
            size_score = abs(
                test_count / total_rows - test_ratio
            )

            # 2. Баланс положительных меток.
            prevalence_score = 0.0

            for index in range(len(target_names)):
                train_share = (
                    train_positive[index] / train_count
                )

                test_share = (
                    test_positive[index] / test_count
                )

                prevalence_score += abs(
                    train_share - test_share
                )

            prevalence_score /= len(target_names)

            # 3. Баланс экспериментальных режимов.
            mode_score = 0.0

            for mode in modes:
                train_share = (
                    train_modes[mode] / train_count
                )

                test_share = (
                    test_modes[mode] / test_count
                )

                mode_score += abs(
                    train_share - test_share
                )

            mode_score /= 2

            # 4. Баланс количества независимых запусков.
            run_score = abs(
                len(candidate_test_ids) / len(experiment_ids)
                - test_ratio
            )

            score = (
                size_score * 2.0
                + prevalence_score * 3.0
                + mode_score * 2.0
                + run_score
            )

            if score < best_score:
                best_score = score
                best_test_ids = candidate_test_ids

        if best_test_ids is None:
            raise ValueError(
                "Не удалось найти корректное разделение.\n\n"
                "Возможно, некоторые неисправности не имеют "
                "достаточного количества положительных или "
                "отрицательных примеров в независимых запусках."
            )

        # ==========================================
        # ФОРМИРОВАНИЕ ИТОГОВЫХ ВЫБОРОК
        # ==========================================

        train_ids = set(experiment_ids) - best_test_ids

        train_rows = [
            row
            for experiment_id in train_ids
            for row in groups[experiment_id]
        ]

        test_rows = [
            row
            for experiment_id in best_test_ids
            for row in groups[experiment_id]
        ]

        if train_ids.intersection(best_test_ids):
            raise RuntimeError(
                "Обнаружено пересечение экспериментов "
                "между обучающей и тестовой выборками."
            )

        # ==========================================
        # ОТЧЁТ
        # ==========================================

        print("\n======= РАЗДЕЛЕНИЕ ПО ЭКСПЕРИМЕНТАМ =======")

        print(f"Всего запусков: {len(experiment_ids)}")
        print(f"Запусков для обучения: {len(train_ids)}")
        print(f"Запусков для тестирования: {len(best_test_ids)}")

        print(f"Обучающих измерений: {len(train_rows)}")
        print(f"Тестовых измерений: {len(test_rows)}")

        print(f"Старых измерений без ID: {self.legacy_rows}")
        print(f"Оценка баланса: {best_score:.5f}")

        print("\n======= РАСПРЕДЕЛЕНИЕ МЕТОК =======")

        for target in target_names:
            train_positive = sum(
                int(row[target]) for row in train_rows
            )

            test_positive = sum(
                int(row[target]) for row in test_rows
            )

            train_negative = len(train_rows) - train_positive
            test_negative = len(test_rows) - test_positive

            train_percent = (
                train_positive / len(train_rows) * 100
            )

            test_percent = (
                test_positive / len(test_rows) * 100
            )

            print(
                f"{target}:\n"
                f"  Обучение: {train_positive} положительных, "
                f"{train_negative} отрицательных "
                f"({train_percent:.1f}% положительных)\n"
                f"  Тест: {test_positive} положительных, "
                f"{test_negative} отрицательных "
                f"({test_percent:.1f}% положительных)"
            )

        print("\n======= СОСТАВ ЭКСПЕРИМЕНТОВ =======")

        print(
            f"{'Выборка':<12} "
            f"{'ID эксперимента':<38} "
            f"{'Режим':<42} "
            f"{'Строк':<8} "
            f"{'Перегрев':<12} "
            f"{'Вибрация':<12} "
            f"{'Перегрузка':<12} "
            f"{'Износ':<12}"
        )

        for experiment_id in sorted(groups):
            rows = groups[experiment_id]

            split_name = (
                "Обучение"
                if experiment_id in train_ids
                else "Тест"
            )

            mode = rows[0].get(
                "experiment_mode",
                "unknown"
            )

            positive_counts = [
                sum(int(row[target]) for row in rows)
                for target in target_names
            ]

            print(
                f"{split_name:<12} "
                f"{experiment_id:<38} "
                f"{mode:<42} "
                f"{len(rows):<8} "
                f"{positive_counts[0]:<12} "
                f"{positive_counts[1]:<12} "
                f"{positive_counts[2]:<12} "
                f"{positive_counts[3]:<12}"
            )

        print("===========================================\n")

        return train_rows, test_rows


    # ==========================================
    # ЭКСПОРТ
    # ==========================================

    @staticmethod
    def write_csv(file_path, rows):
        if not rows:
            raise ValueError(
                "Нельзя экспортировать пустую выборку."
            )

        destination = Path(file_path)

        destination.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        columns = list(rows[0].keys())

        with destination.open(
            "w",
            newline="",
            encoding="utf-8-sig"
        ) as file:
            writer = csv.DictWriter(
                file,
                fieldnames=columns,
                delimiter=";"
            )

            writer.writeheader()
            writer.writerows(rows)

        return destination

    def export_bundle(self, directory):
        if not self.dataset:
            raise ValueError(
                "Сначала сформируйте датасет."
            )

        directory = Path(directory)

        directory.mkdir(
            parents=True,
            exist_ok=True
        )

        train_rows, test_rows = self.split_dataset()

        full_path = self.write_csv(
            directory / "dataset_full.csv",
            self.dataset
        )

        train_path = self.write_csv(
            directory / "dataset_train.csv",
            train_rows
        )

        test_path = self.write_csv(
            directory / "dataset_test.csv",
            test_rows
        )

        return {
            "full": full_path,
            "train": train_path,
            "test": test_path,
            "train_count": len(train_rows),
            "test_count": len(test_rows),
        }
