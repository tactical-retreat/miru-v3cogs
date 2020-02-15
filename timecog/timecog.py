import time
import re
import asyncio
import traceback
from datetime import timedelta, datetime

import pytz
from redbot.core import commands, Config
from redbot.core.utils.chat_formatting import *

from rpadutils import CogSettings

tz_lookup = dict([(pytz.timezone(x).localize(datetime.datetime.now()).tzname(), pytz.timezone(x))
                  for x in pytz.all_timezones])


time_at_regeces = [
    r'(?P<year>\d{4})[-/](?P<month>\d+)[-/](?P<day>\d+) (?P<hour>\d+):(?P<minute>\d\d) ?(?P<merid>pm|am)? ?(?P<tz>\w+\b)?',
    r'(?P<year>\d{4})[-/](?P<month>\d+)[-/](?P<day>\d+)',
    r'(?P<month>\d+)[-/](?P<day>\d+)',
    r'(?P<hour>\d+):(?P<minute>\d\d) ?(?P<merid>pm|am)? ?(?P<tz>\w+\b)?',
]

time_in_regeces = [
    r'(?P<tin>\d+) ?(?P<unit>m(?:inutes)?|h(?:ours)?|d(?:ays)?|w(?:eeks)?|m(?:onths)?|y(?:ears)?)\b'
]


DT_FORMAT = "%b %-d, %Y at %-I:%M %p"

