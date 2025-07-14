import pandas as pd

def transform_customer_orders(engine) -> pd.DataFrame:
    df_raw = pd.read_sql("SELECT * FROM raw_customer_orders", engine)

    df_parsed = df_raw.iloc[:, 0].str.split(";", expand=True)
    df_parsed.columns = [
        "codCustomer", "orderNumber", "orderToCollect", "Reference",
        "Size (US)", "quantity (units)", "creationDate", "waveNumber", "operator"
    ]

    df_clean = df_parsed.dropna(how='all').drop_duplicates()

    str_cols = ["codCustomer", "Reference", "operator"]
    for col in str_cols:
        df_clean[col] = df_clean[col].astype(str).str.strip()

    df_clean["orderNumber"] = pd.to_numeric(df_clean["orderNumber"], errors="coerce")
    df_clean["orderToCollect"] = pd.to_numeric(df_clean["orderToCollect"], errors="coerce")
    df_clean["Size (US)"] = pd.to_numeric(df_clean["Size (US)"], errors="coerce")
    df_clean["quantity (units)"] = pd.to_numeric(df_clean["quantity (units)"], errors="coerce")
    df_clean["waveNumber"] = pd.to_numeric(df_clean["waveNumber"], errors="coerce")
    df_clean["creationDate"] = pd.to_datetime(df_clean["creationDate"], errors="coerce", dayfirst=True)

    df_clean["Reference"] = df_clean["Reference"].str.upper().str.replace("-", "").str.strip()

    df_clean = df_clean.dropna(subset=["orderNumber", "Reference", "creationDate"])

    df_clean.columns = [
        col.strip().lower().replace(" ", "_").replace("(", "").replace(")", "")
        for col in df_clean.columns
    ]

    return df_clean
