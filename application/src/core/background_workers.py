import queue
import threading

from PySide6.QtCore import QThread, Signal

from application.src.core.measurement_logger import MeasurementLogger


class MeasurementWriter(QThread):
    """Фоновая пакетная запись измерений в SQLite."""

    batch_saved = Signal(int)
    error_occurred = Signal(str)

    def __init__(self, logger=None, batch_size=25, flush_interval=0.5, parent=None):
        super().__init__(parent)
        self.logger = logger or MeasurementLogger()
        self.batch_size = max(1, int(batch_size))
        self.flush_interval = max(0.05, float(flush_interval))
        self._queue = queue.Queue()
        self._stop_event = threading.Event()

    def enqueue(self, measurement, diagnosis, active_faults, experiment_id):
        # Копии исключают изменение словарей после помещения в очередь.
        self._queue.put({
            "measurement": dict(measurement),
            "diagnosis": dict(diagnosis or {}),
            "active_faults": list(active_faults or []),
            "experiment_id": experiment_id,
        })

    def stop_and_flush(self, timeout_ms=10000):
        self._stop_event.set()
        if self.isRunning():
            self.wait(timeout_ms)

    def run(self):
        batch = []

        while not self._stop_event.is_set() or not self._queue.empty():
            timed_out = False
            try:
                item = self._queue.get(timeout=self.flush_interval)
                batch.append(item)
            except queue.Empty:
                timed_out = True

            while len(batch) < self.batch_size:
                try:
                    batch.append(self._queue.get_nowait())
                except queue.Empty:
                    break

            if batch and (
                len(batch) >= self.batch_size
                or timed_out
                or self._stop_event.is_set()
            ):
                try:
                    saved = self.logger.log_measurements(batch)
                    self.batch_saved.emit(saved)
                    batch.clear()
                except Exception as error:
                    self.error_occurred.emit(str(error))
                    # Не теряем данные молча: оставляем пакет и завершаем поток.
                    self._stop_event.set()
                    break


class MLPredictionWorker(QThread):
    """Один фоновый поток прогнозирования; устаревшие запросы заменяются."""

    prediction_ready = Signal(dict)
    prediction_error = Signal(str)

    def __init__(self, model_trainer, parent=None):
        super().__init__(parent)
        self.model_trainer = model_trainer
        self._queue = queue.Queue(maxsize=1)
        self._stop_event = threading.Event()

    def submit(self, measurement):
        if not self.isRunning():
            return

        request = dict(measurement)
        try:
            self._queue.put_nowait(request)
        except queue.Full:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._queue.put_nowait(request)
            except queue.Full:
                pass

    def stop_worker(self, timeout_ms=5000):
        self._stop_event.set()
        if self.isRunning():
            self.wait(timeout_ms)

    def run(self):
        while not self._stop_event.is_set():
            try:
                measurement = self._queue.get(timeout=0.1)
            except queue.Empty:
                continue

            try:
                probabilities = self.model_trainer.predict_proba(measurement)
                self.prediction_ready.emit(probabilities)
            except Exception as error:
                self.prediction_error.emit(str(error))
