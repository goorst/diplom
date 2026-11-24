class ConditionMonitor:
    """
    Правила первичной оценки технического состояния
    виртуального станка.

    Пороговые значения предварительные и предназначены
    для экспериментальной модели. Их нужно будет откалибровать.
    """

    LIMITS = {
        "temperature": {
            "warning": 75.0,
            "critical": 90.0,
            "name": "Температура",
            "unit": "°C",
        },
        "vibration": {
            "warning": 3.0,
            "critical": 5.0,
            "name": "Вибрация",
            "unit": "мм/с",
        },
        "spindle_load": {
            "warning": 75.0,
            "critical": 90.0,
            "name": "Нагрузка шпинделя",
            "unit": "%",
        },
        "tool_wear": {
            "warning": 70.0,
            "critical": 90.0,
            "name": "Износ инструмента",
            "unit": "%",
        },
    }

    RECOMMENDATIONS = {
        "temperature": (
            "Проверьте охлаждение и рассмотрите снижение "
            "оборотов шпинделя или подачи."
        ),
        "vibration": (
            "Проверьте закрепление заготовки, инструмент "
            "и состояние шпиндельного узла."
        ),
        "spindle_load": (
            "Снизьте подачу или глубину резания. "
            "Проверьте нагрузку на инструмент."
        ),
        "tool_wear": (
            "Рекомендуется проверить состояние и заменить "
            "изношенный инструмент."
        ),
    }

    @classmethod
    def evaluate(cls, measurement):
        warnings = []
        criticals = []
        recommendations = []

        for key, limits in cls.LIMITS.items():
            value = measurement.get(key)

            if value is None:
                continue

            value = float(value)

            if value >= limits["critical"]:
                criticals.append(
                    f"{limits['name']}: {value:.2f} "
                    f"{limits['unit']} — критический уровень"
                )
                recommendations.append(
                    cls.RECOMMENDATIONS[key]
                )

            elif value >= limits["warning"]:
                warnings.append(
                    f"{limits['name']}: {value:.2f} "
                    f"{limits['unit']} — превышен порог предупреждения"
                )
                recommendations.append(
                    cls.RECOMMENDATIONS[key]
                )

        if criticals:
            status = "КРИТИЧЕСКОЕ СОСТОЯНИЕ"
            color = "#ff5555"
            reasons = criticals + warnings

        elif warnings:
            status = "ПРЕДУПРЕЖДЕНИЕ"
            color = "#ffbd44"
            reasons = warnings

        else:
            status = "НОРМА"
            color = "#65d982"
            reasons = ["Все контролируемые параметры в заданных пределах."]

        # Удаляем повторяющиеся рекомендации
        recommendations = list(dict.fromkeys(recommendations))

        if not recommendations:
            recommendations = [
                "Продолжайте мониторинг параметров обработки."
            ]

        return {
            "status": status,
            "color": color,
            "reasons": reasons,
            "recommendations": recommendations,
        }