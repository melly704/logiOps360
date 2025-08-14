import pandas as pd
import numpy as np
from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor
from sqlalchemy import text
from datetime import timedelta
from .feature_utils import ensure_datetime, weekly_agg, add_lags, add_time_feats

class DemandForecaster:
    def __init__(self, engine, horizon_weeks=8, min_history_weeks=8, top_refs=None, table_raw="clean_customer_orders", val_weeks=4):
        self.engine = engine
        self.h = horizon_weeks
        self.min_hist = min_history_weeks
        self.table_raw = table_raw
        self.top_refs = top_refs
        self.val_weeks = val_weeks
        self.model = None
        self.train_cols = None

    def load(self):
        q = f'SELECT * FROM {self.table_raw}'
        df = pd.read_sql(q, self.engine)
        date_col = ensure_datetime(df, "creationdate")
        ref_col = "reference"
        qty_col = "quantity_units" if "quantity_units" in df.columns else "quantity (units)"
        df = df.dropna(subset=[ref_col])
        agg = weekly_agg(df, date_col, ref_col, qty_col)
        if self.top_refs is not None:
            top = agg.groupby(ref_col)["qty"].sum().sort_values(ascending=False).head(self.top_refs).index
            agg = agg[agg[ref_col].isin(top)]
        return agg

    def make_train(self, agg):
        df = add_lags(agg.rename(columns={"reference":"reference"}), "reference")
        df = add_time_feats(df)
        df = df.dropna()
        counts = df.groupby("reference").size()
        valid_refs = counts[counts >= self.min_hist].index
        df = df[df["reference"].isin(valid_refs)]
        X = df[["reference","dow","month","year","weekofyear","lag_1","lag_2","lag_3","lag_4"]]
        y = df["qty"]
        self.train_cols = X.columns.tolist()
        return X, y, df

    def fit(self, X, y):
        cat = ["reference"]
        num = [c for c in self.train_cols if c not in cat]
        ct = ColumnTransformer([("cat", OneHotEncoder(handle_unknown="ignore"), cat)], remainder="passthrough")
        rf = RandomForestRegressor(n_estimators=300, max_depth=None, random_state=42, n_jobs=-1)
        pipe = Pipeline([("prep", ct), ("model", rf)])
        pipe.fit(X, y)
        self.model = pipe

    def rolling_forecast(self, hist, horizon=None):
        h = horizon if horizon is not None else self.h
        last_week = hist["week"].max()
        refs = hist["reference"].unique()
        future_weeks = [last_week + timedelta(weeks=i) for i in range(1, h+1)]
        out = []
        hist = hist.copy()
        for wk in future_weeks:
            tmp = hist.copy()
            tmp2 = tmp.groupby("reference", as_index=False).tail(4)
            need = tmp2.groupby("reference").size().reset_index(name="n")
            need = need[need["n"] >= 4]["reference"]
            snap = tmp[tmp["reference"].isin(need)].groupby("reference", as_index=False).tail(4)
            snap = snap.sort_values(["reference","week"])
            snap = snap.groupby("reference").apply(lambda d: d.tail(4)["qty"].tolist()).rename("lags").to_frame().reset_index()
            if snap.empty:
                continue
            Xf = pd.DataFrame({"reference": snap["reference"], "week": wk})
            Xf["dow"] = wk.weekday()
            Xf["month"] = wk.month
            Xf["year"] = wk.year
            Xf["weekofyear"] = int(pd.Timestamp(wk).isocalendar().week)
            l = pd.DataFrame(snap["lags"].tolist(), columns=["lag_4","lag_3","lag_2","lag_1"])
            l = l[["lag_1","lag_2","lag_3","lag_4"]]
            Xf = pd.concat([Xf, l], axis=1)
            Xf = Xf[self.train_cols]
            yhat = self.model.predict(Xf)
            yhat = np.clip(np.round(yhat), 0, None).astype(int)
            add = pd.DataFrame({"reference": Xf["reference"], "week": wk, "qty": yhat})
            out.append(add)
            hist = pd.concat([hist, add], ignore_index=True)
        fc = pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["reference","week","qty"])
        return fc

    def split_hist(self, agg):
        weeks = sorted(agg["week"].unique())
        if len(weeks) <= self.val_weeks + 4:
            return agg, pd.DataFrame(columns=agg.columns), []
        val_weeks_list = weeks[-self.val_weeks:]
        train_hist = agg[~agg["week"].isin(val_weeks_list)].copy()
        val_actual = agg[agg["week"].isin(val_weeks_list)].copy()
        return train_hist, val_actual, val_weeks_list

    def compute_metrics(self, actual, pred, val_weeks_list):
        if pred.empty or actual.empty:
            now = pd.Timestamp.utcnow()
            rows = [
                {"model":"rf_weekly","run_ts":now,"scope":"overall","metric":"MAE","value":np.nan},
                {"model":"rf_weekly","run_ts":now,"scope":"overall","metric":"RMSE","value":np.nan},
                {"model":"rf_weekly","run_ts":now,"scope":"overall","metric":"MAPE","value":np.nan},
                {"model":"rf_weekly","run_ts":now,"scope":"overall","metric":"WAPE","value":np.nan},
            ]
