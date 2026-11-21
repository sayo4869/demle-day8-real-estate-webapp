"""不動産価格を予測する Web アプリ（FastAPI + Jinja2 テンプレート）。random-forest ブランチ版。

corporate-ui ブランチの画面のまま、モデルを RandomForestRegressor（model_v2.pickle）に差し替えた版です。
決定木は「しきい値で分けるだけ」なので標準化（StandardScaler）が要りません → scaler.pickle は使いません。

  - /api/predict  … 予測値と「どの項目がどれだけ効いたか」を JSON で返す（画面のリアルタイム予測に使う）
  - 「どれだけ効いたか」は、木をたどったときに各分岐で予測がどれだけ動いたかを、項目ごとに足したもの
    （出発点＝学習データの平均 ＋ 各項目の寄与の合計 ＝ 予測値 になる）

先に model_v2.pickle を main.py と同じフォルダに置いておくこと（`python train_v2.py` でも作れる）。
起動:  python -m uvicorn main:app --reload --port 8080
EC2 :  python3 -m uvicorn main:app --host 0.0.0.0 --port 8080
"""
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BASE = Path(__file__).resolve().parent
MODEL_PATH = BASE / "model_v2.pickle"

if not MODEL_PATH.exists():
    raise SystemExit("model_v2.pickle がありません。Colab で作った pickle を置くか、`python train_v2.py` を実行してください。")

# 自分で作ったファイルだけを読み込む（他人から受け取った pickle は読み込まない）
with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)

app = FastAPI(title="不動産価格予測（ランダムフォレスト）")
templates = Jinja2Templates(directory=str(BASE / "templates"))

# 列の順番と列名は学習のとき（X3, X4, X8, X9, X10）と同じにする
COLUMNS = ["X3", "X4", "X8", "X9", "X10"]
FEATURES = [
    ("station_dist", "駅からの距離"),
    ("conveni_num", "コンビニの数"),
    ("milk_consum", "牛乳の消費量"),
    ("income", "世帯主の年収"),
    ("city_flag", "都市部"),
]


def tree_contributions(x):
    """各木で「根 → 葉」をたどり、分岐ごとの予測の変化を、その分岐に使った項目の寄与として足す。
    木の本数で平均すると  出発点（根の値の平均） ＋ 寄与の合計 ＝ 予測値  になる。"""
    bias, contrib = 0.0, np.zeros(len(COLUMNS))
    for tree in model.estimators_:
        t = tree.tree_
        path = tree.decision_path(x).indices        # 通ったノード番号（親 → 子の順）
        values = t.value[:, 0, 0]
        bias += values[path[0]]
        for parent, child in zip(path[:-1], path[1:]):
            contrib[t.feature[parent]] += values[child] - values[parent]
    n = len(model.estimators_)
    return bias / n, contrib / n


def predict(station_dist, conveni_num, milk_consum, income, city_flag):
    """予測値・各項目の寄与・出発点（平均）を返す。標準化はしない"""
    X = pd.DataFrame([[station_dist, conveni_num, milk_consum, income, city_flag]], columns=COLUMNS)
    price = float(model.predict(X)[0])
    bias, contrib = tree_contributions(X.to_numpy(dtype=np.float32))
    contrib = [
        {"key": key, "label": label, "value": round(float(v), 3)}
        for (key, label), v in zip(FEATURES, contrib)
    ]
    return round(price, 6), contrib, round(float(bias), 3)


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/predict_price/", response_class=HTMLResponse)
async def predict_price(request: Request,
                        station_dist: float = 0.0, conveni_num: float = 0.0,
                        milk_consum: float = 0.0, income: float = 0.0, city_flag: int = 0):
    predicted_price, contrib, bias = predict(station_dist, conveni_num, milk_consum, income, city_flag)
    inputs = {"station_dist": station_dist, "conveni_num": conveni_num, "milk_consum": milk_consum,
              "income": income, "city_flag": city_flag}
    return templates.TemplateResponse(request, "result.html", {
        "predicted_price": predicted_price, "inputs": inputs, "contrib": contrib, "intercept": bias,
    })


@app.get("/api/predict")
async def api_predict(station_dist: float = 0.0, conveni_num: float = 0.0,
                      milk_consum: float = 0.0, income: float = 0.0, city_flag: int = 0):
    predicted_price, contrib, bias = predict(station_dist, conveni_num, milk_consum, income, city_flag)
    return {"predicted_price": predicted_price, "intercept": bias, "contributions": contrib}
