import sqlite3

from pathlib import Path
from datetime import datetime


class ProductManager:
    """
    Управление номенклатурой изделий.

    Отвечает за:
    - подключение к SQLite;
    - создание структуры базы данных;
    - CRUD-операции с изделиями;
    - CRUD-операции с характеристиками;
    - историю изменений.
    """

    def __init__(self, db_path=None):

        # Корневая папка проекта
        project_root = Path(__file__).resolve().parents[3]

        if db_path is None:
            db_path = project_root / "data" / "products" / "catalog.db"

        self.db_path = Path(db_path)

        # Создаём папку базы данных, если её нет
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Создаём таблицы
        self.initialize_database()

    # =========================================================
    # ПОДКЛЮЧЕНИЕ К БАЗЕ ДАННЫХ
    # =========================================================

    def get_connection(self):

        connection = sqlite3.connect(self.db_path)

        connection.row_factory = sqlite3.Row

        connection.execute("PRAGMA foreign_keys = ON")

        return connection

    # =========================================================
    # СОЗДАНИЕ БАЗЫ ДАННЫХ
    # =========================================================

    def initialize_database(self):

        with self.get_connection() as connection:

            connection.executescript("""

                CREATE TABLE IF NOT EXISTS products (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    name TEXT NOT NULL,

                    article TEXT NOT NULL UNIQUE,

                    product_type TEXT,

                    material TEXT,

                    density REAL,

                    description TEXT,

                    created_at TEXT NOT NULL,

                    updated_at TEXT NOT NULL

                );


                CREATE TABLE IF NOT EXISTS product_parameters (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    product_id INTEGER NOT NULL,

                    name TEXT NOT NULL,

                    code TEXT,

                    nominal REAL,

                    min_value REAL,

                    max_value REAL,

                    unit TEXT,

                    source TEXT DEFAULT 'manual',

                    note TEXT,

                    FOREIGN KEY(product_id)
                        REFERENCES products(id)
                        ON DELETE CASCADE

                );


                CREATE TABLE IF NOT EXISTS product_history (

                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    product_id INTEGER NOT NULL,

                    action TEXT NOT NULL,

                    details TEXT,

                    created_at TEXT NOT NULL,

                    FOREIGN KEY(product_id)
                        REFERENCES products(id)
                        ON DELETE CASCADE

                );

            """)

    # =========================================================
    # ИЗДЕЛИЯ: СОЗДАНИЕ
    # =========================================================

    def add_product(self, data):

        """
        Добавление нового изделия.

        Обязательные поля:
        - name
        - article
        """

        name = data.get("name", "").strip()
        article = data.get("article", "").strip()

        if not name:
            raise ValueError("Не указано наименование изделия")

        if not article:
            raise ValueError("Не указан артикул изделия")

        now = datetime.now().isoformat(timespec="seconds")

        with self.get_connection() as connection:

            cursor = connection.execute("""

                INSERT INTO products (

                    name,
                    article,
                    product_type,
                    material,
                    density,
                    description,
                    created_at,
                    updated_at

                )

                VALUES (?, ?, ?, ?, ?, ?, ?, ?)

            """, (

                name,
                article,
                data.get("product_type", ""),
                data.get("material", ""),
                data.get("density"),
                data.get("description", ""),
                now,
                now

            ))

            product_id = cursor.lastrowid

            self._add_history(
                connection,
                product_id,
                "Создание изделия",
                f"Создано изделие {name}"
            )

            return product_id

    # =========================================================
    # ИЗДЕЛИЯ: ПОЛУЧЕНИЕ
    # =========================================================

    def get_product(self, product_id):

        with self.get_connection() as connection:

            product = connection.execute("""

                SELECT *
                FROM products
                WHERE id = ?

            """, (product_id,)).fetchone()

            return dict(product) if product else None

    # =========================================================
    # ИЗДЕЛИЯ: ПОЛУЧЕНИЕ ВСЕХ ЗАПИСЕЙ
    # =========================================================

    def get_all_products(self):

        with self.get_connection() as connection:

            products = connection.execute("""

                SELECT
                    p.*,

                    (
                        SELECT COUNT(*)
                        FROM product_parameters pp
                        WHERE pp.product_id = p.id

                    ) AS parameter_count

                FROM products p

                ORDER BY p.name COLLATE NOCASE

            """).fetchall()

            return [dict(product) for product in products]

    # =========================================================
    # ИЗДЕЛИЯ: ПОИСК И ФИЛЬТРАЦИЯ
    # =========================================================


    def search_products(
        self,
        search_text="",
        product_type="",
        material=""
    ):
        """
        Поиск изделий по наименованию, артикулу,
        типу изделия и материалу.
        Возвращает список изделий с количеством характеристик.
        """

        connection = self.get_connection()

        try:
            query = """
                SELECT
                    p.id,
                    p.name,
                    p.article,
                    p.product_type,
                    p.material,
                    p.density,
                    p.description,
                    p.created_at,
                    p.updated_at,
                    COUNT(pp.id) AS parameter_count
                FROM products AS p
                LEFT JOIN product_parameters AS pp
                    ON pp.product_id = p.id
                WHERE 1 = 1
            """

            params = []

            if search_text:
                query += """
                    AND (
                        p.name LIKE ?
                        OR p.article LIKE ?
                    )
                """
                search_pattern = f"%{search_text}%"
                params.extend([
                    search_pattern,
                    search_pattern
                ])

            if product_type:
                query += " AND p.product_type LIKE ?"
                params.append(f"%{product_type}%")

            if material:
                query += " AND p.material LIKE ?"
                params.append(f"%{material}%")

            query += """
                GROUP BY
                    p.id,
                    p.name,
                    p.article,
                    p.product_type,
                    p.material,
                    p.density,
                    p.description,
                    p.created_at,
                    p.updated_at
                ORDER BY p.name COLLATE NOCASE
            """

            cursor = connection.execute(query, params)

            return [dict(row) for row in cursor.fetchall()]

        finally:
            connection.close()


    # =========================================================
    # ИЗДЕЛИЯ: РЕДАКТИРОВАНИЕ
    # =========================================================

    def update_product(self, product_id, data):

        name = data.get("name", "").strip()
        article = data.get("article", "").strip()

        if not name:
            raise ValueError("Не указано наименование изделия")

        if not article:
            raise ValueError("Не указан артикул изделия")

        now = datetime.now().isoformat(timespec="seconds")

        with self.get_connection() as connection:

            cursor = connection.execute("""

                UPDATE products

                SET

                    name = ?,
                    article = ?,
                    product_type = ?,
                    material = ?,
                    density = ?,
                    description = ?,
                    updated_at = ?

                WHERE id = ?

            """, (

                name,
                article,
                data.get("product_type", ""),
                data.get("material", ""),
                data.get("density"),
                data.get("description", ""),
                now,
                product_id

            ))

            if cursor.rowcount == 0:
                raise ValueError("Изделие не найдено")

            self._add_history(
                connection,
                product_id,
                "Редактирование изделия",
                f"Обновлены данные изделия {name}"
            )

    # =========================================================
    # ИЗДЕЛИЯ: УДАЛЕНИЕ
    # =========================================================

    def delete_product(self, product_id):

        with self.get_connection() as connection:

            cursor = connection.execute("""

                DELETE FROM products
                WHERE id = ?

            """, (product_id,))

            if cursor.rowcount == 0:
                raise ValueError("Изделие не найдено")

    # =========================================================
    # ИЗДЕЛИЯ: ПРОВЕРКА АРТИКУЛА
    # =========================================================

    def article_exists(self, article, exclude_id=None):

        with self.get_connection() as connection:

            if exclude_id is None:

                result = connection.execute("""

                    SELECT id
                    FROM products
                    WHERE article = ?

                """, (article,)).fetchone()

            else:

                result = connection.execute("""

                    SELECT id
                    FROM products
                    WHERE article = ?
                    AND id != ?

                """, (article, exclude_id)).fetchone()

            return result is not None

    # =========================================================
    # ИЗДЕЛИЯ: ДУБЛИРОВАНИЕ
    # =========================================================

    def duplicate_product(self, product_id):

        product = self.get_product(product_id)

        if product is None:
            raise ValueError("Изделие не найдено")

        new_article = f'{product["article"]}-COPY'

        counter = 1

        while self.article_exists(new_article):

            counter += 1

            new_article = f'{product["article"]}-COPY{counter}'

        new_data = {

            "name": f'{product["name"]} (копия)',
            "article": new_article,
            "product_type": product["product_type"],
            "material": product["material"],
            "density": product["density"],
            "description": product["description"]

        }

        new_product_id = self.add_product(new_data)

        parameters = self.get_product_parameters(product_id)

        for parameter in parameters:

            self.add_parameter(

                new_product_id,

                {

                    "name": parameter["name"],
                    "code": parameter["code"],
                    "nominal": parameter["nominal"],
                    "min_value": parameter["min_value"],
                    "max_value": parameter["max_value"],
                    "unit": parameter["unit"],
                    "source": "copy",
                    "note": parameter["note"]

                }

            )

        return new_product_id

    # =========================================================
    # ХАРАКТЕРИСТИКИ: ДОБАВЛЕНИЕ
    # =========================================================

    def add_parameter(self, product_id, data):

        name = data.get("name", "").strip()

        if not name:
            raise ValueError("Не указано название характеристики")

        minimum = data.get("min_value")
        maximum = data.get("max_value")

        if minimum is not None and maximum is not None:

            if minimum > maximum:
                raise ValueError(
                    "Минимальное значение не может быть больше максимального"
                )

        with self.get_connection() as connection:

            connection.execute("""

                INSERT INTO product_parameters (

                    product_id,
                    name,
                    code,
                    nominal,
                    min_value,
                    max_value,
                    unit,
                    source,
                    note

                )

                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

            """, (

                product_id,
                name,
                data.get("code", ""),
                data.get("nominal"),
                minimum,
                maximum,
                data.get("unit", ""),
                data.get("source", "manual"),
                data.get("note", "")

            ))

            self._add_history(
                connection,
                product_id,
                "Добавление характеристики",
                name
            )

    # =========================================================
    # ХАРАКТЕРИСТИКИ: ПОЛУЧЕНИЕ
    # =========================================================

    def get_product_parameters(self, product_id):

        with self.get_connection() as connection:

            parameters = connection.execute("""

                SELECT *
                FROM product_parameters

                WHERE product_id = ?

                ORDER BY id

            """, (product_id,)).fetchall()

            return [dict(parameter) for parameter in parameters]

    # =========================================================
    # ХАРАКТЕРИСТИКИ: РЕДАКТИРОВАНИЕ
    # =========================================================

    def update_parameter(self, parameter_id, data):

        name = data.get("name", "").strip()

        if not name:
            raise ValueError("Не указано название характеристики")

        minimum = data.get("min_value")
        maximum = data.get("max_value")

        if minimum is not None and maximum is not None:

            if minimum > maximum:
                raise ValueError(
                    "Минимальное значение не может быть больше максимального"
                )

        with self.get_connection() as connection:

            parameter = connection.execute("""

                SELECT product_id
                FROM product_parameters
                WHERE id = ?

            """, (parameter_id,)).fetchone()

            if parameter is None:
                raise ValueError("Характеристика не найдена")

            connection.execute("""

                UPDATE product_parameters

                SET

                    name = ?,
                    code = ?,
                    nominal = ?,
                    min_value = ?,
                    max_value = ?,
                    unit = ?,
                    source = ?,
                    note = ?

                WHERE id = ?

            """, (

                name,
                data.get("code", ""),
                data.get("nominal"),
                minimum,
                maximum,
                data.get("unit", ""),
                data.get("source", "manual"),
                data.get("note", ""),
                parameter_id

            ))

            self._add_history(
                connection,
                parameter["product_id"],
                "Редактирование характеристики",
                name
            )

    # =========================================================
    # ХАРАКТЕРИСТИКИ: УДАЛЕНИЕ
    # =========================================================

    def delete_parameter(self, parameter_id):

        with self.get_connection() as connection:

            parameter = connection.execute("""

                SELECT product_id, name
                FROM product_parameters
                WHERE id = ?

            """, (parameter_id,)).fetchone()

            if parameter is None:
                raise ValueError("Характеристика не найдена")

            connection.execute("""

                DELETE FROM product_parameters
                WHERE id = ?

            """, (parameter_id,))

            self._add_history(
                connection,
                parameter["product_id"],
                "Удаление характеристики",
                parameter["name"]
            )

    # =========================================================
    # ИСТОРИЯ ИЗМЕНЕНИЙ
    # =========================================================

    def _add_history(
        self,
        connection,
        product_id,
        action,
        details=""
    ):

        connection.execute("""

            INSERT INTO product_history (

                product_id,
                action,
                details,
                created_at

            )

            VALUES (?, ?, ?, ?)

        """, (

            product_id,
            action,
            details,
            datetime.now().isoformat(timespec="seconds")

        ))

    def get_product_history(self, product_id):

        with self.get_connection() as connection:

            history = connection.execute("""

                SELECT *
                FROM product_history

                WHERE product_id = ?

                ORDER BY id DESC

            """, (product_id,)).fetchall()

            return [dict(item) for item in history]