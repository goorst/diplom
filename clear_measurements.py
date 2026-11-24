import shutil
from datetime import datetime

from application.src.core.measurement_logger import MeasurementLogger


def main():
    logger = MeasurementLogger()
    database_path = logger.database_path

    if not database_path.exists():
        print("База данных не найдена.")
        return

    # Создание резервной копии
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = database_path.with_name(
        f"measurements_backup_{timestamp}.db"
    )

    shutil.copy2(database_path, backup_path)

    print("======= ОЧИСТКА ЭКСПЕРИМЕНТАЛЬНОЙ БАЗЫ =======")
    print(f"База данных: {database_path}")
    print(f"Резервная копия: {backup_path}")

    count_before = logger.count_measurements()

    print(f"Записей до очистки: {count_before}")

    if count_before == 0:
        print("База уже пустая.")
        return

    confirmation = input(
        '\nДля подтверждения введи ОЧИСТИТЬ: '
    )

    if confirmation != "ОЧИСТИТЬ":
        print("Очистка отменена.")
        return

    deleted = logger.clear_measurements()
    count_after = logger.count_measurements()

    print("\n======= РЕЗУЛЬТАТ =======")
    print(f"Удалено записей: {deleted}")
    print(f"Осталось записей: {count_after}")
    print(f"Резервная копия сохранена: {backup_path}")

    if count_after == 0:
        print("База успешно очищена.")
    else:
        print("ВНИМАНИЕ: в базе остались записи!")


if __name__ == "__main__":
    main()