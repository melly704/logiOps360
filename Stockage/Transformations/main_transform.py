import os
import sys
import importlib
from pathlib import Path
from sqlalchemy import text

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.db_utils import connect_db

TRANSFORM_FUNCS = [
    "transform_class_based_storage.transform_class_based_storage",
    "transform_dedicated_storage.transform_dedicated_storage",
    "transform_storage_location.transform_storage_location",
    "transform_random_storage.transform_random_storage",
    "transform_hybrid_storage.transform_hybrid_storage",
    "transform_support_points.transform_support_points"
]

def resolve_callable(dotted_path: str):
    module_path, func_name = dotted_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, func_name)

def create_unified_storage_view(engine):
    view_sql = """
    CREATE OR REPLACE VIEW unified_storage_view AS
WITH all_storage AS (
    SELECT location, class, referenceproduit, quantity, storage_type
    FROM clean_class_based_storage
    UNION ALL
    SELECT location, class, referenceproduit, quantity, storage_type
    FROM clean_dedicated_storage
    UNION ALL
    SELECT location, NULL AS class, referenceproduit, quantity, storage_type
    FROM clean_random_storage
),
aggregated AS (
    SELECT
        location,
        referenceproduit,
        storage_type,
        SUM(quantity) AS total_quantity
    FROM all_storage
    GROUP BY location, referenceproduit, storage_type
)
SELECT
    location,
    referenceproduit,
    COALESCE(MAX(CASE WHEN storage_type = 'class_based' THEN total_quantity END), 0) AS qty_class_based,
    COALESCE(MAX(CASE WHEN storage_type = 'dedicated' THEN total_quantity END), 0) AS qty_dedicated,
    COALESCE(MAX(CASE WHEN storage_type = 'random' THEN total_quantity END), 0) AS qty_random
FROM aggregated
GROUP BY location, referenceproduit
ORDER BY location, referenceproduit;

    """
    with engine.connect() as conn:
        conn.execute(text(view_sql))
        conn.commit()
    print("✅ Vue unified_storage_view créée avec succès")

def main():
    print(">>> MAIN LANCÉ")
    engine = connect_db()
    for dotted_path in TRANSFORM_FUNCS:
        transform_fn = resolve_callable(dotted_path)
        print(f"Execution de la fonction : {transform_fn.__name__}")
        table_suffix = transform_fn.__name__.replace("transform_", "")
        table_name = f"clean_{table_suffix}"
        try:
            df = transform_fn(engine)
            df.to_sql(table_name, engine, if_exists="replace", index=False)
            print(f"{table_name} : {len(df)} lignes insérées")
        except Exception as e:
            print(f"{table_name} : erreur - {e}")

    # Création de la vue après les transformations
    try:
        create_unified_storage_view(engine)
    except Exception as e:
        print(f"Erreur lors de la création de la vue unified_storage_view : {e}")

    print("Transformations terminées.")

if __name__ == "__main__":
    main()
