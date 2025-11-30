import discord
import os
import json
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from openai import AsyncOpenAI

# --- IMPORTS LOCAUX ---
from data_structures import CommandHistory, DialogueTree, TreeNode
from utils import save_game_data, load_game_data, sanitize_filename

# --- 1. CONFIGURATION ---

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
LM_STUDIO_URL = os.getenv('LM_STUDIO_URL', "http://localhost:1234/v1")

if not DISCORD_TOKEN:
    raise ValueError("ERREUR : Token Discord manquant dans le fichier .env")

client = AsyncOpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- 2. ÉTAT GLOBAL ---
global_history = CommandHistory()
active_trees = {}

# --- 3. LOGIQUE IA (LOCALE) ---

async def generate_next_step(interaction_or_ctx, tree, user_input):
    """
    Gère la logique IA. 
    Accepte soit un Context (message texte) soit une Interaction (slash command).
    """
    
    async def send_msg(text=None, embed=None, file=None):
        params = {}
        if text: params['content'] = text
        if embed: params['embed'] = embed
        if file: params['file'] = file

        if isinstance(interaction_or_ctx, discord.Interaction):
            try:
                if interaction_or_ctx.response.is_done():
                    await interaction_or_ctx.followup.send(**params)
                else:
                    await interaction_or_ctx.response.send_message(**params)
            except:
                await interaction_or_ctx.followup.send(**params)
        else:
            await interaction_or_ctx.send(**params)

    system_instruction = """
    Tu es un Senior Prompt Engineer expert en méthode CO-STAR.
    Ton objectif est de construire le prompt ULTIME pour un LLM ou un générateur d'images.
    
    ANALYSE DE L'ETAT ACTUEL :
    Vérifie si tu as toutes les informations suivantes (CO-STAR) :
    1. CONTEXT (C) : Le contexte de la demande.
    2. OBJECTIVE (O) : La tâche précise à accomplir.
    3. STYLE (S) : Le style artistique ou d'écriture (ex: Cyberpunk, Académique...).
    4. TONE (T) : L'ambiance ou le ton (ex: Sombre, Enthousiaste...).
    5. AUDIENCE (A) : Pour qui est ce contenu ?
    6. FORMAT (R) : Le format de sortie (Code, Markdown, Image 16:9...).

    RÈGLES DE FORMATTAGE (CRUCIAL) :
    - Le contenu final DOIT être du Markdown propre et structuré.
    - Utilise des Titres H1 (#) pour le titre du prompt et H2 (##) pour les sections.
    - Utilise des listes à puces (-) pour énumérer les points.
    - Utilise des blocs de citation (>) pour les contextes ou les notes.
    - Sépare l'analyse CO-STAR du Script/Prompt final par une ligne de séparation (---).
    - NE METS PAS le contenu dans un bloc de code (pas de ```).

    RÈGLES DE DÉCISION :
    - Si l'utilisateur n'a donné que l'idée de base -> Pose une question sur le STYLE et le FORMAT.
    - Si tu as le Style mais pas le Contexte -> Creuse le CONTEXTE.
    - NE CONCLUS PAS tant que tu n'as pas au moins 3 ou 4 éléments du CO-STAR, sauf si l'utilisateur demande explicitement de finir.
    
    FORMAT DE RÉPONSE OBLIGATOIRE (JSON RAW) :
    {
        "type": "question" OU "conclusion",
        "content": "Le texte de ta question ou le prompt final optimisé",
        "summary": "Résumé très court pour l'arbre (ex: 'Choix du Style')"
    }
    IMPORTANT : JUSTE LE JSON. PAS DE MARKDOWN AUTOUR DU JSON.
    """

    root_context = tree.root.question if tree.root else "Non défini"
    
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": f"CONTEXTE GLOBAL DU PROJET (Ne l'oublie jamais) : {root_context}"},
        {"role": "user", "content": f"Question précédente : {tree.current_node.question}"},
        {"role": "user", "content": f"Réponse utilisateur : {user_input} (Si c'est la fin, formatte la réponse avec des titres Markdown # et ##)"}
    ]
    
    try:
        response = await client.chat.completions.create(
            model="local-model", 
            messages=messages, 
            temperature=0.3, 
            max_tokens=2000 
        )
        
        raw_content = response.choices[0].message.content.strip()
        
        start_idx = raw_content.find('{')
        
        if start_idx != -1:
            balance = 0
            end_idx = -1
            
            for i, char in enumerate(raw_content[start_idx:], start=start_idx):
                if char == '{':
                    balance += 1
                elif char == '}':
                    balance -= 1
                    if balance == 0:
                        end_idx = i + 1
                        break
            
            if end_idx != -1:
                json_str = raw_content[start_idx:end_idx]
                ai_data = json.loads(json_str)
            else:
                raise ValueError("JSON incomplet (accolade fermante manquante).")
        else:
            print(f"ERREUR JSON BRUT : {raw_content}")
            raise ValueError("Aucun objet JSON trouvé.")

        # --- LOGIQUE DE BRANCHEMENT (GAUCHE / DROITE) ---
        new_node = TreeNode(question=ai_data['content'])
        new_node.parent = tree.current_node
        new_node.cause_answer = user_input
        
        if tree.current_node.left is None:
            tree.current_node.left = new_node
            branch_msg = ""
            
        elif tree.current_node.right is None:
            tree.current_node.right = new_node
            branch_msg = " 🔀 **(Nouvelle branche créée à Droite)**"
            
        else:
            tree.current_node.left = new_node
            branch_msg = " ⚠️ **(Branche Gauche écrasée)**"

        tree.current_node = new_node
        
        if ai_data['type'] == 'question':
            await send_msg(text=f"🤖 **Question :** {ai_data['content']}{branch_msg}")
            
        elif ai_data['type'] == 'conclusion':
            new_node.is_conclusion = True
            embed = discord.Embed(title="✨ Prompt Final", description=ai_data['content'][:4000], color=0x00ff00)
            await send_msg(embed=embed)
            await send_msg(text=f"Utilisez `/export` pour télécharger.{branch_msg}")

    except json.JSONDecodeError:
        print(f"JSON ERROR content: {raw_content}")
        await send_msg(text="⚠️ **Erreur IA** : La réponse était mal formatée. Essaie de relancer.")
    except Exception as e:
        print(f"⚠️ Erreur : {e}")
        await send_msg(text=f"⚠️ Erreur technique IA ({e}).")