class TimeCog(commands.Cog):
    """Utilities pertaining to time"""

    def __init__(self, bot, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = Config.get_conf(self, identifier=7173306)
        self.config.register_user(reminders = {}, tz = 'est')

        self.bot = bot

    @commands.command(aliases=['remindmeat', 'rmdme', 'rmme'], ignore_extra=False)
    async def remindme(self, ctx, time, *, input):
        """Reminds you to do something at a specified time
        [p]remindme "2020-04-13 06:12" Do something!
        [p]remindme "5 weeks" Do something!
        [p]remindme "4:13 PM" Do something!
        [p]remindme "2020-05-03" Do something!
        [p]remindme "04-13" Do something!"""
        D_TZ = tzStrToObj(await self.config.user(ctx.author).tz())
        time = time.lower()
        for ar in time_at_regeces:
            gs = re.search(ar, time)
            if not gs: continue
            gs = gs.groupdict()
            tz = tzStrToObj(gs.get('tz') or D_TZ._tzname)
            now = datetime.datetime.now()
            gs['tz'] = None; del gs['tz']
            defaults = dict(
                year   = now.year,
                month  = now.month,
                day    = now.day,
                hour   = now.hour,
                minute = now.minute,
                merid  = 'am',
            )
            defaults.update({k:v for k,v in gs.items() if v})
            for key in defaults:
                if key not in ['merid']:
                    defaults[key] = int(defaults[key])
            if  defaults['merid'] == 'pm':
                defaults['hour']  += 12
            del defaults['merid']
            rmtime = tz.localize(datetime.datetime(**defaults))
            if rmtime < now:
                rmtime += timedelta(days=1)
            break
        else:
            for ir in time_in_regeces:
                gs = re.findall(ir, time)
                if not gs:
                    continue
                rmtime = D_TZ.localize(datetime.datetime.now())
                for tin, unit in gs:
                    rmtime += tin2tdelta(tin, unit)
                break
            else:
                raise commands.UserFeedbackCheckFailure("Invalid time string: " + time)
                return

        async with self.config.user(ctx.author).reminders() as rms:
            rms[rmtime.timestamp()] = input
        await self.config.user(ctx.author).tz.set(rmtime.tzinfo._tzname)
        await ctx.send("I will tell you "+self.formatrm(rmtime, input, D_TZ))


    @commands.command(aliases = ["getrms"])
    async def getreminders(self, ctx):
        rlist = sorted((await self.config.user(ctx.author).reminders()).items(), key=lambda x: x[0])
        if not rlist:
            await ctx.send(inline("You have no pending reminders!"))
            return
        tz = tzStrToObj(await self.config.user(ctx.author).tz())
        o = []
        for c, (timestamp, input) in enumerate(rlist):
            o.append(str(c+1)+": "+self.formatrm(tz.localize(datetime.datetime.fromtimestamp(float(timestamp))), input, tz))
        o = "```\n"+'\n'.join(o)+"\n```"
        await ctx.send(o)

    @commands.command(aliases = ["delrm","rmrm"])
    async def removereminder(self, ctx, no: int):
        rlist = sorted((await self.config.user(ctx.author).reminders()).keys())
        if len(rlist) < no:
            await ctx.send(inline("There is no reminder #{}".format(no)))
            return
        async with self.config.user(ctx.author).reminders() as rms:
            rms.pop(rlist[no-1])
        await ctx.send(inline("Done"))

    @commands.command(aliases = ['settz'])
    async def settimezone(self, ctx, tzstr):
        try:
            tzStrToObj(tzstr)
            await self.config.user(ctx.author).tz.set(tzstr)
            await ctx.send(inline("Done"))
        except IOError as e:
            await ctx.send(inline("Invalid tzstr: "+tzstr))

    def formatrm(self, rmtime, input, D_TZ):
        return "'{}' on {} {} ({} from now)".format(input, rmtime.strftime(DT_FORMAT),
            rmtime.tzinfo._tzname, fmtHrsMins((rmtime-D_TZ.localize(datetime.datetime.now())).seconds+2))

    async def reminderloop(self):
        await self.bot.wait_until_ready()

        while self == self.bot.get_cog('TimeCog'):
            urs = await self.config.all_users()
            now = datetime.datetime.now()
            for u in urs:
                for rm in urs[u]['reminders']:
                    if datetime.datetime.fromtimestamp(float(rm)) < now:
                        async with self.config.user(self.bot.get_user(u)).reminders() as rms:
                            await self.bot.get_user(u).send(rms.pop(rm))

            try:
                await asyncio.sleep(60 * 60 * 24)
            except Exception as ex:
                print("sqlactivitylog data wait loop failed", ex)
                traceback.print_exc()
                raise ex

    @commands.command()
    async def time(self, ctx, *, tz: str):
        """Displays the current time in the supplied timezone"""
        try:
            tz_obj = tzStrToObj(tz)
        except Exception as e:
            await ctx.send("Failed to parse tz: " + tz)
            return

        now = datetime.datetime.now(tz_obj)
        msg = "The time in " + now.strftime('%Z') + " is " + fmtTimeShort(now).strip()
        await ctx.send(inline(msg))

    @commands.command()
    async def timeto(self, ctx, tz: str, *, time: str):
        """Compute the time remaining until the [timezone] [time]"""
        try:
            tz_obj = tzStrToObj(tz)
        except Exception as e:
            await ctx.send("Failed to parse tz: " + tz)
            return

        try:
            time_obj = timeStrToObj(time)
        except Exception as e:
            print(e)
            await ctx.send("Failed to parse time: " + time)
            return

        now = datetime.datetime.now(tz_obj)
        req_time = now.replace(hour=time_obj.tm_hour, minute=time_obj.tm_min)

        if req_time < now:
            req_time = req_time + timedelta(days=1)
        delta = req_time - now

        msg = "There are " + fmtHrsMins(delta.seconds).strip() + \
              " until " + time.strip() + " in " + now.strftime('%Z')
        await ctx.send(inline(msg))


def timeStrToObj(timestr):
    timestr = timestr.replace(" ", "")
    try:
        return time.strptime(timestr, "%H:%M")
    except:
        pass
    try:
        return time.strptime(timestr, "%I:%M%p")
    except:
        pass
    try:
        return time.strptime(timestr, "%I%p")
    except:
        pass
    raise commands.UserFeedbackCheckFailure("Invalid Time: "+timestr)


def fmtHrsMins(seconds):
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    return '{:2}hrs {:2}mins'.format(int(hours), int(minutes))


def fmtTimeShort(dt):
    return dt.strftime("%I:%M %p")


def tzStrToObj(tz):
    tz = tz.lower().strip()
    if tz in ['edt', 'est', 'et']:
        tz = 'America/New_York'
    elif tz in ['mdt', 'mst', 'mt']:
        tz = 'America/North_Dakota'
    elif tz in ['pdt', 'pst', 'pt']:
        tz = 'America/Los_Angeles'
    elif tz in ['jp', 'jt', 'jst']:
        return tz_lookup['JST']
    elif tz.upper() in tz_lookup:
        return tz_lookup[tz.upper()]
    else:
        for tzo in pytz.all_timezones:
            if tz.lower() == tzo.split("/")[-1].lower():
                tz = tzo
                break
        else:
            raise commands.UserFeedbackCheckFailure("Invalid timezone: "+tz)
    try:
        return pytz.timezone(tz)
    except:
        raise commands.UserFeedbackCheckFailure("Invalid timezone: "+tz)

def tin2tdelta(tin, unit):
    tin = int(tin)
    if unit[0] == 'm':
        return timedelta(minutes=tin)
    if unit[0] == 'h':
        return timedelta(hours=tin)
    if unit[0] == 'd':
        return timedelta(days=tin)
    if unit[0] == 'w':
        return timedelta(weeks=tin2tdelta)
    if unit[0] == 'm':
        return timedelta(months=tin)
    if unit[0] == 'y':
        return timedelta(years=tin)
    raise commands.UserFeedbackCheckFailure("Invalid unit: {}\nPlease use minutes, hours, days, weeks, months, or, if you're feeling especially zealous, years.".format(unit))


class TimeCogSettings(CogSettings):
    def make_default_settings(self):
        config = {

        }
        return config
