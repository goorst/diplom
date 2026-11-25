
import math


class QualityChecker:
    """
    Проверка качества изделий по характеристикам номенклатуры.

    Контролируются только характеристики, для которых заданы
    минимальное и/или максимальное допустимые значения.

    Характеристики без допусков считаются справочными.
    """

    STATUS_GOOD = "GOOD"
    STATUS_DEFECT = "DEFECT"
    STATUS_UNKNOWN = "UNKNOWN"

    STATUS_GOOD_RU = "ГОДНО"
    STATUS_DEFECT_RU = "БРАК"
    STATUS_INCOMPLETE_RU = "НЕДОСТАТОЧНО ДАННЫХ"

    # Алиасы характеристик для сопоставления измерений.
    ALIASES = {
        "inner_diameter": [
            "inner_diameter",
            "d",
            "внутренний диаметр",
            "диаметр отверстия",
            "диаметр внутренний",
        ],
        "outer_diameter": [
            "outer_diameter",
            "d_outer",
            "D",
            "наружный диаметр",
            "внешний диаметр",
            "диаметр наружный",
        ],
        "width": [
            "width",
            "b",
            "B",
            "ширина",
            "ширина изделия",
        ],
        "radial_clearance": [
            "radial_clearance",
            "clearance",
            "зазор",
            "радиальный зазор",
        ],
        "mass": [
            "mass",
            "weight",
            "Mass approx.",
            "масса",
            "вес",
            "приблизительная масса",
        ],
    }

    def __init__(self, product_manager=None):
        if product_manager is None:
            from application.src.products.product_manager import (
                ProductManager,
            )

            product_manager = ProductManager()

        self.product_manager = product_manager

    # =========================================================
    # ОСНОВНАЯ ПРОВЕРКА ПО ID ИЗДЕЛИЯ
    # =========================================================

    def check_measurements(self, product_id, measurements):
        """
        Загружает изделие и его характеристики из номенклатуры
        и выполняет проверку переданных измерений.
        """

        if product_id is None:
            raise ValueError("Не указан ID изделия.")

        product = self.product_manager.get_product(product_id)

        if product is None:
            raise ValueError(
                f"Изделие с ID {product_id} не найдено."
            )

        parameters = (
            self.product_manager.get_product_parameters(product_id)
        )

        if measurements is None:
            measurements = {}

        if not isinstance(measurements, dict):
            raise TypeError(
                "Измерения должны быть представлены словарём."
            )

        checked_parameters = []
        skipped_parameters = []
        defects = []

        controlled_count = 0

        for parameter in parameters:
            minimum = self._to_float(
                parameter.get("min_value")
            )
            maximum = self._to_float(
                parameter.get("max_value")
            )

            # Нет допусков — справочная характеристика.
            if minimum is None and maximum is None:
                skipped_parameters.append({
                    "parameter": parameter.get("name", ""),
                    "code": parameter.get("code", ""),
                    "status": "NOT_CONTROLLED",
                    "message": "Допуски не заданы",
                })
                continue

            controlled_count += 1

            result = self._check_parameter(
                parameter,
                measurements,
            )

            if result["status"] == self.STATUS_DEFECT:
                checked_parameters.append(result)
                defects.append(result)

            elif result["status"] == self.STATUS_GOOD:
                checked_parameters.append(result)

            else:
                skipped_parameters.append(result)

        # Определяем итоговый статус.
        if defects:
            overall_status = self.STATUS_DEFECT

        elif controlled_count == 0:
            overall_status = self.STATUS_UNKNOWN

        elif len(checked_parameters) != controlled_count:
            overall_status = self.STATUS_UNKNOWN

        else:
            overall_status = self.STATUS_GOOD

        return {
            "product_id": product_id,
            "product_name": product.get("name", ""),
            "article": product.get("article", ""),

            "status": overall_status,
            "is_good": overall_status == self.STATUS_GOOD,
            "is_defect": overall_status == self.STATUS_DEFECT,

            "controlled_count": controlled_count,
            "checked_count": len(checked_parameters),
            "defect_count": len(defects),
            "skipped_count": len(skipped_parameters),

            "checked_parameters": checked_parameters,
            "skipped_parameters": skipped_parameters,

            "defects": defects,
            "measurements": measurements,
        }

    # =========================================================
    # ПРОВЕРКА ОДНОЙ ХАРАКТЕРИСТИКИ
    # =========================================================

    def _check_parameter(self, parameter, measurements):
        name = parameter.get("name", "Неизвестный параметр")
        code = parameter.get("code", "")
        unit = parameter.get("unit", "")

        minimum = self._to_float(
            parameter.get("min_value")
        )
        maximum = self._to_float(
            parameter.get("max_value")
        )
        nominal = self._to_float(
            parameter.get("nominal")
        )

        measured = self._find_measurement(
            parameter,
            measurements,
        )

        result = {
            "parameter": name,
            "name": name,
            "code": code,
            "unit": unit,

            "measured": measured,
            "measured_value": measured,

            "nominal": nominal,
            "min_value": minimum,
            "max_value": maximum,

            "deviation": (
                measured - nominal
                if measured is not None and nominal is not None
                else None
            ),

            "status": self.STATUS_UNKNOWN,
            "defect_type": "",
            "message": "",
        }

        # Нет измерения.
        if measured is None:
            result["message"] = "Измерение отсутствует"
            return result

        # Некорректный диапазон.
        if (
            minimum is not None
            and maximum is not None
            and minimum > maximum
        ):
            result["message"] = (
                "Ошибка номенклатуры: минимум больше максимума"
            )
            return result

        # Проверка нижней границы.
        if minimum is not None and measured < minimum:
            result["status"] = self.STATUS_DEFECT
            result["defect_type"] = "BELOW_MINIMUM"
            result["message"] = (
                f"Значение ниже минимума: {minimum} {unit}"
            )
            return result

        # Проверка верхней границы.
        if maximum is not None and measured > maximum:
            result["status"] = self.STATUS_DEFECT
            result["defect_type"] = "ABOVE_MAXIMUM"
            result["message"] = (
                f"Значение выше максимума: {maximum} {unit}"
            )
            return result

        result["status"] = self.STATUS_GOOD
        result["message"] = "Значение в допустимых пределах"

        return result

    # =========================================================
    # ПОИСК ИЗМЕРЕНИЯ
    # =========================================================

    @classmethod
    def _find_measurement(cls, parameter, measurements):
        """
        Ищет измерение сначала по точному коду и названию,
        затем по известным алиасам.

        Точное сопоставление важно для различения d и D.
        """

        code = str(parameter.get("code") or "").strip()
        name = str(parameter.get("name") or "").strip()

        # Сначала точное совпадение ключей.
        for candidate in (code, name):
            if candidate and candidate in measurements:
                value = measurements[candidate]

                if isinstance(value, dict):
                    value = value.get("value")

                return cls._to_float(value)

        # Определяем группу алиасов.
        alias_group = cls._get_alias_group(code, name)

        if alias_group:
            for alias in alias_group:
                if alias in measurements:
                    value = measurements[alias]

                    if isinstance(value, dict):
                        value = value.get("value")

                    return cls._to_float(value)

        # Резервный поиск без учёта регистра и разделителей.
        normalized_measurements = {}

        for key, value in measurements.items():
            normalized_key = cls._normalize_key(key)

            if normalized_key not in normalized_measurements:
                normalized_measurements[normalized_key] = value

        candidates = [code, name]

        if alias_group:
            candidates.extend(alias_group)

        for candidate in candidates:
            if not candidate:
                continue

            # Однобуквенные обозначения d и D регистрозависимы.
            # Их нельзя искать через нормализацию, иначе d и D
            # превращаются в один и тот же ключ.
            if candidate in {"d", "D"}:
                continue

            key = cls._normalize_key(candidate)

            if key not in normalized_measurements:
                continue

            value = normalized_measurements[key]

            if isinstance(value, dict):
                value = value.get("value")

            return cls._to_float(value)

        return None

    @classmethod
    def _get_alias_group(cls, code, name):
        """
        Определяет алиасы характеристики.

        Для кодов d и D используется точное сравнение,
        поскольку это разные размеры подшипника.
        """

        # Коды d и D различаются регистром.
        if code == "d":
            return cls.ALIASES["inner_diameter"]

        if code == "D":
            return cls.ALIASES["outer_diameter"]

        if code == "B":
            return cls.ALIASES["width"]

        normalized_code = cls._normalize_key(code)
        normalized_name = cls._normalize_key(name)

        # Сначала проверяем название, чтобы русские названия
        # не перепутались из-за похожих кодов.
        for group_name, aliases in cls.ALIASES.items():
            normalized_aliases = {
                cls._normalize_key(alias)
                for alias in aliases
            }

            if normalized_name and normalized_name in normalized_aliases:
                return aliases

        for group_name, aliases in cls.ALIASES.items():
            normalized_aliases = {
                cls._normalize_key(alias)
                for alias in aliases
            }

            if normalized_code and normalized_code in normalized_aliases:
                return aliases

        return []

    @staticmethod
    def _normalize_key(value):
        return (
            str(value or "")
            .strip()
            .lower()
            .replace(" ", "")
            .replace("_", "")
            .replace("-", "")
        )

    # =========================================================
    # ПРЕОБРАЗОВАНИЕ ЧИСЕЛ
    # =========================================================

    @staticmethod
    def _to_float(value):
        if value is None or isinstance(value, bool):
            return None

        try:
            if isinstance(value, str):
                value = value.strip().replace(",", ".")

                if not value:
                    return None

            result = float(value)

            # NaN и бесконечности не являются допустимыми измерениями.
            if not math.isfinite(result):
                return None

            return result

        except (ValueError, TypeError, OverflowError):
            return None

    # =========================================================
    # СТАРЫЙ ИНТЕРФЕЙС ДЛЯ СОВМЕСТИМОСТИ
    # =========================================================

    def check_product(self, product, parameters, measurements):
        """
        Проверяет изделие по переданным данным.

        Сохраняет совместимость со старым интерфейсом.
        """

        product = product or {}
        parameters = parameters or []
        measurements = measurements or {}

        checked = []
        skipped = []
        defects = []

        controlled_count = 0

        for parameter in parameters:
            minimum = self._to_float(
                parameter.get("min_value")
            )
            maximum = self._to_float(
                parameter.get("max_value")
            )

            if minimum is None and maximum is None:
                skipped.append({
                    "parameter": parameter.get("name", ""),
                    "status": "NOT_CONTROLLED",
                    "message": "Допуски не заданы",
                })
                continue

            controlled_count += 1

            result = self._check_parameter(
                parameter,
                measurements,
            )

            if result["status"] == self.STATUS_UNKNOWN:
                skipped.append(result)
            else:
                checked.append(result)

            if result["status"] == self.STATUS_DEFECT:
                defects.append(result)

        if defects:
            status = self.STATUS_DEFECT_RU
        elif controlled_count == 0 or len(checked) != controlled_count:
            status = self.STATUS_INCOMPLETE_RU
        else:
            status = self.STATUS_GOOD_RU

        return {
            "product_id": product.get("id"),
            "product_name": product.get("name", ""),
            "article": product.get("article", ""),

            "status": status,
            "is_good": status == self.STATUS_GOOD_RU,
            "is_defect": status == self.STATUS_DEFECT_RU,

            "checked_count": len(checked),
            "defect_count": len(defects),
            "unchecked_count": len(skipped),
            "total_parameters": len(parameters),

            "results": checked + skipped,
            "defects": defects,
            "unchecked": skipped,
        }

    # =========================================================
    # ПРОВЕРКА ПАРТИИ
    # =========================================================

    def check_batch(self, products_data):
        reports = []

        good_count = 0
        defect_count = 0
        incomplete_count = 0

        for item in products_data:
            report = self.check_product(
                product=item.get("product", {}),
                parameters=item.get("parameters", []),
                measurements=item.get("measurements", {}),
            )

            reports.append(report)

            if report["status"] == self.STATUS_GOOD_RU:
                good_count += 1
            elif report["status"] == self.STATUS_DEFECT_RU:
                defect_count += 1
            else:
                incomplete_count += 1

        total_count = len(reports)

        return {
            "total_count": total_count,
            "good_count": good_count,
            "defect_count": defect_count,
            "incomplete_count": incomplete_count,
            "reports": reports,
            "quality_percent": (
                good_count / total_count * 100
                if total_count else 0
            ),
        }
