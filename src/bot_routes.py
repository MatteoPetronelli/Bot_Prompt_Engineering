import discord
from discord import app_commands
from config import bot, active_trees, client, LM_STUDIO_URL
from database import *
from utils import sanitize_filename
from data_structures import DialogueTree, TreeNode
from ai_logic import generate_next_step
from ui import TreeControlView
import os

# --- ÉVÉNEMENTS DISCORD & SYNC ---

@bot.event
async def on_ready():
    init_db()
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ Slash Commands synchronisées : {len(synced)} commandes.")
    except Exception as e:
        print(f"❌ Erreur de sync : {e}")

    print(f'✅ Connecté en tant que {bot.user}')
    print(f'📡 LM Studio : {LM_STUDIO_URL}')

@bot.event
async def on_disconnect():
    print("🔌 Déconnexion en cours...")
    for user_id, tree in active_trees.items():
        save_session(user_id, tree)
    print("💾 Toutes les sessions ont été sauvegardées en DB.")

@bot.event
async def on_message(message):
    if message.author.bot: return

    if message.author.id not in active_trees:
        data = load_session(message.author.id)
        if data:
            active_trees[message.author.id] = DialogueTree.from_dict(data)

    if message.author.id in active_trees:
        tree = active_trees[message.author.id]
        if tree.current_node:
            if not message.content.startswith(("/", "!")):
                async with message.channel.typing():
                    
                    if tree.current_node.is_conclusion:
                        tree.current_node.is_conclusion = False
                    
                    await generate_next_step(message, tree, message.content)
                return

    await bot.process_commands(message)

# --- SLASH COMMANDS ---

@bot.tree.command(name="prompt", description="Démarrer une session d'Architecte de Prompt")
@app_commands.describe(idee="Votre idée de base (ex: Une affiche de concert)")
async def prompt(interaction: discord.Interaction, idee: str):
    if interaction.user.id not in active_trees:
        data = load_session(interaction.user.id)
        if data:
            active_trees[interaction.user.id] = DialogueTree.from_dict(data)

    new_tree = DialogueTree()
    new_tree.root = TreeNode(question=f"Sujet initial : {idee}")
    new_tree.current_node = new_tree.root
    active_trees[interaction.user.id] = new_tree
    
    await interaction.response.defer()
    add_history(interaction.user.id, f"/prompt {idee}")

    view = TreeControlView(new_tree, interaction.user.id)
    
    await interaction.followup.send(f"🏗️ **Architecte Local initialisé pour :** *{idee}*", view=view)
    await generate_next_step(interaction, new_tree, idee)

@bot.tree.command(name="reset", description="Effacer session ET historique (Remise à zéro)")
async def reset(interaction: discord.Interaction):
    if interaction.user.id in active_trees:
        del active_trees[interaction.user.id]
    
    delete_session(interaction.user.id)
    clear_user_history(interaction.user.id)
    
    await interaction.response.send_message("🗑️ **Grand Nettoyage effectué (RAM & SQL).**", ephemeral=True)


@bot.tree.command(name="speak", description="Vérifier si un sujet a été abordé")
@app_commands.describe(sujet="Le mot clé à chercher")
async def speak(interaction: discord.Interaction, sujet: str):
    add_history(interaction.user.id, f"/speak {sujet}")

    if interaction.user.id not in active_trees:
        data = load_session(interaction.user.id)
        if data:
            active_trees[interaction.user.id] = DialogueTree.from_dict(data)
    
    if interaction.user.id in active_trees:
        tree = active_trees[interaction.user.id]
        if tree.search_topic(sujet):
             await interaction.response.send_message(f"✅ Oui, nous avons parlé de **{sujet}**.")
        else:
             await interaction.response.send_message(f"❌ Non, **{sujet}** n'a pas été mentionné.")
    else:
        await interaction.response.send_message("❌ Pas de session active.")


@bot.tree.command(name="history", description="Voir mon historique de commandes")
async def history(interaction: discord.Interaction):
    add_history(interaction.user.id, "/history")

    cmds = get_user_history(interaction.user.id)
    msg = "\n".join(cmds) if cmds else "Historique vide."
    if len(msg) > 1900: msg = msg[:1900] + "..."
    
    await interaction.response.send_message(f"📜 **Historique :**\n{msg}", ephemeral=True)


