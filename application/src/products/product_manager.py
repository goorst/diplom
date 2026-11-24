
import sqlite3
import uuid

from pathlib import Path


# Корневая папка проекта
PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATABASE_DIR = PROJECT_ROOT / "data" / "products"
DATABASE_PATH = DATABASE_DIR / "catalog.db"


class ProductManager:

    def __init__(self, database_path=None):

        self.database_path = Path(
            database_path or DATABASE_PATH
        )

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        self.initialize_database()

    # ==========================================
    # ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ
    # ==========================================

    def _connect(self):

        connection = sqlite3.connect(
            self.database_path,
            timeout=30
        )

        connection.row_factory = sqlite3.Row

        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        return connection

    # ==========================================
    # СОЗДАНИЕ ТАБЛИЦ
    # ==========================================

    def initialize_database(self):

        with self._connect() as connection:

            connection.execute("""
                CREATE TABLE IF NOT EXISTS products (

                    product_id TEXT PRIMARY KEY,

                    name TEXT NOT NULL,

                    part_type TEXT NOT NULL,

                    material TEXT NOT NULL,

                    drawing_number TEXT,

                    description TEXT,

                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,

                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            connection.execute("""
                CREATE TABLE IF NOT EXISTS operations (

                    operation_id TEXT PRIMARY KEY,

                    product_id TEXT NOT NULL,

                    sequence_number INTEGER NOT NULL,

                    operation_name TEXT NOT NULL,

                    spindle_speed REAL,

                    feed_rate REAL,

                    cutting_depth REAL,

                    tool_id TEXT,

                    description TEXT,

                    FOREIGN KEY (product_id)
                        REFERENCES products(product_id)
                        ON DELETE CASCADE
                )
            """)

            connection.execute("""
                CREATE TABLE IF NOT EXISTS documents (

                    document_id TEXT PRIMARY KEY,

                    product_id TEXT NOT NULL,

                    original_name TEXT NOT NULL,

                    stored_path TEXT NOT NULL,

                    extension TEXT NOT NULL,

                    category TEXT,

                    description TEXT,

                    uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (product_id)
                        REFERENCES products(product_id)
                        ON DELETE CASCADE
                )
            """)

    # ==========================================
    # ПРОВЕРКА СУЩЕСТВОВАНИЯ ИЗДЕЛИЯ
    # ==========================================

    def product_exists(self, product_id):

        with self._connect() as connection:

            result = connection.execute(
                """
                SELECT 1
                FROM products
                WHERE product_id = ?
                """,
                (product_id,)
            ).fetchone()

        return result is not None

    # ==========================================
    # ДОБАВЛЕНИЕ ИЗДЕЛИЯ
    # ==========================================

    def add_product(
        self,
        name,
        part_type,
        material,
        drawing_number="",
        description=""
    ):

        name = name.strip()
        part_type = part_type.strip()
        material = material.strip()

        if not name:
            raise ValueError("Не указано название изделия")

        if not part_type:
            raise ValueError("Не указан тип детали")

        if not material:
            raise ValueError("Не указан материал")

        product_id = (
            f"PRD-{uuid.uuid4().hex[:10].upper()}"
        )

        with self._connect() as connection:

            connection.execute(
                """
                INSERT INTO products (
                    product_id,
                    name,
                    part_type,
                    material,
                    drawing_number,
                    description
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    name,
                    part_type,
                    material,
                    drawing_number,
                    description
                )
            )

        return product_id

    # ==========================================
    # РЕДАКТИРОВАНИЕ ИЗДЕЛИЯ
    # ==========================================

    def update_product(
        self,
        product_id,
        **fields
    ):

        allowed_fields = {
            "name",
            "part_type",
            "material",
            "drawing_number",
            "description"
        }

        updates = {
            key: value
            for key, value in fields.items()
            if key in allowed_fields
        }

        if not updates:
            raise ValueError(
                "Нет допустимых полей для изменения"
            )

        for key in ("name", "part_type", "material"):

            if key in updates and not str(updates[key]).strip():
                raise ValueError(
                    f"Поле {key} не может быть пустым"
                )

        assignments = ", ".join(
            f"{field} = ?"
            for field in updates
        )

        values = list(updates.values())

        values.append(product_id)

        with self._connect() as connection:

            cursor = connection.execute(
                f"""
                UPDATE products
                SET {assignments},
                    updated_at = CURRENT_TIMESTAMP
                WHERE product_id = ?
                """,
                values
            )

            if cursor.rowcount == 0:
                raise ValueError(
                    "Изделие не найдено"
                )

    # ==========================================
    # ПОЛУЧЕНИЕ ОДНОГО ИЗДЕЛИЯ
    # ==========================================

    def get_product(self, product_id):

        with self._connect() as connection:

            row = connection.execute(
                """
                SELECT *
                FROM products
                WHERE product_id = ?
                """,
                (product_id,)
            ).fetchone()

        return dict(row) if row else None

    # ==========================================
    # ПОЛУЧЕНИЕ ВСЕХ ИЗДЕЛИЙ
    # ==========================================

    def list_products(
        self,
        part_type=None,
        material=None
    ):

        query = """
            SELECT *
            FROM products
            WHERE 1 = 1
        """

        parameters = []

        if part_type:

            query += " AND part_type = ?"

            parameters.append(part_type)

        if material:

            query += " AND material = ?"

            parameters.append(material)

        query += " ORDER BY created_at DESC"

        with self._connect() as connection:

            rows = connection.execute(
                query,
                parameters
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    # ==========================================
    # УДАЛЕНИЕ ИЗДЕЛИЯ
    # ==========================================

    def delete_product(self, product_id):

        with self._connect() as connection:

            cursor = connection.execute(
                """
                DELETE FROM products
                WHERE product_id = ?
                """,
                (product_id,)
            )

            if cursor.rowcount == 0:

                raise ValueError(
                    "Изделие не найдено"
                )

    # ==========================================
    # ДОБАВЛЕНИЕ ТЕХНОЛОГИЧЕСКОЙ ОПЕРАЦИИ
    # ==========================================

    def add_operation(
        self,
        product_id,
        operation_name,
        sequence_number,
        spindle_speed=None,
        feed_rate=None,
        cutting_depth=None,
        tool_id=None,
        description=""
    ):

        if not self.product_exists(product_id):

            raise ValueError(
                "Изделие не найдено"
            )

        operation_name = operation_name.strip()

        if not operation_name:

            raise ValueError(
                "Не указано название операции"
            )

        numeric_values = {
            "spindle_speed": spindle_speed,
            "feed_rate": feed_rate,
            "cutting_depth": cutting_depth
        }

        for name, value in numeric_values.items():

            if value is not None:

                numeric_values[name] = float(value)

                if numeric_values[name] <= 0:

                    raise ValueError(
                        f"Некорректное значение: {name}"
                    )

        if int(sequence_number) < 1:

            raise ValueError(
                "Номер операции должен быть положительным"
            )

        operation_id = (
            f"OP-{uuid.uuid4().hex[:10].upper()}"
        )

        with self._connect() as connection:

            connection.execute(
                """
                INSERT INTO operations (
                    operation_id,
                    product_id,
                    sequence_number,
                    operation_name,
                    spindle_speed,
                    feed_rate,
                    cutting_depth,
                    tool_id,
                    description
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    operation_id,
                    product_id,
                    int(sequence_number),
                    operation_name,
                    numeric_values["spindle_speed"],
                    numeric_values["feed_rate"],
                    numeric_values["cutting_depth"],
                    tool_id,
                    description
                )
            )

        return operation_id

    # ==========================================
    # ПОЛУЧЕНИЕ ОПЕРАЦИЙ ИЗДЕЛИЯ
    # ==========================================

    def list_operations(self, product_id):

        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT *
                FROM operations
                WHERE product_id = ?
                ORDER BY sequence_number ASC
                """,
                (product_id,)
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    # ==========================================
    # УДАЛЕНИЕ ОПЕРАЦИИ
    # ==========================================

    def delete_operation(self, operation_id):

        with self._connect() as connection:

            cursor = connection.execute(
                """
                DELETE FROM operations
                WHERE operation_id = ?
                """,
                (operation_id,)
            )

            if cursor.rowcount == 0:

                raise ValueError(
                    "Операция не найдена"
                )
