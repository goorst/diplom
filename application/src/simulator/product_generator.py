
import random
from datetime import datetime


class ProductGenerator:
    """
    Универсальный генератор измерений изделий.

    Генерирует измерения только для характеристик,
    у которых задан хотя бы один предел допуска.

    Не зависит от конкретного типа изделия.
    Все параметры получает из ProductManager.
    """

    def __init__(self, parameters, random_seed=None):
        self.parameters = list(parameters or [])
        self.rng = random.Random(random_seed)

        self.controlled_parameters = [
            parameter
            for parameter in self.parameters
            if self._to_float(parameter.get("min_value")) is not None
            or self._to_float(parameter.get("max_value")) is not None
        ]

        if not self.controlled_parameters:
            raise ValueError(
                "Для генерации измерений необходимы характеристики "
                "с заданными допусками"
            )

    @staticmethod
    def _to_float(value):
        if value is None:
            return None

        try:
            return float(str(value).replace(",", "."))
        except (ValueError, TypeError):
            return None

    def _get_nominal(self, parameter):
        nominal = self._to_float(parameter.get("nominal"))
        minimum = self._to_float(parameter.get("min_value"))
        maximum = self._to_float(parameter.get("max_value"))

        if nominal is not None:
            return nominal

        if minimum is not None and maximum is not None:
            return (minimum + maximum) / 2

        if minimum is not None:
            return minimum

        if maximum is not None:
            return maximum

        return None

    def _generate_value(self, parameter):
        nominal = self._get_nominal(parameter)
        minimum = self._to_float(parameter.get("min_value"))
        maximum = self._to_float(parameter.get("max_value"))

        if nominal is None:
            return None

        # Двусторонний допуск.
        if minimum is not None and maximum is not None:
            if minimum > maximum:
                raise ValueError(
                    f"Некорректный допуск для характеристики "
                    f"{parameter.get('code')}: минимум больше максимума"
                )

            tolerance = maximum - minimum
            sigma = max(tolerance / 6, 0.000001)

            value = self.rng.gauss(nominal, sigma)
            value = max(minimum, min(maximum, value))

        # Только нижняя граница.
        elif minimum is not None:
            tolerance = max(abs(nominal - minimum), abs(nominal) * 0.001, 0.001)
            sigma = tolerance / 6

            value = self.rng.gauss(nominal, sigma)
            value = max(minimum, value)

        # Только верхняя граница.
        elif maximum is not None:
            tolerance = max(abs(maximum - nominal), abs(nominal) * 0.001, 0.001)
            sigma = tolerance / 6

            value = self.rng.gauss(nominal, sigma)
            value = min(maximum, value)

        else:
            return None

        return round(value, 6)

    def generate_measurements(self):
        measurements = {}

        for parameter in self.controlled_parameters:
            code = parameter.get("code") or parameter.get("name")

            if not code:
                continue

            value = self._generate_value(parameter)

            if value is not None:
                measurements[code] = value

        return measurements

    def generate_product(self, product_id=None, item_id=None):
        return {
            "product_id": product_id,
            "item_id": item_id,
            "measurements": self.generate_measurements(),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }
