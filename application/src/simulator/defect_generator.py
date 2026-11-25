import random


class DefectGenerator:
    """
    Универсальный генератор дефектов изделий.

    Использует минимальные и максимальные значения
    характеристик из номенклатуры.
    """

    def __init__(
        self,
        defect_probability=0.15,
        random_seed=None,
        min_deviation=0.1,
        max_deviation=0.8,
    ):
        self.rng = random.Random(random_seed)

        self.defect_probability = max(
            0.0,
            min(1.0, float(defect_probability)),
        )

        self.min_deviation = max(0.01, float(min_deviation))
        self.max_deviation = max(
            self.min_deviation,
            float(max_deviation),
        )

    @staticmethod
    def _to_float(value):
        if value is None:
            return None

        try:
            return float(str(value).replace(",", "."))
        except (ValueError, TypeError):
            return None

    def _get_defect_value(self, parameter):
        minimum = self._to_float(parameter.get("min_value"))
        maximum = self._to_float(parameter.get("max_value"))
        nominal = self._to_float(parameter.get("nominal"))

        if minimum is None and maximum is None:
            return None

        if minimum is not None and maximum is not None:
            tolerance = maximum - minimum

        elif nominal is not None and minimum is not None:
            tolerance = abs(nominal - minimum) * 2

        elif nominal is not None and maximum is not None:
            tolerance = abs(maximum - nominal) * 2

        else:
            return None

        tolerance = max(abs(tolerance), 0.001)

        deviation = tolerance * self.rng.uniform(
            self.min_deviation,
            self.max_deviation,
        )

        if minimum is not None and maximum is not None:
            side = self.rng.choice(["below", "above"])

        elif minimum is not None:
            side = "below"

        else:
            side = "above"

        if side == "below":
            return round(minimum - deviation, 6)

        return round(maximum + deviation, 6)

    def generate_defect(self, measurements, parameters):
        """
        С вероятностью defect_probability вносит
        дефект в одну из характеристик.

        Возвращает:
        {
            "measurements": изменённые измерения,
            "has_defect": bool,
            "defective_parameters": [...]
        }
        """

        result = dict(measurements)

        if self.rng.random() >= self.defect_probability:
            return {
                "measurements": result,
                "has_defect": False,
                "defective_parameters": [],
            }

        available_parameters = []

        for parameter in parameters:
            code = (
                parameter.get("code")
                or parameter.get("name")
            )

            if not code or code not in result:
                continue

            minimum = self._to_float(parameter.get("min_value"))
            maximum = self._to_float(parameter.get("max_value"))

            if minimum is None and maximum is None:
                continue

            available_parameters.append(parameter)

        if not available_parameters:
            return {
                "measurements": result,
                "has_defect": False,
                "defective_parameters": [],
            }

        # В базовом сценарии вносим один дефект.
        selected_parameter = self.rng.choice(
            available_parameters
        )

        code = (
            selected_parameter.get("code")
            or selected_parameter.get("name")
        )

        defective_value = self._get_defect_value(
            selected_parameter
        )

        if defective_value is None:
            return {
                "measurements": result,
                "has_defect": False,
                "defective_parameters": [],
            }

        result[code] = defective_value

        return {
            "measurements": result,
            "has_defect": True,
            "defective_parameters": [code],
        }

    def generate_batch_defects(self, products, parameters):
        """
        Вносит дефекты в список уже сгенерированных изделий.
        """

        results = []

        for product in products:
            defect_result = self.generate_defect(
                product.get("measurements", {}),
                parameters,
            )

            updated_product = dict(product)
            updated_product.update(defect_result)

            results.append(updated_product)

        return results