@bot.tree.command(name="last", description="Afficher ma dernière commande")
async def last(interaction: discord.Interaction):
    cmd = get_last_command(interaction.user.id)
    if cmd:
        await interaction.response.send_message(f"🔙 **Dernière commande :** `{cmd}`")
    else:
        await interaction.response.send_message("📭 Vide.")


@bot.tree.command(name="clear_history", description="Vider tout mon historique")
async def clear_history_cmd(interaction: discord.Interaction):
    clear_user_history(interaction.user.id)
    await interaction.response.send_message("🗑️ Historique vidé.", ephemeral=True)


@bot.tree.command(name="export", description="Télécharger le prompt final en fichier texte")
async def export(interaction: discord.Interaction):
    add_history(interaction.user.id, "/export")
    
    if interaction.user.id not in active_trees:
        data = load_session(interaction.user.id)
        if data:
            active_trees[interaction.user.id] = DialogueTree.from_dict(data)
    
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

@bot.tree.command(name="path", description="Visualiser l'arbre graphiquement")
async def path(interaction: discord.Interaction):
    add_history(interaction.user.id, "/path")

    if interaction.user.id not in active_trees:
        data = load_session(interaction.user.id)
        if data: active_trees[interaction.user.id] = DialogueTree.from_dict(data)
        else: return await interaction.response.send_message("❌ Pas de session.", ephemeral=True)

    tree = active_trees[interaction.user.id]
    
    await interaction.response.defer()
    filename_base = f"tree_{interaction.user.id}"
    
    image_path = tree.generate_graph_image(filename_base)

    view = TreeControlView(tree, interaction.user.id)
    
    if image_path and os.path.exists(image_path):
        file = discord.File(image_path, filename="tree_visualization.png")
        embed = discord.Embed(title="🗺️ Carte de votre discussion", color=0x3498db)
        embed.set_image(url="attachment://tree_visualization.png")
        embed.set_footer(text="📍 Rouge = Votre position actuelle | 🟦 Bleu = Branche A | 🟧 Orange = Branche B")
        
        await interaction.followup.send(embed=embed, file=file, view=view)
        
        os.remove(image_path)
    else:
        await interaction.followup.send("⚠️ Impossible de générer l'image (Graphviz manquant ?), mais voici les commandes :", view=view)

@bot.tree.command(name="navigate", description="Se déplacer dans l'arbre (Haut, Bas-Gauche, Bas-Droite)")
@app_commands.describe(direction="Où aller ?", etapes="Nombre d'étapes (Défaut: 1)")
@app_commands.choices(direction=[
    app_commands.Choice(name="⬆️ Reculer (Vers la racine)", value="back"),
    app_commands.Choice(name="↙️ Avancer Gauche (Branche A / Principale)", value="left"),
    app_commands.Choice(name="↘️ Avancer Droite (Branche B / Alternative)", value="right")
])
async def navigate(interaction: discord.Interaction, direction: app_commands.Choice[str], etapes: int = 1):
    add_history(interaction.user.id, f"/navigate {direction.value} {etapes}")
    
    if interaction.user.id not in active_trees:
        data = load_session(interaction.user.id)
        if data:
            active_trees[interaction.user.id] = DialogueTree.from_dict(data)
        else:
            return await interaction.response.send_message("❌ Pas de session.", ephemeral=True)
    
    if etapes <= 0:
        return await interaction.response.send_message("⚠️ Etapes > 0 requises.", ephemeral=True)

    tree = active_trees[interaction.user.id]
    target_node = tree.current_node
    moved_count = 0
    blocked_reason = ""

    for _ in range(etapes):
        if direction.value == "back":
            if target_node.parent:
                target_node = target_node.parent
                moved_count += 1
            else:
                blocked_reason = " (Racine)"
                break 
        elif direction.value == "left":
            if target_node.left:
                target_node = target_node.left
                moved_count += 1
            else:
                blocked_reason = " (Fin Gauche)"
                break
        elif direction.value == "right":
            if target_node.right:
                target_node = target_node.right
                moved_count += 1
            else:
                blocked_reason = " (Fin Droite)"
                break

    tree.current_node = target_node
    
    # SAUVEGARDE DB APRES NAVIGATION
    save_session(interaction.user.id, tree)

    if moved_count == 0:
        await interaction.response.send_message(f"🛑 **Stop.**{blocked_reason}", ephemeral=True)
    else:
        arrow = "⬆️" if direction.value == "back" else "↙️" if direction.value == "left" else "↘️"
        msg = f"{arrow} **Déplacement : {moved_count} pas.**\n\n"
        
        if target_node.is_conclusion:
            preview = target_node.question.replace('\n', ' ')[:100]
            msg += f"🏁 **[FIN]** {preview}..."
        else:
            msg += f"🤖 **[QUESTION]** {target_node.question}"
            
            has_history = False
            if target_node.left:
                msg += f"\n\n↙️ **Réponse A :** `{target_node.left.cause_answer}`"
                has_history = True
            if target_node.right:
                msg += f"\n↘️ **Réponse B :** `{target_node.right.cause_answer}`"
                has_history = True
                
            if not has_history:
                msg += f"\n\n✍️ **En attente de réponse...**"
            else:
                msg += f"\n\n✍️ *Tapez pour créer une nouvelle branche ou écraser A.*"

        await interaction.response.send_message(msg)

