from .padguidedb import *


def setup(bot):
    # TODO: Test this! I don't have the databases
    pdb = PadGuideDb(bot)
    bot.add_cog(pdb)
