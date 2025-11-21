import json
import os

# Chemin vers le fichier de sauvegarde
DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "bot_data.json")

def ensure_data_dir():
    """Vérifie que le dossier 'data' existe, sinon le crée."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"📁 Dossier '{DATA_DIR}' créé.")

def save_game_data(history_instance):
    """
    Sauvegarde l'historique des commandes dans un fichier JSON.
    
    Args:
        history_instance (CommandHistory): L'instance de la liste chaînée à sauvegarder.
    """
    ensure_data_dir()
    
    # On utilise la méthode .to_list_dict() que tu as codée dans CommandHistory
    data_to_save = {
        "history": history_instance.to_list_dict()
    }

    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        print("💾 Données sauvegardées avec succès (History).")
    except Exception as e:
        print(f"⚠️ Erreur lors de la sauvegarde : {e}")

def load_game_data(history_instance):
    """
    Charge l'historique depuis le JSON et remplit la liste chaînée.
    
    Args:
        history_instance (CommandHistory): L'instance vide à remplir.
    """
    if not os.path.exists(DATA_FILE):
        print("📂 Aucun fichier de sauvegarde trouvé, démarrage à neuf.")
        return

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Reconstruction de l'historique (Liste Chaînée)
            saved_history = data.get("history", [])
            for item in saved_history:
                # On réutilise la méthode .add() de ta structure
                history_instance.add(item['cmd'], item['user'])
                
        print(f"📂 Données chargées : {len(saved_history)} entrées d'historique restaurées.")
    except Exception as e:
        print(f"⚠️ Erreur lors du chargement ou fichier corrompu : {e}")

def sanitize_filename(filename):
    """
    (Bonus) Nettoie un nom de fichier pour l'export (enlève les caractères interdits).
    Utile pour ta commande !export.
    """
    return "".join([c for c in filename if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()
