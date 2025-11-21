import discord
import os
import json
import google.generativeai as genai
from discord.ext import commands
from dotenv import load_dotenv

# Import des structures manuelles (Assure-toi que data_structures.py est dans le même dossier)
from data_structures import CommandHistory, DialogueTree, TreeNode

# --- 1. CONFIGURATION & SÉCURITÉ ---

# Chargement des variables d'environnement (.env)
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GEMINI_KEY = os.getenv('GEMINI_API_KEY')

# Vérification de sécurité
if not DISCORD_TOKEN or not GEMINI_KEY:
    raise ValueError("ERREUR : Les clés API sont manquantes dans le fichier .env")

# Configuration de Gemini
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-3-pro-preview')

# Configuration du Bot Discord
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- 2. ÉTAT GLOBAL & PERSISTANCE ---

DATA_FILE = "data/bot_data.json"

# Instanciation des structures manuelles
global_history = CommandHistory() # Liste chaînée pour l'historique
active_trees = {} # Dictionnaire {user_id: DialogueTree}

def save_data():
    """Sauvegarde l'historique dans un fichier JSON."""
    data_to_save = {
        "history": global_history.to_list_dict()
    }
    
    # Création du dossier data s'il n'existe pas
    if not os.path.exists('data'):
        os.makedirs('data')
        
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=4)
    print("💾 Données sauvegardées avec succès.")

def load_data():
    """Charge l'historique au démarrage."""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Reconstruction de la liste chaînée
                for item in data.get("history", []):
                    global_history.add(item['cmd'], item['user'])
            print("📂 Données chargées avec succès.")
        except Exception as e:
            print(f"⚠️ Erreur lors du chargement des données : {e}")

# --- 3. LOGIQUE IA (Cerveau du Bot) ---

async def generate_next_step(ctx, tree, user_input):
    """
    Fonction centrale : 
    1. Envoie le contexte à Gemini.
    2. Reçoit une décision (Question ou Conclusion) en JSON.
    3. Met à jour l'Arbre Binaire manuel.
    """
    
    system_instruction = """
    Tu es un "Prompt Architect" expert. Ton but est d'aider l'utilisateur à construire un prompt parfait.
    Analyse la réponse de l'utilisateur.
    
    Règles :
    1. Si le prompt manque de détails (Contexte, Format, Style), pose une question binaire ou ouverte pour préciser.
    2. Si tu as assez d'infos, génère le prompt final.
    
    Format de réponse STRICTEMENT JSON :
    {
        "type": "question" OU "conclusion",
        "content": "Le texte de la question ou le prompt final",
        "summary": "Résumé très court de la question (ex: 'Demande du style')"
    }
    """
    
    # Construction du prompt pour l'IA
    full_prompt = f"{system_instruction}\n\nContexte actuel : {tree.current_node.question}\nRéponse utilisateur : {user_input}"
    
    try:
        response = model.generate_content(full_prompt)
        # Nettoyage du JSON (au cas où l'IA met des balises markdown)
        clean_text = response.text.replace('```json', '').replace('```', '').strip()
        ai_data = json.loads(clean_text)
        
        # --- MISE À JOUR DE L'ARBRE MANUEL ---
        new_node = TreeNode(question=ai_data['content'])
        
        if ai_data['type'] == 'question':
            # On ajoute un noeud enfant à gauche (chemin par défaut)
            tree.current_node.left = new_node
            tree.current_node = new_node # On avance le pointeur
            await ctx.send(f"🤖 **Question :** {ai_data['content']}")
            
        elif ai_data['type'] == 'conclusion':
            new_node.is_conclusion = True
            tree.current_node.left = new_node
            tree.current_node = new_node
            
            embed = discord.Embed(title="✨ Prompt Final", description=ai_data['content'], color=0x00ff00)
            await ctx.send(embed=embed)
            await ctx.send("Tapez `!export` pour télécharger ce résultat ou `!reset` pour recommencer.")

    except Exception as e:
        await ctx.send(f"⚠️ Erreur IA : {e}")
        print(f"Erreur complete: {e}")

# --- 4. ÉVÉNEMENTS DISCORD ---

@bot.event
async def on_ready():
    load_data()
    print(f'✅ Connecté en tant que {bot.user}')

@bot.event
async def on_disconnect():
    save_data()

@bot.event
async def on_message(message):
    # Ignorer les messages du bot lui-même
    if message.author.bot:
        return

    # Cas 1 : C'est une commande (commence par !)
    if message.content.startswith("!"):
        # Ajout à l'historique (Liste Chaînée)
        global_history.add(message.content, message.author.id)
        await bot.process_commands(message)
        return

    # Cas 2 : C'est une réponse à une discussion en cours
    if message.author.id in active_trees:
        tree = active_trees[message.author.id]
        
        # Si l'arbre n'est pas fini
        if tree.current_node and not tree.current_node.is_conclusion:
            async with message.channel.typing():
                # On stocke la réponse de l'utilisateur dans le noeud actuel
                tree.current_node.user_answer = message.content
                # On déclenche l'IA pour la suite
                await generate_next_step(await bot.get_context(message), tree, message.content)
            return

    # Si aucun cas ne correspond, on laisse faire (ou on ignore)

