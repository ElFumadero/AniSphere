import discord
from discord.ext import commands, tasks
import aiohttp
import json
import os

# Configuration
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  
bot = commands.Bot(command_prefix='!', intents=intents)

ANILIST_API_URL = "https://graphql.anilist.co"
ANIME_TRACK_FILE = "animes_suivis.json"
DEVELOPPEUR = "El Fumadero"

# Chargement des animes suivis depuis le fichier
animes_suivis = {}

if os.path.exists(ANIME_TRACK_FILE):
    with open(ANIME_TRACK_FILE, "r") as file:
        animes_suivis = json.load(file)

@bot.event
async def on_ready():
    print(f'Connecté en tant que {bot.user.name} (Développé par {DEVELOPPEUR}) ')
    check_new_episodes.start()

@tasks.loop(hours=24)
async def check_new_episodes():
    async with aiohttp.ClientSession() as session:
        for user_id, animes in animes_suivis.items():
            for anime in animes:
                query = '''
                query ($id: Int) {
                  Media (id: $id, type: ANIME) {
                    nextAiringEpisode {
                      airingAt
                      timeUntilAiring
                      episode
                    }
                  }
                }
                '''
                variables = {
                    'id': anime['id']
                }
                async with session.post(ANILIST_API_URL, json={'query': query, 'variables': variables}) as response:
                    data = await response.json()
                    next_episode = data['data']['Media']['nextAiringEpisode']
                    if next_episode and next_episode['timeUntilAiring'] < 86400:  # Moins de 24 heures
                        user = await bot.fetch_user(user_id)
                        await user.send(f"L'épisode {next_episode['episode']} de {anime['title']} sort dans moins de 24 heures!")

@bot.command(name="ping")
async def ping(ctx):
    await ctx.send(f"Pong! (Développé par {DEVELOPPEUR})")

@bot.command(name="anime")
async def get_anime(ctx, *, recherche: str):
    query = '''
    query ($search: String) {
      Media (search: $search, type: ANIME) {
        id
        title {
          romaji
          english
          native
        }
        description
        episodes
        status
        nextAiringEpisode {
          airingAt
          timeUntilAiring
          episode
        }
      }
    }
    '''
    variables = {
        'search': recherche
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(ANILIST_API_URL, json={'query': query, 'variables': variables}) as response:
            data = await response.json()
            if "errors" in data:
                await ctx.send("Erreur lors de la recherche de l'anime.")
                return

            media = data['data']['Media']
            titre = media['title']['romaji'] or media['title']['english'] or media['title']['native']
            description = media['description']
            episodes = media['episodes']
            status = media['status']
            prochain_episode = media['nextAiringEpisode']
            
            if prochain_episode:
                prochain_episode_info = f"Prochain épisode : {prochain_episode['episode']} dans {prochain_episode['timeUntilAiring']} secondes."
            else:
                prochain_episode_info = "Pas d'épisodes à venir."

            embed = discord.Embed(title=titre, description=description)
            embed.add_field(name="Épisodes", value=episodes)
            embed.add_field(name="Statut", value=status)
            embed.add_field(name="Prochain épisode", value=prochain_episode_info)
            await ctx.send(embed=embed)

@bot.command(name="recommande")
async def recommend_anime(ctx, *, genre: str):
    query = '''
    query ($genre: String) {
      Page(page: 1, perPage: 5) {
        media(genre: $genre, type: ANIME, sort: POPULARITY_DESC) {
          id
          title {
            romaji
            english
            native
          }
          description
        }
      }
    }
    '''
    variables = {
        'genre': genre
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(ANILIST_API_URL, json={'query': query, 'variables': variables}) as response:
            data = await response.json()
            media_list = data['data']['Page']['media']
            recommandations = []
            for media in media_list:  # Obtenir les 5 meilleures recommandations
                titre = media['title']['romaji'] or media['title']['english'] or media['title']['native']
                recommandations.append(titre)

            embed = discord.Embed(title=f"Top 5 des recommandations {genre}")
            for idx, titre in enumerate(recommandations, 1):
                embed.add_field(name=f"{idx}", value=titre, inline=False)
            await ctx.send(embed=embed)


@bot.command(name="suivre")
async def suivre_anime(ctx, *, recherche: str):
    query = '''
    query ($search: String) {
      Media (search: $search, type: ANIME) {
        id
        title {
          romaji
          english
          native
        }
      }
    }
    '''
    variables = {
        'search': recherche
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(ANILIST_API_URL, json={'query': query, 'variables': variables}) as response:
            data = await response.json()
            media = data['data']['Media']
            titre = media['title']['romaji'] or media['title']['english'] or media['title']['native']
            if str(ctx.author.id) not in animes_suivis:
                animes_suivis[str(ctx.author.id)] = []
            animes_suivis[str(ctx.author.id)].append({'id': media['id'], 'title': titre})

            with open(ANIME_TRACK_FILE, "w") as file:
                json.dump(animes_suivis, file)

            await ctx.send(f"Vous suivez maintenant {titre}.")

@bot.command(name="stop_suivre")
async def stop_suivre_anime(ctx, *, recherche: str):
    user_id = str(ctx.author.id)
    if user_id in animes_suivis:
        animes_suivis[user_id] = [anime for anime in animes_suivis[user_id] if anime['title'].lower() != recherche.lower()]
        with open(ANIME_TRACK_FILE, "w") as file:
            json.dump(animes_suivis, file)
        await ctx.send(f"Vous ne suivez plus {recherche}.")
    else:
        await ctx.send("Vous ne suivez pas cet anime.")

@bot.command(name="manga")
async def get_manga(ctx, *, recherche: str):
    query = '''
    query ($search: String) {
      Media (search: $search, type: MANGA) {
        id
        title {
          romaji
          english
          native
        }
        description
        chapters
        status
      }
    }
    '''
    variables = {
        'search': recherche
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(ANILIST_API_URL, json={'query': query, 'variables': variables}) as response:
            data = await response.json()
            media = data['data']['Media']
            titre = media['title']['romaji'] or media['title']['english'] or media['title']['native']
            description = media['description']
            chapitres = media['chapters']
            status = media['status']

            embed = discord.Embed(title=titre, description=description)
            embed.add_field(name="Chapitres", value=chapitres)
            embed.add_field(name="Statut", value=status)
            await ctx.send(embed=embed)

@bot.command(name="aide")
async def aide(ctx):
    embed = discord.Embed(title="Commandes du Bot", description="Voici la liste des commandes disponibles:")
    embed.add_field(name="!ping", value="Vérifie si le bot est en ligne", inline=False)
    embed.add_field(name="!anime <nom>", value="Recherche un anime par son nom", inline=False)
    embed.add_field(name="!recommande <genre>", value="Recommande des animes basés sur un genre", inline=False)
    embed.add_field(name="!suivre <nom>", value="Suivre un anime pour les notifications d'épisodes", inline=False)
    embed.add_field(name="!stop_suivre <nom>", value="Arrête de suivre un anime", inline=False)
    embed.add_field(name="!manga <nom>", value="Recherche un manga par son nom", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="credits")
async def developpeur(ctx):
    await ctx.send(f"Ce bot a été dev par {DEVELOPPEUR}.")
            

# Token Du Bot
bot.run('TOKEN_DU_BOT')
