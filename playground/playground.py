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
        await ctx.send(message)

    @commands.command()
    async def mask(self, ctx, *, message):
        """Sends a message as Miru."""
        await ctx.message.delete()
        await ctx.send(message)

    @commands.command()
    async def yell(self, ctx, *, message):
        """Yells some text."""
        await ctx.send(message.upper().rstrip(",.!?")+"!!!!!!")
