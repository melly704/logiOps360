import pandas as pd

def transform_supply_chain_data(engine) -> pd.DataFrame:
    query = "SELECT * FROM raw_supply_chain_data"
    df_commandes = pd.read_sql(query, engine)

    commandes_cols = [
        "SKU", "Product type", "Availability", "Number of products sold",
        "Revenue generated", "Order quantities", "Lead times", "Customer demographics"
    ]

    df_clean_commandes = df_commandes[commandes_cols].copy()

    df_clean_commandes.columns = [
        col.strip().lower().replace(" ", "_").replace("(", "").replace(")", "")
        for col in df_clean_commandes.columns
    ]

    str_cols = df_clean_commandes.select_dtypes(include='object').columns
    for col in str_cols:
        df_clean_commandes[col] = (
            df_clean_commandes[col]
            .astype(str)
            .str.strip()
            .str.replace(r"\s+", " ", regex=True)
            .str.upper()
        )

    df_clean_commandes = df_clean_commandes.drop_duplicates()

    return df_clean_commandes
