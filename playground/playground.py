import json
import re
from fnmatch import fnmatch

from ply import lex
from redbot.core import checks
from redbot.core import commands
from redbot.core.utils.chat_formatting import box, pagify

from rpadutils import rpadutils

class Playground(commands.Cog):
    """Just lil' fun things."""

    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    @commands.command(aliases = ["parrot", "repeat"])
    async def say(self, ctx, *, message):
        """Make Miru parrot a phrase."""
        message = self.emojify(message)
        await ctx.send(message)

    @commands.command()
    async def mask(self, ctx, *, message):
        """Sends a message as Miru."""
        message = self.emojify(message)
        await ctx.message.delete()
        await ctx.send(message)

    @commands.command()
    async def yell(self, ctx, *, message):
        """Yells some text."""
        message = self.emojify(message)
        await ctx.send(message.upper().rstrip(",.!?")+"!!!!!!")

    def emojify(self, message):
        emojis = list()
        for guild in self.bot.guilds:
            emojis.extend(guild.emojis)
        message = rpadutils.replace_emoji_names_with_code(emojis, message)
        return rpadutils.fix_emojis_for_server(emojis, message)
