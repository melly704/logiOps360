import pandas as pd
import numpy as np
 
def transform_storage_location(engine) -> pd.DataFrame:
    """
    Transforme et prétraite les données de localisation de stockage avec:
    - Nettoyage des textes
    - Validation des coordonnées
    - Calcul de métriques dérivées
    - Ajout du label du support le plus proche (optimisé)
    """
    # 1. Chargement des données
    df_clean = pd.read_sql("SELECT * FROM raw_storage_location", engine)
    df_support = pd.read_sql("SELECT * FROM clean_support_points", engine)
<<<<<<< HEAD
   
=======
    
>>>>>>> 9a4ff29a128998a49834fb8d91439c4038c41a4c
    # 2. Nettoyage des textes
    text_cols = ["originalLocation", "position"]
    for col in text_cols:
        if col in df_clean.columns:
            df_clean[col] = (
                df_clean[col].astype(str)
                .str.strip()
                .str.upper()
                .str.replace(r'[^A-Z0-9\-_]', '', regex=True)
            )
<<<<<<< HEAD
   
=======
    
>>>>>>> 9a4ff29a128998a49834fb8d91439c4038c41a4c
    # 3. Prétraitement des coordonnées
    coord_cols = ["x", "y", "z"]
    for col in coord_cols:
        if col in df_clean.columns:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').replace(0, np.nan)
<<<<<<< HEAD
   
=======
    
>>>>>>> 9a4ff29a128998a49834fb8d91439c4038c41a4c
    # 4. Renommage des colonnes
    df_clean.columns = (
        df_clean.columns
        .str.lower()
        .str.replace(' ', '_')
        .str.replace('[^a-z0-9_]', '', regex=True)
    )
    df_clean = df_clean.rename(columns={'originallocation': 'location', 'position': 'position_code'})
<<<<<<< HEAD
   
=======
    
>>>>>>> 9a4ff29a128998a49834fb8d91439c4038c41a4c
    # 5. Calcul des métriques dérivées
    if all(c in df_clean.columns for c in ['x', 'y', 'z']):
        df_clean['volume'] = df_clean['x'] * df_clean['y'] * df_clean['z']
        df_clean['area'] = df_clean['x'] * df_clean['y']
<<<<<<< HEAD
   
=======
    
>>>>>>> 9a4ff29a128998a49834fb8d91439c4038c41a4c
    # 6. Ajout du label du support le plus proche (version optimisée)
    if all(c in df_support.columns for c in ['label', 'x_coord', 'y_coord', 'z_coord']):
        # Conversion en arrays numpy
        points_storage = df_clean[['x', 'y', 'z']].to_numpy()
        points_support = df_support[['x_coord', 'y_coord', 'z_coord']].to_numpy()
        support_labels = df_support['label'].to_numpy()
<<<<<<< HEAD
       
=======
        
>>>>>>> 9a4ff29a128998a49834fb8d91439c4038c41a4c
        # Calcul de toutes les distances en une seule fois
        # points_storage.shape = (n_storage, 3)
        # points_support.shape = (n_support, 3)
        # On crée un tableau de distances (n_storage x n_support)
        diff = points_storage[:, np.newaxis, :] - points_support[np.newaxis, :, :]
        distances = np.linalg.norm(diff, axis=2)
<<<<<<< HEAD
       
        # Pour chaque storage point, on prend l'indice du support le plus proche
        closest_idx = np.argmin(distances, axis=1)
        df_clean['support_label'] = support_labels[closest_idx]
   
=======
        
        # Pour chaque storage point, on prend l'indice du support le plus proche
        closest_idx = np.argmin(distances, axis=1)
        df_clean['support_label'] = support_labels[closest_idx]
    
>>>>>>> 9a4ff29a128998a49834fb8d91439c4038c41a4c
    # 7. Validation et filtrage
    df_clean = df_clean[df_clean['location'].str.match(r'^[A-Z0-9\-_]+$')]
    if all(c in df_clean.columns for c in ['x', 'y', 'z']):
        df_clean = df_clean.dropna(subset=['x', 'y', 'z'], how='all')
<<<<<<< HEAD
   
=======
    
>>>>>>> 9a4ff29a128998a49834fb8d91439c4038c41a4c
    # 8. Typage final
    dtype_mapping = {
        'location': 'category',
        'position_code': 'category',
        'x': 'float32',
        'y': 'float32',
        'z': 'float32',
        'support_label': 'category'
    }
    for col, dtype in dtype_mapping.items():
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].astype(dtype, errors='ignore')
<<<<<<< HEAD
   
=======
    
>>>>>>> 9a4ff29a128998a49834fb8d91439c4038c41a4c
    # 9. Réorganisation des colonnes
    base_cols = ['location', 'position_code', 'support_label']
    metric_cols = [c for c in ['x', 'y', 'z', 'volume', 'area'] if c in df_clean.columns]
    df_clean = df_clean[base_cols + metric_cols]
<<<<<<< HEAD
   
    # 10. Suppression des doublons
    df_clean = df_clean.drop_duplicates(subset=['location', 'position_code'], keep='first')
   
    return df_clean.reset_index(drop=True)
=======
    
    # 10. Suppression des doublons
    df_clean = df_clean.drop_duplicates(subset=['location', 'position_code'], keep='first')
    
    return df_clean.reset_index(drop=True)
>>>>>>> 9a4ff29a128998a49834fb8d91439c4038c41a4c
