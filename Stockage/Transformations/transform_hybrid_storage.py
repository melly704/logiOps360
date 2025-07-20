import pandas as pd
import numpy as np

def transform_hybrid_storage(engine) -> pd.DataFrame:
    """
    Transforme les données de stockage hybride avec :
    - Extraction des informations depuis les colonnes numérotées 1 à 18
    - Nettoyage des données
    - Calcul de métriques clés
    - Ajout des informations XYZCOD
    """
    # Chargement des données
    df_raw = pd.read_sql("SELECT * FROM raw_hybrid_storage", engine)
    
    # 1. Transformation de la structure
    melted_data = []
    
    for _, row in df_raw.iterrows():
        location = row['Location']
        xyzcod = row['XYZCOD']
        
        # Traitement des 18 colonnes de stockage (1 à 18)
        for i in range(1, 19):
            col_name = str(i)  # Les colonnes sont nommées "1" à "18"
            cell_content = row[col_name]
            
            if pd.notna(cell_content) and isinstance(cell_content, str):
                try:
                    # Séparation des composants (format: "MATERIEL;QUANTITE")
                    parts = [p.strip() for p in cell_content.split(';') if p.strip()]
                    
                    if len(parts) >= 2:
                        material = parts[0].upper()
                        quantity = float(parts[1])
                        
                        melted_data.append({
                            'location': location,
                            'xyzcod': xyzcod,
                            'position': f'POS-{i:02d}',  # Format POS-01 à POS-18
                            'material': material,
                            'quantity': quantity,
                            'source_column': col_name
                        })
                except (ValueError, AttributeError):
                    continue
    
    # Création du DataFrame transformé
    df_clean = pd.DataFrame(melted_data)
    
    # 2. Nettoyage avancé
    # a. Validation des localisations
    df_clean['location'] = (
        df_clean['location']
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(r'[^A-Z0-9\-_]', '', regex=True)
    )
    
    # b. Validation du code XYZ
    df_clean['xyzcod'] = (
        df_clean['xyzcod']
        .astype(str)
        .str.strip()
        .str.upper()
        .str.replace(r'[^A-Z0-9]', '', regex=True)
    )
    
    # c. Filtrage des entrées invalides
    df_clean = df_clean[
        (df_clean['location'].str.len() > 0) &
        (df_clean['xyzcod'].str.len() > 0) &
        (df_clean['material'].str.len() > 0) &
        (df_clean['quantity'] > 0)
    ]
    
    # 3. Calcul des métriques
    # a. Détection des doublons
    df_clean['is_duplicate'] = df_clean.duplicated(
        subset=['location', 'position', 'material'], 
        keep=False
    )
    
    # b. Calcul des statistiques par emplacement
    stats_df = df_clean.groupby(['location', 'xyzcod']).agg(
        total_items=('material', 'count'),
        total_quantity=('quantity', 'sum'),
        unique_materials=('material', 'nunique'),
        positions_used=('position', 'nunique')
    ).reset_index()
    
    df_clean = pd.merge(df_clean, stats_df, on=['location', 'xyzcod'], how='left')
    
    # 4. Optimisation du typage
    dtype_mapping = {
        'location': 'category',
        'xyzcod': 'category',
        'position': 'category',
        'material': 'category',
        'quantity': 'float32',
        'source_column': 'category',
        'is_duplicate': 'bool',
        'total_items': 'uint16',
        'total_quantity': 'float32',
        'unique_materials': 'uint16',
        'positions_used': 'uint8'
    }
    
    for col, dtype in dtype_mapping.items():
        if col in df_clean.columns:
            df_clean[col] = df_clean[col].astype(dtype)
    
    # 5. Réorganisation des colonnes
    final_columns = [
        'location', 'xyzcod', 'position', 'material', 'quantity',
        'total_items', 'total_quantity', 'unique_materials', 'positions_used',
        'is_duplicate', 'source_column'
    ]
    
    return df_clean[[c for c in final_columns if c in df_clean.columns]]