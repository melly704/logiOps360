import pandas as pd

def transform_supply_chain_problem(engine) -> pd.DataFrame:
    df_logistics = pd.read_sql("SELECT * FROM raw_supply_chain_problem", engine)

    df_clean_logistics = df_logistics.copy()

    df_clean_logistics.columns = [
        col.strip().lower().replace(" ", "_").replace("(", "").replace(")", "")
        for col in df_clean_logistics.columns
    ]

    str_cols = df_clean_logistics.select_dtypes(include='object').columns
    for col in str_cols:
        df_clean_logistics[col] = (
            df_clean_logistics[col]
            .astype(str)
            .str.strip()
            .str.replace(r"\s+", " ", regex=True)
            .str.upper()
        )

    df_clean_logistics = df_clean_logistics.drop_duplicates()

    return df_clean_logistics
