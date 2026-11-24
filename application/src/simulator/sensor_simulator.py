import random
import threading

from datetime import datetime

from .fault_simulator import FaultSimulator


class SensorSimulator:

    def __init__(self):

        self.lock = threading.RLock()

        self.rng = random.Random()

        # Текущая деталь
        self.product = {
            "product_id": None,
            "part_type": "Вал",
            "material": "Сталь",
            "operation": "Черновая обработка",
            "tool_id": "TOOL-001"
        }

        # Режимы обработки
        self.parameters = {
            "spindle_speed": 1800.0,
            "feed_rate": 200.0,
            "cutting_depth": 1.5
        }

        # Неисправности
        self.active_faults = []

        # Состояние инструмента
        self.tool_wear = 0.0

        # Счётчик измерений
        self.counter = 0

        # Материалы и их условные коэффициенты
        self.material_coefficients = {
            "Алюминий": 0.7,
            "Сталь": 1.0,
            "Титан": 1.5,
            "Нержавеющая сталь": 1.25
        }

    # ==================================
    # ВЫБОР ИЗДЕЛИЯ
    # ==================================

    def set_product(self, product):

        with self.lock:

            self.product.update(product)

    # ==================================
    # УСТАНОВКА РЕЖИМОВ ОБРАБОТКИ
    # ==================================

    def set_parameters(self, parameters):

        allowed = {
            "spindle_speed",
            "feed_rate",
            "cutting_depth"
        }

        with self.lock:

            for key, value in parameters.items():

                if key not in allowed:
                    continue

                value = float(value)

                if value <= 0:
                    raise ValueError(
                        f"Некорректное значение параметра {key}"
                    )

                self.parameters[key] = value

    # ==================================
    # УПРАВЛЕНИЕ НЕИСПРАВНОСТЯМИ
    # ==================================

    def set_faults(self, faults):

        with self.lock:

            unknown = set(faults) - set(
                FaultSimulator.AVAILABLE_FAULTS
            )

            if unknown:
                raise ValueError(
                    f"Неизвестные неисправности: {unknown}"
                )

            self.active_faults = list(faults)

    # ==================================
    # СБРОС ИЗНОСА ИНСТРУМЕНТА
    # ==================================

    def reset_tool(self):

        with self.lock:

            self.tool_wear = 0.0

    # ==================================
    # ГЕНЕРАЦИЯ ОДНОГО ИЗМЕРЕНИЯ
    # ==================================

    def generate_measurement(self):

        with self.lock:

            self.counter += 1

            speed = self.parameters["spindle_speed"]

            feed = self.parameters["feed_rate"]

            depth = self.parameters["cutting_depth"]

            material = self.product["material"]

            coefficient = self.material_coefficients.get(
                material,
                1.0
            )

            # Постепенный износ инструмента
            self.tool_wear = min(
                100.0,
                self.tool_wear + 0.015 * coefficient
            )

            # Расчёт условной температуры
            temperature = (
                30
                + speed * 0.012
                + feed * 0.035
                + depth * 8
            ) * coefficient

            # Расчёт вибрации
            vibration = (
                0.4
                + feed * 0.002
                + depth * 0.15
                + self.tool_wear * 0.006
            )

            # Нагрузка шпинделя
            spindle_load = (
                15
                + feed * 0.08
                + depth * 8
            ) * coefficient

            # Добавление случайного шума
            temperature += self.rng.gauss(0, 1.2)

            vibration += self.rng.gauss(0, 0.08)

            spindle_load += self.rng.gauss(0, 1.5)

            # Формирование измерения
            data = {
                "timestamp": datetime.now().isoformat(
                    timespec="seconds"
                ),

                "measurement_id": self.counter,

                "product_id": self.product["product_id"],

                "part_type": self.product["part_type"],

                "material": material,

                "operation": self.product["operation"],

                "tool_id": self.product["tool_id"],

                "spindle_speed": speed,

                "feed_rate": feed,

                "cutting_depth": depth,

                "temperature": temperature,

                "vibration": max(0, vibration),

                "spindle_load": max(0, spindle_load),

                "tool_wear": self.tool_wear
            }

            # Имитация неисправностей
            data = FaultSimulator.apply_faults(
                data,
                self.active_faults
            )

            return data