import json
import re
import discord.utils
import youtube_dl
import asyncio

from ply import lex
from redbot.core import checks, Config
from redbot.core import commands
from redbot.core.utils.chat_formatting import box, pagify, inline

HSTRING = """The counter commands are the following:
{0.prefix}addmoney          Add money to your team's counter.
{0.prefix}setmoney          Set a team's counter to a specific amount.
{0.prefix}getmoney          Get the value of your team's counter.
{0.prefix}setcstr           Change the output when changing money. (default is "The counter for {{role}} is {{amount}}.")
{0.prefix}setdefaultrole    Change your default role.  With a default role set, you don't need to add a role argument to {0.prefix}addmoney and {0.prefix}getmoney
{0.prefix}helpmoney         Displays this help text.
"""

class TCustom(commands.Cog):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

        self.config = Config.get_conf(self, identifier=7375707)
        self.config.register_role(counter=0, cstr="The counter for {role} is {amount}.", private=True, valid=False)
        self.config.register_user(drole={})

    @commands.command()
    @commands.guild_only()
    async def addmoney(self, ctx, amount: int, *, role: discord.Role = None):
        role = role or ctx.guild.get_role(await self.config.user(ctx.author).drole().get(ctx.guild.id))
        if role is None:
            await ctx.send(("Either you don't have a default role set or your default role has been",
                            "deleted from this guild.  Set it with {0.prefix}defaultrole.").format(ctx))
            return
        if not await self.config.role(role).valid():
            await ctx.send("That role is not set up for a counter.")
        if role not in ctx.author.roles and not ctx.channel.permissions_for(ctx.author).administrator:
            await ctx.send("You don't have permission to change that role's counter!")
            return
        await self.config.role(role).counter.set(amount + await self.config.role(role).counter())
        cstr = await self.config.role(role).cstr()
        await ctx.send(cstr.format(role=role.name, amount=await self.config.role(role).counter()))

    @commands.command()
    @commands.guild_only()
    @checks.admin()
    async def setmoney(self, ctx, amount: int, *, role: discord.Role):
        await self.config.role(role).counter.set(amount)
        cstr = await self.config.role(role).cstr()
        await ctx.send(cstr.format(role=role.name, amount=await self.config.role(role).counter()))

    @commands.command()
    @commands.guild_only()
    async def getmoney(self, ctx, *, role: discord.Role = None):
        role = role or ctx.guild.get_role(await self.config.user(ctx.author).drole().get(ctx.guild.id))
        if role is None:
            await ctx.send(("Either you don't have a default role set or your default role has been",
                            "deleted from this guild.  Set it with {0.prefix}defaultrole.").format(ctx))
            return
        if not await self.config.role(role).valid():
            await ctx.send("That role is not set up for a counter.")
        if role not in ctx.author.roles and not ctx.channel.permissions_for(ctx.author).administrator \
                and await self.config.role(role).private():
            await ctx.send("You don't have permission to get that role's counter!")
            return
        cstr = await self.config.role(role).cstr()
        await ctx.send(cstr.format(role=role.name, amount=await self.config.role(role).counter()))

    @commands.command()
    @commands.guild_only()
    async def setcstr(self, ctx, role: discord.Role, *, cstr):
        if role not in ctx.author.roles and not ctx.channel.permissions_for(ctx.author).administrator:
            await ctx.send("You don't have permission to change that role's cstr!")
            return
        await self.config.role(role).cstr.set(cstr)
        await ctx.send(inline("Done"))

    @commands.command()
    @commands.guild_only()
    async def setdefaultrole(self, ctx, *, role: discord.Role):
        if role not in ctx.author.roles:
            await ctx.send("You must have a role to set it as your default.")
            return
        if not await self.config.role(role).valid():
            await ctx.send("That role is not set up for a counter.")
        async with self.config.user(ctx.author).drole() as drole:
            drole[ctx.guild.id] = role.id
        await ctx.send(inline("Done"))

    @commands.command()
    @commands.guild_only()
    @checks.admin()
    async def setprivate(self, ctx, private: bool, *, role: discord.Role):
        await self.config.role(role).private.set(private)
        await ctx.send(inline("Done"))

    @commands.command()
    @commands.guild_only()
    @checks.admin()
    async def setvalid(self, ctx, valid: bool, *, role: discord.Role):
        await self.config.role(role).valid.set(valid)
        await ctx.send(inline("Done"))

    @commands.command()
    @commands.guild_only()
    async def getroleinfo(self, ctx, *, role: discord.Role):
        await ctx.send(box("Private: {}\nValid: {}".format(await self.config.role(role).private(),
                                                       await self.config.role(role).valid())))
    @commands.command()
    async def helpmoney(self, ctx):
        await ctx.send(box(HSTRING.format(ctx)))
