class FaultSimulator:

    AVAILABLE_FAULTS = {
        "overheating": "Перегрев",
        "high_vibration": "Повышенная вибрация",
        "overload": "Перегрузка шпинделя",
        "tool_wear": "Критический износ инструмента",
        "combined": "Комплексная неисправность"
    }

    @staticmethod
    def apply_faults(data, faults):

        result = data.copy()

        if "combined" in faults:
            faults = [
                "overheating",
                "high_vibration",
                "overload",
                "tool_wear"
            ]

        if "overheating" in faults:
            result["temperature"] += 35

        if "high_vibration" in faults:
            result["vibration"] += 2.0

        if "overload" in faults:
            result["spindle_load"] += 35

        if "tool_wear" in faults:
            result["tool_wear"] = max(
                result["tool_wear"],
                90
            )

        return result