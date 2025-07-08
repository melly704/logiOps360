import pandas as pd

def clean_customer_orders(df):
    df["creationDate"] = pd.to_datetime(df["creationDate"], errors="coerce")
    df["quantity (units)"] = pd.to_numeric(df["quantity (units)"], errors="coerce")
    return df
