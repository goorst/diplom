import csv
import json
import sqlite3

from contextlib import contextmanager
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATABASE_DIR = PROJECT_ROOT / "data" / "experiments"
DATABASE_PATH = DATABASE_DIR / "measurements.db"


class MeasurementLogger:
    """Хранение экспериментальных измерений виртуального станка."""

    COLUMNS = (
        "timestamp", "measurement_id", "product_id", "part_type",
        "material", "operation", "tool_id", "spindle_speed",
        "feed_rate", "cutting_depth", "temperature", "vibration",
        "spindle_load", "tool_wear", "diagnosis_status",
        "diagnosis_reasons", "recommendations", "active_faults",
        "experiment_id",
    )

    INSERT_SQL = """
        INSERT INTO measurements (
            timestamp, measurement_id, product_id, part_type, material,
            operation, tool_id, spindle_speed, feed_rate, cutting_depth,
            temperature, vibration, spindle_load, tool_wear,
            diagnosis_status, diagnosis_reasons, recommendations,
            active_faults, experiment_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    def __init__(self, database_path=None):
        self.database_path = Path(database_path or DATABASE_PATH)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize_database()

    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize_database(self):
        with self._connection() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS measurements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    measurement_id INTEGER,
                    product_id TEXT,
                    part_type TEXT,
                    material TEXT,
                    operation TEXT,
                    tool_id TEXT,
                    spindle_speed REAL,
                    feed_rate REAL,
                    cutting_depth REAL,
                    temperature REAL,
                    vibration REAL,
                    spindle_load REAL,
                    tool_wear REAL,
                    diagnosis_status TEXT,
                    diagnosis_reasons TEXT,
                    recommendations TEXT,
                    active_faults TEXT,
                    experiment_id TEXT
                )
            """)

            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(measurements)"
                ).fetchall()
            }
            if "experiment_id" not in columns:
                connection.execute("""
                    ALTER TABLE measurements ADD COLUMN experiment_id TEXT
                """)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_measurements_product
                ON measurements(product_id)
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_measurements_timestamp
                ON measurements(timestamp)
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS idx_measurements_experiment
                ON measurements(experiment_id)
            """)

    @staticmethod
    def _prepare_values(item):
        measurement = item["measurement"]
        diagnosis = item.get("diagnosis") or {}
        active_faults = item.get("active_faults") or []

        return (
            measurement.get("timestamp"),
            measurement.get("measurement_id"),
            measurement.get("product_id"),
            measurement.get("part_type"),
            measurement.get("material"),
            measurement.get("operation"),
            measurement.get("tool_id"),
            measurement.get("spindle_speed"),
            measurement.get("feed_rate"),
            measurement.get("cutting_depth"),
            measurement.get("temperature"),
            measurement.get("vibration"),
            measurement.get("spindle_load"),
            measurement.get("tool_wear"),
            diagnosis.get("status"),
            json.dumps(diagnosis.get("reasons", []), ensure_ascii=False),
            json.dumps(
                diagnosis.get("recommendations", []), ensure_ascii=False
            ),
            json.dumps(active_faults, ensure_ascii=False),
            item.get("experiment_id"),
        )

    def log_measurements(self, items):
        """Пакетная запись нескольких измерений одной транзакцией."""
        prepared = [self._prepare_values(item) for item in items]
        if not prepared:
            return 0

        with self._connection() as connection:
            connection.executemany(self.INSERT_SQL, prepared)
        return len(prepared)

    def log_measurement(
        self, measurement, diagnosis=None, active_faults=None,
        experiment_id=None
    ):
        """Совместимый метод записи одного измерения."""
        return self.log_measurements([{
            "measurement": measurement,
            "diagnosis": diagnosis,
            "active_faults": active_faults,
            "experiment_id": experiment_id,
        }])

    def list_measurements(self, product_id=None, limit=None):
        query = "SELECT * FROM measurements"
        parameters = []
        if product_id:
            query += " WHERE product_id = ?"
            parameters.append(product_id)
        query += " ORDER BY id DESC"

        if limit is not None:
            limit = int(limit)
            if limit < 1:
                raise ValueError("Лимит должен быть положительным")
            query += " LIMIT ?"
            parameters.append(limit)

        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [dict(row) for row in rows]

    def count_measurements(self, product_id=None):
        query = "SELECT COUNT(*) FROM measurements"
        parameters = []
        if product_id:
            query += " WHERE product_id = ?"
            parameters.append(product_id)
        with self._connection() as connection:
            return connection.execute(query, parameters).fetchone()[0]

    def export_csv(self, file_path, product_id=None):
        rows = self.list_measurements(product_id=product_id)
        if not rows:
            raise ValueError("Нет измерений для экспорта")

        columns = list(rows[0].keys())
        destination = Path(file_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        with destination.open("w", newline="", encoding="utf-8-sig") as file:
            writer = csv.DictWriter(
                file, fieldnames=columns, delimiter=";"
            )
            writer.writeheader()
            writer.writerows(rows)
        return destination

    def clear_measurements(self, product_id=None):
        """Удаляет измерения. Использовать осторожно."""
        with self._connection() as connection:
            if product_id:
                cursor = connection.execute(
                    "DELETE FROM measurements WHERE product_id = ?",
                    (product_id,)
                )
            else:
                cursor = connection.execute("DELETE FROM measurements")
            return cursor.rowcount