# --- 5. COMMANDES DE DISCUSSION (ARBRE) ---

@bot.command()
async def prompt(ctx, *, initial_idea):
    """Démarre une session de Prompt Engineering."""
    # Création d'un nouvel arbre manuel
    new_tree = DialogueTree()
    # Racine de l'arbre
    new_tree.root = TreeNode(question=f"Sujet initial : {initial_idea}")
    new_tree.current_node = new_tree.root
    
    # Stockage dans le dictionnaire global
    active_trees[ctx.author.id] = new_tree
    
    await ctx.send(f"🏗️ **Initialisation du plan pour :** *{initial_idea}*")
    async with ctx.channel.typing():
        await generate_next_step(ctx, new_tree, initial_idea)

@bot.command()
async def reset(ctx):
    """Recommence la discussion depuis le début."""
    if ctx.author.id in active_trees:
        active_trees[ctx.author.id].reset()
        await ctx.send("🔄 Retour à la racine de l'arbre.")
        # On pourrait relancer la première question ici si on stockait le prompt initial
    else:
        await ctx.send("❌ Pas de session active.")

@bot.command()
async def speak_about(ctx, *, topic):
    """Vérifie si un sujet a été abordé dans l'arbre."""
    if ctx.author.id in active_trees:
        tree = active_trees[ctx.author.id]
        # Utilisation de la méthode récursive manuelle search_topic
        found = tree.search_topic(topic)
        if found:
            await ctx.send(f"✅ Oui, nous avons parlé de **{topic}**.")
        else:
            await ctx.send(f"❌ Non, **{topic}** n'a pas été mentionné.")
    else:
        await ctx.send("❌ Pas de session active.")

# --- 6. COMMANDES D'HISTORIQUE (LISTE CHAÎNÉE) ---

@bot.command()
async def my_history(ctx):
    """Affiche tout l'historique de l'utilisateur."""
    cmds = global_history.get_all(ctx.author.id)
    if cmds:
        await ctx.send(f"📜 **Vos commandes :**\n" + "\n".join(cmds))
    else:
        await ctx.send("📭 Historique vide.")

@bot.command()
async def last_cmd(ctx):
    """Affiche la dernière commande."""
    cmd = global_history.get_last(ctx.author.id)
    if cmd:
        await ctx.send(f"🔙 **Dernière commande :** `{cmd}`")
    else:
        await ctx.send("📭 Aucune commande trouvée.")

@bot.command()
async def clear_history(ctx):
    """Vide l'historique complet."""
    global_history.clear()
    await ctx.send("🗑️ Historique vidé.")

# --- 7. FONCTIONNALITÉS SUPPLÉMENTAIRES (BONUS) ---

# Bonus 1 : Export (Fichier)
@bot.command()
async def export(ctx):
    """Exporte le prompt final dans un fichier texte."""
    if ctx.author.id not in active_trees:
        return await ctx.send("❌ Rien à exporter.")
        
    tree = active_trees[ctx.author.id]
    if not tree.current_node.is_conclusion:
        return await ctx.send("⚠️ Finissez la discussion d'abord !")
        
    filename = f"prompt_{ctx.author.id}.txt"
    with open(filename, "w", encoding='utf-8') as f:
        f.write(tree.current_node.question) # Le noeud conclusion contient le prompt
        
    await ctx.send("📁 Voici votre fichier :", file=discord.File(filename))
    os.remove(filename) # Nettoyage

# Bonus 2 : Visualisation du chemin (Path)
@bot.command()
async def path(ctx):
    """Affiche le chemin parcouru dans l'arbre."""
    if ctx.author.id not in active_trees:
        return await ctx.send("❌ Pas de session.")
        
    tree = active_trees[ctx.author.id]
    node = tree.root
    path_str = "🌲 **Chemin parcouru :**\n"
    
    # Parcours manuel simple depuis la racine
    while node:
        label = "🏁 Conclusion" if node.is_conclusion else "❓ Question"
        content = (node.question[:40] + '...') if len(node.question) > 40 else node.question
        path_str += f"⬇️ [{label}] {content}\n"
        
        # Dans cette implémentation simplifiée, on suit toujours 'left' car 
        # l'IA génère le chemin linéairement pour l'instant
        node = node.left 
        
    await ctx.send(f"```{path_str}```")

# Bonus 3 : Statut (Info Meta)
@bot.command()
async def status(ctx):
    """Affiche l'état de santé du bot."""
    active_users = len(active_trees)
    # On pourrait ajouter la latence ou la mémoire ici
    await ctx.send(f"🟢 **Bot en ligne**\nSessions actives : {active_users}\nModèle IA : Gemini 1.5 Flash")

# Lancement
bot.run(DISCORD_TOKEN)
