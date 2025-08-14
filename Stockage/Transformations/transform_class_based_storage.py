import pandas as pd

def transform_class_based_storage(engine) -> pd.DataFrame:
    # Chargement des données depuis PostgreSQL
    df_raw = pd.read_sql("SELECT * FROM raw_class_based_storage", engine)
    
    # Transformation des données
    melted_data = []
    
    for _, row in df_raw.iterrows():
        location = row['Location']
        abc_class = row['ABCCOD']
        
        # Colonnes produits (1 à 18)
        for i in range(1, 19):
            col_name = str(i)
            material_info = row[col_name]
            
            if pd.notna(material_info) and ';' in material_info:
                referenceproduit, quantity = material_info.split(';')
                melted_data.append({
                    'location': location,
                    'class': abc_class,
                    'referenceproduit': referenceproduit.strip(),
                    'quantity': float(quantity),
                    'storage_type': 'class_based'
                })
    
    # Création du dataframe transformé
    df_clean = pd.DataFrame(melted_data)
    
    # Nettoyage
    df_clean['referenceproduit'] = df_clean['referenceproduit'].str.strip().str.upper()
    df_clean['class'] = df_clean['class'].str.strip().str.upper()
    
    # Suppression des lignes incomplètes
    df_clean = df_clean.dropna(subset=['referenceproduit', 'class', 'quantity'])
    
    return df_clean
