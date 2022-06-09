import discord
import json
import logging
import urllib

from bs4 import BeautifulSoup
from datetime import datetime
from discord.ext import commands, tasks
from dotenv import load_dotenv
from os import environ
from random import randint, sample
import time
from youtube_dl import YoutubeDL

import requests
import re

logging.basicConfig(
    handlers=[logging.FileHandler("bot.log", 'w', 'utf-8')],
    level=logging.INFO
)

load_dotenv()
TOKEN = environ.get('TOKEN')
BALLS_CHANNEL_ID = environ.get('BALLS_CHANNEL_ID')
KITCHEN_CHANNEL_ID = environ.get('KITCHEN_CHANNEL_ID')
TEST_CHANNEL_ID = environ.get('TEST_CHANNEL_ID')

SOS_URL = environ.get('SOS_URL')

PREFIX = "#"
intents = discord.Intents.all()
client = commands.Bot(command_prefix=PREFIX, intents=intents)

global queues; queues = {}
perish_limit = 5
traditional_limit = 1

def update_user_remaining(file_name, id, command, limit):
    try:
        with open(file_name) as f:
            data = json.load(f)
    except Exception as e:
        with open(file_name, "w") as f:
            json.dump({}, f)

    with open(file_name) as f:
        data = json.load(f)
    try:
        remaining = data[id][command]
        if remaining != 0:
            data[id][command] -= 1
    except KeyError as e:
        remaining = limit - 1
        try:
            data[id][command] = remaining
        except KeyError as e:
            data[id] = { command: remaining }
    finally:
        with open(file_name, "w") as f:
            json.dump(data, f)
    return remaining


@client.event
async def on_ready():
    activity = discord.Activity(
        type=discord.ActivityType.listening,
        name="Dua Lipa"
    )
    await client.change_presence(activity=activity)

    for guild in client.guilds:
        queues[guild.id] = []
    
    test_chan = await client.fetch_channel(TEST_CHANNEL_ID)
    await test_chan.send("Ready")


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


@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith(PREFIX):
        if message.content.split()[0][1:].lower() == "help":
            help_msg = discord.Embed(title="Commands", url=SOS_URL, description="```\njoin                Sosmosis joins the current channel\nleave               Sosmosis leave the current channel\nplay                Plays the following Youtube URL\npause               Pause music playback\nresume              Resume music playback\nstop                End current song\nskip                Start playing next song in the queue\nqueue               Display the current queue\nclearqueue          Remove all songs from the queue\n```", color=57599)
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
            remaining = update_user_remaining(
                "user_data.json", str(message.author.id), "perish", perish_limit
                )
            if remaining != 0:
                channel = await client.fetch_channel(BALLS_CHANNEL_ID)
                if len(channel.members) > 0:
                    member = channel.members[randint(0, len(channel.members)-1)]
                    t = 5
                    while t:
                        await message.channel.send(f"Perish: {t}")
                        time.sleep(1)
                        t -= 1
                    nick = member.nick if member.nick is not None else member.name;
                    await message.channel.send(f"Perish: Wagwan {nick}")
                    time.sleep(0.5)
                    await member.move_to(None)
                else:
                    await message.channel.send("Perish: No members in voice channel")
            else:
                if message.author.voice is not None:
                    nick = message.author.nick if message.author.nick is not None else message.author.name;
                    await message.channel.send(f"Perish: Wagwan {nick}")
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
        
        elif message.content[1:].lower() in ["traditional", "woman", "makemeasandwich"]:
            remaining = update_user_remaining(
                "user_data.json", str(message.author.id), "traditional", traditional_limit
                )
            if remaining != 0:
                og_channel = await client.fetch_channel(BALLS_CHANNEL_ID)
                new_channel = await client.fetch_channel(KITCHEN_CHANNEL_ID)
                if len(og_channel.members) > 0:
                    t = 5
                    while t:
                        await message.channel.send(f"Traditional: {t}")
                        time.sleep(1)
                        t -= 1
                    selected_members = sample(og_channel.members, round(len(og_channel.members)/2))
                    for member in selected_members:
                        try:
                            time.sleep(1)
                            member_name = member.nick if member.nick is not None else member.name
                            await message.channel.send(f"Traditional: Wagwan {member_name}")
                            time.sleep(0.5)
                            await member.move_to(new_channel)
                        except Exception as e:
                            print(e)
                else:
                    await message.channel.send("Traditional: No members in voice channel")
            else:
                if message.author.voice is not None:
                    nick = message.author.nick if message.author.nick is not None else message.author.name;
                    await message.channel.send(f"Traditional: Wagwan {nick}")
                    time.sleep(0.5)
                    await message.author.move_to(None)
                else:
                    await message.channel.send("Traditional: You may not do this today")

        elif message.content.split()[0][1:] == "happybirthday":
            channel = await client.fetch_channel(int(message.content.split()[1]))
            await channel.send(f"Happy Birthday {message.content.split(' ', 2)[3]}, there is now a wider age gap between you and a 16 year old")

        elif message.content.split()[0][1:] == "spiked":
            page = requests.get(
                "https://www.spiked-online.com/")
            soup = BeautifulSoup(page.content, 'html.parser')

            all_links = []
            links = soup.select('a')
            for ahref in links:
                href = ahref.get('href')
                href = href.strip() if href is not None else ''

                if re.search(r'/[0-9]+/[0-9]+/[0-9]+/', href):
                    all_links.append(href)

            link = all_links[randint(0, len(all_links)-1)]
            await message.channel.send(link)


client.run(TOKEN)