# --- 4. ÉVÉNEMENTS DISCORD & SYNC ---

@bot.event
async def on_ready():
    load_game_data(global_history, active_trees)
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ Slash Commands synchronisées : {len(synced)} commandes.")
    except Exception as e:
        print(f"❌ Erreur de sync : {e}")

    print(f'✅ Connecté en tant que {bot.user}')
    print(f'📡 LM Studio : {LM_STUDIO_URL}')

@bot.event
async def on_disconnect():
    save_game_data(global_history, active_trees)
    print("🔌 Sauvegarde effectuée.")

@bot.event
async def on_message(message):
    if message.author.bot: return

    if message.author.id in active_trees:
        tree = active_trees[message.author.id]
        if tree.current_node:
            if not message.content.startswith(("/", "!")):
                async with message.channel.typing():
                    
                    if tree.current_node.is_conclusion:
                        tree.current_node.is_conclusion = False
                    
                    await generate_next_step(message.channel, tree, message.content)
                return

    await bot.process_commands(message)

# --- 5. SLASH COMMANDS (Le Cœur du Changement) ---

@bot.tree.command(name="prompt", description="Démarrer une session d'Architecte de Prompt")
@app_commands.describe(idee="Votre idée de base (ex: Une affiche de concert)")
async def prompt(interaction: discord.Interaction, idee: str):
    await interaction.response.defer()
    
    global_history.add(f"/prompt {idee}", interaction.user.id)
    
    new_tree = DialogueTree()
    new_tree.root = TreeNode(question=f"Sujet initial : {idee}")
    new_tree.current_node = new_tree.root
    active_trees[interaction.user.id] = new_tree
    
    await interaction.followup.send(f"🏗️ **Architecte Local initialisé pour :** *{idee}*")
    
    await generate_next_step(interaction, new_tree, idee)


@bot.tree.command(name="reset", description="Effacer session ET historique (Remise à zéro)")
async def reset(interaction: discord.Interaction):
    deleted_session = False
    if interaction.user.id in active_trees:
        del active_trees[interaction.user.id]
        deleted_session = True

    global_history.remove_user_history(interaction.user.id)
    
    msg = "🗑️ **Grand Nettoyage effectué.**\n"
    msg += "- Session active : Effacée\n" if deleted_session else "- Session active : Aucune\n"
    msg += "- Historique des commandes : Vidé de la base de données."
    
    await interaction.response.send_message(msg, ephemeral=True)


