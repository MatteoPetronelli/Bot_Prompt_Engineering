# Bot_Prompt_Engineering

**Présentation**
- **But**: Projet de bot Discord orienté "Prompt Engineering". Le code Python se trouve dans le dossier `src` et contient les scripts principaux du bot.

**Structure du dépôt**
- **`src`**: Contient tous les scripts Python du projet (logique du bot, utilitaires, structures de données, point d'entrée `main.py`).
- **`data`**: Emplacement local pour les données sauvegardées par le bot (ex. `bot_data.json`). Ce dossier est essentiel pour le fonctionnement local mais n'est pas suivi par Git (voir section *Données & sécurité*).
- **`.env`**: Fichier local contenant les variables d'environnement sensibles (token Discord, URL du serveur LM Studio). **Ne pas** commiter ce fichier ni y inscrire de jeton public.
- **`requirements.txt`**: Liste des dépendances Python requises pour exécuter le projet.

**Configuration**
- **Variables d'environnement**: Créez un fichier `.env` à la racine (non commité) et définissez au minimum :

```
DISCORD_TOKEN=your_discord_token_here
LMSTUDIO_URL=http://<lm-studio-host>:<port>/v1
```

- **Important**: N'insérez jamais votre `DISCORD_TOKEN` dans le dépôt ou dans le `README`. L'URL de LM Studio peut changer si le serveur est arrêté/redémarré ; mettez à jour la valeur dans `.env` quand nécessaire.

- **Faciliter l'installation**: Un fichier `.env.template` est fourni à la racine. Pour créer votre fichier `.env`, copiez simplement le template et remplissez les valeurs.

Remplissez ensuite `DISCORD_TOKEN` et `LM_STUDIO_URL` dans le fichier `.env` avant d'exécuter le bot.

**Données & sécurité**
- **`data/`**: Le dossier sert à stocker les données sauvegardées localement. Il contient une entrée `.keep` pour maintenir la structure et des fichiers JSON (ex. `bot_data.json`).
- **Exclusion Git**: Le fichier `.gitignore` du projet exclut `data/*.json`, `.env`, et autres fichiers sensibles. Cela permet de conserver des données et clés privées hors du dépôt public.
- **Sauvegarde**: Si vous souhaitez versionner certaines données, utilisez un stockage privé ou chiffré — évitez de stocker des tokens en clair.

**Prérequis & installation**
- **Python**: Installez Python 3.10+.
- **Environnement virtuel (recommandé)**:

PowerShell:
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Démarrage**
- Après avoir configuré le `.env` et installé les dépendances, lancez le bot :

```
python -m src.main
```

ou (depuis la racine)

```
python src/main.py
```

**Documentation détaillée**
- La documentation complète (explication des commandes et captures d'écran) se trouve dans `doc/doc.md`.
- Les images utilisées dans la documentation sont stockées dans `doc/img/`.
