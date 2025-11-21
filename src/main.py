import discord
import os
import json
from discord.ext import commands
from dotenv import load_dotenv
from openai import OpenAI

# --- IMPORTS LOCAUX ---
from data_structures import CommandHistory, DialogueTree, TreeNode
from utils import save_game_data, load_game_data, sanitize_filename

# --- 1. CONFIGURATION ---

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
LM_STUDIO_URL = os.getenv('LM_STUDIO_URL', "http://localhost:1234/v1")

if not DISCORD_TOKEN:
    raise ValueError("ERREUR : Token Discord manquant dans le fichier .env")

# Configuration du client pour LM Studio
# LM Studio imite l'API d'OpenAI, donc on utilise ce client
client = OpenAI(
    base_url=LM_STUDIO_URL,
    api_key="lm-studio" # Clé factice requise par la librairie
)

# Configuration Discord
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- 2. ÉTAT GLOBAL ---
global_history = CommandHistory()
active_trees = {}

# --- 3. LOGIQUE IA (LOCALE) ---

async def generate_next_step(ctx, tree, user_input):
    """
    Fonction connectée à LM Studio.
    """
    
    # C'est le prompt STRICT que tu as validé lors du crash test
    system_instruction = """
    Tu es un architecte de prompt expert.
    Ton but : Construire le prompt parfait pour une IA générative.
    
    Règles :
    1. Analyse la réponse de l'utilisateur par rapport au contexte.
    2. Si flou -> Pose une question de clarification.
    3. Si clair -> Génère le prompt final.
    
    FORMAT DE RÉPONSE OBLIGATOIRE (JSON RAW) :
    {
        "type": "question" OU "conclusion",
        "content": "Texte de la question ou du prompt final",
        "summary": "Résumé court"
    }
    IMPORTANT :
    - NE DIS RIEN D'AUTRE.
    - PAS DE PHRASE D'INTRO ("Voici le JSON...").
    - PAS DE MARKDOWN (Pas de ```json ... ```).
    - JUSTE L'OBJET JSON BRUT.
    """
    
    # Construction de l'historique court pour le modèle local
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": f"Question précédente du bot : {tree.current_node.question}"},
        {"role": "user", "content": f"Réponse utilisateur : {user_input}"}
    ]
    
    try:
        # Appel à LM Studio
        response = client.chat.completions.create(
            model="local-model", # LM Studio utilise le modèle chargé, ce nom importe peu
            messages=messages,
            temperature=0.3, # Température basse pour forcer le respect du JSON
            max_tokens=500
        )
        
        raw_content = response.choices[0].message.content.strip()
        
        # --- NETTOYAGE DU JSON (Sécurité Anti-Bug pour la démo) ---
        # Même si le modèle bave un peu, on extrait ce qui est entre { et }
        start_idx = raw_content.find('{')
        end_idx = raw_content.rfind('}') + 1
        
        if start_idx != -1 and end_idx != -1:
            json_str = raw_content[start_idx:end_idx]
            ai_data = json.loads(json_str)
        else:
            # Fallback critique si vraiment pas de JSON (très rare avec ton test)
            print(f"ERREUR JSON BRUT : {raw_content}")
            raise ValueError("Le modèle n'a pas renvoyé de structure JSON détectable.")

        # --- MISE À JOUR DE L'ARBRE ---
        new_node = TreeNode(question=ai_data['content'])
        
        if ai_data['type'] == 'question':
            tree.current_node.left = new_node
            tree.current_node = new_node
            await ctx.send(f"🤖 **Question :** {ai_data['content']}")
            
        elif ai_data['type'] == 'conclusion':
            new_node.is_conclusion = True
            tree.current_node.left = new_node
            tree.current_node = new_node
            
            embed = discord.Embed(title="✨ Prompt Final", description=ai_data['content'], color=0x00ff00)
            await ctx.send(embed=embed)
            await ctx.send("Tapez `!export` pour télécharger ce résultat.")

    except Exception as e:
        print(f"⚠️ Erreur : {e}")
        # En démo, mieux vaut dire qu'il y a une erreur plutôt que de planter silencieusement
        await ctx.send(f"⚠️ Petite erreur technique de l'IA ({e}). Essaie de reformuler ta réponse.")

# --- 4. ÉVÉNEMENTS DISCORD ---

@bot.event
async def on_ready():
    load_game_data(global_history)
    print(f'✅ Connecté en tant que {bot.user}')
    print(f'📡 Prêt à communiquer avec LM Studio sur {LM_STUDIO_URL}')

@bot.event
async def on_disconnect():
    save_game_data(global_history)
    print("🔌 Déconnexion - Sauvegarde effectuée.")