@bot.tree.command(name="save", description="Sauvegarder le prompt actuel dans votre bibliothèque")
@app_commands.describe(nom="Nom unique pour retrouver ce prompt")
async def save(interaction: discord.Interaction, nom: str):
    add_history(interaction.user.id, f"/save {nom}")
    
    if interaction.user.id not in active_trees:
        return await interaction.response.send_message("❌ Pas de session active à sauvegarder.", ephemeral=True)
    
    tree = active_trees[interaction.user.id]
    content_to_save = tree.current_node.question
    
    safe_name = sanitize_filename(nom)
    
    success = save_prompt_to_library(interaction.user.id, safe_name, content_to_save)
    
    if success:
        await interaction.response.send_message(f"💾 Prompt sauvegardé sous : **{safe_name}**", ephemeral=True)
    else:
        await interaction.response.send_message(f"⚠️ Le nom **{safe_name}** existe déjà. Choisissez-en un autre.", ephemeral=True)

async def prompt_name_autocomplete(interaction: discord.Interaction, current: str):
    names = get_all_prompts_names(interaction.user.id)
    return [
        app_commands.Choice(name=name, value=name)
        for name in names if current.lower() in name.lower()
    ][:25]


@bot.tree.command(name="load", description="Afficher un prompt sauvegardé")
@app_commands.autocomplete(nom=prompt_name_autocomplete)
async def load(interaction: discord.Interaction, nom: str):
    add_history(interaction.user.id, f"/load {nom}")
    
    content = get_prompt_content(interaction.user.id, nom)
    
    if content:
        if len(content) > 1900:
            filename = f"{nom}.md"
            with open(filename, "w", encoding="utf-8") as f: f.write(content)
            await interaction.response.send_message(f"📂 **Prompt : {nom}**", file=discord.File(filename))
            import os
            os.remove(filename)
        else:
            await interaction.response.send_message(f"📂 **Prompt : {nom}**\n```markdown\n{content}\n```")
    else:
        await interaction.response.send_message(f"❌ Prompt introuvable : {nom}", ephemeral=True)


@bot.tree.command(name="delete_prompt", description="Supprimer un prompt de la bibliothèque")
@app_commands.autocomplete(nom=prompt_name_autocomplete)
async def delete_prompt(interaction: discord.Interaction, nom: str):
    success = delete_prompt_from_library(interaction.user.id, nom)
    if success:
        await interaction.response.send_message(f"🗑️ Prompt **{nom}** supprimé.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Impossible de trouver **{nom}**.", ephemeral=True)

@bot.tree.command(name="library", description="Lister tous mes prompts sauvegardés")
async def library(interaction: discord.Interaction):
    names = get_all_prompts_names(interaction.user.id)
    if not names:
        await interaction.response.send_message("📭 Votre bibliothèque est vide.", ephemeral=True)
    else:
        liste = "\n".join([f"- {name}" for name in names])
        await interaction.response.send_message(f"📚 **Votre Bibliothèque :**\n{liste}", ephemeral=True)

@bot.tree.command(name="status", description="Vérifier l'état du bot et de LM Studio")
async def status(interaction: discord.Interaction):
    active_users = len(active_trees)
    try:
        client.models.list()
        state = "🟢 Connecté à LM Studio"
    except:
        state = "🔴 LM Studio injoignable"
    
    await interaction.response.send_message(f"**État du Bot :**\n{state}\nSessions actives : {active_users}")
