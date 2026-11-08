"""不動産価格を予測する Web アプリ（FastAPI + Jinja2 テンプレート）。

先に train.py を実行して model.pickle と scaler.pickle を作っておくこと。
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
    raise SystemExit("model.pickle / scaler.pickle がありません。先に `python train.py` を実行してください（README の手順2）。")

# 自分で train.py を実行して作ったファイルだけを読み込む（他人から受け取った pickle は読み込まない）
with open(MODEL_PATH, "rb") as f:
    model = pickle.load(f)
with open(SCALER_PATH, "rb") as f:
    scaler = pickle.load(f)

app = FastAPI(title="不動産価格予測")
templates = Jinja2Templates(directory=str(BASE / "templates"))


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/predict_price/", response_class=HTMLResponse)
async def predict_price(request: Request,
                        station_dist: float = 0.0, conveni_num: float = 0.0,
                        milk_consum: float = 0.0, income: float = 0.0, city_flag: int = 0):
    # 列の順番は train.py の FEATURES（X3, X4, X8, X9, X10）と同じにする
    x = [[station_dist, conveni_num, milk_consum, income, city_flag]]
    predicted = model.predict(scaler.transform(x))
    predicted_price = round(float(predicted[0]), 6)
    return templates.TemplateResponse(request, "result.html", {"predicted_price": predicted_price})
