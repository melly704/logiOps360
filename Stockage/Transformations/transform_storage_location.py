import pandas as pd
import numpy as np

def transform_storage_location(engine) -> pd.DataFrame:
    """
    Transforme et prétraite les données de localisation de stockage avec:
    - Nettoyage des textes
    - Validation des coordonnées
    - Calcul de métriques dérivées
    - Gestion des valeurs aberrantes
    """
    # Chargement des données
    df_raw = pd.read_sql("SELECT * FROM raw_storage_location", engine)
    
    # Copie pour transformation
    df_clean = df_raw.copy()
    
    # 1. Nettoyage des textes
    text_cols = ["originalLocation", "position"]
    for col in text_cols:
        if col in df_clean.columns:
            # Standardisation texte
            df_clean[col] = (
                df_clean[col]
                .astype(str)
                .str.strip()
                .str.upper()
                .str.replace(r'[^A-Z0-9\-_]', '', regex=True)  # Suppression caractères spéciaux
            )
    
    # 2. Prétraitement des coordonnées
    coord_cols = ["x", "y", "z"]
    for col in coord_cols:
        if col in df_clean.columns:
            # Conversion numérique avec gestion des erreurs
            df_clean[col] = (
                pd.to_numeric(df_clean[col], errors='coerce')
                .replace(0, np.nan)  # 0 considéré comme non valide
            )
    
    # 3. Renommage et normalisation des colonnes
    df_clean.columns = (
        df_clean.columns
        .str.lower()
        .str.replace(' ', '_')
        .str.replace('[^a-z0-9_]', '', regex=True)
    )
    df_clean = df_clean.rename(columns={
        'originallocation': 'location',
        'position': 'position_code'
    })
    
    # 4. Calcul des métriques dérivées
    if all(c in df_clean.columns for c in ['x', 'y', 'z']):
        df_clean['volume'] = df_clean['x'] * df_clean['y'] * df_clean['z']
        df_clean['area'] = df_clean['x'] * df_clean['y']
        
        # Détection des valeurs aberrantes (seuils arbitraires à adapter)
        df_clean['outlier_flag'] = (
            (df_clean['volume'] > 1000) | 
            (df_clean[['x', 'y', 'z']].gt(20).any(axis=1))
        )
    
    # 5. Validation et filtrage des données
    # a. Suppression des lignes sans localisation valide
    df_clean = df_clean[df_clean['location'].str.match(r'^[A-Z0-9\-_]+$')]
    
    # b. Filtrage des coordonnées non valides
    if all(c in df_clean.columns for c in ['x', 'y', 'z']):
        df_clean = df_clean.dropna(subset=['x', 'y', 'z'], how='all')
    
    # 6. Typage final des colonnes
    dtype_mapping = {
        'location': 'category',
        'position_code': 'category',
        'x': 'float32',
        'y': 'float32', 
        'z': 'float32'
    }
    
    for col, dtype in dtype_mapping.items():
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].astype(dtype, errors='ignore')
    
    # 7. Réorganisation des colonnes
    base_cols = ['location', 'position_code']
    metric_cols = [c for c in ['x', 'y', 'z', 'volume', 'area', 'outlier_flag'] 
                  if c in df_clean.columns]
    
    df_clean = df_clean[base_cols + metric_cols]
    
    # 8. Suppression des doublons (si nécessaire)
    df_clean = df_clean.drop_duplicates(
        subset=['location', 'position_code'], 
        keep='first'
    )
    
    return df_clean.reset_index(drop=True)