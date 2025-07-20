import pandas as pd

def transform_dedicated_storage(engine) -> pd.DataFrame:
    # Chargement des données depuis PostgreSQL
    df_raw = pd.read_sql("SELECT * FROM raw_dedicated_storage", engine)
    
    # Transformation des données
    melted_data = []
    
    # Pour chaque ligne du dataframe original
    for _, row in df_raw.iterrows():
        location = row['Location']
        xyz_class = row['XYZCOD']
        
        # Pour chaque colonne de matériel (colonnes 1 à 18)
        for i in range(1, 19):
            col_name = str(i)
            material_info = row[col_name]
            
            # Vérifier si la valeur existe et contient bien un point-virgule
            if pd.notna(material_info) and isinstance(material_info, str) and ';' in material_info:
                try:
                    parts = material_info.split(';')
                    # Certaines cellules pourraient avoir plus d'infos (ex: "MATERIEL;QTE;TAUX_UTILISATION")
                    material = parts[0]
                    quantity = parts[1]
                    utilization_rate = parts[2] if len(parts) > 2 else None
                    
                    melted_data.append({
                        'location': location.strip() if pd.notna(location) else None,
                        'xyz_class': xyz_class.strip() if pd.notna(xyz_class) else None,
                        'material': material.strip().upper() if pd.notna(material) else None,
                        'quantity': float(quantity) if pd.notna(quantity) else None,
                        'utilization_rate': float(utilization_rate) if pd.notna(utilization_rate) else None
                    })
                except (ValueError, AttributeError, IndexError):
                    # Gérer les cas où la conversion échoue
                    continue
    
    # Création du dataframe transformé
    df_clean = pd.DataFrame(melted_data)
    
    # Suppression des éventuelles lignes avec des valeurs manquantes essentielles
    df_clean = df_clean.dropna(subset=['material', 'xyz_class', 'quantity'])
    
    # Conversion des types
    df_clean['quantity'] = pd.to_numeric(df_clean['quantity'], errors='coerce')
    df_clean['utilization_rate'] = pd.to_numeric(df_clean['utilization_rate'], errors='coerce')
    
    # Nettoyage des noms de colonnes
    df_clean.columns = [col.lower().strip() for col in df_clean.columns]
    
    return df_clean