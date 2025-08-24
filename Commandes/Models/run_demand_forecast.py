# Commandes/Models/run_demand_forecast.py
# -*- coding: utf-8 -*-

import sys
import argparse
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.db_utils import connect_db

# Import robuste de la classe
try:
    from .forecasts import DemandForecaster
except Exception:
    try:
        from Commandes.Models.forecasts import DemandForecaster
    except Exception:
        from forecasts import DemandForecaster


def main():
    parser = argparse.ArgumentParser(description="Run demand forecast (standard) ou avec coupure (cutoff).")
    parser.add_argument("--cutoff", type=str, default=None, help="YYYY-MM-DD (ex: 2025-08-01) -> entraîne avant cette date")
    parser.add_argument("--end", type=str, default=None, help="YYYY-MM-DD fin exclue (ex: 2025-10-01). Défaut = cutoff + 2 mois")
    parser.add_argument("--persist-eval", action="store_true", help="Écrire les prévisions d'évaluation dans fct_order_forecast")
    parser.add_argument("--val-weeks", type=int, default=4, help="Fenêtre de validation pour le run standard")
    args = parser.parse_args()

    eng = connect_db()

    # Instanciation
    forecaster = DemandForecaster(
        engine=eng,
        horizon_weeks=8,
        min_history_weeks=8,
        top_refs=None,
        table_raw="clean_customer_orders",
        val_weeks=args.val_weeks,
        write_back=True,
    )

    if args.cutoff:
        # Scénario "avant cutoff -> prédire jusqu'à end"
        res = forecaster.run_with_cutoff("2025-08-01", "2025-10-01", persist_eval=False, model_tag="rf_aug_sep")
        print("\n=== Résumé cutoff ===")
        for k, v in res["metrics"].items():
            print(f"{k}: {v}")
        # Sauvegardes locales utiles
        try:
            res["weekly_df"].to_csv("outputs/cutoff_weekly_join.csv", index=False)
            res["monthly_df"].to_csv("outputs/cutoff_monthly_join.csv", index=False)
            res["preds_df"].to_csv("outputs/cutoff_predictions.csv", index=False)
            print("→ Fichiers écrits dans outputs/")
        except Exception:
            pass
    else:
        # Run standard (split train/val interne + H7 + forecast futur)
        fc = forecaster.run()
        print("\n=== Extrait des prévisions futures ===")
        try:
            print(fc.head())
        except Exception:
            print("(pas de lignes à afficher)")


if __name__ == "__main__":
    main()
