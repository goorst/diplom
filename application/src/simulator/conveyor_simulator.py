from datetime import datetime
from uuid import uuid4

from application.src.products.product_manager import ProductManager
from application.src.quality.quality_checker import QualityChecker
from application.src.core.measurement_logger import MeasurementLogger

from .product_generator import ProductGenerator
from .defect_generator import DefectGenerator


class ConveyorSimulator:
    """
    Универсальный симулятор производственного процесса.

    Последовательность обработки:

    1. Получение характеристик изделия из номенклатуры.
    2. Генерация измерений.
    3. Внесение искусственного дефекта.
    4. Контроль качества.
    5. Сохранение результата.
    6. Привязка результата к эксперименту и запуску.
    """

    def __init__(
        self,
        product_manager=None,
        quality_checker=None,
        measurement_logger=None,
        defect_probability=0.15,
    ):
        self.product_manager = (
            product_manager or ProductManager()
        )

        self.quality_checker = (
            quality_checker
            or QualityChecker(
                product_manager=self.product_manager
            )
        )

        self.measurement_logger = (
            measurement_logger or MeasurementLogger()
        )

        self.defect_probability = max(
            0.0,
            min(1.0, float(defect_probability)),
        )

        # Генераторы хранятся отдельно для каждого изделия.
        self.product_generators = {}
        self.defect_generators = {}

        # Сигнатуры позволяют обнаруживать изменение допусков.
        self.product_signatures = {}

        # Счётчики.
        self.item_counter = 0
        self.run_item_counter = 0

        self.current_product_id = None

        # Идентификаторы эксперимента и запуска.
        self.experiment_id = None
        self.run_id = None

        self.experiment_name = None
        self.experiment_started_at = None
        self.run_started_at = None

    # ---------------------------------------------------------
    # ЭКСПЕРИМЕНТЫ
    # ---------------------------------------------------------

    def start_experiment(self, name=None):
        """
        Начинает новый эксперимент.

        Один эксперимент может содержать несколько запусков.
        Результаты всех запусков будут иметь общий experiment_id.

        Возвращает идентификатор эксперимента.
        """

        self.experiment_id = str(uuid4())
        self.experiment_name = (
            name or f"Эксперимент {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

        self.experiment_started_at = (
            datetime.now().isoformat(timespec="seconds")
        )

        self.run_id = None
        self.run_started_at = None
        self.run_item_counter = 0

        # Первый запуск создаётся автоматически.
        self.start_run()

        return self.experiment_id

    def start_run(self):
        """
        Начинает новый запуск текущего эксперимента.

        Все изделия, произведённые после вызова этого метода,
        получают новый run_id.
        """

        if self.experiment_id is None:
            self.start_experiment()

        self.run_id = str(uuid4())

        self.run_started_at = (
            datetime.now().isoformat(timespec="seconds")
        )

        self.run_item_counter = 0

        return self.run_id

    def get_experiment_info(self):
        """Возвращает сведения о текущем эксперименте и запуске."""

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
        """
        Формирует сигнатуру характеристик.

        Если изменились номиналы или допуски, сигнатура изменится,
        и генераторы будут пересозданы.
        """

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
        """
        Выбирает изделие и загружает его характеристики.
        """

        product = self.product_manager.get_product(
            product_id
        )

        if product is None:
            raise ValueError(
                f"Изделие с ID {product_id} не найдено."
            )

        parameters = (
            self.product_manager.get_product_parameters(
                product_id
            )
        )

        if not parameters:
            raise ValueError(
                "У выбранного изделия отсутствуют характеристики."
            )

        signature = self._parameter_signature(parameters)

        # Создаём генераторы с актуальными характеристиками.
        self.product_generators[product_id] = (
            ProductGenerator(parameters)
        )

        self.defect_generators[product_id] = (
            DefectGenerator(
                defect_probability=self.defect_probability
            )
        )

        self.product_signatures[product_id] = signature

        self.current_product_id = product_id

        return {
            "product": product,
            "parameters": parameters,
        }

    def _ensure_product_loaded(self, product_id):
        """
        Проверяет наличие генераторов и актуальность параметров.
        """

        parameters = (
            self.product_manager.get_product_parameters(
                product_id
            )
        )

        if not parameters:
            raise ValueError(
                f"У изделия с ID {product_id} отсутствуют характеристики."
            )

        current_signature = self._parameter_signature(
            parameters
        )

        saved_signature = self.product_signatures.get(
            product_id
        )

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
        """
        Генерирует одно изделие и выполняет контроль качества.

        Каждое изделие получает:
        - item_id;
        - experiment_id;
        - run_id;
        - измерения;
        - сведения об искусственно внесённых дефектах;
        - результат контроля.
        """

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

        # 1. Генерация нормальных измерений.
        generated_product = (
            product_generator.generate_product(
                product_id=product_id,
                item_id=item_id,
            )
        )

        # 2. Внесение искусственного дефекта.
        defect_result = defect_generator.generate_defect(
            generated_product["measurements"],
            parameters,
        )

        measurements = defect_result["measurements"]

        injected_defects = list(
            defect_result.get(
                "defective_parameters",
                [],
            )
        )

        # 3. Контроль качества.
        quality_result = (
            self.quality_checker.check_measurements(
                product_id,
                measurements,
            )
        )

        # 4. Формирование итогового результата.
        result = dict(quality_result)

        processed_at = (
            datetime.now().isoformat(timespec="seconds")
        )

        result.update({
            "product_id": product_id,
            "item_id": item_id,
            "measurements": measurements,

            # Фактически внесённый симулятором дефект.
            "simulated_defect": bool(
                defect_result["has_defect"]
            ),

            "simulated_defective_parameters": injected_defects,

            # Единое поле для MeasurementLogger.
            "injected_defects": injected_defects,

            "generated_at": generated_product["generated_at"],
            "processed_at": processed_at,

            # Принадлежность к эксперименту.
            "experiment_id": self.experiment_id,
            "experiment_name": self.experiment_name,
            "experiment_started_at": self.experiment_started_at,

            # Принадлежность к запуску.
            "run_id": self.run_id,
            "run_started_at": self.run_started_at,
            "run_item_number": self.run_item_counter,
        })

        # 5. Сохранение результата.
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
        """
        Генерирует партию изделий.

        Все изделия партии относятся к одному запуску,
        если между вызовами не вызывался start_run().
        """

        count = int(count)

        if count < 1:
            raise ValueError(
                "Количество изделий должно быть больше нуля."
            )

        results = []

        for _ in range(count):
            result = self.generate_item(product_id)
            results.append(result)

        return results

    # ---------------------------------------------------------
    # СТАТИСТИКА
    # ---------------------------------------------------------

    def get_current_run_statistics(self):
        """Возвращает статистику текущего запуска."""

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
        """Возвращает статистику всех запусков эксперимента."""

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
        """
        Сбрасывает счётчики и текущий выбор.

        История измерений в базе данных не удаляется.
        """

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