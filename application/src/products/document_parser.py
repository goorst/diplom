
import re
from pathlib import Path

from docx import Document
from openpyxl import load_workbook


class DocumentParser:
    """
    Извлечение технических характеристик из документации.

    Поддерживаемые форматы:
    PDF, DOCX, XLSX, PNG, JPG, TIFF.

    Распознаются:
    - табличные характеристики;
    - русские и английские названия;
    - условные обозначения d, D, B, Cr, C0r и другие;
    - номинальные значения;
    - симметричные и асимметричные допуски;
    - односторонние допуски.

    Допуски рассчитываются только при наличии явного указания
    в техническом документе.
    """

    SUPPORTED_EXTENSIONS = {
        ".pdf", ".docx", ".xlsx",
        ".png", ".jpg", ".jpeg", ".tif", ".tiff",
    }

    TABLE_PARAMETER_NAMES = {
        "d": "Диаметр отверстия",
        "D": "Наружный диаметр",
        "B": "Ширина изделия",
        "r (min.)": "Минимальный радиус фаски",
        "Cr": "Динамическая грузоподъёмность",
        "C0r": "Статическая грузоподъёмность",
        "da (min.)": "Минимальный диаметр опорной поверхности вала",
        "da (max.)": "Максимальный диаметр опорной поверхности вала",
        "Da (max.)": "Максимальный диаметр опорной поверхности корпуса",
        "ra (max.)": "Максимальный радиус галтели",
        "fo": "Расчётный коэффициент",
        "z": "Количество тел качения",
        "Dw": "Диаметр шарика",
        "Mass approx.": "Приблизительная масса",
    }

    # ---------------------------------------------------------
    # ИЗВЛЕЧЕНИЕ ТЕКСТА
    # ---------------------------------------------------------

    def extract_text(self, file_path):
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Файл не найден: {path}")

        extension = path.suffix.lower()

        if extension == ".pdf":
            return self._extract_pdf(path)

        if extension == ".docx":
            return self._extract_docx(path)

        if extension == ".xlsx":
            return self._extract_xlsx(path)

        if extension in {
            ".png", ".jpg", ".jpeg", ".tif", ".tiff"
        }:
            return self._extract_image(path)

        raise ValueError(
            f"Формат {extension} не поддерживается парсером"
        )

    # ---------------------------------------------------------
    # PDF
    # ---------------------------------------------------------

    def _extract_pdf(self, path):
        try:
            import fitz

            pdf = fitz.open(str(path))
            pages_text = []

            for page in pdf:
                words = page.get_text("words")

                if words:
                    rows = self._group_pdf_words_into_rows(words)
                    page_text = "\n".join(rows)
                else:
                    page_text = page.get_text("text", sort=True)

                if page_text.strip():
                    pages_text.append(page_text)

            pdf.close()

            text = "\n\n".join(pages_text)

            if text.strip():
                return self.normalize_text(text)

        except ImportError:
            pass

        except Exception as error:
            print(f"Ошибка PyMuPDF: {error}")

        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            pages_text = []

            for page in reader.pages:
                page_text = page.extract_text() or ""

                if page_text.strip():
                    pages_text.append(page_text)

            text = "\n\n".join(pages_text)

            if text.strip():
                return self.normalize_text(text)

        except ImportError:
            pass

        except Exception as error:
            print(f"Ошибка pypdf: {error}")

        return self._extract_pdf_ocr(path)

    @staticmethod
    def _group_pdf_words_into_rows(words):
        if not words:
            return []

        sorted_words = sorted(
            words,
            key=lambda item: (item[1], item[0]),
        )

        rows = []
        current_row = []
        current_y = None
        tolerance = 3.5

        for word in sorted_words:
            x0, y0 = word[0], word[1]

            if current_y is None:
                current_y = y0
                current_row = [word]
                continue

            if abs(y0 - current_y) <= tolerance:
                current_row.append(word)
            else:
                current_row.sort(key=lambda item: item[0])

                row_text = " ".join(
                    str(item[4]) for item in current_row
                )

                if row_text.strip():
                    rows.append(row_text)

                current_row = [word]
                current_y = y0

        if current_row:
            current_row.sort(key=lambda item: item[0])

            row_text = " ".join(
                str(item[4]) for item in current_row
            )

            if row_text.strip():
                rows.append(row_text)

        return rows

    def _extract_pdf_ocr(self, path):
        try:
            import fitz
            from PIL import Image
            import pytesseract
            from io import BytesIO

        except ImportError as error:
            raise RuntimeError(
                "Для OCR установите:\n"
                "python -m pip install PyMuPDF Pillow pytesseract\n"
                "Также необходимо установить Tesseract OCR."
            ) from error

        pdf = fitz.open(str(path))
        pages_text = []

        for page in pdf:
            pix = page.get_pixmap(
                matrix=fitz.Matrix(2.5, 2.5),
                alpha=False,
            )

            image = Image.open(BytesIO(pix.tobytes("png")))

            try:
                page_text = pytesseract.image_to_string(
                    image,
                    lang="rus+eng",
                    config="--psm 6",
                )
            except Exception:
                page_text = pytesseract.image_to_string(
                    image,
                    lang="eng",
                    config="--psm 6",
                )

            if page_text.strip():
                pages_text.append(page_text)

        pdf.close()

        text = "\n\n".join(pages_text)

        if not text.strip():
            raise ValueError(
                "Не удалось распознать текст документа"
            )

        return self.normalize_text(text)

    # ---------------------------------------------------------
    # DOCX
    # ---------------------------------------------------------

    def _extract_docx(self, path):
        document = Document(str(path))
        result = []

        for paragraph in document.paragraphs:
            text = paragraph.text.strip()

            if text:
                result.append(text)

        for table_index, table in enumerate(
            document.tables,
            start=1,
        ):
            result.append(f"\nТаблица {table_index}:")

            for row in table.rows:
                values = [
                    cell.text.strip().replace("\n", " ")
                    for cell in row.cells
                ]

                result.append(" | ".join(values))

        return self.normalize_text("\n".join(result))

    # ---------------------------------------------------------
    # XLSX
    # ---------------------------------------------------------

    def _extract_xlsx(self, path):
        workbook = load_workbook(
            filename=str(path),
            data_only=True,
            read_only=True,
        )

        result = []

        for sheet in workbook.worksheets:
            result.append(f"\nЛист: {sheet.title}")

            for row in sheet.iter_rows(values_only=True):
                values = [
                    str(value).strip()
                    for value in row
                    if value is not None
                ]

                if values:
                    result.append(" | ".join(values))

        workbook.close()

        return self.normalize_text("\n".join(result))

    # ---------------------------------------------------------
    # ИЗОБРАЖЕНИЯ
    # ---------------------------------------------------------

    def _extract_image(self, path):
        try:
            from PIL import Image
            import pytesseract

        except ImportError as error:
            raise RuntimeError(
                "Для OCR изображений установите:\n"
                "python -m pip install Pillow pytesseract"
            ) from error

        image = Image.open(str(path))

        try:
            text = pytesseract.image_to_string(
                image,
                lang="rus+eng",
                config="--psm 6",
            )
        except Exception:
            text = pytesseract.image_to_string(
                image,
                lang="eng",
                config="--psm 6",
            )

        return self.normalize_text(text)

    # ---------------------------------------------------------
    # НОРМАЛИЗАЦИЯ
    # ---------------------------------------------------------

    @staticmethod
    def normalize_text(text):
        if not text:
            return ""

        text = str(text)

        replacements = {
            "\xa0": " ",
            "\u200b": "",
            "×": "x",
            "Ø": "⌀",
            "ø": "⌀",
            "−": "-",
            "–": "-",
            "—": "-",
            "±": "±",
        }

        for old, new in replacements.items():
            text = text.replace(old, new)

        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    @staticmethod
    def _parse_float(value):
        if value is None:
            return None

        value = str(value).strip().replace(",", ".")

        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _make_parameter(
        name,
        code="",
        nominal=None,
        minimum=None,
        maximum=None,
        unit="",
        source="document",
        note="",
    ):
        return {
            "name": name,
            "code": code,
            "nominal": nominal,
            "min_value": minimum,
            "max_value": maximum,
            "unit": unit,
            "source": source,
            "note": note,
        }

    # ---------------------------------------------------------
    # ЕДИНИЦЫ ИЗМЕРЕНИЯ
    # ---------------------------------------------------------

    @staticmethod
    def _normalize_unit(unit):
        unit = (unit or "").strip().lower()

        units = {
            "mm": "мм",
            "cm": "см",
            "m": "м",
            "kg": "кг",
            "g": "г",
            "mg": "мг",
            "n": "Н",
            "kn": "кН",
            "mpa": "МПа",
            "gpa": "ГПа",
            "rpm": "об/мин",
            "min-1": "об/мин",
            "µm": "мкм",
            "um": "мкм",
        }

        return units.get(unit, unit)

    # ---------------------------------------------------------
    # НОРМАЛИЗАЦИЯ КОДА
    # ---------------------------------------------------------

    @staticmethod
    def _normalize_code(code):
        return re.sub(
            r"\s+",
            " ",
            str(code or "").strip(),
        )

    # ---------------------------------------------------------
    # РАЗБОР ЗАПИСИ ДОПУСКА
    # ---------------------------------------------------------

    def _parse_deviation(self, text):
        """
        Возвращает пару отклонений (нижнее, верхнее).

        Поддерживаются:
        ±0.01
        +0.2/-0.1
        0/-0.008
        -0.008/0

        Для записи двух отклонений используются их числовые
        значения, а не положение в строке.
        """

        if not text:
            return None

        text = text.strip().replace(",", ".")

        # Симметричный допуск: ±0.01
        match = re.fullmatch(
            r"±\s*(\d+(?:\.\d+)?)",
            text,
        )

        if match:
            tolerance = float(match.group(1))
            return -tolerance, tolerance

        # Два отклонения через дробную черту.
        # Например: +0.2/-0.1 или 0/-0.008.
        match = re.fullmatch(
            r"([+-]?\d+(?:\.\d+)?)"
            r"\s*/\s*"
            r"([+-]?\d+(?:\.\d+)?)",
            text,
        )

        if match:
            first = float(match.group(1))
            second = float(match.group(2))

            return min(first, second), max(first, second)

        return None

    @staticmethod
    def _find_tolerance_in_tail(tail):
        """
        Ищет запись допуска после номинального значения.
        Возвращает текст допуска либо None.
        """

        if not tail:
            return None

        tail = tail.strip().replace(",", ".")

        patterns = [
            r"±\s*\d+(?:\.\d+)?",
            (
                r"[+-]?\d+(?:\.\d+)?"
                r"\s*/\s*"
                r"[+-]?\d+(?:\.\d+)?"
            ),
        ]

        for pattern in patterns:
            match = re.search(pattern, tail)

            if match:
                return match.group(0)

        return None

    # ---------------------------------------------------------
    # НАЗВАНИЯ ХАРАКТЕРИСТИК
    # ---------------------------------------------------------

    def _get_table_parameter_name(self, code, label=""):
        label_lower = (label or "").lower()

        label_rules = [
            (
                ("bore diameter", "диаметр отверстия"),
                "Диаметр отверстия",
            ),
            (
                ("outside diameter", "outer diameter", "наружный диаметр"),
                "Наружный диаметр",
            ),
            (
                ("width", "ширина"),
                "Ширина изделия",
            ),
            (
                ("chamfer dimension", "размер фаски"),
                "Размер фаски",
            ),
            (
                ("basic dynamic load rating", "динамическая грузоподъёмность"),
                "Динамическая грузоподъёмность",
            ),
            (
                ("basic static load rating", "статическая грузоподъёмность"),
                "Статическая грузоподъёмность",
            ),
            (
                ("diameter of shaft abutment", "диаметр опорной поверхности вала"),
                "Диаметр опорной поверхности вала",
            ),
            (
                ("diameter of housing abutment", "диаметр опорной поверхности корпуса"),
                "Диаметр опорной поверхности корпуса",
            ),
            (
                ("radius of shaft or housing fillet", "радиус галтели"),
                "Радиус галтели",
            ),
            (
                ("number of balls", "количество шариков"),
                "Количество шариков",
            ),
            (
                ("ball diameter", "диаметр шарика"),
                "Диаметр шарика",
            ),
            (
                ("factor", "коэффициент"),
                "Расчётный коэффициент",
            ),
        ]

        for keywords, name in label_rules:
            if any(keyword in label_lower for keyword in keywords):
                return name

        code_clean = re.sub(
            r"\s+",
            " ",
            str(code).strip(),
        )

        for known_code, name in self.TABLE_PARAMETER_NAMES.items():
            if code_clean.lower() == known_code.lower():
                return name

        return None

    # ---------------------------------------------------------
    # РАЗБОР ТАБЛИЧНОЙ СТРОКИ
    # ---------------------------------------------------------

    def _parse_table_line(self, line):
        line = line.strip()

        if not line:
            return None

        # Масса.
        mass_match = re.search(
            r"mass\s+approx\.?\s*"
            r"([-+]?\d+(?:[.,]\d+)?)\s*"
            r"(kg|g|mg)?",
            line,
            flags=re.IGNORECASE,
        )

        if mass_match:
            value = self._parse_float(mass_match.group(1))
            unit = (mass_match.group(2) or "").lower()

            if value is not None:
                if unit == "kg":
                    value *= 1000
                elif unit == "mg":
                    value /= 1000

                return self._make_parameter(
                    name="Приблизительная масса",
                    code="Mass approx.",
                    nominal=value,
                    unit="г" if unit else "",
                    note=f"Извлечено из строки: {line}",
                )

        code_pattern = (
            r"(?P<code>"
            r"C0r|Cr|Dw|Da|da|ra|fo|"
            r"d|D|B|z|"
            r"r\s*\(\s*min\.?\s*\)|"
            r"da\s*\(\s*min\.?\s*\)|"
            r"da\s*\(\s*max\.?\s*\)|"
            r"Da\s*\(\s*max\.?\s*\)|"
            r"ra\s*\(\s*max\.?\s*\)"
            r")"
        )

        match = re.match(
            code_pattern
            + r"\s+"
            + r"(?P<value>[-+]?\d+(?:[.,]\d+)?)"
            + r"\s*"
            + r"(?P<unit>mm|cm|m|kg|g|mg|n|kn|mpa|gpa|rpm|min-1)?"
            + r"(?P<tail>.*)$",
            line,
            flags=re.IGNORECASE,
        )

        if not match:
            return None

        code = match.group("code").strip()
        value = self._parse_float(match.group("value"))
        unit = self._normalize_unit(match.group("unit") or "")
        tail = match.group("tail") or ""

        if value is None:
            return None

        # Удаляем из хвоста разделители и пробелы.
        tail = re.sub(r"^[\s:;|]+", "", tail)

        tolerance_text = self._find_tolerance_in_tail(tail)
        deviation = self._parse_deviation(tolerance_text)

        minimum = None
        maximum = None

        if deviation is not None:
            lower_deviation, upper_deviation = deviation
            minimum = round(value + lower_deviation, 9)
            maximum = round(value + upper_deviation, 9)

        label = tail

        if tolerance_text:
            label = label.replace(tolerance_text, "", 1)

        label = label.strip(" |;:-")

        name = self._get_table_parameter_name(code, label)

        if not name:
            return None

        return self._make_parameter(
            name=name,
            code=code,
            nominal=value,
            minimum=minimum,
            maximum=maximum,
            unit=unit,
            note=f"Извлечено из табличной строки: {line}",
        )

    def _extract_table_parameters(self, text):
        results = []

        for line in text.splitlines():
            parameter = self._parse_table_line(line)

            if parameter:
                results.append(parameter)

        return results

    # ---------------------------------------------------------
    # ПОИСК ДОПУСКОВ В ОБЫЧНОМ ТЕКСТЕ
    # ---------------------------------------------------------

    def _extract_tolerance_parameters(self, text):
        """
        Распознаёт допуски в текстовых строках.

        Примеры:
        Диаметр 50 ±0.1 мм
        Диаметр 50 +0.2/-0.1 мм
        Диаметр 50 0/-0.1 мм
        Diameter 50 ±0.1 mm
        """

        results = []

        name_pattern = (
            r"(?P<name>"
            r"диаметр отверстия|наружный диаметр|диаметр|"
            r"длина|ширина изделия|ширина|высота|"
            r"bore diameter|outside diameter|outer diameter|"
            r"diameter|length|width|height"
            r")"
        )

        number = r"[-+]?\d+(?:[.,]\d+)?"

        unit_pattern = r"(?:мм|см|м|mm|cm|m)?"

        tolerance_pattern = (
            r"(?:"
            r"±\s*\d+(?:[.,]\d+)?"
            r"|"
            r"[+-]?\d+(?:[.,]\d+)?"
            r"\s*/\s*"
            r"[+-]?\d+(?:[.,]\d+)?"
            r")"
        )

        pattern = re.compile(
            name_pattern
            + r"\s*[:=]?\s*"
            + r"(?P<nominal>" + number + r")"
            + r"\s*"
            + r"(?P<tolerance>" + tolerance_pattern + r")"
            + r"\s*"
            + r"(?P<unit>" + unit_pattern + r")",
            flags=re.IGNORECASE,
        )

        name_map = {
            "диаметр отверстия": "Диаметр отверстия",
            "наружный диаметр": "Наружный диаметр",
            "диаметр": "Диаметр",
            "длина": "Длина",
            "ширина изделия": "Ширина изделия",
            "ширина": "Ширина",
            "высота": "Высота",
            "bore diameter": "Диаметр отверстия",
            "outside diameter": "Наружный диаметр",
            "outer diameter": "Наружный диаметр",
            "diameter": "Диаметр",
            "length": "Длина",
            "width": "Ширина",
            "height": "Высота",
        }

        code_map = {
            "диаметр отверстия": "d",
            "наружный диаметр": "D",
            "диаметр": "diameter",
            "длина": "length",
            "ширина изделия": "B",
            "ширина": "width",
            "высота": "height",
            "bore diameter": "d",
            "outside diameter": "D",
            "outer diameter": "D",
            "diameter": "diameter",
            "length": "length",
            "width": "width",
            "height": "height",
        }

        for line in text.splitlines():
            for match in pattern.finditer(line):
                nominal = self._parse_float(
                    match.group("nominal")
                )

                deviation = self._parse_deviation(
                    match.group("tolerance")
                )

                if nominal is None or deviation is None:
                    continue

                lower_deviation, upper_deviation = deviation

                minimum = round(nominal + lower_deviation, 9)
                maximum = round(nominal + upper_deviation, 9)

                raw_name = match.group("name").lower()
                unit = self._normalize_unit(
                    match.group("unit")
                )

                results.append(
                    self._make_parameter(
                        name=name_map.get(raw_name, raw_name),
                        code=code_map.get(raw_name, ""),
                        nominal=nominal,
                        minimum=minimum,
                        maximum=maximum,
                        unit=unit,
                        note=(
                            "Допуск явно указан в документе: "
                            f"{line.strip()}"
                        ),
                    )
                )

        return results

    # ---------------------------------------------------------
    # ХАРАКТЕРИСТИКИ ИЗ ОБЫЧНОГО ТЕКСТА
    # ---------------------------------------------------------

    def _extract_text_parameters(self, text):
        results = []

        patterns = [
            {
                "name": "Диаметр",
                "code": "diameter",
                "pattern": (
                    r"(?:диаметр|⌀)"
                    r"\s*[:=]?\s*"
                    r"([-+]?\d+(?:[.,]\d+)?)"
                    r"\s*(мм|см|м)?"
                ),
            },
            {
                "name": "Длина",
                "code": "length",
                "pattern": (
                    r"(?:длина|length)"
                    r"\s*[:=]?\s*"
                    r"([-+]?\d+(?:[.,]\d+)?)"
                    r"\s*(мм|см|м)?"
                ),
            },
            {
                "name": "Ширина",
                "code": "width",
                "pattern": (
                    r"(?:ширина|width)"
                    r"\s*[:=]?\s*"
                    r"([-+]?\d+(?:[.,]\d+)?)"
                    r"\s*(мм|см|м)?"
                ),
            },
            {
                "name": "Высота",
                "code": "height",
                "pattern": (
                    r"(?:высота|height)"
                    r"\s*[:=]?\s*"
                    r"([-+]?\d+(?:[.,]\d+)?)"
                    r"\s*(мм|см|м)?"
                ),
            },
            {
                "name": "Масса",
                "code": "mass",
                "pattern": (
                    r"(?:масса|mass)"
                    r"\s*[:=]?\s*"
                    r"([-+]?\d+(?:[.,]\d+)?)"
                    r"\s*(кг|г|мг|kg|g|mg)?"
                ),
            },
            {
                "name": "Плотность",
                "code": "density",
                "pattern": (
                    r"(?:плотность|density)"
                    r"\s*[:=]?\s*"
                    r"([-+]?\d+(?:[.,]\d+)?)"
                    r"\s*(кг/м3|кг/м³|г/см3|г/см³|kg/m3)?"
                ),
            },
            {
                "name": "Шероховатость поверхности",
                "code": "roughness",
                "pattern": (
                    r"(?:шероховатость|ra)"
                    r"\s*[:=]?\s*"
                    r"([-+]?\d+(?:[.,]\d+)?)"
                    r"\s*(мкм|µm|um)?"
                ),
            },
        ]

        for rule in patterns:
            match = re.search(
                rule["pattern"],
                text,
                flags=re.IGNORECASE,
            )

            if not match:
                continue

            value = self._parse_float(match.group(1))

            if value is None:
                continue

            raw_unit = (match.group(2) or "").lower()
            unit = self._normalize_unit(raw_unit)

            if rule["code"] == "mass":
                if raw_unit in ("кг", "kg"):
                    value *= 1000
                elif raw_unit in ("мг", "mg"):
                    value /= 1000

                unit = "г"

            if rule["code"] == "density":
                if raw_unit in ("г/см3", "г/см³"):
                    value *= 1000

                unit = "кг/м³"

            if rule["code"] == "roughness":
                unit = "мкм"

            results.append(
                self._make_parameter(
                    name=rule["name"],
                    code=rule["code"],
                    nominal=value,
                    unit=unit,
                    note="Извлечено из текстового описания",
                )
            )

        return results

    # ---------------------------------------------------------
    # УДАЛЕНИЕ ДУБЛЕЙ
    # ---------------------------------------------------------

    @staticmethod
    def _remove_duplicates(parameters):
        result = []
        positions = {}

        for parameter in parameters:
            key = (
                str(parameter.get("code") or "").strip().lower(),
                str(parameter.get("name") or "").strip().lower(),
            )

            if key not in positions:
                positions[key] = len(result)
                result.append(parameter)
                continue

            index = positions[key]
            existing = result[index]

            # Если одна запись содержит допуски, а другая нет,
            # сохраняем вариант с допусками.
            if (
                existing.get("min_value") is None
                and existing.get("max_value") is None
                and (
                    parameter.get("min_value") is not None
                    or parameter.get("max_value") is not None
                )
            ):
                result[index] = parameter

        return result

    # ---------------------------------------------------------
    # ОСНОВНОЙ МЕТОД
    # ---------------------------------------------------------

    def suggest_parameters(self, text):
        """
        Возвращает список распознанных характеристик.

        Метод не записывает данные в базу.
        """

        if not text or not str(text).strip():
            return []

        text = self.normalize_text(text)

        results = []

        results.extend(
            self._extract_table_parameters(text)
        )

        results.extend(
            self._extract_text_parameters(text)
        )

        results.extend(
            self._extract_tolerance_parameters(text)
        )

        return self._remove_duplicates(results)
