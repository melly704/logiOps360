import pandas as pd

def transform_dedicated_storage(engine) -> pd.DataFrame:
    # Chargement des données depuis PostgreSQL
    df_raw = pd.read_sql("SELECT * FROM raw_dedicated_storage", engine)
    
    # Transformation des données
    melted_data = []
    
    for _, row in df_raw.iterrows():
        location = row['Location']
        xyz_class = row['XYZCOD']
        
        # Colonnes produits (1 à 18)
        for i in range(1, 19):
            col_name = str(i)
            material_info = row[col_name]
            
            if pd.notna(material_info) and isinstance(material_info, str) and ';' in material_info:
                try:
                    parts = material_info.split(';')
                    referenceproduit = parts[0]
                    quantity = parts[1]
                    utilization_rate = parts[2] if len(parts) > 2 else None
                    
                    melted_data.append({
                        'location': location.strip() if pd.notna(location) else None,
                        'class': xyz_class.strip().upper() if pd.notna(xyz_class) else None,
                        'referenceproduit': referenceproduit.strip().upper() if pd.notna(referenceproduit) else None,
                        'quantity': float(quantity) if pd.notna(quantity) else None,
                        'utilization_rate': float(utilization_rate) if pd.notna(utilization_rate) else None,
                        'storage_type': 'dedicated'
                    })
                except (ValueError, AttributeError, IndexError):
                    continue
    
    # Création du dataframe transformé
    df_clean = pd.DataFrame(melted_data)
    
    # Suppression des lignes incomplètes
    df_clean = df_clean.dropna(subset=['referenceproduit', 'class', 'quantity'])
    
    # Conversion numérique
    df_clean['quantity'] = pd.to_numeric(df_clean['quantity'], errors='coerce')
    df_clean['utilization_rate'] = pd.to_numeric(df_clean['utilization_rate'], errors='coerce')
    
    return df_clean