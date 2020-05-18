from .override import *


def setup(bot):
    pdb = Override(bot)
    bot.add_cog(pdb)
