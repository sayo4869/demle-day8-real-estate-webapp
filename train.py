"""data/dataset_real_estate.csv から予測モデルを学習し、model.pickle と scaler.pickle を保存する。

Day8 のノートブック（Colab）と同じ前処理・同じモデル（SGDRegressor）を、1本のスクリプトにまとめたもの。
EC2 の上で実行すれば、サーバーの scikit-learn のバージョンと pickle のバージョンが必ずそろう。

使い方:  python train.py
"""
import pickle
from pathlib import Path

import pandas as pd
from sklearn.linear_model import SGDRegressor
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

BASE = Path(__file__).resolve().parent
DATA = BASE / "data" / "dataset_real_estate.csv"
COLS = ["No", "X1", "X2", "X3", "X4", "X5", "X6", "X7", "X8", "X9", "X10", "Y"]
FEATURES = ["X3", "X4", "X8", "X9", "X10"]   # 駅からの距離, コンビニ数, 牛乳消費量, 年収, 都市部フラグ


def load_clean(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = COLS
    df = df.drop(columns=["No", "X1"]).dropna()        # ノートブックと同じ順番：不要列を落としてから欠損行を削除
    df = df[(df["X7"] < 4000) & (df["Y"] < 2000)]   # ノートブックと同じ外れ値の除去
    return df


def main():
    if not DATA.exists():
        raise SystemExit(f"{DATA} がありません。講座の配布データを data/ に置いてください（data/README.md）。")
    df = load_clean(DATA)
    X, y = df[FEATURES], df["Y"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=0)

    scaler = StandardScaler().fit(X_train)
    model = SGDRegressor(random_state=0).fit(scaler.transform(X_train), y_train)
    mse = mean_squared_error(y_test, model.predict(scaler.transform(X_test)))
    print(f"学習 {len(X_train)} 件 / テスト {len(X_test)} 件  MSE = {mse:.2f}")

    with open(BASE / "model.pickle", "wb") as f:
        pickle.dump(model, f)
    with open(BASE / "scaler.pickle", "wb") as f:
        pickle.dump(scaler, f)
    print("model.pickle と scaler.pickle を保存しました")


if __name__ == "__main__":
    main()