@bot.tree.command(name="speak", description="Vérifier si un sujet a été abordé")
@app_commands.describe(sujet="Le mot clé à chercher")
async def speak(interaction: discord.Interaction, sujet: str):
    global_history.add(f"/speak {sujet}", interaction.user.id)
    
    if interaction.user.id in active_trees:
        tree = active_trees[interaction.user.id]
        found = tree.search_topic(sujet)
        if found:
             await interaction.response.send_message(f"✅ Oui, nous avons parlé de **{sujet}**.")
        else:
             await interaction.response.send_message(f"❌ Non, **{sujet}** n'a pas été mentionné.")
    else:
        await interaction.response.send_message("❌ Pas de session active.")


@bot.tree.command(name="history", description="Voir mon historique de commandes")
async def history(interaction: discord.Interaction):
    global_history.add("/history", interaction.user.id)
    
    cmds = global_history.get_all(interaction.user.id)
    if cmds:
        msg = "\n".join(cmds)
        if len(msg) > 1900: msg = msg[:1900] + "..."
        await interaction.response.send_message(f"📜 **Historique :**\n{msg}", ephemeral=True)
    else:
        await interaction.response.send_message("📭 Historique vide.", ephemeral=True)


@bot.tree.command(name="last", description="Afficher ma dernière commande")
async def last(interaction: discord.Interaction):
    cmds = global_history.get_all(interaction.user.id)
    if cmds:
        await interaction.response.send_message(f"🔙 **Dernière commande :** `{cmds[-1]}`")
    else:
        await interaction.response.send_message("📭 Vide.")


@bot.tree.command(name="clear_history", description="Vider tout mon historique")
async def clear_history_cmd(interaction: discord.Interaction):
    global_history.clear()
    await interaction.response.send_message("🗑️ Historique vidé.", ephemeral=True)


@bot.tree.command(name="export", description="Télécharger le prompt final en fichier texte")
async def export(interaction: discord.Interaction):
    global_history.add("/export", interaction.user.id)
    
    if interaction.user.id not in active_trees:
        return await interaction.response.send_message("❌ Rien à exporter.", ephemeral=True)
    
    tree = active_trees[interaction.user.id]
    if not tree.current_node.is_conclusion:
        return await interaction.response.send_message("⚠️ Discussion pas finie.", ephemeral=True)
    
    safe_name = sanitize_filename(f"prompt_{interaction.user.name}")
    filename = f"{safe_name}.txt"
    with open(filename, "w", encoding='utf-8') as f:
        f.write(tree.current_node.question)
        
    await interaction.response.send_message("📁 Fichier généré :", file=discord.File(filename))
    os.remove(filename)


@bot.tree.command(name="path", description="Visualiser l'arbre complet avec branches")
async def path(interaction: discord.Interaction):
    global_history.add("/path", interaction.user.id)
    
    if interaction.user.id not in active_trees:
        return await interaction.response.send_message("❌ Pas de session.", ephemeral=True)
        
    tree = active_trees[interaction.user.id]
    
    lines = []
    stack = [(tree.root, 0, "🌱")] if tree.root else []
    visited_ids = set()
    MAX_NODES = 1000

    while stack:
        node, level, prefix = stack.pop()
        
        if len(lines) > MAX_NODES: break
        if id(node) in visited_ids: continue
        visited_ids.add(id(node))

        indent = "   " * level
        
        position_marker = " 📍 VOUS ÊTES ICI" if node == tree.current_node else ""
        
        clean_q = node.question.replace('\n', ' ')
        if len(clean_q) > 60: clean_q = clean_q[:57] + "..."
        
        if node.cause_answer:
            clean_a = node.cause_answer.replace('\n', ' ')
            if len(clean_a) > 60: clean_a = clean_a[:57] + "..."
            lines.append(f"{indent}└─👤 USER: {clean_a}")
        
        lines.append(f"{indent}{prefix} BOT: {clean_q}{position_marker}")

        if node.right:
            stack.append((node.right, level + 1, "👉 [BRANCHE B]"))
        if node.left:
            stack.append((node.left, level + 1, "👇 [BRANCHE A]"))

    full_tree_str = "\n".join(lines)
    
    if len(full_tree_str) > 1900:
        with open("tree_view.txt", "w", encoding="utf-8") as f:
            f.write(full_tree_str)
        await interaction.response.send_message("🌳 Arbre complet (fichier joint) :", file=discord.File("tree_view.txt"))
        os.remove("tree_view.txt")
    else:
        await interaction.response.send_message(f"```text\n{full_tree_str}\n```")

