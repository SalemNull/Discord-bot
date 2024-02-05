import yt_dlp
import discord
import asyncio
import logging
from discord.ext import commands


log = logging.getLogger(__name__)

# Found good success with the android player client setting here
# Compiling FFmpeg from source helped massively with performance on the Pi, likely from the large version jump

ydl_opts = {#'outtmpl': "/songs/%(title)s.%(ext)s",
            'format': 'bestaudio',
#            'restrictfilenames': True,
            'noplaylist': True,
            'socket_timeout': 5,
            'skip_download': True,
            'quiet': True,
            'no_warnings': False,
            'extractor_args': {
                "youtube" : {
                    #"player_skip": ["js"],
                    "player_client": ["android"],
                }
            }
#            'ffmpeg_location': "C:/ffmpeg/ffmpeg.exe",
#            'postprocessors': [{
#                'key': 'FFmpegExtractAudio',
#                'preferredcodec': 'mp3',
#                'preferredquality': '320',
#            }],
}
# Reconnect setting is important for the Pi especially
ffmpeg_options = {
    #'pipe': True,
    'options': '-vn',
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
}

# TODO : new approach for playlist - current is very hackish
# Functional, especially with tweaks for the Pi, could be better though
# May be worth dropping stream all together in favor of DLing track, likely would burn thru write-cycles on SD card though
# 
class MusicBot(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.is_playing = False
        self.is_paused = False
        self.vc = None

        self.queue = []
        self.ytdl = yt_dlp.YoutubeDL(ydl_opts)
        self.loop = asyncio.get_running_loop()

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Bot ready")

    async def search_yt(self, query):
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = await self.loop.run_in_executor(None, lambda: ydl.extract_info(f'ytsearch:{query}', download=False))
                info = info['entries'][0]
            except Exception:
                return False
        return {'source' : info['url'], 'title': info['title']}

    async def play_next(self):
        if self.queue:
            self.is_playing = True
            m_url = self.queue[0][0]['source']
            self.queue.pop(0)
            source = discord.FFmpegOpusAudio(m_url, **ffmpeg_options)
            source.read()
            # The above line will cache the source start, removing the initial catch-up that was occurring 
            self.vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(), self.loop))
        else:
            self.is_playing = False

    async def play_music(self, ctx):
        if self.queue:
            self.is_playing = True
            m_url = self.queue[0][0]['source']

            if self.vc == None or not self.vc.is_connected():
                self.vc = await self.queue[0][1].connect()
                if not self.vc:
                    await ctx.send('Could not connect to voice channel')
                    self.is_playing = False
                    return
            else:
                await self.vc.move_to(self.queue[0][1])

            self.queue.pop(0)
            source = discord.FFmpegOpusAudio(m_url, **ffmpeg_options)
            source.read()
            self.vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(self.play_next(), self.loop))

        else:
            self.is_playing = False


    @commands.command(name='play', aliases=['p', 'add'], help='Play the selected audio from Youtube')
    async def play(self, ctx, *args):
        query = ' '.join(args)

        try:
            voice_channel = ctx.author.voice.channel
        except:
            await ctx.reply("Please connect to a voice channel first")
            return
        if self.is_paused:
            self.is_playing = True
            self.is_paused = False
            self.vc.resume()
        else:
            song = await self.search_yt(query)
            if isinstance(song, bool):
                await ctx.send('Could not download song. Incorrect format; possibly playlist or livestream')
            else:
                await ctx.send(f"{song['title']} added to the queue")
                self.queue.append([song, voice_channel])
                if self.is_playing == False:
                    await self.play_music(ctx)

    @commands.command(name='pause', help='Pauses the audio playback')
    async def pause(self, ctx):
        if self.is_playing:
            self.is_playing = False
            self.is_paused = True
            self.vc.pause()
        elif self.is_paused:
            self.is_playing = True
            self.is_paused = False
            self.vc.resume()

    @commands.command(name='resume', aliases=['unpause'], help='Resumes audio playback')
    async def resume(self, ctx):
        if self.is_paused:
            self.is_playing = True
            self.is_paused = False
            self.vc.resume()

    @commands.command(name='skip', aliases=['next'], help='Skips the current track')
    async def skip(self, ctx):
        if self.vc != None and self.vc:
            self.vc.stop()

    @commands.command(name='queue', aliases=['q', ], help='Displays the top 7 items in queue')
    async def display_queue(self, ctx):
        if self.queue:
            result = 'Displaying the top 7 tracks in queue:\n'
            for i in range(min(len(self.queue), 7)):
                result += f"**{i+1} - {self.queue[i][0]['title']}**\n"
            await ctx.send(result)
        else:
            await ctx.reply('No songs in queue')

    @commands.command(name='clear', aliases=['empty'], help='Clears playback queue')
    async def clear(self, ctx):
        if self.vc != None and self.is_playing:
            self.vc.stop()
        self.queue = []
        await ctx.send('Queue cleared')

    @commands.command(name='stop', aliases=['disconnect'], help="Disconnect from voice chat")
    async def dc(self, ctx):
            self.is_playing = False
            self.is_paused = False
            self.queue = []
            await self.vc.disconnect()

async def setup(bot) -> None:
    await bot.add_cog(MusicBot(bot))



