"""Day8 宿題「オンライン学習」: data/dataset_real_estate_add.csv で既存モデルを追加学習（partial_fit）する。

使い方:  python train.py → python online_update.py
比べやすいように、追加学習の「前」と「後」の MSE を同じテストデータで表示する。
"""
import pickle
from pathlib import Path

import pandas as pd
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split

BASE = Path(__file__).resolve().parent
DATA_ADD = BASE / "data" / "dataset_real_estate_add.csv"
FEATURES = ["X3", "X4", "X8", "X9", "X10"]


def main():
    if not DATA_ADD.exists():
        raise SystemExit(f"{DATA_ADD} がありません（data/README.md）。")
    with open(BASE / "model.pickle", "rb") as f:
        model = pickle.load(f)
    with open(BASE / "scaler.pickle", "rb") as f:
        scaler = pickle.load(f)          # 標準化は最初の学習のものをそのまま使う

    df = pd.read_csv(DATA_ADD)
    df.columns = ["No", "X1", "X2", "X3", "X4", "X5", "X6", "X7", "X8", "X9", "X10", "Y"]
    df = df[FEATURES + ["Y"]].dropna()
    X_tr, X_te, y_tr, y_te = train_test_split(df[FEATURES], df["Y"], test_size=0.2, random_state=0)
    X_tr, X_te = scaler.transform(X_tr), scaler.transform(X_te)

    before = mean_squared_error(y_te, model.predict(X_te))
    model.partial_fit(X_tr, y_tr)
    after = mean_squared_error(y_te, model.predict(X_te))
    print(f"追加データのテスト {len(y_te)} 件での MSE: 追加学習前 {before:.2f} → 後 {after:.2f}")

    with open(BASE / "model.pickle", "wb") as f:
        pickle.dump(model, f)
    print("model.pickle を上書き保存しました（サーバーを再起動すると新しいモデルで予測します）")


if __name__ == "__main__":
    main()
