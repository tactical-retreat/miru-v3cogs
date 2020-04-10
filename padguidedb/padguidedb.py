import asyncio
import concurrent.futures
import json
import re
import subprocess

import discord
import pymysql
from redbot.core import checks
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import inline, box, pagify

from rpadutils import CogSettings

PADGUIDEDB_COG = None


def is_padguidedb_admin_check(ctx):
    is_owner = PADGUIDEDB_COG.bot.owner_id == ctx.author.id
    return is_owner or PADGUIDEDB_COG.settings.checkAdmin(ctx.author.id)


def is_padguidedb_admin():
    return commands.check(is_padguidedb_admin_check)


class PadGuideDb(commands.Cog):
    """PadGuide Database manipulator"""

    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self.settings = PadGuideDbSettings("padguidedb")

        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.queue_size = 0
        self.full_etl_running = False
        self.extract_images_running = False

        global PADGUIDEDB_COG
        PADGUIDEDB_COG = self

    def get_connection(self):
        with open(self.settings.configFile(), 'a+') as f:
            f.seek(0)
            db_config = json.load(f)
        return self.connect(db_config)

    def connect(self, db_config):
        return pymysql.connect(host=db_config['host'],
                               user=db_config['user'],
                               password=db_config['password'],
                               db=db_config['db'],
                               charset=db_config['charset'],
                               cursorclass=pymysql.cursors.DictCursor,
                               autocommit=True)

    @commands.group(aliases=['pdb'])
    @is_padguidedb_admin()
    async def padguidedb(self, context):
        """PadGuide database manipulation."""

    @padguidedb.command()
    @checks.is_owner()
    async def addadmin(self, ctx, user: discord.Member):
        """Adds a user to the padguide db admin"""
        self.settings.addAdmin(user.id)
        await ctx.send("done")

    @padguidedb.command(pass_context=True)
    @checks.is_owner()
    async def rmadmin(self, ctx, user: discord.Member):
        """Removes a user from the padguide db admin"""
        self.settings.rmAdmin(user.id)
        await ctx.send("done")

    @padguidedb.command(pass_context=True)
    @checks.is_owner()
    async def setconfigfile(self, ctx, *, config_file):
        """Set the database config file."""
        self.settings.setConfigFile(config_file)
        await ctx.send(inline('Done'))

    @padguidedb.command()
    @is_padguidedb_admin()
    async def searchdungeon(self, ctx, *, search_text):
        """Search"""
        search_text = re.sub(r"[@#\$%\^&\*;\/<>?\\|`~\-\=]", " ", search_text)
        with self.get_connection() as cursor:
            sql = ("select dungeon_id, name_na, name_jp, visible from dungeons"
                   " where (lower(name_na) like '%{}%' or lower(name_jp) like '%{}%')"
                   " order by dungeon_id desc limit 20".format(search_text, search_text))
            cursor.execute(sql)
            results = list(cursor.fetchall())
            msg = 'Results\n' + json.dumps(results, indent=2, ensure_ascii=False)
            await ctx.send(inline(sql))
            for page in pagify(msg):
                await ctx.send(box(page))

    @padguidedb.command()
    @checks.is_owner()
    async def setdungeonscriptfile(self, ctx, *, dungeon_script_file):
        """Set the dungeon script."""
        self.settings.setDungeonScriptFile(dungeon_script_file)
        await ctx.send(inline('Done'))

    @padguidedb.command()
    @checks.is_owner()
    async def setuserinfo(self, ctx, server: str, user_uuid: str, user_intid: str):
        """Set the dungeon script."""
        self.settings.setUserInfo(server, user_uuid, user_intid)
        await ctx.send(inline('Done'))

    @padguidedb.command()
    @is_padguidedb_admin()
    async def loaddungeon(self, ctx, server: str, dungeon_id: int, dungeon_floor_id: int):
        event_loop = asyncio.get_event_loop()

        running_load = event_loop.run_in_executor(
            self.executor, self.do_dungeon_load,
            server.upper(), dungeon_id, dungeon_floor_id)

        self.queue_size += 1
        await ctx.send(inline('queued load in slot {}'.format(self.queue_size)))
        await running_load
        self.queue_size -= 1
        await ctx.send(inline('load for {} {} {} finished'.format(server, dungeon_id, dungeon_floor_id)))

    def do_dungeon_load(self, server, dungeon_id, dungeon_floor_id):
        args = [
            '/usr/bin/python3',
            self.settings.dungeonScriptFile(),
            '--db_config={}'.format(self.settings.configFile()),
            '--server={}'.format(server),
            '--dungeon_id={}'.format(dungeon_id),
            '--floor_id={}'.format(dungeon_floor_id),
            '--user_uuid={}'.format(self.settings.userUuidFor(server)),
            '--user_intid={}'.format(self.settings.userIntidFor(server)),
        ]
        subprocess.run(args)

    @padguidedb.command()
    @is_padguidedb_admin()
    async def dungeondrops(self, ctx, dungeon_id: int, dungeon_floor_id: int):
        with self.get_connection() as cursor:
            sql = ("SELECT stage, drop_monster_id, plus_amount, pull_time, COUNT(*) AS count"
                   " FROM wave_data"
                   " WHERE dungeon_id = {} AND floor_id = {}"
                   " GROUP BY 1, 2"
                   " ORDER BY 1, 2".format(dungeon_id, dungeon_floor_id))
            cursor.execute(sql)
            results = list(cursor.fetchall())
            msg = 'stage,drop_monster_id,pluses,time'
            for row in results:
                msg += '\n{},{},{},{}'.format(row['stage'], row['drop_monster_id'], row['plus_amount'], row['pull_time'])
            for page in pagify(msg):
                await ctx.send(box(page))

    @padguidedb.group()
    @is_padguidedb_admin()
    async def pipeline(self, context):
        """PadGuide pipeline utilities."""

    @pipeline.command()
    @is_padguidedb_admin()
    async def fulletl(self, ctx):
        """Runs a job which downloads pad data, and updates the padguide database."""
        if self.full_etl_running:
            await ctx.send(inline('Full ETL already running'))
            return

        event_loop = asyncio.get_event_loop()
        running_load = event_loop.run_in_executor(self.executor, self.do_full_etl)

        self.full_etl_running = True
        await ctx.send(inline('Running full ETL pipeline: this could take a while'))
        await running_load
        self.full_etl_running = False
        await ctx.send(inline('Full ETL finished'))

    def do_full_etl(self):
        args = [
            'bash',
            '/home/tactical0retreat/dadguide/dadguide-jobs/run_loader.sh',
        ]
        subprocess.run(args)

    @pipeline.command()
    @is_padguidedb_admin()
    async def extractimages(self, ctx):
        """Runs a job which downloads image updates, generates full images, and portraits."""
        if self.extract_images_running:
            await ctx.send(inline('Extract images already running'))
            return

        event_loop = asyncio.get_event_loop()
        running_load = event_loop.run_in_executor(self.executor, self.do_extract_images)

        self.extract_images_running = True
        await ctx.send(inline('Running image extract pipeline: this could take a while'))
        await running_load
        self.extract_images_running = False
        await ctx.send(inline('Image extract finished'))

    def do_extract_images(self):
        args = [
            'bash',
            '/home/tactical0retreat/dadguide/dadguide-jobs/media/update_image_files.sh',
        ]
        subprocess.run(args)


