import discord
import json
import logging
import urllib

from bs4 import BeautifulSoup
from datetime import datetime
from discord.ext import commands, tasks
from dotenv import load_dotenv
from os import environ
from random import randint
import time
from youtube_dl import YoutubeDL

logging.basicConfig(
    handlers=[logging.FileHandler("bot.log", 'w', 'utf-8')],
    level=logging.INFO
)

load_dotenv()
TOKEN = environ.get('TOKEN')
GAMERNET_GUILD = environ.get('GAMERNET_GUILD')
BALLS_CHANNEL = environ.get('BALLS_CHANNEL')
SOS_URL = environ.get('SOS_URL')

PREFIX = "#"
intents = discord.Intents.all()
client = commands.Bot(command_prefix=PREFIX, intents=intents)

global queues; queues = {}
perish_limit = 5

def perish_validate():
    try:
        with open("perish.json") as f:
            data = json.load(f)
    except Exception as e:
        print(e)
        with open("perish.json", "w") as f:
            json.dump({}, f)


@client.event
async def on_ready():
    activity = discord.Activity(
        type=discord.ActivityType.listening,
        name="Dua Lipa"
    )
    await client.change_presence(activity=activity)

    for guild in client.guilds:
        queues[guild.id] = []

    print('Ready')


def get_title(url: str) -> str:
    page = urllib.request.urlopen(url)
    html = BeautifulSoup(page.read(), "html.parser")
    return html.title.string[:len(html.title.string)-10]


def play_url(guild, url):
    YDL_OPTIONS = {
        'format': 'bestaudio/best',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'stream': True
    }
    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn'
    }
    
    logging.info("[play] Extracting info with YoutubeDL...")
    with YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(url, download=False)
    
    song = info['formats'][0]['url']
    guild.voice_client.play(discord.FFmpegPCMAudio(song, **FFMPEG_OPTIONS), after=lambda e: after_song(guild))
    guild.voice_client.is_playing()
    logging.info(f"[play] Playing {url}")


def after_song(guild):
    try:
        play_url(guild, queues[guild.id].pop(0))
    except IndexError:
        logging.info("[queue] No songs left in queue")


