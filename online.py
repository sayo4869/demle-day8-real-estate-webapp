"""オンライン学習（partial_fit）でモデルを更新し、バージョン管理するための部品。online-learning ブランチ版。

ポイント
- 標準化（scaler）は最初の学習のものをそのまま使い、モデルだけを partial_fit で少しずつ更新する（Day8 宿題と同じ）
- 追加データを「学習用 80%」「確認用 20%」に分け、同じ確認用データで更新前と更新後の MSE を比べる
- さらに「基準データ」（元のテストデータ＋これまでの確認用データ）でも悪くなっていないか確かめる
  → 追加データの中だけで良くなっても、今までのデータで大きく悪くなるなら採用しない（でたらめなデータ対策）
- どちらかで悪くなったら、新しいモデルは採用しない（force=True のときだけ採用）
- 採用したモデルは models/ に番号付きで保存し、いつでも前のバージョンに戻せる
- サーバーを再起動しなくても、次のリクエストから新しいモデルで予測する
"""
import copy
import io
import json
import os
import pickle
import threading
import time
from pathlib import Path

import pandas as pd
from sklearn.metrics import mean_squared_error
from sklearn.model_selection import train_test_split

APP_COLS = ["station_dist", "conveni_num", "milk_consum", "income", "city_flag"]
TARGET = "price"
# 講座の CSV（dataset_real_estate_add.csv）の列の並び
COURSE_COLS = ["No", "X1", "X2", "X3", "X4", "X5", "X6", "X7", "X8", "X9", "X10", "Y"]
COURSE_MAP = {"X3": "station_dist", "X4": "conveni_num", "X8": "milk_consum", "X9": "income", "X10": "city_flag", "Y": TARGET}

MAX_BYTES = 2 * 1024 * 1024   # 2MB まで
MAX_ROWS = 20000
MIN_ROWS = 10
REF_TOLERANCE = 1.05   # 基準データの MSE は 5% までの悪化なら許す


class LearnError(ValueError):
    """利用者に見せてよいエラー（CSV の形がおかしい など）"""


def read_csv(raw: bytes) -> pd.DataFrame:
    """講座の形式（12列）か、このアプリの列名（station_dist,...,price）の CSV を読み、6列にそろえる"""
    if len(raw) > MAX_BYTES:
        raise LearnError(f"ファイルが大きすぎます（{MAX_BYTES // 1024 // 1024}MB まで）")
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception:
        raise LearnError("CSV として読み込めませんでした")
    if set(APP_COLS + [TARGET]) <= set(df.columns):
        df = df[APP_COLS + [TARGET]]
    elif len(df.columns) == len(COURSE_COLS):
        df.columns = COURSE_COLS
        df = df[list(COURSE_MAP)].rename(columns=COURSE_MAP)
    else:
        raise LearnError("列が合いません。講座の CSV（12列）か、station_dist,conveni_num,milk_consum,income,city_flag,price の6列にしてください")
    df = df.apply(pd.to_numeric, errors="coerce").dropna()
    if len(df) < MIN_ROWS:
        raise LearnError(f"使える行が {len(df)} 行しかありません（{MIN_ROWS} 行以上必要）")
    if len(df) > MAX_ROWS:
        raise LearnError(f"行が多すぎます（{MAX_ROWS} 行まで）")
    return df


