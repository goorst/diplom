from application.src.quality.ensemble_model import EnsembleModel
from application.src.quality.dataset_builder import DatasetBuilder

builder = DatasetBuilder()
dataset = builder.build_dataset()

train = dataset["train_dataframe"]
test = dataset["test_dataframe"]

model = EnsembleModel()

model.fit(train)

print("\n======= ОЦЕНКА АНСАМБЛЕВОЙ МОДЕЛИ =======")

metrics = model.evaluate(test)

print("Accuracy:", metrics["accuracy"])
print("Precision:", metrics["precision"])
print("Recall:", metrics["recall"])
print("F1:", metrics["f1"])
print("ROC-AUC:", metrics["roc_auc"])

print("\nМатрица ошибок:")
print(metrics["confusion_matrix"])

print("\nОтчёт классификации:")
for class_name, values in metrics["classification_report"].items():
    if isinstance(values, dict):
        print(class_name, values)

model_path = model.save()

print("\nМодель сохранена:", model_path)

loaded_model = EnsembleModel()
loaded_model.load(model_path)

print("\nПроверка загруженной модели:")
print(loaded_model.predict_quality(test.head(5)))