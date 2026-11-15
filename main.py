"""不動産価格を予測する Web アプリ（FastAPI + Jinja2 テンプレート）。online-learning ブランチ版。

main ブランチと同じ / と /predict_price/ に加えて、Web からオンライン学習できるようにした版です。
  GET  /learn          … 追加データ（CSV）をアップロードする画面
  POST /api/learn      … CSV を受け取って partial_fit。更新前後の MSE を比べて、良くなったときだけ採用
  GET  /api/model      … 今のモデルのバージョンと更新の履歴
  POST /api/rollback   … 1つ前のバージョンに戻す
学習・巻き戻しは、環境変数 ADMIN_TOKEN と同じ値をヘッダー X-API-Key で送った人だけができます。

起動:  ADMIN_TOKEN=好きな長い文字列 python -m uvicorn main:app --port 8080
EC2 :  ADMIN_TOKEN=好きな長い文字列 python3 -m uvicorn main:app --host 0.0.0.0 --port 8080
（--reload は付けない。学習でファイルが書き換わるたびに再起動してしまうため）
"""
import os
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from online import LearnError, ModelStore, read_csv

BASE = Path(__file__).resolve().parent
store = ModelStore(BASE)

app = FastAPI(title="不動産価格予測（オンライン学習版）")
templates = Jinja2Templates(directory=str(BASE / "templates"))


def require_admin(x_api_key: str = Header(default="")):
    """学習・巻き戻しは、ADMIN_TOKEN を知っている人だけ"""
    token = os.environ.get("ADMIN_TOKEN", "")
    if not token:
        raise HTTPException(503, "学習は無効です。サーバーを環境変数 ADMIN_TOKEN 付きで起動してください")
    if not secrets.compare_digest(x_api_key, token):
        raise HTTPException(401, "X-API-Key が違います")


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse(request, "index.html", {"version": store.history[-1]["version"]})


@app.get("/predict_price/", response_class=HTMLResponse)
async def predict_price(request: Request,
                        station_dist: float = 0.0, conveni_num: float = 0.0,
                        milk_consum: float = 0.0, income: float = 0.0, city_flag: int = 0):
    # 列の順番は train.py の FEATURES（X3, X4, X8, X9, X10）と同じにする
    predicted_price = round(store.predict([station_dist, conveni_num, milk_consum, income, city_flag]), 6)
    return templates.TemplateResponse(request, "result.html", {
        "predicted_price": predicted_price, "version": store.history[-1]["version"]})


@app.get("/learn", response_class=HTMLResponse)
async def learn_page(request: Request):
    return templates.TemplateResponse(request, "learn.html", {
        "history": list(reversed(store.history)), "enabled": bool(os.environ.get("ADMIN_TOKEN"))})


@app.get("/api/model")
async def model_info():
    return {"version": store.history[-1]["version"], "history": store.history}


@app.post("/api/learn", dependencies=[Depends(require_admin)])
async def learn(file: UploadFile = File(...), force: bool = False):
    try:
        df = read_csv(await file.read())
        return store.learn(df, force=force)
    except LearnError as e:
        raise HTTPException(400, str(e))


@app.post("/api/rollback", dependencies=[Depends(require_admin)])
async def rollback():
    try:
        return store.rollback()
    except LearnError as e:
        raise HTTPException(400, str(e))
