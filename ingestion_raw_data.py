import pandas as pd
from utils.db_utils import connect_db
import os

RAW_PATHS = {
    # Commandes
    "Commandes/Data/Customer_Order.csv": "raw_customer_orders",
    "Commandes/Data/Product.csv": "raw_products",
    "Commandes/Data/Picking_Wave.csv": "raw_picking_wave",
    "Commandes/Data/Supply_chain_logisitcs_problem.xlsx": "raw_supply_chain_problem",
    "Commandes/Data/supply_chain_data.csv": "raw_supply_chain_data",

    # Stockage
    "Stockage/Data/Class_Based_Storage.csv": "raw_class_based_storage",
    "Stockage/Data/Dedicated_Storage.csv": "raw_dedicated_storage",
    "Stockage/Data/Hybrid_Storage.csv": "raw_hybrid_storage",
    "Stockage/Data/Random_Storage.csv": "raw_random_storage",
    "Stockage/Data/Storage_Location.csv": "raw_storage_location",
    "Stockage/Data/Support_Points_Navigation.csv": "raw_support_points",

    # Transport
    "Transport/Data/Monthly_Modal_Time_Series_20250611.csv": "raw_monthly_modal",
    "Transport/Data/smart_logistics_dataset.csv": "raw_smart_logistics",
    "Transport/Data/Supply chain logisitcs problem.xlsx": "raw_supply_chain_problem_2",
    "Transport/Data/Transportation and Logistics Tracking Dataset..xlsx": "raw_transport_tracking"
}


def ingest_raw():
    engine = connect_db()
    for file_path, table_name in RAW_PATHS.items():  
        try:
            if file_path.endswith(".csv"):
                df = pd.read_csv(file_path)
            elif file_path.endswith(".xlsx"):
                df = pd.read_excel(file_path)
            else:
                raise ValueError("Format non pris en charge")
            df.to_sql(table_name, engine, if_exists="replace", index=False)
            print(f"[✓] {file_path} → {table_name}")
        except Exception as e:
            print(f"[✗] {file_path} → {table_name} : {e}")

if __name__ == "__main__":
    ingest_raw()
