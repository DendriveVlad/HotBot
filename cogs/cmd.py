from discord import *
from discord.ext import commands

from config import *
from DataBase import db


class CMD(commands.Cog):
    def __init__(self, client):
        self.client = client


def setup(client):
    client.add_cog(CMD(client))
