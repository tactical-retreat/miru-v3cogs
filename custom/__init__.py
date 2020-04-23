from .custom_music import csetup
from .custom_tug import TCustom


def setup(bot):
    bot.add_cog(TCustom(bot))
    csetup(bot)
    pass
