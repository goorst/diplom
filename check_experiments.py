
import pandas as pd

for filename in ["train.csv", "test.csv"]:

    df = pd.read_csv("data/quality/" + filename)

    print("\n" + "=" * 60)
    print(filename)
    print("=" * 60)

    print("\nРаспределение экспериментов по изделиям:")

    result = (
        df.groupby(["product_id", "experiment_id"])
        .agg(
            records=("target", "count"),
            good=("target", lambda x: (x == 0).sum()),
            defect=("target", lambda x: (x == 1).sum())
        )
        .reset_index()
    )

    print(result.to_string(index=False))

    print("\nКоличество экспериментов на каждое изделие:")

    print(
        df.groupby("product_id")["experiment_id"]
        .nunique()
    )

print("\nПроверка завершена.")
