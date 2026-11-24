import threading

from PySide6.QtCore import QThread, Signal

from .sensor_simulator import SensorSimulator


class MachineSimulator(QThread):

    measurement_ready = Signal(dict)

    status_changed = Signal(str)

    error_occurred = Signal(str)

    def __init__(self, interval=1000, parent=None):

        super().__init__(parent)

        self.sensor = SensorSimulator()

        self.interval = interval

        self._stop_event = threading.Event()

        self._running = False

    # ==================================
    # ЗАПУСК ЭМУЛЯТОРА
    # ==================================

    def start_simulation(self):

        if self.isRunning():
            return

        self._stop_event.clear()

        self.start()

    # ==================================
    # ОСТАНОВКА ЭМУЛЯТОРА
    # ==================================

    def stop_simulation(self):

        self._stop_event.set()

        if self.isRunning():
            self.wait(3000)

    # ==================================
    # ВЫБОР ИЗДЕЛИЯ
    # ==================================

    def set_product(self, product):

        self.sensor.set_product(product)

    # ==================================
    # ИЗМЕНЕНИЕ РЕЖИМОВ
    # ==================================

    def set_parameters(self, parameters):

        self.sensor.set_parameters(parameters)

    # ==================================
    # ВКЛЮЧЕНИЕ НЕИСПРАВНОСТЕЙ
    # ==================================

    def set_faults(self, faults):

        self.sensor.set_faults(faults)

    # ==================================
    # СБРОС ИНСТРУМЕНТА
    # ==================================

    def reset_tool(self):

        self.sensor.reset_tool()

    # ==================================
    # ИЗМЕНЕНИЕ ЧАСТОТЫ ИЗМЕРЕНИЙ
    # ==================================

    def set_interval(self, milliseconds):

        if milliseconds < 100:
            raise ValueError(
                "Минимальный интервал составляет 100 мс"
            )

        self.interval = milliseconds

    # ==================================
    # РАБОЧИЙ ЦИКЛ
    # ==================================

    def run(self):

        self._running = True

        self.status_changed.emit(
            "Эмулятор запущен"
        )

        try:

            while not self._stop_event.is_set():

                measurement = (
                    self.sensor.generate_measurement()
                )

                self.measurement_ready.emit(
                    measurement
                )

                self._stop_event.wait(
                    self.interval / 1000
                )

        except Exception as error:

            self.error_occurred.emit(
                str(error)
            )

        finally:

            self._running = False

            self.status_changed.emit(
                "Эмулятор остановлен"
            )