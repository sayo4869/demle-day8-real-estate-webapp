"""不動産価格を予測する Web アプリ（FastAPI + Jinja2 テンプレート）。rich-ui ブランチ版。

main ブランチと同じモデル・同じ URL（/ と /predict_price/）のまま、画面を作り込んだ版です。
追加したもの:
  - /api/predict  … 予測値と「どの項目がどれだけ効いたか」を JSON で返す（画面のリアルタイム予測に使う）
  - result.html に入力値と寄与を渡す

先に model.pickle と scaler.pickle を main.py と同じフォルダに置いておくこと。
起動:  python -m uvicorn main:app --reload --port 8080
EC2 :  python3 -m uvicorn main:app --host 0.0.0.0 --port 8080
"""
import pickle
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

BASE = Path(__file__).resolve().parent
MODEL_PATH, SCALER_PATH = BASE / "model.pickle", BASE / "scaler.pickle"

if not (MODEL_PATH.exists() and SCALER_PATH.exists()):
    raise SystemExit("model.pickle / scaler.pickle がありません。Colab で作った pickle を置くか、`python train.py` を実行してください。")

# 自分で作ったファイルだけを読み込む（他人から受け取った pickle は読み込まない）
with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)
with open(SCALER_PATH, "rb") as f:
    scaler = pickle.load(f)

app = FastAPI(title="不動産価格予測")
templates = Jinja2Templates(directory=str(BASE / "templates"))

# 列の順番は train.py の FEATURES（X3, X4, X8, X9, X10）と同じにする
FEATURES = [
    ("station_dist", "駅からの距離"),
    ("conveni_num", "コンビニの数"),
    ("milk_consum", "牛乳の消費量"),
    ("income", "世帯主の年収"),
    ("city_flag", "都市部"),
]


def predict(station_dist, conveni_num, milk_consum, income, city_flag):
    """予測値と、各項目の寄与（係数 × 標準化した値）を返す。寄与をすべて足して切片を足すと予測値になる"""
    x = [[station_dist, conveni_num, milk_consum, income, city_flag]]
    z = scaler.transform(x)[0]
    price = float(model.predict([z])[0])
    contrib = [
        {"key": key, "label": label, "value": round(float(c * v), 3)}
        for (key, label), c, v in zip(FEATURES, model.coef_, z)
    ]
    return round(price, 6), contrib


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/predict_price/", response_class=HTMLResponse)
async def predict_price(request: Request,
                        station_dist: float = 0.0, conveni_num: float = 0.0,
                        milk_consum: float = 0.0, income: float = 0.0, city_flag: int = 0):
    predicted_price, contrib = predict(station_dist, conveni_num, milk_consum, income, city_flag)
    inputs = {"station_dist": station_dist, "conveni_num": conveni_num, "milk_consum": milk_consum,
              "income": income, "city_flag": city_flag}
    return templates.TemplateResponse(request, "result.html", {
        "predicted_price": predicted_price, "inputs": inputs, "contrib": contrib,
        "intercept": round(float(model.intercept_[0]), 3),
    })


@app.get("/api/predict")
async def api_predict(station_dist: float = 0.0, conveni_num: float = 0.0,
                      milk_consum: float = 0.0, income: float = 0.0, city_flag: int = 0):
    predicted_price, contrib = predict(station_dist, conveni_num, milk_consum, income, city_flag)
    return {"predicted_price": predicted_price, "intercept": round(float(model.intercept_[0]), 3),
            "contributions": contrib}
