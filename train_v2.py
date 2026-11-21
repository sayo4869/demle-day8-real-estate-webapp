"""data/dataset_real_estate.csv からランダムフォレストを学習し、model_v2.pickle を保存する（random-forest ブランチ）。

train.py（SGDRegressor）と同じ前処理・同じ5項目。決定木はしきい値で分けるだけなので、標準化（scaler）は不要。
使い方:  python train_v2.py
"""
import pickle
from pathlib import Path

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split

from train import DATA, FEATURES, load_clean

BASE = Path(__file__).resolve().parent


def main():
    if not DATA.exists():
        raise SystemExit(f"{DATA} がありません。講座の配布データを data/ に置いてください（data/README.md）。")
    df = load_clean(DATA)
    X, y = df[FEATURES], df["Y"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=0)

    model = RandomForestRegressor(n_estimators=100, max_depth=7, random_state=0).fit(X_train, y_train)
    mse = mean_squared_error(y_test, model.predict(X_test))
    print(f"学習 {len(X_train)} 件 / テスト {len(X_test)} 件  MSE = {mse:.2f}")

    with open(BASE / "model_v2.pickle", "wb") as f:
        pickle.dump(model, f)
    print("model_v2.pickle を保存しました")


if __name__ == "__main__":
    main()
