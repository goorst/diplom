
import hashlib
import math
import random

from datetime import datetime


class ProductGenerator:
    """
    Универсальный генератор измерений изделий.

    Генерирует:
    1. Технологические параметры обработки.
    2. Базовые значения измеряемых характеристик.
    3. Отклонения характеристик под влиянием технологических параметров.

    Характеристики и допуски получает из ProductManager.

    Модель влияния технологических параметров является
    экспериментальной симуляционной моделью.
    Ее коэффициенты не являются физически откалиброванными
    характеристиками станка.
    """

    DEFAULT_PROCESS_RANGES = {
        "cutting_speed": {
            "min": 80.0,
            "max": 160.0,
            "unit": "m/min",
        },
        "feed_rate": {
            "min": 0.08,
            "max": 0.25,
            "unit": "mm/rev",
        },
        "depth_of_cut": {
            "min": 0.5,
            "max": 2.0,
            "unit": "mm",
        },
        "tool_wear": {
            "min": 0.0,
            "max": 1.0,
            "unit": "normalized",
        },
        "vibration": {
            "min": 0.0,
            "max": 1.0,
            "unit": "normalized",
        },
    }

    def __init__(
        self,
        parameters,
        random_seed=None,
        process_ranges=None,
        process_effect_strength=0.25,
    ):
        self.parameters = list(parameters or [])
        self.rng = random.Random(random_seed)

        self.process_ranges = self._prepare_process_ranges(
            process_ranges
        )

        self.process_effect_strength = max(
            0.0,
            float(process_effect_strength),
        )

        self.controlled_parameters = [
            parameter
            for parameter in self.parameters
            if (
                self._to_float(parameter.get("min_value")) is not None
                or self._to_float(parameter.get("max_value")) is not None
            )
        ]

        if not self.controlled_parameters:
            raise ValueError(
                "Для генерации измерений необходимы характеристики "
                "с заданными допусками"
            )

    # ---------------------------------------------------------
    # ПОДГОТОВКА ДАННЫХ
    # ---------------------------------------------------------

    @staticmethod
    def _to_float(value):
        if value is None:
            return None

        try:
            result = float(
                str(value).replace(",", ".")
            )

            if not math.isfinite(result):
                return None

            return result

        except (ValueError, TypeError):
            return None

    def _prepare_process_ranges(self, custom_ranges):
        ranges = {
            key: dict(value)
            for key, value in self.DEFAULT_PROCESS_RANGES.items()
        }

        if custom_ranges:
            for key, value in custom_ranges.items():
                if key not in ranges:
                    continue

                if not isinstance(value, dict):
                    continue

                ranges[key].update(value)

        prepared = {}

        for key, value in ranges.items():
            minimum = self._to_float(
                value.get("min")
            )

            maximum = self._to_float(
                value.get("max")
            )

            if minimum is None or maximum is None:
                raise ValueError(
                    f"Некорректный диапазон параметра {key}"
                )

            if minimum >= maximum:
                raise ValueError(
                    f"Минимум должен быть меньше максимума: {key}"
                )

            prepared[key] = {
                "min": minimum,
                "max": maximum,
                "unit": value.get("unit", ""),
            }

        return prepared

    # ---------------------------------------------------------
    # ГЕНЕРАЦИЯ ТЕХНОЛОГИЧЕСКИХ ПАРАМЕТРОВ
    # ---------------------------------------------------------

    def generate_process_parameters(self):
        """
        Генерирует набор технологических параметров.
        """

        result = {}

        for name, limits in self.process_ranges.items():
            result[name] = round(
                self.rng.uniform(
                    limits["min"],
                    limits["max"],
                ),
                6,
            )

        return result

    # ---------------------------------------------------------
    # НОРМИРОВАНИЕ ТЕХНОЛОГИЧЕСКИХ ПАРАМЕТРОВ
    # ---------------------------------------------------------

    def _normalize_process_parameters(self, process_parameters):
        """
        Переводит параметры в диапазон [-1; 1].

        0 — середина диапазона.
        -1 — нижняя граница.
        +1 — верхняя граница.
        """

        normalized = {}

        for name, limits in self.process_ranges.items():
            value = self._to_float(
                process_parameters.get(name)
            )

            if value is None:
                continue

            minimum = limits["min"]
            maximum = limits["max"]

            center = (minimum + maximum) / 2
            half_range = (maximum - minimum) / 2

            normalized[name] = max(
                -1.0,
                min(
                    1.0,
                    (value - center) / half_range,
                ),
            )

        return normalized

    # ---------------------------------------------------------
    # МОДЕЛЬ ВЛИЯНИЯ ТЕХНОЛОГИЧЕСКИХ ПАРАМЕТРОВ
    # ---------------------------------------------------------

    @staticmethod
    def _get_stable_coefficient(
        parameter_code,
        process_name,
    ):
        """
        Получает стабильный коэффициент влияния.

        Коэффициент зависит от названия характеристики
        и технологического параметра.
        """

        source = f"{parameter_code}:{process_name}"

        digest = hashlib.sha256(
            source.encode("utf-8")
        ).hexdigest()

        integer_value = int(
            digest[:8],
            16,
        )

        normalized = integer_value / 0xFFFFFFFF

        return (normalized * 2.0) - 1.0

    def _get_process_effect(
        self,
        parameter,
        process_parameters,
    ):
        """
        Рассчитывает смещение характеристики.

        Результат выражен в долях ширины допуска.
        """

        if self.process_effect_strength == 0:
            return 0.0

        code = (
            parameter.get("code")
            or parameter.get("name")
        )

        if not code:
            return 0.0

        normalized = self._normalize_process_parameters(
            process_parameters
        )

        if not normalized:
            return 0.0

        weighted_effect = 0.0

        for process_name, process_value in normalized.items():
            coefficient = self._get_stable_coefficient(
                str(code),
                process_name,
            )

            weighted_effect += (
                coefficient * process_value
            )

        effect = (
            weighted_effect
            / math.sqrt(len(normalized))
        )

        return effect * self.process_effect_strength

    # ---------------------------------------------------------
    # НОМИНАЛЬНЫЕ ЗНАЧЕНИЯ И ДОПУСКИ
    # ---------------------------------------------------------

    def _get_nominal(self, parameter):
        nominal = self._to_float(
            parameter.get("nominal")
        )

        minimum = self._to_float(
            parameter.get("min_value")
        )

        maximum = self._to_float(
            parameter.get("max_value")
        )

        if nominal is not None:
            return nominal

        if minimum is not None and maximum is not None:
            return (minimum + maximum) / 2

        if minimum is not None:
            return minimum

        if maximum is not None:
            return maximum

        return None

    def _get_generation_center(self, parameter):
        """
        Определяет центр базового распределения.

        Если заданы обе границы допуска, используется
        середина допустимого интервала.

        Если задана только одна граница, используется
        номинальное значение.

        Номинал в номенклатуре при этом не изменяется.
        """

        minimum = self._to_float(
            parameter.get("min_value")
        )

        maximum = self._to_float(
            parameter.get("max_value")
        )

        if (
            minimum is not None
            and maximum is not None
        ):
            if minimum > maximum:
                raise ValueError(
                    f"Некорректный допуск для характеристики "
                    f"{parameter.get('code')}: минимум больше максимума"
                )

            return (minimum + maximum) / 2

        return self._get_nominal(parameter)

    def _get_tolerance_scale(self, parameter, center):
        """
        Определяет масштаб отклонения характеристики.

        Для двухстороннего допуска используется ширина допуска.
        Для одностороннего — расстояние от центра до границы.
        """

        minimum = self._to_float(
            parameter.get("min_value")
        )

        maximum = self._to_float(
            parameter.get("max_value")
        )

        if (
            minimum is not None
            and maximum is not None
        ):
            return maximum - minimum

        if minimum is not None:
            return max(
                abs(center - minimum) * 2,
                abs(center) * 0.001,
                0.001,
            )

        if maximum is not None:
            return max(
                abs(maximum - center) * 2,
                abs(center) * 0.001,
                0.001,
            )

        return None

    # ---------------------------------------------------------
    # ГЕНЕРАЦИЯ ОДНОГО ИЗМЕРЕНИЯ
    # ---------------------------------------------------------

    def _generate_value(
        self,
        parameter,
        process_parameters,
    ):
        minimum = self._to_float(
            parameter.get("min_value")
        )

        maximum = self._to_float(
            parameter.get("max_value")
        )

        center = self._get_generation_center(
            parameter
        )

        if center is None:
            return None

        if (
            minimum is not None
            and maximum is not None
            and minimum > maximum
        ):
            raise ValueError(
                f"Некорректный допуск для характеристики "
                f"{parameter.get('code')}: минимум больше максимума"
            )

        tolerance_scale = self._get_tolerance_scale(
            parameter,
            center,
        )

        if tolerance_scale is None:
            return None

        tolerance_scale = max(
            abs(tolerance_scale),
            0.001,
        )

        # -----------------------------------------------------
        # 1. Базовое случайное отклонение
        # -----------------------------------------------------

        sigma = tolerance_scale / 6

        base_value = self.rng.gauss(
            center,
            sigma,
        )

        # Не обрезаем базовое значение по допускам.
        # Выход за границы будет определяться фактическим
        # результатом генерации и QualityChecker.

        # -----------------------------------------------------
        # 2. Влияние технологических параметров
        # -----------------------------------------------------

        process_effect = self._get_process_effect(
            parameter,
            process_parameters,
        )

        process_deviation = (
            process_effect * tolerance_scale
        )

        # -----------------------------------------------------
        # 3. Итоговое измерение
        # -----------------------------------------------------

        result = base_value + process_deviation

        return round(
            result,
            6,
        )

    # ---------------------------------------------------------
    # ГЕНЕРАЦИЯ НАБОРА ИЗМЕРЕНИЙ
    # ---------------------------------------------------------

    def generate_measurements(
        self,
        process_parameters=None,
    ):
        """
        Генерирует измерения с учетом технологических режимов.
        """

        if process_parameters is None:
            process_parameters = (
                self.generate_process_parameters()
            )

        measurements = {}

        for parameter in self.controlled_parameters:
            code = (
                parameter.get("code")
                or parameter.get("name")
            )

            if not code:
                continue

            value = self._generate_value(
                parameter,
                process_parameters,
            )

            if value is not None:
                measurements[code] = value

        return measurements

    # ---------------------------------------------------------
    # ГЕНЕРАЦИЯ ИЗДЕЛИЯ
    # ---------------------------------------------------------

    def generate_product(
        self,
        product_id=None,
        item_id=None,
        process_parameters=None,
    ):
        """
        Генерирует полную запись изделия.
        """

        if process_parameters is None:
            process_parameters = (
                self.generate_process_parameters()
            )
        else:
            process_parameters = dict(
                process_parameters
            )

        measurements = self.generate_measurements(
            process_parameters
        )

        return {
            "product_id": product_id,
            "item_id": item_id,
            "measurements": measurements,
            "process_parameters": process_parameters,
            "generated_at": datetime.now().isoformat(
                timespec="seconds"
            ),
        }
