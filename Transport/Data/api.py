import requests
import pandas as pd
import io
import os

# Dossier de destination
output_dir = "logiOps360/Transport/Data"
os.makedirs(output_dir, exist_ok=True)

# Chemin du fichier final
file_path = os.path.join(output_dir, "Monthly_Modal_Time_Series.csv")

# URL de base
base_url = "https://data.transportation.gov/resource/5ti2-5uiv.csv"

# Pagination
limit = 1000
offset = 0
all_data = []

while True:
    url = f"{base_url}?$limit={limit}&$offset={offset}"
    print(f"Fetching: {url}")
    response = requests.get(url)

    if response.status_code != 200 or not response.content.strip():
        break

    chunk = pd.read_csv(io.StringIO(response.text))
    if chunk.empty:
        break

    all_data.append(chunk)
    offset += limit

# Fusion des données
df = pd.concat(all_data, ignore_index=True)

# Écrase l'ancien fichier à chaque fois
df.to_csv(file_path, index=False)
print(f"✅ Données sauvegardées dans {file_path}")
