
import json
import sqlite3

from pathlib import Path
from datetime import datetime


class MeasurementLogger:
    """
    Журнал результатов контроля качества.

    Сохраняет:
    - изделие и номер экземпляра;
    - измеренные характеристики;
    - статус контроля и обнаруженные дефекты;
    - сведения об искусственно внесённых дефектах;
    - идентификаторы эксперимента и запуска;
    - дату и время обработки.
    """

    def __init__(self, db_path=None):

        if db_path is None:
            project_root = Path(__file__).resolve().parents[3]

            db_path = (
                project_root
                / "data"
                / "quality"
                / "measurements.db"
            )

        self.db_path = Path(db_path)

        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.initialize_database()

    # ---------------------------------------------------------
    # ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ
    # ---------------------------------------------------------

    def get_connection(self):
        connection = sqlite3.connect(
            str(self.db_path),
            timeout=30,
        )

        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")

        return connection

    def initialize_database(self):
        """Создаёт таблицу и обновляет её структуру при необходимости."""

        with self.get_connection() as connection:

            connection.execute("""
                CREATE TABLE IF NOT EXISTS measurements (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    item_id INTEGER,
                    measurements_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    defects_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    simulated_defect INTEGER NOT NULL DEFAULT 0,
                    injected_defects_json TEXT NOT NULL DEFAULT '[]',
                    experiment_id TEXT,
                    run_id TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            existing_columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(measurements)"
                ).fetchall()
            }

            # Миграция старой базы данных.
            migrations = {
                "injected_defects_json": (
                    "ALTER TABLE measurements "
                    "ADD COLUMN injected_defects_json "
                    "TEXT NOT NULL DEFAULT '[]'"
                ),
                "experiment_id": (
                    "ALTER TABLE measurements "
                    "ADD COLUMN experiment_id TEXT"
                ),
                "run_id": (
                    "ALTER TABLE measurements "
                    "ADD COLUMN run_id TEXT"
                ),
            }

            for column, sql in migrations.items():
                if column not in existing_columns:
                    connection.execute(sql)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_measurements_product_id
                ON measurements(product_id)
            """)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_measurements_status
                ON measurements(status)
            """)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_measurements_created_at
                ON measurements(created_at)
            """)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_measurements_experiment_id
                ON measurements(experiment_id)
            """)

            connection.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_measurements_run_id
                ON measurements(run_id)
            """)

            connection.commit()

    # ---------------------------------------------------------
    # НОРМАЛИЗАЦИЯ ДАННЫХ
    # ---------------------------------------------------------

    @staticmethod
    def _normalize_status(status):
        status = str(status or "UNKNOWN").strip().upper()

        if status not in ("GOOD", "DEFECT", "UNKNOWN"):
            return "UNKNOWN"

        return status

    @staticmethod
    def _build_filters(
        product_id=None,
        experiment_id=None,
        run_id=None,
    ):
        conditions = []
        values = []

        if product_id is not None:
            conditions.append("product_id = ?")
            values.append(product_id)

        if experiment_id is not None:
            conditions.append("experiment_id = ?")
            values.append(experiment_id)

        if run_id is not None:
            conditions.append("run_id = ?")
            values.append(run_id)

        where = ""

        if conditions:
            where = " WHERE " + " AND ".join(conditions)

        return where, values

    # ---------------------------------------------------------
    # СОХРАНЕНИЕ РЕЗУЛЬТАТА
    # ---------------------------------------------------------

    def log_result(
        self,
        result,
        item_id=None,
        simulated_defect=False,
        experiment_id=None,
        run_id=None,
    ):
        """
        Сохраняет результат контроля.

        experiment_id и run_id позволяют разделять
        данные по экспериментам и отдельным запускам.
        """

        if not isinstance(result, dict):
            raise TypeError(
                "Результат контроля должен быть словарём."
            )

        product_id = result.get("product_id")

        if product_id is None:
            raise ValueError(
                "В результате контроля отсутствует product_id."
            )

        if item_id is None:
            item_id = result.get("item_id")

        if experiment_id is None:
            experiment_id = result.get("experiment_id")

        if run_id is None:
            run_id = result.get("run_id")

        measurements = result.get("measurements", {})
        defects = result.get("defects", [])
        injected_defects = result.get("injected_defects", [])

        if not isinstance(measurements, dict):
            raise TypeError(
                "Измерения должны быть представлены словарём."
            )

        if not isinstance(defects, list):
            defects = []

        if not isinstance(injected_defects, list):
            injected_defects = []

        status = self._normalize_status(
            result.get("status")
        )

        created_at = (
            result.get("processed_at")
            or result.get("checked_at")
            or datetime.now().isoformat(timespec="seconds")
        )

        result_to_save = dict(result)

        result_to_save.update({
            "status": status,
            "measurements": measurements,
            "defects": defects,
            "injected_defects": injected_defects,
            "experiment_id": experiment_id,
            "run_id": run_id,
        })

        with self.get_connection() as connection:

            cursor = connection.execute(
                """
                INSERT INTO measurements (
                    product_id,
                    item_id,
                    measurements_json,
                    status,
                    defects_json,
                    result_json,
                    simulated_defect,
                    injected_defects_json,
                    experiment_id,
                    run_id,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    item_id,

                    json.dumps(
                        measurements,
                        ensure_ascii=False,
                    ),

                    status,

                    json.dumps(
                        defects,
                        ensure_ascii=False,
                    ),

                    json.dumps(
                        result_to_save,
                        ensure_ascii=False,
                    ),

                    int(bool(simulated_defect)),

                    json.dumps(
                        injected_defects,
                        ensure_ascii=False,
                    ),

                    experiment_id,
                    run_id,
                    created_at,
                ),
            )

            connection.commit()

            return cursor.lastrowid

    # ---------------------------------------------------------
    # ПОЛУЧЕНИЕ ЗАПИСЕЙ
    # ---------------------------------------------------------

    def get_result(self, record_id):
        with self.get_connection() as connection:

            row = connection.execute(
                """
                SELECT *
                FROM measurements
                WHERE id = ?
                """,
                (record_id,),
            ).fetchone()

        return self._convert_row(row) if row else None

    def get_all_records(
        self,
        product_id=None,
        limit=10000,
        experiment_id=None,
        run_id=None,
    ):
        where, values = self._build_filters(
            product_id=product_id,
            experiment_id=experiment_id,
            run_id=run_id,
        )

        query = """
            SELECT *
            FROM measurements
        """ + where + """
            ORDER BY id DESC
            LIMIT ?
        """

        values.append(max(1, int(limit)))

        with self.get_connection() as connection:

            rows = connection.execute(
                query,
                values,
            ).fetchall()

        return [
            self._convert_row(row)
            for row in rows
        ]

    def get_experiment_records(self, experiment_id, limit=10000):
        return self.get_all_records(
            experiment_id=experiment_id,
            limit=limit
        )

    # ---------------------------------------------------------
    # СТАТИСТИКА КОНТРОЛЯ
    # ---------------------------------------------------------

    def get_statistics(
        self,
        product_id=None,
        experiment_id=None,
        run_id=None,
    ):
        """
        Статистика по всем записям либо по выбранному
        изделию, эксперименту или запуску.
        """

        where, values = self._build_filters(
            product_id=product_id,
            experiment_id=experiment_id,
            run_id=run_id,
        )

        query = """
            SELECT
                COUNT(*) AS total,

                SUM(
                    CASE WHEN status = 'GOOD'
                    THEN 1 ELSE 0 END
                ) AS good,

                SUM(
                    CASE WHEN status = 'DEFECT'
                    THEN 1 ELSE 0 END
                ) AS defect,

                SUM(
                    CASE WHEN status = 'UNKNOWN'
                    THEN 1 ELSE 0 END
                ) AS unknown

            FROM measurements
        """ + where

        with self.get_connection() as connection:
            row = connection.execute(
                query,
                values,
            ).fetchone()

        unknown = row["unknown"] or 0

        return {
            "total": row["total"] or 0,
            "good": row["good"] or 0,
            "defect": row["defect"] or 0,
            "unknown": unknown,
            "incomplete": unknown,
        }

    # ---------------------------------------------------------
    # СТАТИСТИКА ИСКУССТВЕННЫХ ДЕФЕКТОВ
    # ---------------------------------------------------------

    def get_simulation_statistics(
        self,
        product_id=None,
        experiment_id=None,
        run_id=None,
    ):
        where, values = self._build_filters(
            product_id=product_id,
            experiment_id=experiment_id,
            run_id=run_id,
        )

        query = """
            SELECT
                COUNT(*) AS total,

                SUM(
                    CASE WHEN simulated_defect = 1
                    THEN 1 ELSE 0 END
                ) AS generated_defects

            FROM measurements
        """ + where

        with self.get_connection() as connection:
            row = connection.execute(
                query,
                values,
            ).fetchone()

        return {
            "total": row["total"] or 0,
            "generated_defects": (
                row["generated_defects"] or 0
            ),
        }

    # ---------------------------------------------------------
    # УДАЛЕНИЕ ЗАПИСЕЙ
    # ---------------------------------------------------------

    def clear_records(
        self,
        product_id=None,
        experiment_id=None,
        run_id=None,
    ):
        """
        Удаляет записи с заданными фильтрами.

        Без фильтров очищает всю таблицу.
        """

        where, values = self._build_filters(
            product_id=product_id,
            experiment_id=experiment_id,
            run_id=run_id,
        )

        with self.get_connection() as connection:

            connection.execute(
                "DELETE FROM measurements" + where,
                values,
            )

            connection.commit()

    # ---------------------------------------------------------
    # ПРЕОБРАЗОВАНИЕ ЗАПИСЕЙ
    # ---------------------------------------------------------

    @staticmethod
    def _convert_row(row):
        if row is None:
            return None

        record = dict(row)

        record["measurements"] = json.loads(
            record.pop("measurements_json")
        )

        record["defects"] = json.loads(
            record.pop("defects_json")
        )

        record["result"] = json.loads(
            record.pop("result_json")
        )

        record["injected_defects"] = json.loads(
            record.pop("injected_defects_json", "[]")
        )

        return record
