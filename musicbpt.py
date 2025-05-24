import discord
from discord.ext import commands
import yt_dlp
import logging
import time
from threading import Thread
from flask import Flask, request, redirect
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# === CONFIG ===
SPOTIFY_CLIENT_ID = 'id'
SPOTIFY_CLIENT_SECRET = 'secret'
REDIRECT_URI = 'http://127.0.0.1:8888/callback'
DISCORD_BOT_TOKEN = 'your-bot-token'
SPOTIFY_SCOPE = 'user-read-private'

# === GLOBAL ===
SPOTIFY_TOKEN = None

# === SPOTIFY AUTH SERVER ===
auth_app = Flask(__name__)
auth_oauth = SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope=SPOTIFY_SCOPE
)

@auth_app.route('/login')
def login():
    return redirect(auth_oauth.get_authorize_url())

@auth_app.route('/callback')
def callback():
    global SPOTIFY_TOKEN
    code = request.args.get('code')
    token_info = auth_oauth.get_access_token(code, as_dict=True)
    SPOTIFY_TOKEN = token_info['access_token']
    return '✅ Spotify authorized! You can return to Discord.'

def run_flask():
    auth_app.run(port=8888)

# Start Flask server in background
Thread(target=run_flask, daemon=True).start()

# === DISCORD BOT ===
logging.basicConfig(level=logging.INFO)
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')

@bot.event
async def on_command_error(ctx, error):
    await ctx.send(f'⚠️ Error: {str(error)}')
    print(f'Command error: {error}')

@bot.command()
async def join(ctx):
    if ctx.author.voice:
        await ctx.author.voice.channel.connect()
        await ctx.send("🔊 Joined your voice channel.")
    else:
        await ctx.send("❌ You're not in a voice channel.")

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("👋 Left the voice channel.")
    else:
        await ctx.send("❌ I'm not in a voice channel.")

@bot.command()
async def stop(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("⏹️ Playback stopped.")
    else:
        await ctx.send("❌ Nothing is playing.")

@bot.command()
async def volume(ctx, vol: int):
    """Set the playback volume (0–100)."""
    if ctx.voice_client and ctx.voice_client.source:
        vol = max(0, min(vol, 100))
        ctx.voice_client.source.volume = vol / 100
        await ctx.send(f"🔊 Volume set to {vol}%")
    else:
        await ctx.send("❌ I'm not playing any audio.")

@bot.command()
async def spotify(ctx):
    await ctx.send("🔗 Authorize Spotify here: http://127.0.0.1:8888/login")

@bot.command()
async def play(ctx, *, url_or_search):
    global SPOTIFY_TOKEN

    if not ctx.voice_client:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            await ctx.send("❌ You need to be in a voice channel or bot must be connected.")
            return

    if "open.spotify.com/track" in url_or_search:
        if not SPOTIFY_TOKEN:
            await ctx.send("❗ Please run `!spotify` and authorize first.")
            return
        try:
            sp = spotipy.Spotify(auth=SPOTIFY_TOKEN)
            track_id = url_or_search.split("/")[-1].split("?")[0]
            track = sp.track(track_id)
            query = f"{track['name']} {track['artists'][0]['name']}"
        except Exception as e:
            await ctx.send(f"❌ Spotify error: {e}")
            print(f"Spotify Error: {e}")
            return
    else:
        query = url_or_search

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'default_search': 'ytsearch',
        'noplaylist': True,
        'extract_flat': 'in_playlist'
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if 'entries' in info:
                info = info['entries'][0]
            url = info['url'] if 'url' in info else info['webpage_url']
            title = info.get('title', 'Unknown Title')

        source = discord.FFmpegPCMAudio(url)
        source = discord.PCMVolumeTransformer(source, volume=0.5)

        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        ctx.voice_client.play(source)
        await ctx.send(f"🎶 Now playing: **{title}**")
    except Exception as e:
        await ctx.send(f"❌ Error playing track: {e}")
        print(f"Error in play command: {e}")

# === RUN BOT ===
try:
    bot.run(DISCORD_BOT_TOKEN)
except Exception as e:
    print(f"Bot crashed: {e}")
    time.sleep(10)
