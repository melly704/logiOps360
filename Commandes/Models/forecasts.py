# Commandes/Models/forecasts.py
# -*- coding: utf-8 -*-

# --- Patch imports pour exécution directe du script ou en package ---
import sys
from pathlib import Path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
try:
    # import en mode package
    from Commandes.Models.feature_utils import (
        ensure_datetime, weekly_agg, add_lags, add_time_feats
    )
except ImportError:
    # fallback si lancé depuis le dossier Models
    from feature_utils import ensure_datetime, weekly_agg, add_lags, add_time_feats

import pandas as pd
import numpy as np
from datetime import timedelta

from sklearn.preprocessing import OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.ensemble import RandomForestRegressor


class DemandForecaster:
    """
    Forecast hebdo par référence + évaluation H7 (RF vs Naïf S-1) sur une fenêtre de validation.

    Sorties optionnelles (write_back=True):
      - fct_order_forecast(reference, date_week, qty_pred, model, run_ts)
      - ml_forecast_metrics(model, run_ts, scope, metric, value, extra_json)
    """

    def __init__(
        self,
        engine,
        horizon_weeks=8,
        min_history_weeks=8,
        top_refs=None,
        table_raw="clean_customer_orders",
        val_weeks=4,
        out_table_forecast="fct_order_forecast",
        out_table_metrics="ml_forecast_metrics",
        write_back=True,
    ):
        self.engine = engine
        self.h = horizon_weeks
        self.min_hist = min_history_weeks
        self.table_raw = table_raw
        self.top_refs = top_refs
        self.val_weeks = val_weeks
        self.out_table_forecast = out_table_forecast
        self.out_table_metrics = out_table_metrics
        self.write_back = write_back

        self.model = None
        self.train_cols = None

    # ---------- Chargement & préparation ----------
    def load(self):
        q = f"SELECT * FROM {self.table_raw}"
        df = pd.read_sql(q, self.engine)

        date_col = ensure_datetime(df, "creationdate")
        ref_col = "reference"
        qty_col = "quantity_units" if "quantity_units" in df.columns else "quantity (units)"

        df = df.dropna(subset=[ref_col])
        agg = weekly_agg(df, date_col, ref_col, qty_col)  # -> [reference, week, qty]

        if self.top_refs is not None:
            top = (
                agg.groupby(ref_col)["qty"]
                .sum()
                .sort_values(ascending=False)
                .head(self.top_refs)
                .index
            )
            agg = agg[agg[ref_col].isin(top)]
        return agg

    def _prep_supervised(self, agg):
        df = add_lags(agg.rename(columns={"reference": "reference"}), "reference")
        df = add_time_feats(df)
        # dropna strict uniquement sur les lags
        lag_cols = ["lag_1", "lag_2", "lag_3", "lag_4"]
        df = df.dropna(subset=lag_cols)

        counts = df.groupby("reference").size()
        valid_refs = counts[counts >= self.min_hist].index
        df = df[df["reference"].isin(valid_refs)]

        X = df[["reference", "dow", "month", "year", "weekofyear", "lag_1", "lag_2", "lag_3", "lag_4"]]
        y = df["qty"]
        self.train_cols = X.columns.tolist()
        return X, y, df

    # ---------- Modèle ----------
    def fit(self, X, y):
        """
        Pipeline:
          - Imputer catégoriel (most_frequent) + OneHotEncoder pour 'reference'
          - Imputer numérique (fill_value=0.0) pour lags/temps
          - RandomForestRegressor
        """
        X = X.copy()
        if "reference" in X:
            X["reference"] = X["reference"].astype(str).fillna("MISSING")

        cat = ["reference"]
        num = [c for c in self.train_cols if c not in cat]

        # Cast explicite en float pour éviter le mismatch int/float au transform
        for c in num:
            X[c] = pd.to_numeric(X[c], errors="coerce").astype(float)

        ct = ColumnTransformer(
            transformers=[
                ("cat", Pipeline([
                    ("imputer", SimpleImputer(strategy="most_frequent")),
                    ("ohe", OneHotEncoder(handle_unknown="ignore"))
                ]), cat),
                ("num", Pipeline([
                    ("imputer", SimpleImputer(strategy="constant", fill_value=0.0))
                ]), num),
            ],
            remainder="drop",
        )

        rf = RandomForestRegressor(n_estimators=300, max_depth=None, random_state=42, n_jobs=-1)
        pipe = Pipeline([("prep", ct), ("model", rf)])
        pipe.fit(X, y)
        self.model = pipe

    # ---------- Rolling forecast (pad des lags manquants) ----------
    def rolling_forecast(self, hist, horizon=None, min_required_lags=1):
        """
        hist: DataFrame [reference, week, qty] (historique connu à l’instant t)
        horizon: nb de semaines à projeter (séquentiel)
        min_required_lags: nb min de lags existants pour autoriser l'inférence (les manquants sont pad à 0)
        """
        h = horizon if horizon is not None else self.h
        if hist.empty:
            return pd.DataFrame(columns=["reference", "week", "qty"])

        last_week = hist["week"].max()
        future_weeks = [last_week + timedelta(weeks=i) for i in range(1, h + 1)]
        out = []
        hist = hist.copy()

        for wk in future_weeks:
            # Dernières obs par ref (jusqu'à 4)
            snap = (
                hist.sort_values(["reference", "week"])
                .groupby("reference")
                .tail(4)
                .groupby("reference")["qty"]
                .apply(list)
                .rename("lags")
                .reset_index()
            )

            # Au moins min_required_lags
            snap = snap[snap["lags"].map(lambda x: len(x) >= min_required_lags)]
            if snap.empty:
                continue

            # pad gauche à 4 avec 0
            def pad4(lst):
                if len(lst) >= 4:
                    return lst[-4:]
                return [0] * (4 - len(lst)) + lst

            snap["lags"] = snap["lags"].map(pad4)

            Xf = pd.DataFrame({"reference": snap["reference"], "week": wk})
            Xf["dow"] = wk.weekday()
            Xf["month"] = wk.month
            Xf["year"] = wk.year
            Xf["weekofyear"] = int(pd.Timestamp(wk).isocalendar().week)

            # lag_1 = plus récent (comme en training)
            l = pd.DataFrame(snap["lags"].tolist(), columns=["lag_4", "lag_3", "lag_2", "lag_1"])
            l = l[["lag_1", "lag_2", "lag_3", "lag_4"]]
            Xf = pd.concat([Xf, l], axis=1)

            # Forcer l'ordre et types
            Xf = Xf[self.train_cols]
            if "reference" in Xf:
                Xf["reference"] = Xf["reference"].astype(str).fillna("MISSING")
            num_cols = [c for c in self.train_cols if c != "reference"]
            for c in num_cols:
                Xf[c] = pd.to_numeric(Xf[c], errors="coerce").astype(float)
            # Pas de fillna: l'imputer du pipeline gère

            yhat = self.model.predict(Xf)
            yhat = np.clip(np.round(yhat), 0, None).astype(int)

            add = pd.DataFrame({"reference": Xf["reference"], "week": wk, "qty": yhat})
            out.append(add)
            # réinjection pour les lags suivants
            hist = pd.concat([hist, add], ignore_index=True)

        fc = pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["reference", "week", "qty"])
        return fc

    # ---------- Split train/val (hold-out) ----------
    def split_hist(self, agg):
        weeks = sorted(agg["week"].unique())
        if len(weeks) <= self.val_weeks + 4:
            return agg, pd.DataFrame(columns=agg.columns), []
        val_weeks_list = weeks[-self.val_weeks:]
        train_hist = agg[~agg["week"].isin(val_weeks_list)].copy()
        val_actual = agg[agg["week"].isin(val_weeks_list)].copy()
        return train_hist, val_actual, val_weeks_list

    # ---------- Baseline & H7 ----------
    def _naive_prevweek(self, full_agg):
        tmp = full_agg.sort_values(["reference", "week"]).copy()
        tmp["qty_naive_pred"] = tmp.groupby("reference")["qty"].shift(1)
        return tmp[["reference", "week", "qty_naive_pred"]]

    def _evaluate_h7(self, val_actual, pred_val, full_agg, val_weeks_list):
        if pred_val.empty or val_actual.empty or len(val_weeks_list) == 0:
            return (
                pd.DataFrame(columns=["reference", "week", "qty_actual", "qty_pred", "qty_naive_pred", "ae_rf", "ae_naive"]),
                {
                    "H7_N_obs": 0,
                    "H7_MAE_RF": np.nan,
                    "H7_MAE_Naive": np.nan,
                    "H7_WAPE_RF": np.nan,
                    "H7_WAPE_Naive": np.nan,
                    "H7_Wilcoxon_stat": np.nan,
                    "H7_Wilcoxon_p": np.nan,
                    "H7_Decision": "Non évaluable (fenêtre de validation vide)",
                    "H7_Amélioration_MAE_%": np.nan,
                    "H7_Amélioration_WAPE_%": np.nan,
                },
            )

        j = (
            val_actual.rename(columns={"qty": "qty_actual"})
            .merge(pred_val.rename(columns={"qty": "qty_pred"}), on=["reference", "week"], how="inner")
        )

        naive_all = self._naive_prevweek(full_agg)
        j = j.merge(naive_all, on=["reference", "week"], how="left")

        j["ae_rf"] = (j["qty_pred"] - j["qty_actual"]).abs()
        j["ae_naive"] = (j["qty_naive_pred"] - j["qty_actual"]).abs()

        mae_rf = j["ae_rf"].mean()
        mae_nv = j["ae_naive"].mean()
        denom = j["qty_actual"].sum()
        wape_rf = j["ae_rf"].sum() / denom if denom else np.nan
        wape_nv = j["ae_naive"].sum() / denom if denom else np.nan
        improve_mae = (mae_nv - mae_rf) / mae_nv if mae_nv else np.nan
        improve_wape = (wape_nv - wape_rf) / wape_nv if wape_nv else np.nan

        try:
            from scipy.stats import wilcoxon
            w_stat, w_p = wilcoxon(j["ae_rf"], j["ae_naive"], zero_method="wilcox", alternative="less")
        except Exception:
            w_stat, w_p = np.nan, np.nan

        decision = (
            "RF < Naïf (significatif)"
            if (pd.notna(w_p) and w_p < 0.05 and (improve_mae is not np.nan) and (improve_mae > 0))
            else ("Tendance RF < Naïf" if (improve_mae is not np.nan and improve_mae > 0) else "Non concluant / Baseline ≥ RF")
        )

        h7 = {
            "H7_N_obs": int(len(j)),
            "H7_MAE_RF": mae_rf,
            "H7_MAE_Naive": mae_nv,
            "H7_WAPE_RF": wape_rf,
            "H7_WAPE_Naive": wape_nv,
            "H7_Amélioration_MAE_%": None if pd.isna(improve_mae) else round(100 * improve_mae, 2),
            "H7_Amélioration_WAPE_%": None if pd.isna(improve_wape) else round(100 * improve_wape, 2),
            "H7_Wilcoxon_stat": w_stat,
            "H7_Wilcoxon_p": w_p,
            "H7_Decision": decision,
        }
        return j, h7

    def _persist_metrics(self, metrics_rows):
        if not self.write_back or not metrics_rows:
            return
        dfm = pd.DataFrame(metrics_rows)
        try:
            dfm.to_sql(self.out_table_metrics, self.engine, if_exists="append", index=False)
        except Exception:
            dfm.to_csv("ml_forecast_metrics_fallback.csv", index=False)

    def _persist_forecasts(self, fc_future):
        if not self.write_back or fc_future.empty:
            return
        df_fc = fc_future.rename(columns={"week": "date_week", "qty": "qty_pred"}).copy()
        df_fc["model"] = "rf_weekly"
        df_fc["run_ts"] = pd.Timestamp.utcnow()
        try:
            df_fc.to_sql(self.out_table_forecast, self.engine, if_exists="append", index=False)
        except Exception:
            df_fc.to_csv("fct_order_forecast_fallback.csv", index=False)

    # ---------- Orchestration standard ----------
    def run(self):
        """
        - Charge l’historique agrégé hebdo
        - Split train/val (dernières `val_weeks`)
        - Fit RF, rolling forecast sur validation
        - Calcule H7 + écrit métriques
        - Rolling forecast futur (horizon h) + écriture en base
        - Retourne les prévisions futures (DataFrame)
        """
        agg = self.load()  # [reference, week, qty]

        # split
        train_hist, val_actual, val_weeks_list = self.split_hist(agg)

        # fit
        X, y, _ = self._prep_supervised(train_hist if not train_hist.empty else agg)
        if X.empty:
            now = pd.Timestamp.utcnow()
            self._persist_metrics([{
                "model": "rf_weekly", "run_ts": now, "scope": "overall",
                "metric": "H7_status", "value": np.nan,
                "extra_json": '{"decision":"Non évaluable (historique insuffisant)"}'
            }])
            return pd.DataFrame(columns=["reference", "week", "qty"])

        self.fit(X, y)

        # validation rolling
        if len(val_weeks_list) > 0 and not train_hist.empty:
            pred_val = self.rolling_forecast(train_hist, horizon=len(val_weeks_list))
            pred_val = pred_val[pred_val["week"].isin(val_weeks_list)]
        else:
            pred_val = pd.DataFrame(columns=["reference", "week", "qty"])

        # H7
        val_join, h7 = self._evaluate_h7(val_actual, pred_val, agg, val_weeks_list)
        run_ts = pd.Timestamp.utcnow()

        # persistance métriques
        metrics_rows = [
            {"model": "rf_weekly", "run_ts": run_ts, "scope": "overall", "metric": "H7_N_obs", "value": h7["H7_N_obs"], "extra_json": None},
            {"model": "rf_weekly", "run_ts": run_ts, "scope": "overall", "metric": "MAE_RF", "value": h7["H7_MAE_RF"], "extra_json": None},
            {"model": "rf_weekly", "run_ts": run_ts, "scope": "overall", "metric": "MAE_Naive", "value": h7["H7_MAE_Naive"], "extra_json": None},
            {"model": "rf_weekly", "run_ts": run_ts, "scope": "overall", "metric": "WAPE_RF", "value": h7["H7_WAPE_RF"], "extra_json": None},
            {"model": "rf_weekly", "run_ts": run_ts, "scope": "overall", "metric": "WAPE_Naive", "value": h7["H7_WAPE_Naive"], "extra_json": None},
            {"model": "rf_weekly", "run_ts": run_ts, "scope": "overall", "metric": "Wilcoxon_p", "value": h7["H7_Wilcoxon_p"], "extra_json": None},
            {"model": "rf_weekly", "run_ts": run_ts, "scope": "overall", "metric": "H7_decision", "value": None,
             "extra_json": f'{{"decision":"{h7["H7_Decision"]}","improve_MAE_pct":{h7["H7_Amélioration_MAE_%"]},"improve_WAPE_pct":{h7["H7_Amélioration_WAPE_%"]}}}'}
        ]
        self._persist_metrics(metrics_rows)

        # Prévisions futures (H+1..H+h)
        fc_future = self.rolling_forecast(agg, horizon=self.h)
        self._persist_forecasts(fc_future)

        # Sauvegarde locale utile (debug)
        try:
            val_join.to_csv("forecast_validation_join.csv", index=False)
        except Exception:
            pass

        return fc_future

    # ---------- Scénario "avant cutoff -> prédire & évaluer sur [cutoff; end)" ----------
    def run_with_cutoff(self, cutoff_date, end_date=None, persist_eval=False, model_tag=None):
        """
        Entraîne le modèle STRICTEMENT avant `cutoff_date`, prédit et compare sur les
        semaines qui **chevauchent** l’intervalle [cutoff ; end) :
        - Filtrage par chevauchement: on conserve toute semaine ssi [week, week+7) intersecte [cutoff, end)
        - Jointure LEFT sur les prédictions : on affiche aussi les semaines prédites sans réel

        cutoff_date : str/Timestamp (ex: "2025-08-01")
        end_date    : str/Timestamp (défaut = cutoff + 2 mois -> le 1er du 3e mois)
        persist_eval: écrit les prévisions d’évaluation dans fct_order_forecast si True
        model_tag   : tag pour la colonne model (défaut "rf_cutoff_<YYYY-MM-DD>")
        """
        from scipy.stats import wilcoxon

        agg = self.load()  # [reference, week, qty]

        cutoff = pd.Timestamp(cutoff_date).normalize()
        if end_date is None:
            tmp = cutoff + pd.DateOffset(months=2)
            end = tmp.to_period("M").to_timestamp()  # 1er jour du 3e mois
        else:
            end = pd.Timestamp(end_date).normalize()

        # Train < cutoff ; Eval = semaines qui CHEVAUCHENT [cutoff, end)
        train_hist = agg[agg["week"] < cutoff].copy()
        eval_actual = agg[(agg["week"] + pd.Timedelta(days=7) > cutoff) & (agg["week"] < end)].copy()

        if train_hist.empty:
            return {"metrics": {"note": "Train vide avant cutoff"}, "weekly_df": pd.DataFrame(),
                    "monthly_df": pd.DataFrame(), "preds_df": pd.DataFrame()}

        X, y, _ = self._prep_supervised(train_hist)
        if X.empty:
            return {"metrics": {"note": "Historique insuffisant (lags incomplets)"}, "weekly_df": pd.DataFrame(),
                    "monthly_df": pd.DataFrame(), "preds_df": pd.DataFrame()}
        self.fit(X, y)

        # horizon jusqu'à end (exclus)
        last_train_week = train_hist["week"].max()
        start_next = last_train_week + pd.Timedelta(days=7)
        horizon_weeks = int(np.ceil(max((end - start_next).days, 0) / 7.0))
        if horizon_weeks <= 0:
            pred_all = pd.DataFrame(columns=["reference", "week", "qty"])
        else:
            pred_all = self.rolling_forecast(train_hist, horizon=horizon_weeks)

        pred_eval = pred_all[(pred_all["week"] + pd.Timedelta(days=7) > cutoff) & (pred_all["week"] < end)].copy()

        # Jointure LEFT sur prédictions -> garde les semaines prédites même sans réel
        join_w = (pred_eval.rename(columns={"qty": "qty_pred"})
                  .merge(eval_actual.rename(columns={"qty": "qty_actual"}),
                         on=["reference", "week"], how="left"))

        # Baseline naïve S-1, alignée sur la fenêtre par chevauchement
        naive_all = agg.sort_values(["reference", "week"]).copy()
        naive_all["qty_naive_pred"] = naive_all.groupby("reference")["qty"].shift(1)
        naive_eval = naive_all[(naive_all["week"] + pd.Timedelta(days=7) > cutoff) & (naive_all["week"] < end)][
            ["reference", "week", "qty_naive_pred"]
        ]
        join_w = join_w.merge(naive_eval, on=["reference", "week"], how="left")

        # Erreurs (NaN là où qty_actual manque)
        join_w["ae_rf"] = (join_w["qty_pred"] - join_w["qty_actual"]).abs()
        join_w["ae_naive"] = (join_w["qty_naive_pred"] - join_w["qty_actual"]).abs()

        # ---- Métriques hebdo sur les lignes avec réel
        j_valid = join_w.dropna(subset=["qty_actual"]).copy()

        def _mae(s): return float(s.mean()) if len(s) else np.nan
        def _wape(ae, act):
            den = act.sum()
            return float(ae.sum()/den) if den else np.nan

        mae_rf_w  = _mae(j_valid["ae_rf"])
        wape_rf_w = _wape(j_valid["ae_rf"], j_valid["qty_actual"])
        mae_nv_w  = _mae(j_valid["ae_naive"])
        wape_nv_w = _wape(j_valid["ae_naive"], j_valid["qty_actual"])
        gain_mae  = (mae_nv_w - mae_rf_w)/mae_nv_w if (mae_nv_w and not pd.isna(mae_nv_w)) else np.nan
        gain_wape = (wape_nv_w - wape_rf_w)/wape_nv_w if (wape_nv_w and not pd.isna(wape_nv_w)) else np.nan

        # Wilcoxon sur AE appariées (RF < Naïf)
        try:
            aligned = j_valid.dropna(subset=["ae_rf","ae_naive"])
            if not aligned.empty:
                w_stat, w_p = wilcoxon(aligned["ae_rf"], aligned["ae_naive"], zero_method="wilcox", alternative="less")
            else:
                w_stat, w_p = np.nan, np.nan
        except Exception:
            w_stat, w_p = np.nan, np.nan

        # ---- Agrégations mensuelles (sur lignes avec réel)
        if not j_valid.empty:
            j_valid["month"] = j_valid["week"].dt.to_period("M").dt.to_timestamp()
            m_pred = j_valid.groupby("month", as_index=False)["qty_pred"].sum()
            m_act  = j_valid.groupby("month", as_index=False)["qty_actual"].sum()
            m_nv   = j_valid.groupby("month", as_index=False)["qty_naive_pred"].sum()
            join_m = m_act.merge(m_pred, on="month", how="inner").merge(m_nv, on="month", how="left")
            join_m["ae_month_rf"]    = (join_m["qty_pred"] - join_m["qty_actual"]).abs()
            join_m["ae_month_naive"] = (join_m["qty_naive_pred"] - join_m["qty_actual"]).abs()
            mae_rf_m  = _mae(join_m["ae_month_rf"])
            wape_rf_m = _wape(join_m["ae_month_rf"], join_m["qty_actual"])
            mae_nv_m  = _mae(join_m["ae_month_naive"])
            wape_nv_m = _wape(join_m["ae_month_naive"], join_m["qty_actual"])
        else:
            join_m = pd.DataFrame(columns=["month","qty_actual","qty_pred","qty_naive_pred","ae_month_rf","ae_month_naive"])
            mae_rf_m = wape_rf_m = mae_nv_m = wape_nv_m = np.nan

        # ---- Persistance optionnelle des prévisions d'éval
        if persist_eval and not pred_eval.empty:
            tag = model_tag or f"rf_cutoff_{cutoff.date()}"
            df_val = pred_eval.rename(columns={"week": "date_week", "qty": "qty_pred"}).copy()
            df_val["model"] = tag
            df_val["run_ts"] = pd.Timestamp.utcnow()
            try:
                df_val.to_sql(self.out_table_forecast, self.engine, if_exists="append", index=False)
            except Exception:
                df_val.to_csv(f"fct_order_forecast_eval_{tag}.csv", index=False)

        # ---- Persistance des métriques (scope=cutoff)
        run_ts = pd.Timestamp.utcnow()
        metrics_rows = [
            {"model":"rf_weekly","run_ts":run_ts,"scope":"cutoff","metric":"cutoff_date","value":None,
             "extra_json":f'{{"cutoff":"{cutoff.date()}","end":"{end.date()}"}}'},
            {"model":"rf_weekly","run_ts":run_ts,"scope":"cutoff","metric":"MAE_weekly_RF","value":mae_rf_w,"extra_json":None},
            {"model":"rf_weekly","run_ts":run_ts,"scope":"cutoff","metric":"MAE_weekly_Naive","value":mae_nv_w,"extra_json":None},
            {"model":"rf_weekly","run_ts":run_ts,"scope":"cutoff","metric":"WAPE_weekly_RF","value":wape_rf_w,"extra_json":None},
            {"model":"rf_weekly","run_ts":run_ts,"scope":"cutoff","metric":"WAPE_weekly_Naive","value":wape_nv_w,"extra_json":None},
            {"model":"rf_weekly","run_ts":run_ts,"scope":"cutoff","metric":"Gain_MAE_pct","value":None,
             "extra_json":f'{{"value":{(None if pd.isna(gain_mae) else round(100*gain_mae,2))}}}'},
            {"model":"rf_weekly","run_ts":run_ts,"scope":"cutoff","metric":"Gain_WAPE_pct","value":None,
             "extra_json":f'{{"value":{(None if pd.isna(gain_wape) else round(100*gain_wape,2))}}}'},
            {"model":"rf_weekly","run_ts":run_ts,"scope":"cutoff","metric":"Wilcoxon_p","value":w_p,"extra_json":None},
            {"model":"rf_weekly","run_ts":run_ts,"scope":"cutoff","metric":"MAE_monthly_RF","value":mae_rf_m,"extra_json":None},
            {"model":"rf_weekly","run_ts":run_ts,"scope":"cutoff","metric":"MAE_monthly_Naive","value":mae_nv_m,"extra_json":None},
            {"model":"rf_weekly","run_ts":run_ts,"scope":"cutoff","metric":"WAPE_monthly_RF","value":wape_rf_m,"extra_json":None},
            {"model":"rf_weekly","run_ts":run_ts,"scope":"cutoff","metric":"WAPE_monthly_Naive","value":wape_nv_m,"extra_json":None},
        ]
        try:
            pd.DataFrame(metrics_rows).to_sql(self.out_table_metrics, self.engine, if_exists="append", index=False)
        except Exception:
            pd.DataFrame(metrics_rows).to_csv("ml_forecast_metrics_cutoff_fallback.csv", index=False)

        metrics = {
            "cutoff_date": cutoff.date(),
            "end_date_excl": end.date(),
            "MAE_weekly_RF": mae_rf_w, "WAPE_weekly_RF": wape_rf_w,
            "MAE_weekly_Naive": mae_nv_w, "WAPE_weekly_Naive": wape_nv_w,
            "Gain_MAE_%": None if pd.isna(gain_mae) else round(100*gain_mae,2),
            "Gain_WAPE_%": None if pd.isna(gain_wape) else round(100*gain_wape,2),
            "Wilcoxon_p": w_p,
            "MAE_monthly_RF": mae_rf_m, "WAPE_monthly_RF": wape_rf_m,
            "MAE_monthly_Naive": mae_nv_m, "WAPE_monthly_Naive": wape_nv_m,
        }
        return {"metrics": metrics, "weekly_df": join_w, "monthly_df": join_m, "preds_df": pred_eval}