class ModelStore:
    def __init__(self, base: Path):
        self.base = base
        self.model_path = base / "model.pickle"
        self.scaler_path = base / "scaler.pickle"
        self.dir = base / "models"
        self.history_path = self.dir / "history.json"
        self.lock = threading.Lock()
        if not (self.model_path.exists() and self.scaler_path.exists()):
            raise SystemExit("model.pickle / scaler.pickle がありません。Colab で作った pickle を置くか、`python train.py` を実行してください。")
        # 自分で作ったファイルだけを読み込む（他人から受け取った pickle は読み込まない）
        with open(self.model_path, "rb") as f:
            self.model = pickle.load(f)
        with open(self.scaler_path, "rb") as f:
            self.scaler = pickle.load(f)
        self.dir.mkdir(exist_ok=True)
        self.ref_path = self.dir / "reference.csv"
        self.reference = self._load_reference()
        self.history = self._load_history()
        if not self.history:   # 初めて起動したとき、今のモデルを v1 として保存しておく
            self._save_version(self.model, {"kind": "initial", "note": "起動時のモデル"})

    # ---------- 予測 ----------
    def predict(self, row):
        z = self.scaler.transform([row])
        with self.lock:
            return float(self.model.predict(z)[0])

    # ---------- 学習 ----------
    def learn(self, df: pd.DataFrame, force: bool = False) -> dict:
        X, y = df[APP_COLS].values, df[TARGET].values
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=0)
        Z_tr, Z_te = self.scaler.transform(X_tr), self.scaler.transform(X_te)
        with self.lock:
            candidate = copy.deepcopy(self.model)        # 今のモデルは触らずに、コピーで試す
            before = mean_squared_error(y_te, self.model.predict(Z_te))
            candidate.partial_fit(Z_tr, y_tr)
            after = mean_squared_error(y_te, candidate.predict(Z_te))
            report = {"rows": int(len(df)), "train_rows": int(len(y_tr)), "test_rows": int(len(y_te)),
                      "mse_before": round(float(before), 3), "mse_after": round(float(after), 3)}
            ok_batch = after <= before
            ok_ref = True
            if len(self.reference):
                Z_ref = self.scaler.transform(self.reference[APP_COLS].values)
                y_ref = self.reference[TARGET].values
                ref_before = mean_squared_error(y_ref, self.model.predict(Z_ref))
                ref_after = mean_squared_error(y_ref, candidate.predict(Z_ref))
                ok_ref = ref_after <= ref_before * REF_TOLERANCE
                report.update({"ref_rows": int(len(y_ref)), "ref_mse_before": round(float(ref_before), 3),
                               "ref_mse_after": round(float(ref_after), 3)})
            adopted = force or (ok_batch and ok_ref)
            report.update({"adopted": bool(adopted), "forced": bool(force and not (ok_batch and ok_ref))})
            if adopted:
                self.model = candidate
                entry = self._save_version(candidate, {"kind": "partial_fit", **report})
                report["version"] = entry["version"]
            if adopted and not report["forced"]:
                # 今回の確認用データも、次からの基準データに加える（強制採用したデータは信用しないので加えない）
                new_ref = pd.DataFrame(X_te, columns=APP_COLS).assign(**{TARGET: y_te})
                self.reference = pd.concat([self.reference, new_ref], ignore_index=True)
                self.reference.to_csv(self.ref_path, index=False)
            if not adopted:
                report["version"] = self.history[-1]["version"]
                report["reason"] = ("追加データの確認用で MSE が悪くなった" if not ok_batch else
                                    f"これまでの基準データで MSE が {REF_TOLERANCE - 1:.0%} を超えて悪くなった（追加データがおかしいかも）") + \
                                   "ので、新しいモデルは採用しませんでした"
        return report

    def rollback(self) -> dict:
        with self.lock:
            if len(self.history) < 2:
                raise LearnError("戻せる前のバージョンがありません")
            prev = self.history[-2]
            with open(self.dir / prev["file"], "rb") as f:
                model = pickle.load(f)
            self.model = model
            entry = self._save_version(model, {"kind": "rollback", "note": f"v{prev['version']} に戻した"})
        return entry

    # ---------- 保存まわり ----------
    def _load_reference(self) -> pd.DataFrame:
        """基準データ。保存済みならそれを、なければ元の学習データのテスト部分（train.py と同じ分け方）を使う"""
        if self.ref_path.exists():
            return pd.read_csv(self.ref_path)
        src = self.base / "data" / "dataset_real_estate.csv"
        if not src.exists():
            return pd.DataFrame(columns=APP_COLS + [TARGET])
        df = pd.read_csv(src)
        df.columns = COURSE_COLS
        df = df.drop(columns=["No", "X1"]).dropna()
        df = df[(df["X7"] < 4000) & (df["Y"] < 2000)]          # train.py と同じ前処理
        df = df[list(COURSE_MAP)].rename(columns=COURSE_MAP)
        _, ref = train_test_split(df, test_size=0.2, random_state=0)   # train.py と同じテスト部分
        ref = ref.reset_index(drop=True)
        ref.to_csv(self.ref_path, index=False)
        return ref

    def _load_history(self):
        if self.history_path.exists():
            return json.loads(self.history_path.read_text(encoding="utf-8"))
        return []

    def _save_version(self, model, info: dict) -> dict:
        version = (self.history[-1]["version"] + 1) if self.history else 1
        name = f"model_v{version:03d}.pickle"
        self._atomic_pickle(model, self.dir / name)
        self._atomic_pickle(model, self.model_path)     # いま使うモデルとしても保存（再起動しても続きから）
        entry = {"version": version, "file": name, "time": time.strftime("%Y-%m-%d %H:%M:%S"), **info}
        self.history.append(entry)
        tmp = self.history_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.history, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.history_path)
        return entry

    @staticmethod
    def _atomic_pickle(obj, path: Path):
        # 書きかけのファイルを読まれないように、別名で書いてから一瞬で置き換える
        tmp = path.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            pickle.dump(obj, f)
        os.replace(tmp, path)
