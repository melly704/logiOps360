# generate_product_categories.py
import numpy as np
import pandas as pd
from pathlib import Path
import sys

# On remonte de deux niveaux pour accéder à utils/
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.db_utils import connect_db

CATEGORIES = [
    "SKINCARE", "HAIRCARE", "COSMETICS", "FRAGRANCES", "PERSONAL_HYGIENE",
    "BODY_CARE", "MEN_GROOMING", "ORAL_CARE", "BABY_CARE", "SUN_CARE", "WELLNESS"
]

def fetch_references(engine):
    try:
        return pd.read_sql("SELECT DISTINCT reference FROM clean_product", engine).rename(columns={"reference": "Reference"})
    except Exception:
        return pd.read_sql('SELECT DISTINCT "Reference" FROM product', engine)

def main(seed=None):
    if seed is not None:
        np.random.seed(seed)

    engine = connect_db()
    refs = fetch_references(engine)
    if refs.empty:
        print("Aucune référence trouvée dans la base.")
        return

    refs["category"] = np.random.choice(CATEGORIES, size=len(refs))

    out_path = Path("product_category_mapping.csv")
    refs[["Reference", "category"]].to_csv(out_path, index=False, sep=";")
    print(f"Mapping généré : {out_path.resolve()} ({len(refs)} lignes)")

if __name__ == "__main__":
    # Pour résultat reproductible, mets un seed : main(seed=42)
    main()
