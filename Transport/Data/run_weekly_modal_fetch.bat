@echo off
REM Script pour exécuter le script Python qui met à jour les données Modal depuis l’API

REM Chemin vers le interpréteur Python
set PYTHON_PATH=C:\Users\ahmed\AppData\Local\Programs\Python\Python312\python.exe

REM Chemin complet vers le script API
set SCRIPT_PATH=C:\Users\ahmed\OneDrive\Bureau\Projet LogiOps360\logiOps360\logiOps360\Transport\Data\api.py

echo Démarrage de la mise à jour des données Modal...
"%PYTHON_PATH%" "%SCRIPT_PATH%"
echo Fin de l’exécution.

pause














