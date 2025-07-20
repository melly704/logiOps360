import pandas as pd
import numpy as np
import re

def transform_support_points(engine) -> pd.DataFrame:
    """
    Transforme les données des points de support avec correction automatique :
    - Correction des formats de coordonnées
    - Nettoyage intelligent des labels
    - Remplacement des valeurs manquantes
    - Conservation de toutes les lignes originales
    """
    # 1. Chargement des données
    df_raw = pd.read_sql("SELECT * FROM raw_support_points", engine)
    
    # 2. Initialisation des listes pour les données corrigées
    corrected_data = []
    
    for idx, row in df_raw.iterrows():
        # Initialisation avec valeurs par défaut
        correction_report = {
            'original_label': row['labels'],
            'original_points': row['points_specified'],
            'corrections_applied': [],
            'is_valid': True
        }
        
        # Gestion du label
        label = str(row['labels']) if pd.notna(row['labels']) else "UNLABELED"
        correction_report['label'] = label.strip().upper()[:50]  # Truncation pour sécurité
        
        # Gestion des coordonnées
        points_str = str(row['points_specified']) if pd.notna(row['points_specified']) else ""
        
        try:
            # Correction 1: Normalisation des séparateurs
            points_normalized = re.sub(r'[;,|\s]+', ',', points_str.strip())
            if points_normalized != points_str:
                correction_report['corrections_applied'].append(f"Normalized separators: {points_str} -> {points_normalized}")
            
            # Extraction des nombres (plus permissive)
            coord_values = re.findall(r"[-+]?\d*\.?\d+", points_normalized)
            
            # Correction 2: Complétion des coordonnées manquantes
            if len(coord_values) < 3:
                coord_values += [0] * (3 - len(coord_values))
                correction_report['corrections_applied'].append(f"Completed missing coordinates with 0")
                correction_report['is_valid'] = False
            
            # Conversion en float avec gestion d'erreur
            try:
                x, y, z = map(float, coord_values[:3])
            except ValueError:
                x, y, z = 0, 0, 0
                correction_report['corrections_applied'].append("Invalid coordinates -> set to (0,0,0)")
                correction_report['is_valid'] = False
            
            correction_report.update({
                'x_coord': x,
                'y_coord': y,
                'z_coord': z
            })
            
        except Exception as e:
            correction_report.update({
                'x_coord': 0,
                'y_coord': 0,
                'z_coord': 0,
                'corrections_applied': [f"Error during processing: {str(e)}"],
                'is_valid': False
            })
        
        corrected_data.append(correction_report)
    
    # 3. Création du DataFrame final
    df_corrected = pd.DataFrame(corrected_data)
    
    # 4. Calcul des métriques supplémentaires
    df_corrected['norm'] = np.sqrt(
        df_corrected['x_coord']**2 + 
        df_corrected['y_coord']**2 + 
        df_corrected['z_coord']**2
    )
    
    # 5. Optimisation du typage
    dtype_mapping = {
        'label': 'category',
        'x_coord': 'float32',
        'y_coord': 'float32',
        'z_coord': 'float32',
        'norm': 'float32',
        'is_valid': 'bool',
        'original_label': 'string',
        'original_points': 'string'
    }
    
    for col, dtype in dtype_mapping.items():
        df_corrected[col] = df_corrected[col].astype(dtype)
    
    # 6. Réorganisation des colonnes
    final_columns = [
        'label', 'x_coord', 'y_coord', 'z_coord', 'norm', 'is_valid',
        'original_label', 'original_points', 'corrections_applied'
    ]
    
    return df_corrected[final_columns]