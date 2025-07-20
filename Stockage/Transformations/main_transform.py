import os
import sys
import importlib
from pathlib import Path

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
    print("Transformations terminées.")

if __name__ == "__main__":
    main()
