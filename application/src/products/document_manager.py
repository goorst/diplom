
import shutil
import uuid

from pathlib import Path

from .product_manager import ProductManager, PROJECT_ROOT


DOCUMENTS_DIR = (
    PROJECT_ROOT / "data" / "documents" / "products"
)


class DocumentManager:

    SUPPORTED_FORMATS = {
        ".pdf",
        ".dxf",
        ".step",
        ".stp",
        ".dwg",
        ".png",
        ".jpg",
        ".jpeg",
        ".xlsx",
        ".docx"
    }

    def __init__(self, product_manager=None):

        self.product_manager = (
            product_manager or ProductManager()
        )

        self.database_path = (
            self.product_manager.database_path
        )

        DOCUMENTS_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

    # ==========================================
    # ПОДКЛЮЧЕНИЕ К БАЗЕ
    # ==========================================

    def _connect(self):

        return self.product_manager._connect()

    # ==========================================
    # ПРОВЕРКА ФОРМАТА
    # ==========================================

    def validate_document(self, file_path):

        path = Path(file_path)

        if not path.exists():

            raise FileNotFoundError(
                "Выбранный файл не существует"
            )

        if not path.is_file():

            raise ValueError(
                "Выбранный объект не является файлом"
            )

        extension = path.suffix.lower()

        if extension not in self.SUPPORTED_FORMATS:

            raise ValueError(
                f"Формат {extension} не поддерживается"
            )

        if path.stat().st_size == 0:

            raise ValueError(
                "Выбран пустой файл"
            )

        return extension

    # ==========================================
    # ДОБАВЛЕНИЕ ДОКУМЕНТА
    # ==========================================

    def add_document(
        self,
        product_id,
        file_path,
        category="Техническая документация",
        description=""
    ):

        if not self.product_manager.product_exists(
            product_id
        ):

            raise ValueError(
                "Изделие не найдено"
            )

        source_path = Path(file_path)

        extension = self.validate_document(
            source_path
        )

        document_id = (
            f"DOC-{uuid.uuid4().hex[:12].upper()}"
        )

        # Отдельная папка для каждого изделия
        product_directory = (
            DOCUMENTS_DIR / product_id
        )

        product_directory.mkdir(
            parents=True,
            exist_ok=True
        )

        # Уникальное имя файла
        stored_name = (
            f"{document_id}{extension}"
        )

        destination = (
            product_directory / stored_name
        )

        # Копирование оригинала
        shutil.copy2(
            source_path,
            destination
        )

        relative_path = destination.relative_to(
            PROJECT_ROOT
        )

        try:

            with self._connect() as connection:

                connection.execute(
                    """
                    INSERT INTO documents (
                        document_id,
                        product_id,
                        original_name,
                        stored_path,
                        extension,
                        category,
                        description
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        document_id,
                        product_id,
                        source_path.name,
                        str(relative_path),
                        extension,
                        category,
                        description
                    )
                )

        except Exception:

            destination.unlink(missing_ok=True)

            raise

        return document_id

    # ==========================================
    # СПИСОК ДОКУМЕНТОВ ИЗДЕЛИЯ
    # ==========================================

    def list_documents(self, product_id):

        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT *
                FROM documents
                WHERE product_id = ?
                ORDER BY uploaded_at DESC
                """,
                (product_id,)
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    # ==========================================
    # ПОЛУЧЕНИЕ ПУТИ К ДОКУМЕНТУ
    # ==========================================

    def get_document_path(self, document_id):

        with self._connect() as connection:

            row = connection.execute(
                """
                SELECT stored_path
                FROM documents
                WHERE document_id = ?
                """,
                (document_id,)
            ).fetchone()

        if row is None:

            raise ValueError(
                "Документ не найден"
            )

        path = (
            PROJECT_ROOT / row["stored_path"]
        ).resolve()

        # Проверка, что путь остаётся внутри папки документов
        documents_root = DOCUMENTS_DIR.resolve()

        if not path.is_relative_to(documents_root):

            raise ValueError(
                "Недопустимый путь к документу"
            )

        if not path.is_file():

            raise FileNotFoundError(
                "Файл документа отсутствует на диске"
            )

        return path

    # ==========================================
    # УДАЛЕНИЕ ДОКУМЕНТА
    # ==========================================

    def delete_document(self, document_id):

        with self._connect() as connection:

            row = connection.execute(
                """
                SELECT stored_path
                FROM documents
                WHERE document_id = ?
                """,
                (document_id,)
            ).fetchone()

            if row is None:

                raise ValueError(
                    "Документ не найден"
                )

            relative_path = Path(
                row["stored_path"]
            )

            file_path = (
                PROJECT_ROOT / relative_path
            ).resolve()

            if not file_path.is_relative_to(
                DOCUMENTS_DIR.resolve()
            ):

                raise ValueError(
                    "Недопустимый путь к документу"
                )

            connection.execute(
                """
                DELETE FROM documents
                WHERE document_id = ?
                """,
                (document_id,)
            )

        file_path.unlink(missing_ok=True)

    # ==========================================
    # ПОЛУЧЕНИЕ ВСЕХ ДОКУМЕНТОВ
    # ==========================================

    def list_all_documents(self):

        with self._connect() as connection:

            rows = connection.execute(
                """
                SELECT
                    documents.*,
                    products.name AS product_name
                FROM documents
                JOIN products
                    ON documents.product_id = products.product_id
                ORDER BY documents.uploaded_at DESC
                """
            ).fetchall()

        return [
            dict(row)
            for row in rows
        ]
