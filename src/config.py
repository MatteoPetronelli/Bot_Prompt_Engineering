import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
LM_STUDIO_URL = os.getenv('LM_STUDIO_URL', "http://localhost:1234/v1")

if not DISCORD_TOKEN:
    raise ValueError("ERREUR : Token Discord manquant.")

client = AsyncOpenAI(base_url=LM_STUDIO_URL, api_key="lm-studio")

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

active_trees = {}