@bot.event
async def on_message(message):
    if message.author.bot: return

    # Historique global des commandes
    if message.content.startswith("!"):
        global_history.add(message.content, message.author.id)
        await bot.process_commands(message)
        return

    # Discussion active dans l'arbre
    if message.author.id in active_trees:
        tree = active_trees[message.author.id]
        if tree.current_node and not tree.current_node.is_conclusion:
            async with message.channel.typing():
                tree.current_node.user_answer = message.content
                await generate_next_step(await bot.get_context(message), tree, message.content)
            return

# --- 5. COMMANDES ---

@bot.command()
async def prompt(ctx, *, initial_idea):
    """Lance la démo."""
    new_tree = DialogueTree()
    new_tree.root = TreeNode(question=f"Sujet initial : {initial_idea}")
    new_tree.current_node = new_tree.root
    active_trees[ctx.author.id] = new_tree
    
    await ctx.send(f"🏗️ **Architecte Local initialisé pour :** *{initial_idea}*")
    async with ctx.channel.typing():
        await generate_next_step(ctx, new_tree, initial_idea)

@bot.command()
async def reset(ctx):
    """Supprime complètement la session en cours."""
    if ctx.author.id in active_trees:
        del active_trees[ctx.author.id]
        await ctx.send("🗑️ **Session effacée.** Tout est oublié. Tapez `!prompt` pour recommencer.")
    else:
        await ctx.send("❌ Aucune session à effacer.")

@bot.command(name="speak")
async def speak(ctx, *, topic):
    """Permet de taper '!speak about X' ou '!speak X'."""
    
    if topic.lower().startswith("about "):
        topic = topic[6:] # Coupe les 6 premiers caractères ("about ")

    if ctx.author.id in active_trees:
        tree = active_trees[ctx.author.id]
        found = tree.search_topic(topic)
        
        if found:
             await ctx.send(f"✅ Oui, nous avons parlé de **{topic}**.")
        else:
             await ctx.send(f"❌ Non, **{topic}** n'a pas été mentionné.")
    else:
        await ctx.send("❌ Pas de session active.")

@bot.command()
async def my_history(ctx):
    cmds = global_history.get_all(ctx.author.id)
    if cmds:
        msg = "\n".join(cmds)
        if len(msg) > 1900: msg = msg[:1900] + "..."
        await ctx.send(f"📜 **Historique :**\n{msg}")
    else:
        await ctx.send("📭 Vide.")

@bot.command(aliases=['last'])
@bot.command(aliases=['last'])
async def last_cmd(ctx):
    """Affiche la commande précédente (en ignorant la commande actuelle)."""
    
    # On récupère tout l'historique de l'utilisateur sous forme de liste
    cmds = global_history.get_all(ctx.author.id)
    
    # On a besoin d'au moins 2 éléments pour avoir un "avant-dernier"
    if len(cmds) >= 2:
        # On prend l'élément à l'index -2 (l'avant-dernier)
        previous_cmd = cmds[-2]
        await ctx.send(f"🔙 **Commande précédente :** `{previous_cmd}`")
    else:
        # S'il n'y a que ["!last"], c'est qu'il n'y a pas d'historique avant
        await ctx.send("📭 Pas d'historique avant cette commande.")

@bot.command()
async def clear_history(ctx):
    global_history.clear()
    await ctx.send("🗑️ Historique vidé.")

@bot.command()
async def export(ctx):
    if ctx.author.id not in active_trees: return await ctx.send("❌ Rien à exporter.")
    tree = active_trees[ctx.author.id]
    if not tree.current_node.is_conclusion: return await ctx.send("⚠️ Discussion pas finie.")
    
    safe_name = sanitize_filename(f"prompt_{ctx.author.name}")
    filename = f"{safe_name}.txt"
    with open(filename, "w", encoding='utf-8') as f:
        f.write(tree.current_node.question)
    await ctx.send("📁 Fichier généré :", file=discord.File(filename))
    os.remove(filename)

@bot.command()
async def path(ctx):
    if ctx.author.id not in active_trees: return await ctx.send("❌ Pas de session.")
    tree = active_trees[ctx.author.id]
    node = tree.root
    path_str = "🌲 **Chemin parcouru (Arbre Binaire) :**\n"
    while node:
        label = "🏁" if node.is_conclusion else "❓"
        content = (node.question[:40] + '...') if len(node.question) > 40 else node.question
        path_str += f"⬇️ [{label}] {content}\n"
        node = node.left 
    await ctx.send(f"```{path_str}```")

@bot.command()
async def status(ctx):
    active_users = len(active_trees)
    # Petit check ping vers LM Studio
    try:
        client.models.list()
        state = "🟢 Connecté à LM Studio"
    except:
        state = "🔴 LM Studio injoignable (Check port 1234)"
    
    await ctx.send(f"**État du Bot :**\n{state}\nSessions actives : {active_users}")

bot.run(DISCORD_TOKEN)