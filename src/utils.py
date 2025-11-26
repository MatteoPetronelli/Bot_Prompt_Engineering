import json
import os
from data_structures import DialogueTree

DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "bot_data.json")

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

def save_game_data(history_instance, active_trees_dict):
    """
    Sauvegarde l'historique ET les sessions actives.
    """
    ensure_data_dir()
    
    sessions_data = {}
    for user_id, tree in active_trees_dict.items():
        sessions_data[str(user_id)] = tree.to_dict()

    data_to_save = {
        "history": history_instance.to_list_dict(),
        "sessions": sessions_data
    }

    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=4)
        print("💾 Sauvegarde complète (Historique + Sessions).")
    except Exception as e:
        print(f"⚠️ Erreur sauvegarde : {e}")

def load_game_data(history_instance, active_trees_dict):
    """
    Charge l'historique ET reconstruit les arbres de discussion.
    """
    if not os.path.exists(DATA_FILE):
        return

    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            saved_history = data.get("history", [])
            history_instance.clear()
            for item in saved_history:
                history_instance.add(item['cmd'], item['user'])
            
            saved_sessions = data.get("sessions", {})
            active_trees_dict.clear()
            
            for user_id_str, tree_data in saved_sessions.items():
                reconstructed_tree = DialogueTree.from_dict(tree_data)
                if reconstructed_tree:
                    active_trees_dict[int(user_id_str)] = reconstructed_tree
                
        print(f"📂 Données chargées : {len(saved_history)} cmds, {len(active_trees_dict)} sessions actives.")
    except Exception as e:
        print(f"⚠️ Erreur chargement : {e}")

def sanitize_filename(filename):
    return "".join([c for c in filename if c.isalpha() or c.isdigit() or c in (' ', '-', '_')]).rstrip()