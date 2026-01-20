import discord
import os

# --- ÉTAT GLOBAL DU MODULE ---
# Mémoire pour stocker les liens des transferts en cours
# Structure : { channel_id: [ { "name": "nom_fichier", "url": "url_discord" }, ... ] }
active_transfers = {}

async def handle_nanodrop_file(message):
    """
    Gère les fichiers reçus via Webhook (NanoDrop).
    Collectionne les liens et génère le script final .bat.
    """
    channel_id = message.channel.id
    
    if channel_id not in active_transfers:
        active_transfers[channel_id] = []

    attachment = message.attachments[0]
    filename = attachment.filename
    url = attachment.url

    # CAS A : C'est une partie (.partXXX)
    if ".part" in filename and not filename.endswith(".txt"):
        active_transfers[channel_id].append({
            "name": filename,
            "url": url
        })
        print(f"📥 Partie reçue : {filename}")
        return
    
    # CAS B : C'est le fichier texte final (RECONSTRUIRE.bat.txt)
    if "RECONSTRUIRE.bat.txt" in filename:
        print("✅ Fin de transfert détectée. Génération du script...")
        
        parts = active_transfers[channel_id]
        if not parts:
            return

        parts.sort(key=lambda x: x["name"])

        try:
            base_name = parts[0]["name"].split(".compressed")[0]
        except IndexError:
            base_name = "fichier_reconstruit"
            
        zip_name = f"{base_name}.compressed.zip"

        # --- GÉNÉRATION DU SCRIPT BATCH ---
        bat_lines = [
            "@echo off",
            f"title NanoDrop Downloader - {base_name}",
            f"echo Telechargement de {base_name} en cours...",
            "echo Ne fermez pas cette fenetre.",
            "echo.",
            "mkdir \"NanoDrop_Temp\"",
            "cd \"NanoDrop_Temp\"",
            ""
        ]

        for i, part in enumerate(parts):
            bat_lines.append(f"echo Telechargement partie {i+1}/{len(parts)}...")
            bat_lines.append(f"curl -L -o \"{part['name']}\" \"{part['url']}\"")
        
        bat_lines.append("")
        bat_lines.append("echo Reconstruction du fichier...")
        
        first_part = parts[0]['name']
        bat_lines.append(f"copy /b \"{first_part}\" \"{zip_name}\"")
        
        for part in parts[1:]:
             bat_lines.append(f"copy /b \"{zip_name}\" + \"{part['name']}\" \"{zip_name}\"")

        bat_lines.append("")
        bat_lines.append("echo Extraction et Finalisation...")
        
        bat_lines.append(f"powershell -command \"Expand-Archive -Force '{zip_name}' .\"")
        
        bat_lines.append(f"move \"{base_name}\" ..\\")
        
        bat_lines.append("cd ..")
        bat_lines.append("rmdir /s /q \"NanoDrop_Temp\"")
        
        bat_lines.append("echo.")
        bat_lines.append("echo TELECHARGEMENT TERMINE ! Le fichier est pret.")
        bat_lines.append("pause")
        
        bat_lines.append("del \"%~f0\"") 

        final_script_name = f"TELECHARGER_{base_name}.bat"
        
        with open(final_script_name, "w", encoding="cp850") as f: 
            f.write("\n".join(bat_lines))

        await message.channel.send(
            content=f"🚀 **{base_name}** est prêt ! Cliquez ci-dessous pour lancer le téléchargement et la reconstruction automatique.",
            file=discord.File(final_script_name)
        )

        try:
            os.remove(final_script_name)
        except Exception as e:
            print(f"Erreur lors de la suppression du fichier temporaire: {e}")
            
        del active_transfers[channel_id]