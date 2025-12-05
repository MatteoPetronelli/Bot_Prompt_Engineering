from config import bot, DISCORD_TOKEN, active_trees
from database import save_session
import bot_routes

if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("🛑 Arrêt manuel.")
    finally:
        print("🔌 Sauvegarde finale...")
        for user_id, tree in active_trees.items():
            save_session(user_id, tree)
        print("💾 Base de données à jour.")