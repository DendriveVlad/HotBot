from time import time, ctime as ct
from datetime import datetime

from nextcord import utils, Member, Embed

from config import CHANNELS, LEVEL_POINTS


async def send_log(guild, log_type: str, info: str = "", member: Member = None, fields: list = None, color: hex = 0x3B3B3B):
    channel = utils.get(guild.channels, id=CHANNELS["logs"])
    print(f"[{ct()}] {' '.join((str(member.id), log_type, info))}")
    embed = Embed(title=log_type, description=f"{info}", colour=color, timestamp=datetime.fromtimestamp(time()))
    if member:
        embed.set_footer(text="memberID: " + str(member.id))
        embed.set_author(
            name=member,
            icon_url=member.avatar.url if member.avatar else Embed.Empty
        )
    if isinstance(fields, tuple):
        embed.add_field(name=fields[0], value=fields[-1] if len(fields[-1]) else "~~не текст~~")
    elif isinstance(fields, list):
        for field in fields:
            embed.add_field(name=field[0], value=field[-1] if len(field[-1]) else "~~не текст~~")
    await channel.send(embed=embed)


async def get_level(points):
    for level, need_points in LEVEL_POINTS.items():
        if points < need_points:
            return level - 1
