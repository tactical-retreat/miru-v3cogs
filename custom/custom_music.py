import json
import re
import discord.utils
import youtube_dl
import asyncio

from ply import lex
from redbot.core import checks, Config
from redbot.core import commands
from redbot.core.utils.chat_formatting import box, pagify

try:
    from rpadutils import rpadutils
except:
    pass

old_invite = None

# Suppress noise about console usage from errors
youtube_dl.utils.bug_reports_message = lambda: ''


ytdl_format_options = {
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
    'source_address': '0.0.0.0' # bind to ipv4 since ipv6 addresses cause issues sometimes
}

ffmpeg_options = {
    'options': '-vn'
}

ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)

        self.data = data

        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    def from_url(cls, url, *, loop=None, stream=False):
        data = ytdl.extract_info(url, download=not stream)

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

class MCustom(commands.Cog):
    """Just for me~"""

    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        global C_COG
        C_COG = self
        self.bot = bot
        self.config = Config.get_conf(self, identifier=335707)
        self.config.register_guild(cid=None, queue=[], loop=False)

        """
        CONFIG: Config
        |   GUILDS: Config
        |   |   vc: Optional[str]
        |   |   queue: list
        |   |   loop: bool
        """


    def cog_unload(self):
        global old_invite
        if old_invite:
            try:
                self.bot.remove_command("disconnect")
            except:
                pass
            self.bot.add_command(old_invite)

    @commands.command()
    async def waitmerge(self, ctx):
        await asyncio.sleep(5)
        await rpadutils.doubleup(ctx, "Done!")


    @commands.command(aliases = ["join"])
    async def connect(self, ctx):
        """Joins a voice channel."""
        try:
            vc = await ctx.author.voice.channel.connect()
            await self.config.guild(ctx.guild).cid.set(vc.channel.id)
        except discord.ClientException:
            pass
        except Exception as e:
            await ctx.send("My botmaster (Aradia Megido#2552) needs to implement the error: " + repr(e))

    @commands.command(aliases = ["leave"])
    async def disconnect(self, ctx):
        """Leaves a voice channel."""
        try:
            vc = ctx.voice_client
            if vc is None:
                await ctx.send("I am not connected to a voice channel.")
            await vc.disconnect()
            await self.config.guild(ctx.guild).queue.set([])
            await self.config.guild(ctx.guild).cid.set(None)
        except Exception as e:
            await ctx.send("My botmaster (Aradia Megido#2552) needs to implement the error: " + str(e))

    @commands.command()
    @checks.is_owner()
    async def playfile(self, ctx, *, path):
        song = File(path)
        await self._play(ctx, song)

    @commands.command()
    async def play(self, ctx, *, url):
        song = YTDL(url, stream = True)
        await self._play(ctx, song)

    async def _play(self, ctx, song):
        cid = await self.config.guild(ctx.guild).cid()
        start = False
        async with self.config.guild(ctx.guild).queue() as queue:
            if not queue:
                start = True
            queue.append(song.sterilize())
        vc = discord.utils.get(self.bot.voice_clients, channel__id=cid)
        if vc and start:
            vc.play(song.make(), after=await self.after_wrapper(ctx, cid, await self.make_data(ctx.guild)))

    @commands.command()
    async def loop(self, ctx):
        old = await self.config.guild(ctx.guild).loop()
        await self.config.guild(ctx.guild).loop.set(not old)
        await ctx.send("Looping set to " + str(not old))

    @playfile.before_invoke
    @play.before_invoke
    @connect.before_invoke
    async def ensure_voice(self, ctx):
        if ctx.voice_client is None:
            if ctx.author.voice:
                vc = await ctx.author.voice.channel.connect()
                await self.config.guild(ctx.guild).cid.set(vc.channel.id)
            else:
                await ctx.send("You are not connected to a voice channel.")
                raise commands.CommandError("Author not connected to a voice channel.")
        elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()

    @commands.command()
    async def clearqueue(self, ctx):
        await self.config.guild(ctx.guild).queue.set([])
        await ctx.send("Done!")

    @commands.command()
    async def queue(self, ctx):
        queue = await self.config.guild(ctx.guild).queue()
        if not queue:
            await ctx.send("The queue is empty.")
        o = ""
        for c,s in enumerate(queue):
            o += "{}) {}\n".format(c.zfill(len(str(len(queue)))), str(s))
        for page in pagify(o):
            await ctx.send(box(page))

    async def make_data(self, guild):
        loop = await self.config.guild(ctx.guild).loop()
        queue = await self.config.guild(ctx.guild).queue()
        return {
            'loop':loop,
            'queue':queue,
        }

    async def after_wrapper(self, ctx, cid, data={}):
        loop = await self.config.guild(ctx.guild).loop()
        queue = await self.config.guild(ctx.guild).queue()
        def after(error):
            if error:
                print(error)
            elif loop and queue:
                queue.append(queue.pop(0))
            elif data.get('queue'):
                data.get('queue').pop(0)
            else:
                return

            song = desterilize(data.get('queue')[0])
            vc = discord.utils.get(C_COG.bot.voice_clients, channel__id=cid)
            vc.play(song.make(), after=after)

        return after




def desterilize(sterilized):
    type, args, kwargs = sterilized
    format = discord.utils.get(formats, type=type)
    return format(*args, **kwargs)


class Song:
    type = 0
    func = None
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
    def sterilize(self): return (self.type, self.args, self.kwargs)
    def make(self): return self.func(*self.args, **self.kwargs)
    def __str__(self):
        return str(self.args)


class File(Song):
    type = 1
    func = discord.FFmpegPCMAudio

class YTDL(Song):
    type = 2
    func = YTDLSource.from_url


formats = [
    File,
    YTDL,
]

def csetup(bot):
    global old_invite
    old_invite = bot.get_command("leave")
    if old_invite:
        bot.remove_command(old_invite.name)
    bot.add_cog(MCustom(bot))
