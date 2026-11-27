
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import joblib
import pandas as pd

from application.src.products.product_manager import ProductManager
from application.src.quality.quality_checker import QualityChecker
from application.src.core.measurement_logger import MeasurementLogger

from .product_generator import ProductGenerator
from .defect_generator import DefectGenerator


class ConveyorSimulator:
    """
    Универсальный симулятор производственного процесса.

    Последовательность обработки изделия:

    1. Получение характеристик изделия.
    2. Генерация технологических параметров.
    3. Прогноз качества обученной ML-моделью.
    4. Генерация измерений.
    5. При необходимости внесение искусственного дефекта.
    6. Фактический контроль качества.
    7. Сравнение прогноза с фактическим результатом.
    8. Сохранение результата.
    """

    PROCESS_FEATURES = {
        "cutting_speed": "process__cutting_speed",
        "feed_rate": "process__feed_rate",
        "depth_of_cut": "process__depth_of_cut",
        "tool_wear": "process__tool_wear",
        "vibration": "process__vibration",
    }

    def __init__(
        self,
        product_manager=None,
        quality_checker=None,
        measurement_logger=None,
        defect_probability=0.0,
        process_ranges=None,
        process_effect_strength=0.25,
        model_path=None,
    ):
        self.product_manager = product_manager or ProductManager()

        self.quality_checker = (
            quality_checker
            or QualityChecker(product_manager=self.product_manager)
        )

        self.measurement_logger = (
            measurement_logger or MeasurementLogger()
        )

        self.defect_probability = max(
            0.0,
            min(1.0, float(defect_probability)),
        )

        self.process_ranges = process_ranges
        self.process_effect_strength = max(
            0.0,
            float(process_effect_strength),
        )

        self.product_generators = {}
        self.defect_generators = {}
        self.product_signatures = {}

        self.item_counter = 0
        self.run_item_counter = 0

        self.current_product_id = None

        self.experiment_id = None
        self.run_id = None

        self.experiment_name = None
        self.experiment_started_at = None
        self.run_started_at = None

        # Загрузка обученной модели.
        self.model_path = (
            Path(model_path)
            if model_path
            else Path(__file__).resolve().parents[3]
            / "data"
            / "model"
            / "best_model.joblib"
        )

        self.model = None
        self.model_name = None
        self.model_error = None

        self._load_model()

    # ---------------------------------------------------------
    # ЗАГРУЗКА ML-МОДЕЛИ
    # ---------------------------------------------------------

    def _load_model(self):
        """
        Загружает best_model.joblib.

        Файл ModelTrainer сохраняет в формате:
        {
            "name": "...",
            "model": обученная_модель
        }
        """

        if not self.model_path.exists():
            self.model_error = (
                f"Файл модели не найден: {self.model_path}"
            )
            return

        try:
            saved_data = joblib.load(self.model_path)

            if isinstance(saved_data, dict):
                self.model = saved_data.get("model")
                self.model_name = saved_data.get("name")
            else:
                self.model = saved_data
                self.model_name = type(saved_data).__name__

            if self.model is None:
                raise ValueError(
                    "В файле модели отсутствует объект модели."
                )

            self.model_error = None

        except Exception as error:
            self.model = None
            self.model_error = str(error)

    @property
    def is_model_loaded(self):
        return self.model is not None

    def get_model_info(self):
        return {
            "loaded": self.is_model_loaded,
            "name": self.model_name,
            "path": str(self.model_path),
            "error": self.model_error,
        }

    # ---------------------------------------------------------
    # ПРОГНОЗ КАЧЕСТВА
    # ---------------------------------------------------------

    def _build_model_features(
        self,
        product_id,
        process_parameters,
    ):
        """
        Формирует признаки для ML-модели.

        Измерения и сведения об искусственных дефектах
        в модель не передаются.
        """

        features = {
            "product_id": product_id,
        }

        for source_name, feature_name in self.PROCESS_FEATURES.items():
            if source_name not in process_parameters:
                raise ValueError(
                    "Отсутствует технологический параметр "
                    f"'{source_name}'."
                )

            features[feature_name] = float(
                process_parameters[source_name]
            )

        return pd.DataFrame([features])

    @staticmethod
    def _get_class_index(classes, target):
        """
        Находит индекс класса GOOD или DEFECT.
        """

        if classes is None:
            return None

        target_values = {
            "GOOD": {0, "0", "GOOD"},
            "DEFECT": {1, "1", "DEFECT"},
        }

        for index, value in enumerate(classes):
            normalized = (
                str(value).strip().upper()
            )

            if normalized in target_values[target]:
                return index

        return None

    def predict_quality(
        self,
        product_id,
        process_parameters,
    ):
        """
        Выполняет прогноз до генерации измерений.

        Возвращает:
        - predicted_status;
        - good_probability;
        - defect_probability;
        - predicted_class.
        """

        if self.model is None:
            return {
                "available": False,
                "predicted_status": "UNAVAILABLE",
                "predicted_class": None,
                "good_probability": None,
                "defect_probability": None,
                "model_name": self.model_name,
                "error": self.model_error,
            }

        try:
            features = self._build_model_features(
                product_id,
                process_parameters,
            )

            # Поддержка пользовательского EnsembleModel.
            if hasattr(self.model, "predict_quality"):
                prediction = self.model.predict_quality(features)[0]

                predicted_status = prediction.get(
                    "predicted_status",
                    "UNKNOWN",
                )

                predicted_class = prediction.get(
                    "predicted_class"
                )

                good_probability = prediction.get(
                    "good_probability"
                )

                defect_probability = prediction.get(
                    "defect_probability"
                )

            # Поддержка sklearn Pipeline,
            # используемого в best_model.joblib.
            else:
                predicted_class = self.model.predict(
                    features
                )[0]

                classes = getattr(
                    self.model,
                    "classes_",
                    None,
                )

                if classes is None:
                    raise ValueError(
                        "Модель не предоставляет classes_."
                    )

                classes = list(classes)

                normalized_class = str(
                    predicted_class
                ).strip().upper()

                if normalized_class in {"0", "GOOD"}:
                    predicted_status = "GOOD"
                elif normalized_class in {"1", "DEFECT"}:
                    predicted_status = "DEFECT"
                else:
                    raise ValueError(
                        f"Неизвестный класс модели: {predicted_class}"
                    )

                good_probability = None
                defect_probability = None

                if hasattr(self.model, "predict_proba"):
                    probabilities = self.model.predict_proba(
                        features
                    )[0]

                    good_index = self._get_class_index(
                        classes,
                        "GOOD",
                    )

                    defect_index = self._get_class_index(
                        classes,
                        "DEFECT",
                    )

                    if good_index is not None:
                        good_probability = float(
                            probabilities[good_index]
                        )

                    if defect_index is not None:
                        defect_probability = float(
                            probabilities[defect_index]
                        )

            return {
                "available": True,
                "predicted_status": predicted_status,
                "predicted_class": (
                    int(predicted_class)
                    if isinstance(
                        predicted_class,
                        (int, float)
                    )
                    else str(predicted_class)
                ),
                "good_probability": (
                    float(good_probability)
                    if good_probability is not None
                    else None
                ),
                "defect_probability": (
                    float(defect_probability)
                    if defect_probability is not None
                    else None
                ),
                "model_name": self.model_name,
                "error": None,
            }

        except Exception as error:
            return {
                "available": False,
                "predicted_status": "ERROR",
                "predicted_class": None,
                "good_probability": None,
                "defect_probability": None,
                "model_name": self.model_name,
                "error": str(error),
            }

    # ---------------------------------------------------------
    # ЭКСПЕРИМЕНТЫ
    # ---------------------------------------------------------

    def start_experiment(self, name=None):
        self.experiment_id = str(uuid4())

        self.experiment_name = (
            name
            or f"Эксперимент {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        self.experiment_started_at = (
            datetime.now().isoformat(timespec="seconds")
        )

        self.run_id = None
        self.run_started_at = None
        self.run_item_counter = 0

        self.start_run()

        return self.experiment_id

    def start_run(self):
        if self.experiment_id is None:
            self.start_experiment()

        self.run_id = str(uuid4())

        self.run_started_at = (
            datetime.now().isoformat(timespec="seconds")
        )

        self.run_item_counter = 0

        return self.run_id

    def get_experiment_info(self):
        return {
            "experiment_id": self.experiment_id,
            "experiment_name": self.experiment_name,
            "experiment_started_at": self.experiment_started_at,
            "run_id": self.run_id,
            "run_started_at": self.run_started_at,
            "run_item_counter": self.run_item_counter,
        }

    # ---------------------------------------------------------
    # ПОДГОТОВКА ИЗДЕЛИЯ
    # ---------------------------------------------------------

    @staticmethod
    def _parameter_signature(parameters):
        signature = []

        for parameter in parameters:
            signature.append((
                parameter.get("id"),
                parameter.get("code"),
                parameter.get("name"),
                parameter.get("nominal"),
                parameter.get("min_value"),
                parameter.get("max_value"),
                parameter.get("unit"),
            ))

        return tuple(signature)

    def set_product(self, product_id):
        product = self.product_manager.get_product(product_id)

        if product is None:
            raise ValueError(
                f"Изделие с ID {product_id} не найдено."
            )

        parameters = (
            self.product_manager.get_product_parameters(product_id)
        )

        if not parameters:
            raise ValueError(
                "У выбранного изделия отсутствуют характеристики."
            )

        signature = self._parameter_signature(parameters)

        self.product_generators[product_id] = ProductGenerator(
            parameters=parameters,
            process_ranges=self.process_ranges,
            process_effect_strength=self.process_effect_strength,
        )

        self.defect_generators[product_id] = DefectGenerator(
            defect_probability=self.defect_probability
        )

        self.product_signatures[product_id] = signature
        self.current_product_id = product_id

        return {
            "product": product,
            "parameters": parameters,
        }

    def _ensure_product_loaded(self, product_id):
        parameters = (
            self.product_manager.get_product_parameters(product_id)
        )

        if not parameters:
            raise ValueError(
                f"У изделия с ID {product_id} отсутствуют характеристики."
            )

        current_signature = self._parameter_signature(parameters)
        saved_signature = self.product_signatures.get(product_id)

        if (
            product_id not in self.product_generators
            or product_id not in self.defect_generators
            or saved_signature != current_signature
        ):
            self.set_product(product_id)

        return (
            self.product_generators[product_id],
            self.defect_generators[product_id],
            parameters,
        )

    # ---------------------------------------------------------
    # ГЕНЕРАЦИЯ ИЗДЕЛИЙ
    # ---------------------------------------------------------

    def generate_item(self, product_id=None):
        if product_id is None:
            product_id = self.current_product_id

        if product_id is None:
            raise ValueError(
                "Не выбрано изделие для симуляции."
            )

        if self.experiment_id is None or self.run_id is None:
            self.start_experiment()

        (
            product_generator,
            defect_generator,
            parameters,
        ) = self._ensure_product_loaded(product_id)

        self.item_counter += 1
        self.run_item_counter += 1

        item_id = self.item_counter

        # 1. Генерация технологических параметров.
        process_parameters = dict(
            product_generator.generate_process_parameters()
        )

        # 2. Прогноз качества ДО генерации измерений.
        ml_prediction = self.predict_quality(
            product_id,
            process_parameters,
        )

        # 3. Генерация измерений с уже заданными
        # технологическими параметрами.
        generated_product = product_generator.generate_product(
            product_id=product_id,
            item_id=item_id,
            process_parameters=process_parameters,
        )

        measurements = dict(
            generated_product["measurements"]
        )

        # 4. Внесение искусственного дефекта.
        defect_result = defect_generator.generate_defect(
            measurements,
            parameters,
        )

        measurements = defect_result["measurements"]

        injected_defects = list(
            defect_result.get("defective_parameters", [])
        )

        # 5. Фактический контроль качества.
        quality_result = self.quality_checker.check_measurements(
            product_id,
            measurements,
        )

        actual_status = str(
            quality_result.get("status", "UNKNOWN")
        ).upper()

        predicted_status = str(
            ml_prediction.get("predicted_status", "UNAVAILABLE")
        ).upper()

        # Сравнение имеет смысл только для GOOD/DEFECT.
        comparison_available = (
            ml_prediction.get("available", False)
            and actual_status in {"GOOD", "DEFECT"}
            and predicted_status in {"GOOD", "DEFECT"}
        )

        prediction_correct = (
            predicted_status == actual_status
            if comparison_available
            else None
        )

        # Для оценки модели исключаем искусственно внесённые дефекты.
        prediction_evaluable = (
            comparison_available
            and not defect_result["has_defect"]
        )

        processed_at = datetime.now().isoformat(
            timespec="seconds"
        )

        # 6. Формирование итогового результата.
        result = dict(quality_result)

        result.update({
            "product_id": product_id,
            "item_id": item_id,

            "measurements": measurements,
            "process_parameters": process_parameters,

            "process_parameter_units": {
                name: limits["unit"]
                for name, limits
                in product_generator.process_ranges.items()
            },

            "process_model": {
                "type": "normalized_linear",
                "effect_strength": self.process_effect_strength,
            },

            "simulated_defect": bool(
                defect_result["has_defect"]
            ),

            "simulated_defective_parameters": injected_defects,
            "injected_defects": injected_defects,

            # Результат предварительного ML-прогноза.
            "ml_prediction": ml_prediction,

            # Фактический результат контроля.
            "actual_status": actual_status,

            # Сравнение прогноза и факта.
            "prediction_comparison_available": comparison_available,
            "prediction_correct": prediction_correct,
            "prediction_evaluable": prediction_evaluable,

            "generated_at": generated_product["generated_at"],
            "processed_at": processed_at,

            "experiment_id": self.experiment_id,
            "experiment_name": self.experiment_name,
            "experiment_started_at": self.experiment_started_at,

            "run_id": self.run_id,
            "run_started_at": self.run_started_at,
            "run_item_number": self.run_item_counter,
        })

        # 7. Сохранение результата.
        self.measurement_logger.log_result(
            result,
            item_id=item_id,
            simulated_defect=defect_result["has_defect"],
            experiment_id=self.experiment_id,
            run_id=self.run_id,
        )

        return result

    # ---------------------------------------------------------
    # ПАРТИЯ ИЗДЕЛИЙ
    # ---------------------------------------------------------

    def generate_batch(self, product_id, count):
        count = int(count)

        if count < 1:
            raise ValueError(
                "Количество изделий должно быть больше нуля."
            )

        results = []

        for _ in range(count):
            results.append(
                self.generate_item(product_id)
            )

        return results

    # ---------------------------------------------------------
    # СТАТИСТИКА
    # ---------------------------------------------------------

    def get_current_run_statistics(self):
        if self.run_id is None:
            return {
                "total": 0,
                "good": 0,
                "defect": 0,
                "unknown": 0,
                "generated_defects": 0,
            }

        statistics = self.measurement_logger.get_statistics(
            run_id=self.run_id
        )

        simulation_statistics = (
            self.measurement_logger.get_simulation_statistics(
                run_id=self.run_id
            )
        )

        statistics["generated_defects"] = (
            simulation_statistics["generated_defects"]
        )

        return statistics

    def get_current_experiment_statistics(self):
        if self.experiment_id is None:
            return {
                "total": 0,
                "good": 0,
                "defect": 0,
                "unknown": 0,
                "generated_defects": 0,
            }

        statistics = self.measurement_logger.get_statistics(
            experiment_id=self.experiment_id
        )

        simulation_statistics = (
            self.measurement_logger.get_simulation_statistics(
                experiment_id=self.experiment_id
            )
        )

        statistics["generated_defects"] = (
            simulation_statistics["generated_defects"]
        )

        return statistics

    # ---------------------------------------------------------
    # СБРОС
    # ---------------------------------------------------------

    def reset(self):
        self.item_counter = 0
        self.run_item_counter = 0

        self.current_product_id = None

        self.product_generators.clear()
        self.defect_generators.clear()
        self.product_signatures.clear()

        self.experiment_id = None
        self.run_id = None

        self.experiment_name = None
        self.experiment_started_at = None
        self.run_started_at = None
