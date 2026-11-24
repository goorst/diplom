
import tempfile

from pathlib import Path

from application.src.core import MeasurementLogger


def main():
    with tempfile.TemporaryDirectory() as temp_dir:
        database_path = (
            Path(temp_dir) / "test_measurements.db"
        )

        logger = MeasurementLogger(database_path)

        measurement = {
            "timestamp": "2026-11-24T16:00:00",
            "measurement_id": 1,
            "product_id": "PRD-TEST001",
            "part_type": "Вал",
            "material": "Сталь 40Х",
            "operation": "Черновое точение",
            "tool_id": "T01",
            "spindle_speed": 1200,
            "feed_rate": 180,
            "cutting_depth": 2.0,
            "temperature": 65.5,
            "vibration": 1.2,
            "spindle_load": 55.0,
            "tool_wear": 10.0
        }

        diagnosis = {
            "status": "НОРМА",
            "reasons": [
                "Все параметры в пределах нормы"
            ],
            "recommendations": [
                "Продолжайте мониторинг"
            ]
        }

        logger.log_measurement(
            measurement,
            diagnosis,
            active_faults=[]
        )

        assert logger.count_measurements() == 1

        records = logger.list_measurements(
            product_id="PRD-TEST001"
        )

        assert len(records) == 1
        assert records[0]["temperature"] == 65.5
        assert records[0]["diagnosis_status"] == "НОРМА"

        export_path = (
            Path(temp_dir) / "measurements.csv"
        )

        logger.export_csv(export_path)

        assert export_path.exists()

        print("Количество записей:", logger.count_measurements())
        print("Температура:", records[0]["temperature"])
        print("Диагноз:", records[0]["diagnosis_status"])
        print("CSV создан:", export_path.exists())

        print("\nТЕСТ УСПЕШНО ПРОЙДЕН")


if __name__ == "__main__":
    main()
