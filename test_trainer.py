
from application.src.quality.model_trainer import ModelTrainer

trainer = ModelTrainer()

result = trainer.train()

print("\n======= СРАВНЕНИЕ МОДЕЛЕЙ =======")

print(
    result["comparison"].to_string(
        index=False
    )
)

print("\nЛучшая модель:")
print(result["best_model"])

print("\n======= ИНФОРМАЦИЯ О ВЫБОРКАХ =======")

print("Обучающих записей:", result["train_records"])
print("Тестовых записей:", result["test_records"])

print("Обучающих экспериментов:", result["train_experiments"])
print("Тестовых экспериментов:", result["test_experiments"])

print("Изделий в обучении:", result["train_products"])
print("Изделий в тестировании:", result["test_products"])

print("\n======= СОХРАНЁННЫЕ ФАЙЛЫ =======")

for name, path in result["paths"].items():
    print(f"{name}: {path}")

print("\n======= МАТРИЦЫ ОШИБОК =======")

for model_name, metrics in result["results"].items():
    print(f"\n{model_name}")
    print(metrics["confusion_matrix"])
