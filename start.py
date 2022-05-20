from time import time

from nextcord import Intents, Message, Status
from nextcord.ext import tasks, commands

from main import BotThread

__author__ = "Vladi4ka | DendriveVlad"

BOT = 879324092732420107
GUILD = 473076474329694218

ACCESS = [280536559403532290, 455008287188844544, 700622143741755472, 700622143741755472]


class Bot(commands.Bot):
    def __init__(self):
        super().__init__("/", intents=Intents.all())
        self.last_restart = time()
        self.bot = BotThread()

    async def on_ready(self):
        await self.change_presence(status=Status.invisible)
        print("run")
        if not self.check_online.is_running():
            self.check_online.start()
        print("running the bot...")
        self.bot.start()
        print("bot is running")

    async def on_message(self, message: Message):
        if message.author.id in ACCESS and message.content.lower() == "bot-force-restart":
            await message.delete()
            if time() - self.last_restart < 1800:
                return
            print("restart command executing...")
            self.bot.stop()
            print("bot stopped...")
            self.bot = BotThread()
            self.bot.start()
            print("bot is running")

    @tasks.loop(minutes=2)
    async def check_online(self):
        bot = self.get_guild(GUILD).get_member(BOT)
        if bot.status == Status.offline:
            self.bot.stop()
            print("bot stopped...")
            self.bot = BotThread()
            self.bot.start()
            print("bot is running")


Bot().run("SECRET")
