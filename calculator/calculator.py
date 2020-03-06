"""
A cloned and improved version of paddo's calculator cog.
"""

import numbers
import os
import re
import shlex
import subprocess
import sys

import discord
from redbot.core import commands
from redbot.core.utils.chat_formatting import inline, box

from rpadutils.rpadutils import CtxIO

ACCEPTED_TOKENS = r'[\[\]\-()*+/0-9=.,% ]|>|<|==|>=|<=|\||&|~|!=|factorial|randrange|isfinite|copysign|radians|isclose|degrees|randint|lgamma|choice|random|round|log1p|log10|ldexp|isnan|isinf|hypot|gamma|frexp|floor|expm1|atanh|atan2|asinh|acosh|False|range|tanh|sqrt|sinh|modf|log2|fmod|fabs|erfc|cosh|ceil|atan|asin|acos|else|True|fsum|tan|sin|pow|nan|log|inf|gcd|sum|exp|erf|cos|for|not|and|pi|in|is|or|if|e|x'

ALTERED_TOKENS = {'^': '**'}

HELP_MSG = '''
This calculator works by first validating the content of your query against a whitelist, and then
executing a python eval() on it, so some common syntax wont work.  Here is the full symbol whitelist:
'''


class Calculator(commands.Cog):
    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    @commands.group()
    async def helpcalc(self, ctx):
        '''Whispers info on how to use the calculator.'''
        help_msg = HELP_MSG + '\n' + ACCEPTED_TOKENS
        await ctx.author.send(box(help_msg))

    @commands.command(aliases=['calc'])
    async def calculator(self, ctx, *, inp):
        '''Evaluate equations. Use helpcalc for more info.'''
        unaccepted = list(filter(None, re.split(ACCEPTED_TOKENS, inp)))
        bad_inp = []
        for token in unaccepted:
            if token in ALTERED_TOKENS:
                inp = inp.replace(token, ALTERED_TOKENS[token])
            else:
                bad_inp.append(token)

        if bad_inp:
            err_msg = 'Found unexpected symbols inside the input: {}'.format(bad_inp)
            help_msg = 'Use {0.prefix}helpcalc for info on how to use this command'
            await ctx.send(inline(err_msg + '\n' + help_msg.format(ctx)))
            return

        cmd = """{} -c "from math import *;from random import *;print(eval('{}'), end='', flush=True)" """.format(
            sys.executable, inp)

        try:
            if os.name != 'nt' and sys.platform != 'win32':
                cmd = shlex.split(cmd)
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=2)
            calc_result = output.decode('utf-8').strip()
        except subprocess.TimeoutExpired:
            await ctx.send(inline('Command took too long to execute. Quit trying to break the bot.'))
            return
        except subprocess.CalledProcessError as e:
            await ctx.send(inline(e.output.decode("utf-8").strip().split('\n')[-1]))
            return


        if len(str(calc_result)) > 1024:
            await ctx.send(inline("The result is obnoxiously long!  Try a request under 1k characters!"))
        elif len(str(calc_result)) > 0:
            if isinstance(calc_result, numbers.Number):
                if calc_result > 1:
                    calc_result = round(calc_result, 3)

            em = discord.Embed(color=discord.Color.greyple())
            em.add_field(name='Input', value='`{}`'.format(inp))
            em.add_field(name='Result', value=calc_result)
            await ctx.send(embed=em)
