import pandas as pd

def transform_monthly_modal(engine) -> pd.DataFrame:
    # Lecture des données depuis la table RAW PostgreSQL
    df = pd.read_sql("SELECT * FROM raw_monthly_modal", engine)

    # Nettoyage des noms de colonnes
    df.columns = [
        col.lower()
           .replace(" ", "_")
           .replace("(", "")
           .replace(")", "")
           .replace("/", "_")
           .replace("-", "_")
           .replace("__", "_")
        for col in df.columns
    ]

    # Supprimer les colonnes avec plus de 80 % de valeurs manquantes
    seuil_null = 0.8
    df = df.loc[:, df.isnull().mean() < seuil_null]

    # Supprimer les colonnes manuellement jugées inutiles
    colonnes_inutiles = [
        "primary_uza_sq_miles", "primary_uza_population",
        "service_area_sq_miles", "service_area_population",
        "mo_yr", "month_year_timestamp",
        "non_major_physical_assaults_on_operators",
        "non_major_non_physical_assaults_on_operators",
        "non_major_physical_assaults_on_other_transit_workers",
        "non_major_non_physical_assaults_on_other_transit_workers",
        "major_physical_assaults_on_operators",
        "major_non_physical_assaults_on_operators",
        "major_physical_assaults_on_other_transit_workers",
        "major_non_physical_assaults_on_other_transit_workers",
        "total_assaults_on_transit_workers"
    ]
    df = df.drop(columns=[col for col in colonnes_inutiles if col in df.columns])

    # Nettoyer les chaînes de caractères (colonnes catégorielles)
    cat_cols = df.select_dtypes(include="object").columns
    for col in cat_cols:
        df[col] = df[col].astype(str).str.strip().str.upper()

    # Convertir les colonnes numériques
    num_cols = df.select_dtypes(include=["float64", "int64"]).columns
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Conversion de mo_yr (si encore présente) en datetime
    if "mo_yr" in df.columns:
        df["date"] = pd.to_datetime(df["mo_yr"].astype(str), format="%Y%m%d", errors="coerce")

    # Supprimer les doublons
    df = df.drop_duplicates()

    # Supprimer les lignes avec valeurs incohérentes
    if "vehicle_revenue_hours" in df.columns:
        df = df[df["vehicle_revenue_hours"] >= 0]

    return df