help_msg = discord.Embed(title="Commands", url=SOS_URL, description="```\njoin                Sosmosis joins the current channel\nleave               Sosmosis leave the current channel\nplay                Plays the following Youtube URL\npause               Pause music playback\nresume              Resume music playback\nstop                End current song\nskip                Start playing next song in the queue\nqueue               Display the current queue\nclearqueue          Remove all songs from the queue\n```", color=57599)


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith(PREFIX):
        if message.content.split()[0][1:].lower() == "help":
            await message.channel.send(embed=help_msg)

        elif message.content.split()[0][1:].lower() == "join":
            if message.author.voice:
                logging.info("[join] Joining voice channel")
                channel = message.author.voice.channel
                await channel.connect()
            else:
                await message.channel.send("You must be in a voice channel.")
        
        elif message.content.split()[0][1:].lower() in ["leave", "disconnect", "dc"]:
            if (message.guild.voice_client):
                logging.info("[leave] Leaving voice channel")
                await message.guild.voice_client.disconnect()
            else:
                await message.channel.send("I am not currently in a voice channel.")
        
        elif message.content.split()[0][1:].lower() == "play":
            vc = message.guild.voice_client
            if message.author.voice:
                if vc is None:
                    logging.info("[play] Joining voice channel")
                    channel = message.author.voice.channel
                    await channel.connect()
            else:
                await message.channel.send("You must be in a voice channel.")
                return
            
            if vc is not None:
                if message.guild.id in queues:
                    if vc.is_playing():
                        queues[message.guild.id].append(message.content.split()[1])
                        await message.channel.send("Added " + get_title(message.content.split()[1]) + " to the queue.")
                        logging.info(f"[play] Added {message.content.split()[1]} to the queue")
                    else:
                        play_url(message.guild, message.content.split()[1])
                else:
                    queues[message.guild.id] = [message.content.split()[1]]
                    await message.channel.send("Added " + get_title(message.content.split()[1]) + " to the queue.")
                    logging.info(f"[play] Added {message.content.split()[1]} to the queue")
            else:
                play_url(message.guild, message.content.split()[1])
            await message.add_reaction("⏯️")

        elif message.content[1:].lower() == "pause":
            message.guild.voice_client.pause()
            await message.add_reaction("⏸️")
        
        elif message.content[1:].lower() == "resume":
            message.guild.voice_client.resume()
        
        elif message.content[1:].lower() == "stop":
            logging.info("[stop] Stopping playback")
            queues[message.guild.id] = []
            message.guild.voice_client.stop()
            await message.add_reaction("⏹️")
        
        elif message.content[1:].lower() == "skip":
            logging.info("[skip] Skipping current song")
            message.guild.voice_client.stop()
        
        elif message.content[1:].lower() in ["queue", "q", "que"]:
            # Optimise by storing name in queue with URL when initially queued
            msg = ""
            if len(queues[message.guild.id]) > 0:
                for i in range(0, len(queues[message.guild.id])):
                    msg += str(i+1) + ". " + get_title(queues[message.guild.id][i]) + "\n"
            else:
                msg = "The queue is currently empty"
            await message.channel.send(msg)
        
        elif message.content[1:].lower() in ["clearqueue", "cq"]:
            queues[message.guild.id] = []
            logging.info(f"[clearq] Cleared queue for {message.guild.id}")

        elif message.content[1:].lower() in "remove":
            pass

        elif message.content[1:].lower() == "playnext":
            pass
        
        elif message.content[1:].lower() == "volume":
            pass

        elif message.content.split()[0][1:].lower() == "ban":
            await message.channel.send("👍")
        
        elif message.content[1:].lower() == "perish":
            perish_validate()
            with open("perish.json") as f:
                data = json.load(f)
            try:
                remaining = data[str(message.author.id)]
                if remaining is not 0:
                    data[str(message.author.id)] -= 1
            except KeyError as e:
                print(e)
                remaining = perish_limit - 1
                data[str(message.author.id)] = remaining
            finally:
                print(data)
                with open("perish.json", "w") as f:
                    json.dump(data, f)

            if remaining != 0:
                print("Perish")
                channel = await client.fetch_channel(BALLS_CHANNEL)
                if len(channel.members) > 0:
                    member = channel.members[randint(0, len(channel.members)-1)]
                    # t = 5
                    # while t:
                    #     await message.channel.send(f"Perish: {t}")
                    #     time.sleep(1)
                    #     t -= 1
                    # await message.channel.send(f"Perish: Wagwan {member.nick}")
                    # time.sleep(0.5)
                    # await member.move_to(None)
                else:
                    await message.channel.send("Perish: No members in voice channel")
            else:
                if message.author.voice is not None:
                    await message.channel.send(f"Perish: Wagwan {message.author.nick}")
                    time.sleep(0.5)
                    await message.author.move_to(None)
                else:
                    await message.channel.send("Perish: You may not perish today")
        
        elif message.content.split()[0][1:].lower() in ["select", "downitfresher"]:
            try:
                t = 5
                while t:
                    await message.channel.send(
                        f"{message.content.split()[0][1:].lower().capitalize()}: {t}"
                    )
                    time.sleep(1)
                    t -= 1
                text = message.content.split()[randint(1, len(message.content.split())-1)]
                await message.channel.send(
                    f"{message.content.split()[0][1:].lower().capitalize()}: {text}"
                )
            except:
                pass

    elif "wag" in message.content.lower().split(" "):
        await message.channel.send("wag")
    
    elif "wagwan" in message.content.lower().split(" "):
        await message.channel.send("wagwan")


client.run(TOKEN)