class PadGuideDbSettings(CogSettings):
    def make_default_settings(self):
        config = {
            'admins': [],
            'config_file': '',
            'dungeon_script_file': '',
            'users': {}
        }
        return config

    def admins(self):
        return self.bot_settings['admins']

    def checkAdmin(self, user_id):
        admins = self.admins()
        return user_id in admins

    def addAdmin(self, user_id):
        admins = self.admins()
        if user_id not in admins:
            admins.append(user_id)
            self.save_settings()

    def rmAdmin(self, user_id):
        admins = self.admins()
        if user_id in admins:
            admins.remove(user_id)
            self.save_settings()

    def configFile(self):
        return self.bot_settings.get('config_file', '')

    def setConfigFile(self, config_file):
        self.bot_settings['config_file'] = config_file
        self.save_settings()

    def dungeonScriptFile(self):
        return self.bot_settings.get('dungeon_script_file', '')

    def setDungeonScriptFile(self, dungeon_script_file):
        self.bot_settings['dungeon_script_file'] = dungeon_script_file
        self.save_settings()

    def setUserInfo(self, server, user_uuid, user_intid):
        self.bot_settings['users'][server.upper()] = [user_uuid, user_intid]
        self.save_settings()

    def userUuidFor(self, server):
        return self.bot_settings['users'][server.upper()][0]

    def userIntidFor(self, server):
        return self.bot_settings['users'][server.upper()][1]
