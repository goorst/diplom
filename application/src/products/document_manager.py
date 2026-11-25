
import json
import shutil
import sqlite3

from pathlib import Path
from datetime import datetime

from .document_parser import DocumentParser


class DocumentManager:
    """
    Управление технической документацией изделий.

    Отвечает за:
    - хранение файлов документов;
    - регистрацию документов в SQLite;
    - извлечение текста;
    - сохранение распознанных характеристик;
    - передачу подтверждённых характеристик в ProductManager.

    Распознанные характеристики не записываются в номенклатуру
    автоматически. Для этого необходимо вызвать
    apply_parameter_suggestions().
    """

    ALLOWED_EXTENSIONS = {
        ".pdf",
        ".docx",
        ".doc",
        ".xlsx",
        ".xls",
        ".png",
        ".jpg",
        ".jpeg",
        ".tif",
        ".tiff",
    }

    PARSER_EXTENSIONS = {
        ".pdf",
        ".docx",
        ".xlsx",
        ".png",
        ".jpg",
        ".jpeg",
        ".tif",
        ".tiff",
    }

    def __init__(self, db_path=None, documents_dir=None):
        project_root = Path(__file__).resolve().parents[3]

        if db_path is None:
            db_path = (
                project_root
                / "data"
                / "products"
                / "catalog.db"
            )

        if documents_dir is None:
            documents_dir = (
                project_root
                / "data"
                / "documents"
                / "products"
            )

        self.db_path = Path(db_path)
        self.documents_dir = Path(documents_dir)

        self.db_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.documents_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.parser = DocumentParser()

        self.initialize_database()

    # =========================================================
    # ПОДКЛЮЧЕНИЕ К БАЗЕ
    # =========================================================

    def get_connection(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    # =========================================================
    # СОЗДАНИЕ И ОБНОВЛЕНИЕ ТАБЛИЦЫ
    # =========================================================

    def initialize_database(self):
        with self.get_connection() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS product_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER NOT NULL,
                    original_name TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    extension TEXT NOT NULL,
                    file_size INTEGER DEFAULT 0,
                    description TEXT DEFAULT '',
                    extracted_text TEXT DEFAULT '',
                    uploaded_at TEXT NOT NULL,
                    FOREIGN KEY(product_id)
                        REFERENCES products(id)
                        ON DELETE CASCADE
                )
            """)

            # Миграция существующей таблицы.
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(product_documents)"
                ).fetchall()
            }

            if "parsed_parameters" not in columns:
                connection.execute("""
                    ALTER TABLE product_documents
                    ADD COLUMN parsed_parameters TEXT DEFAULT '[]'
                """)

    # =========================================================
    # ПРОВЕРКА ФАЙЛА
    # =========================================================

    def validate_file(self, file_path):
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Файл не найден: {path}"
            )

        if not path.is_file():
            raise ValueError(
                "Указанный путь не является файлом"
            )

        extension = path.suffix.lower()

        if extension not in self.ALLOWED_EXTENSIONS:
            raise ValueError(
                f"Формат {extension} не поддерживается"
            )

        if path.stat().st_size == 0:
            raise ValueError(
                "Нельзя загрузить пустой файл"
            )

        return path

    # =========================================================
    # ПАПКА ИЗДЕЛИЯ
    # =========================================================

    def get_product_directory(self, product_id):
        directory = self.documents_dir / str(product_id)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    # =========================================================
    # УНИКАЛЬНОЕ ИМЯ ФАЙЛА
    # =========================================================

    @staticmethod
    def generate_unique_filename(directory, original_name):
        original = Path(original_name)

        stem = original.stem
        extension = original.suffix
        target = directory / original.name

        counter = 1

        while target.exists():
            target = directory / f"{stem}_{counter}{extension}"
            counter += 1

        return target

    # =========================================================
    # ДОБАВЛЕНИЕ ДОКУМЕНТА
    # =========================================================

    def add_document(self, product_id, file_path, description=""):
        """
        Копирует документ в папку изделия
        и регистрирует его в базе.

        Возвращает ID документа.
        """

        source = self.validate_file(file_path)

        with self.get_connection() as connection:
            product = connection.execute("""
                SELECT id
                FROM products
                WHERE id = ?
            """, (product_id,)).fetchone()

        if product is None:
            raise ValueError(
                "Изделие с указанным ID не найдено"
            )

        target_directory = self.get_product_directory(product_id)

        target_path = self.generate_unique_filename(
            target_directory,
            source.name,
        )

        shutil.copy2(source, target_path)

        file_size = target_path.stat().st_size

        uploaded_at = datetime.now().isoformat(
            timespec="seconds"
        )

        try:
            with self.get_connection() as connection:
                cursor = connection.execute("""
                    INSERT INTO product_documents (
                        product_id,
                        original_name,
                        stored_path,
                        extension,
                        file_size,
                        description,
                        extracted_text,
                        uploaded_at,
                        parsed_parameters
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    product_id,
                    source.name,
                    str(target_path),
                    source.suffix.lower(),
                    file_size,
                    description,
                    "",
                    uploaded_at,
                    "[]",
                ))

                return cursor.lastrowid

        except Exception:
            target_path.unlink(missing_ok=True)
            raise

    # =========================================================
    # ПОЛУЧЕНИЕ ДОКУМЕНТОВ
    # =========================================================

    def get_product_documents(self, product_id):
        with self.get_connection() as connection:
            documents = connection.execute("""
                SELECT *
                FROM product_documents
                WHERE product_id = ?
                ORDER BY uploaded_at DESC
            """, (product_id,)).fetchall()

            return [dict(document) for document in documents]

    def get_document(self, document_id):
        with self.get_connection() as connection:
            document = connection.execute("""
                SELECT *
                FROM product_documents
                WHERE id = ?
            """, (document_id,)).fetchone()

            return dict(document) if document else None

    # =========================================================
    # СОХРАНЕНИЕ ИЗВЛЕЧЁННОГО ТЕКСТА
    # =========================================================

    def save_extracted_text(self, document_id, extracted_text):
        with self.get_connection() as connection:
            cursor = connection.execute("""
                UPDATE product_documents
                SET extracted_text = ?
                WHERE id = ?
            """, (extracted_text, document_id))

            if cursor.rowcount == 0:
                raise ValueError("Документ не найден")

    # =========================================================
    # СОХРАНЕНИЕ РАСПОЗНАННЫХ ХАРАКТЕРИСТИК
    # =========================================================

    def save_parsed_parameters(self, document_id, parameters):
        serialized = json.dumps(
            parameters or [],
            ensure_ascii=False,
            indent=2,
        )

        with self.get_connection() as connection:
            cursor = connection.execute("""
                UPDATE product_documents
                SET parsed_parameters = ?
                WHERE id = ?
            """, (serialized, document_id))

            if cursor.rowcount == 0:
                raise ValueError("Документ не найден")

    def get_document_suggestions(self, document_id):
        """
        Возвращает характеристики, ранее распознанные из документа.
        """

        document = self.get_document(document_id)

        if document is None:
            raise ValueError("Документ не найден")

        raw_data = document.get("parsed_parameters") or "[]"

        try:
            parameters = json.loads(raw_data)
        except (TypeError, json.JSONDecodeError):
            parameters = []

        return parameters

    # =========================================================
    # ИЗВЛЕЧЕНИЕ ХАРАКТЕРИСТИК ИЗ ДОКУМЕНТА
    # =========================================================

    def parse_document(self, document_id):
        """
        Извлекает текст документа и распознаёт характеристики.

        Результат сохраняется в product_documents.
        Номенклатура при этом не изменяется.
        """

        document = self.get_document(document_id)

        if document is None:
            raise ValueError("Документ не найден")

        extension = document["extension"].lower()

        if extension not in self.PARSER_EXTENSIONS:
            raise ValueError(
                f"Извлечение данных из {extension} пока не поддерживается. "
                "Файл можно хранить, но для DOC и XLS требуется "
                "предварительное преобразование в DOCX или XLSX."
            )

        file_path = Path(document["stored_path"])

        if not file_path.exists():
            raise FileNotFoundError(
                f"Файл документа отсутствует: {file_path}"
            )

        extracted_text = self.parser.extract_text(file_path)

        if not extracted_text.strip():
            raise ValueError(
                "В документе не найден текст"
            )

        parameters = self.parser.suggest_parameters(
            extracted_text
        )

        self.save_extracted_text(
            document_id,
            extracted_text,
        )

        self.save_parsed_parameters(
            document_id,
            parameters,
        )

        return {
            "document_id": document_id,
            "product_id": document["product_id"],
            "original_name": document["original_name"],
            "extracted_text": extracted_text,
            "parameters": parameters,
            "parameters_count": len(parameters),
        }

    # =========================================================
    # ПОДТВЕРЖДЁННОЕ СОХРАНЕНИЕ В НОМЕНКЛАТУРУ
    # =========================================================

    def apply_parameter_suggestions(
        self,
        document_id,
        selected_parameters=None,
    ):
        """
        Записывает подтверждённые характеристики в ProductManager.

        selected_parameters:
            список распознанных характеристик, которые пользователь
            проверил и подтвердил.

        Если список не передан, используются все сохранённые
        предложения, у которых есть хотя бы одна граница допуска.

        Обновляются только уже существующие характеристики изделия.
        Новые характеристики автоматически не создаются.
        """

        from .product_manager import ProductManager

        document = self.get_document(document_id)

        if document is None:
            raise ValueError("Документ не найден")

        if selected_parameters is None:
            selected_parameters = self.get_document_suggestions(
                document_id
            )

        product_id = document["product_id"]

        product_manager = ProductManager()

        existing_parameters = (
            product_manager.get_product_parameters(product_id)
        )

        # Точное сопоставление кодов.
        # Регистр важен: d и D — разные характеристики.
        existing_by_code = {}

        for parameter in existing_parameters:
            code = str(parameter.get("code") or "").strip()

            if code:
                existing_by_code[code] = parameter

        updated = []
        skipped = []
        errors = []

        for suggestion in selected_parameters:
            code = str(suggestion.get("code") or "").strip()

            minimum = suggestion.get("min_value")
            maximum = suggestion.get("max_value")

            # Не записываем характеристику без явно найденного допуска.
            if minimum is None and maximum is None:
                skipped.append({
                    "code": code,
                    "reason": "В документе не найден допуск",
                })
                continue

            if not code:
                skipped.append({
                    "code": "",
                    "reason": "Отсутствует обозначение характеристики",
                })
                continue

            existing = existing_by_code.get(code)

            if existing is None:
                skipped.append({
                    "code": code,
                    "reason": "Характеристика с таким кодом не найдена в номенклатуре",
                })
                continue

            try:
                data = {
                    "name": suggestion.get("name")
                    or existing.get("name"),

                    "code": code,

                    "nominal": (
                        suggestion.get("nominal")
                        if suggestion.get("nominal") is not None
                        else existing.get("nominal")
                    ),

                    "min_value": minimum,
                    "max_value": maximum,

                    "unit": suggestion.get("unit")
                    or existing.get("unit", ""),

                    "source": "document",

                    "note": (
                        f"Источник: {document['original_name']}. "
                        f"Документ ID: {document_id}. "
                        f"{suggestion.get('note', '')}"
                    ).strip(),
                }

                product_manager.update_parameter(
                    existing["id"],
                    data,
                )

                updated.append({
                    "code": code,
                    "name": data["name"],
                    "min_value": minimum,
                    "max_value": maximum,
                })

            except Exception as error:
                errors.append({
                    "code": code,
                    "error": str(error),
                })

        return {
            "document_id": document_id,
            "product_id": product_id,
            "updated": updated,
            "skipped": skipped,
            "errors": errors,
            "updated_count": len(updated),
            "skipped_count": len(skipped),
            "errors_count": len(errors),
        }

    # =========================================================
    # ОПИСАНИЕ ДОКУМЕНТА
    # =========================================================

    def update_description(self, document_id, description):
        with self.get_connection() as connection:
            cursor = connection.execute("""
                UPDATE product_documents
                SET description = ?
                WHERE id = ?
            """, (description, document_id))

            if cursor.rowcount == 0:
                raise ValueError("Документ не найден")

    # =========================================================
    # ПОЛУЧЕНИЕ ПУТИ К ОРИГИНАЛУ
    # =========================================================

    def get_document_path(self, document_id):
        document = self.get_document(document_id)

        if document is None:
            raise ValueError("Документ не найден")

        path = Path(document["stored_path"])

        if not path.exists():
            raise FileNotFoundError(
                "Файл документа отсутствует на диске"
            )

        return path

    # =========================================================
    # ПРОВЕРКА НАЛИЧИЯ ФАЙЛА
    # =========================================================

    def document_file_exists(self, document_id):
        document = self.get_document(document_id)

        if document is None:
            return False

        return Path(document["stored_path"]).is_file()

    # =========================================================
    # УДАЛЕНИЕ ДОКУМЕНТА
    # =========================================================

    def delete_document(self, document_id):
        document = self.get_document(document_id)

        if document is None:
            raise ValueError("Документ не найден")

        file_path = Path(document["stored_path"])

        with self.get_connection() as connection:
            connection.execute("""
                DELETE FROM product_documents
                WHERE id = ?
            """, (document_id,))

        try:
            file_path.unlink(missing_ok=True)
        except OSError as error:
            raise OSError(
                "Запись удалена из базы данных, "
                f"но файл не удалось удалить: {error}"
            )

    # =========================================================
    # РАЗМЕР ФАЙЛА
    # =========================================================

    @staticmethod
    def format_file_size(size):
        if size < 1024:
            return f"{size} Б"

        if size < 1024 * 1024:
            return f"{size / 1024:.1f} КБ"

        if size < 1024 * 1024 * 1024:
            return f"{size / (1024 * 1024):.1f} МБ"

        return f"{size / (1024 * 1024 * 1024):.2f} ГБ"
