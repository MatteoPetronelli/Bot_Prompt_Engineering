import discord
from database import save_session
from utils import sanitize_filename
import os

class ResponseModal(discord.ui.Modal, title="Votre Réponse"):
    reponse = discord.ui.TextInput(
        label="Écrivez votre réponse :",
        style=discord.TextStyle.paragraph,
        placeholder="Ex: Je veux un style Cyberpunk...",
        required=True,
        max_length=1000
    )

    def __init__(self, tree):
        super().__init__()
        self.tree = tree

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        if self.tree.current_node.is_conclusion:
            self.tree.current_node.is_conclusion = False

        from ai_logic import generate_next_step
        
        await generate_next_step(interaction, self.tree, self.reponse.value)


class TreeControlView(discord.ui.View):
    def __init__(self, tree, user_id):
        super().__init__(timeout=None)
        self.tree = tree
        self.user_id = user_id

    @discord.ui.button(label="Retour", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id: return
        
        if self.tree.current_node.parent:
            self.tree.current_node = self.tree.current_node.parent
            
            save_session(self.user_id, self.tree)
            
            await interaction.response.send_message(
                f"⏪ **Retour en arrière.**\nQuestion : {self.tree.current_node.question}",
                view=TreeControlView(self.tree, self.user_id)
            )
        else:
            await interaction.response.send_message("🛑 Vous êtes déjà à la racine !", ephemeral=True)

    @discord.ui.button(label="Répondre", style=discord.ButtonStyle.primary, emoji="📝")
    async def answer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id: return
        await interaction.response.send_modal(ResponseModal(self.tree))

    @discord.ui.button(label="Export", style=discord.ButtonStyle.success, emoji="💾")
    async def export_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id: return
        
        if not self.tree.current_node.is_conclusion:
            return await interaction.response.send_message("⚠️ Discussion pas finie.", ephemeral=True)
            
        safe_name = sanitize_filename(f"prompt_{interaction.user.name}")
        filename = f"{safe_name}.txt"
        with open(filename, "w", encoding='utf-8') as f:
            f.write(self.tree.current_node.question)
        await interaction.response.send_message("📁 Fichier généré :", file=discord.File(filename), ephemeral=True)
        os.remove(filename)

    @discord.ui.button(label="Plan", style=discord.ButtonStyle.gray, emoji="📍")
    async def path_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id: return
        
        full_tree_str = self.tree.get_visualization()
        
        if len(full_tree_str) > 1900:
            filename = "tree_view.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(full_tree_str)
            
            await interaction.response.send_message(
                "🌳 **Arbre complet (fichier joint) :**", 
                file=discord.File(filename), 
                ephemeral=True
            )
            import os
            os.remove(filename)
        else:
            await interaction.response.send_message(f"```text\n{full_tree_str}\n```", ephemeral=True)