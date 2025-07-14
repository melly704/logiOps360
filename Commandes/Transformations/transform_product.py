import pandas as pd

def transform_product(engine) -> pd.DataFrame:
    df_product = pd.read_sql("SELECT * FROM raw_products", engine)

    df_product = df_product.iloc[:, 0].str.split(";", expand=True)
    df_product.columns = ["Reference", "ABCCOD", "Sector"]

    df_product.columns = [
        col.strip().lower().replace(" ", "_").replace("(", "").replace(")", "")
        for col in df_product.columns
    ]

    df_clean_product = df_product.drop_duplicates()

    str_cols = df_clean_product.select_dtypes(include='object').columns
    for col in str_cols:
        df_clean_product[col] = df_clean_product[col].astype(str).str.strip()

    df_clean_product = df_clean_product.dropna(how='all')
    df_clean_product = df_clean_product.dropna(subset=['reference'])

    df_clean_product['reference'] = df_clean_product['reference'].str.upper().str.replace("-", "").str.strip()

    return df_clean_product