@bot.tree.command(name="navigate", description="Se déplacer dans l'arbre (Haut, Bas-Gauche, Bas-Droite)")
@app_commands.describe(direction="Où aller ?", etapes="Nombre d'étapes (Défaut: 1)")
@app_commands.choices(direction=[
    app_commands.Choice(name="⬆️ Reculer (Vers la racine)", value="back"),
    app_commands.Choice(name="↙️ Avancer Gauche (Branche A / Principale)", value="left"),
    app_commands.Choice(name="↘️ Avancer Droite (Branche B / Alternative)", value="right")
])
async def navigate(interaction: discord.Interaction, direction: app_commands.Choice[str], etapes: int = 1):
    global_history.add(f"/navigate {direction.value} {etapes}", interaction.user.id)
    
    if interaction.user.id not in active_trees:
        return await interaction.response.send_message("❌ Pas de session active.", ephemeral=True)
    
    if etapes <= 0:
        return await interaction.response.send_message("⚠️ Le nombre d'étapes doit être au moins 1.", ephemeral=True)

    tree = active_trees[interaction.user.id]
    target_node = tree.current_node
    moved_count = 0
    blocked_reason = ""

    # --- Logique de déplacement ---
    for _ in range(etapes):
        
        if direction.value == "back":
            if target_node.parent:
                target_node = target_node.parent
                moved_count += 1
            else:
                blocked_reason = " (Racine atteinte)"
                break 
    
        elif direction.value == "left":
            if target_node.left:
                target_node = target_node.left
                moved_count += 1
            else:
                blocked_reason = " (Pas de branche à Gauche ici)"
                break

        elif direction.value == "right":
            if target_node.right:
                target_node = target_node.right
                moved_count += 1
            else:
                blocked_reason = " (Pas de branche à Droite ici)"
                break

    tree.current_node = target_node

    if moved_count == 0:
        await interaction.response.send_message(f"🛑 **Impossible de bouger.**{blocked_reason}", ephemeral=True)
    else:
        if direction.value == "back": arrow = "⬆️"
        elif direction.value == "left": arrow = "↙️"
        else: arrow = "↘️"

        msg = f"{arrow} **Déplacement effectué ({moved_count} étapes).**\n\n"
        
        if target_node.is_conclusion:
            preview = target_node.question.replace('\n', ' ')[:100]
            msg += f"🏁 **[CONCLUSION]** {preview}..."
        else:
            msg += f"🤖 **[QUESTION]** {target_node.question}"
            
            has_history = False
            
            if target_node.left:
                msg += f"\n\n↙️ **Réponse Gauche (Existante) :** `{target_node.left.cause_answer}`"
                has_history = True
                
            if target_node.right:
                msg += f"\n↘️ **Réponse Droite (Existante) :** `{target_node.right.cause_answer}`"
                has_history = True
                
            if not has_history:
                msg += f"\n\n✍️ **Aucune réponse enregistrée.** Tapez votre message."
            else:
                msg += f"\n\n✍️ *Tapez un nouveau message pour créer une nouvelle branche ou écraser la Gauche.*"

        await interaction.response.send_message(msg)

@bot.tree.command(name="status", description="Vérifier l'état du bot et de LM Studio")
async def status(interaction: discord.Interaction):
    active_users = len(active_trees)
    try:
        client.models.list()
        state = "🟢 Connecté à LM Studio"
    except:
        state = "🔴 LM Studio injoignable"
    
    await interaction.response.send_message(f"**État du Bot :**\n{state}\nSessions actives : {active_users}")

if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        print("🛑 Arrêt manuel détecté (Ctrl+C).")
    finally:
        save_game_data(global_history, active_trees)
        print("💾 Sauvegarde de fermeture effectuée.")