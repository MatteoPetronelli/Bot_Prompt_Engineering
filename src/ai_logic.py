import discord
import json
import os
from config import client
from database import save_session
from data_structures import TreeNode
from ui import TreeControlView

async def generate_next_step(interaction_or_ctx, tree, user_input):
    """
    Gère la logique IA. 
    Accepte soit un Context (message texte) soit une Interaction (slash command).
    """

    if isinstance(interaction_or_ctx, discord.Interaction):
        current_user_id = interaction_or_ctx.user.id
    elif isinstance(interaction_or_ctx, discord.Message):
        current_user_id = interaction_or_ctx.author.id
    else:
        current_user_id = interaction_or_ctx.author.id
    
    async def send_msg(text=None, embed=None, file=None, view=None):
        params = {}
        if text: params['content'] = text
        if embed: params['embed'] = embed
        if file: params['file'] = file
        if view: params['view'] = view

        if isinstance(interaction_or_ctx, discord.Interaction):
            # Cas Slash Command
            try:
                if interaction_or_ctx.response.is_done():
                    await interaction_or_ctx.followup.send(**params)
                else:
                    await interaction_or_ctx.response.send_message(**params)
            except:
                await interaction_or_ctx.followup.send(**params)
        
        elif isinstance(interaction_or_ctx, discord.Message):
            await interaction_or_ctx.channel.send(**params)
            
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
            buttons_view = TreeControlView(tree, current_user_id)
            await send_msg(text=f"🤖 **Question :** {ai_data['content']}{branch_msg}", view=buttons_view)
            
        elif ai_data['type'] == 'conclusion':
            new_node.is_conclusion = True
            embed = discord.Embed(title="✨ Prompt Final", description=ai_data['content'][:4000], color=0x00ff00)
            buttons_view = TreeControlView(tree, current_user_id)
            await send_msg(embed=embed, view=buttons_view)
            await send_msg(text=f"Utilisez `/export` pour télécharger.{branch_msg}")

    except json.JSONDecodeError:
        print(f"JSON ERROR content: {raw_content}")
        await send_msg(text="⚠️ **Erreur IA** : La réponse était mal formatée. Essaie de relancer.")
    except Exception as e:
        print(f"⚠️ Erreur : {e}")
        await send_msg(text=f"⚠️ Erreur technique IA ({e}).")
    save_session(current_user_id, tree)