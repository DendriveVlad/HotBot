from discord import *
from discord.ext import commands

from config import *
from DataBase import db


class CMD(commands.Cog):
    def __init__(self, client):
        self.client = client

    @commands.command(aliases=["lvl", "level"])
    async def rank(self, ctx):
        points = db.select("users", f"user_id == {ctx.author.id}", "points")["points"]
        for level, need_points in LEVEL_POINTS.items():
            if points < need_points:
                if str(points)[-2] == "1":
                    exp = "очков"
                elif str(points)[-1] == "1":
                    exp = "очко"
                elif str(points)[-1] in "234":
                    exp = "очка"
                else:
                    exp = "очков"
                await ctx.send(embed=Embed(title=f"Ваш уровень: **{level - 1}**", description=f"У Вас на данный момент **{points}** {exp}", colour=0x0CE2FF))
                break

    @commands.command(aliases=["levels"])
    async def top(self, ctx):
        message = []
        container = {}
        for date in db.select("users", f"", "user_id", "points"):
            if date["points"] != 0:
                container[date["user_id"]] = date["points"]
        author_request = False
        place = 0
        for id, points in sorted(container.items(), key=lambda item: item[1], reverse=True):
            place += 1
            medal = None
            if place == 1:
                medal = "🥇"
            elif place == 2:
                medal = "🥈"
            elif place == 3:
                medal = "🥉"
            if place > 10 and author_request:
                break
            if id == ctx.author.id:
                author_request = True
            if place == 12:
                message.append("-----------------")
            if place > 10 and not author_request:
                continue
            lvl = 0
            for level, need_points in LEVEL_POINTS.items():
                if points < need_points:
                    lvl = level - 1
                    break
            if str(points)[-2] == "1":
                exp = "очков"
            elif str(points)[-1] == "1":
                exp = "очко"
            elif str(points)[-1] in "234":
                exp = "очка"
            else:
                exp = "очков"
            message.append(f"{medal if medal else place}. [{lvl}]<@{id}>: {points} {exp}")
        await ctx.send(embed=Embed(title="**Топ по очкам:**", description="\n".join(message), colour=0x0CE2FF))


def setup(client):
    client.add_cog(CMD(client))
