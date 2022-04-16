from datetime import datetime
from time import time, ctime as ct

from nextcord import slash_command, Embed, Interaction, Member, SlashOption, TextChannel, utils
from nextcord.ext import commands

from config import *
from DataBase import DB

db = DB()


class Admin(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.guild = client.get_guild(SERVER_ID)
        self.channel = self.guild.get_channel(CHANNELS["staff"])

    @slash_command(name="channel-ban", description="Заблокировать участника в определённом канале", guild_ids=[SERVER_ID])
    async def channel_ban(self, interaction: Interaction, str_member: str, str_channel: str):
        member = self.__get_member(str_member)
        ban_channel = self.__get_channel(str_channel)
        if not await self.checks(interaction, "13456", member=member, channel=ban_channel):
            return

        await ban_channel.set_permissions(member, read_messages=False)
        await interaction.response.send_message(embed=Embed(title=f"Участник заблокирован в канале {ban_channel}", colour=0x21F300), ephemeral=False)

    @slash_command(name="channel-unban", description="Разблокировать  участника в определённом канале", guild_ids=[SERVER_ID])
    async def channel_unban(self, interaction: Interaction, str_member: str, str_channel: str):
        member = self.__get_member(str_member)
        ban_channel = self.__get_channel(str_channel)
        if not await self.checks(interaction, "13456", member=member, channel=ban_channel):
            return

        await ban_channel.set_permissions(member, read_messages=None)
        await interaction.response.send_message(embed=Embed(title=f"Участник разблокирован в канале {ban_channel}", colour=0x21F300), ephemeral=False)

    @slash_command(name="set", description="Изменить количество золота или опыта участника но новое значение", guild_ids=[SERVER_ID])
    async def set(self, interaction: Interaction, thing: str = SlashOption(name="thing", description="gold/points", choices={"Золото": "gold", "Очки": "points"}), str_member: str = None, count: int = 0):
        member = self.__get_member(str_member)
        if not await self.checks(interaction, "234578", member=member, count=count):
            return

        eval(f"db.update('users', 'user_id == {member.id}', {thing}={int(count)})")
        await interaction.response.send_message(embed=Embed(title=f"Данные участника {member} обновлены", colour=0x21F300), ephemeral=False)

    @slash_command(name="remove", description="Удалить определённое количество золота или опыта у участника", guild_ids=[SERVER_ID])
    async def remove(self, interaction: Interaction, thing: str = SlashOption(name="thing", description="gold/points", choices={"Золото": "gold", "Очки": "points"}), str_member: str = None, count: int = 0):
        member = self.__get_member(str_member)
        if not await self.checks(interaction, "234578", member=member, count=count):
            return

        eval(f"db.update('users', 'user_id == {member.id}', {thing}={db.select('users', f'user_id == {member.id}', thing)[thing] - int(count)})")
        await interaction.response.send_message(embed=Embed(title=f"Данные участника {member} обновлены", colour=0x21F300), ephemeral=False)

    @slash_command(name="add", description="Добавить определённое количество золота или опыта участнику", guild_ids=[SERVER_ID])
    async def add(self, interaction: Interaction, thing: str = SlashOption(name="thing", description="gold/points", choices={"Золото": "gold", "Очки": "points"}), str_member: str = None, count: int = 0):
        member = self.__get_member(str_member)
        if not await self.checks(interaction, "234578", member=member, count=count):
            return

        eval(f"db.update('users', 'user_id == {member.id}', {thing}={db.select('users', f'user_id == {member.id}', thing)[thing] + int(count)})")
        await interaction.response.send_message(embed=Embed(title=f"Данные участника {member} обновлены", colour=0x21F300), ephemeral=False)

    async def checks(self, interaction: Interaction, checks, **other) -> bool:
        await self.send_log(log_type="CommandUse", info=f"Использует команду **/{' '.join((interaction.data['name'], *[str(i['value']) for i in interaction.data['options']]))}**", member=interaction.user)

        if "1" in checks:
            mod = False
            for r in interaction.user.roles:
                if r.id in (ROLES["Admin"], ROLES["Owner"], ROLES["Vlad"]):
                    mod = True
                    break
            if not mod:
                await interaction.response.send_message(embed=Embed(title="Ты кто такой, сцуко?", colour=0xBF1818), ephemeral=True)
                return False

        if "2" in checks:
            adm = False
            for r in interaction.user.roles:
                if r.id in (ROLES["Admin"], ROLES["Owner"], ROLES["Moder"], ROLES["Vlad"]):
                    adm = True
                    break
            if not adm:
                await interaction.response.send_message(embed=Embed(title="Ты кто такой, сцуко?", colour=0xBF1818), ephemeral=True)
                return False

        if "3" in checks and interaction.channel.id != CHANNELS["Admin"]:
            await interaction.response.send_message(embed=Embed(title="Данное действие разрешено только в канале", colour=0xBF1818), ephemeral=True)
            return False

        if "4" in checks and not other["member"]:
            await interaction.response.send_message(embed=Embed(title="Не верно задан пользователь", colour=0xBF1818), ephemeral=True)
            return False

        if "5" in checks and other["member"].bot:
            await interaction.response.send_message(embed=Embed(title="Использование команд на ботов отключено", colour=0xBF1818), ephemeral=True)
            return False

        if "6" in checks and not other["channel"]:
            await interaction.response.send_message(embed=Embed(title="Не верно задан канал", colour=0xBF1818), ephemeral=True)
            return False

        if "7" in checks and int(other["count"]) < 0:
            await interaction.response.send_message(embed=Embed(title="Участник не может иметь отрицательное количество золота или очков", colour=0xBF1818), ephemeral=True)
            return False

        if "8" in checks and (int(other["count"]) > 500000):
            await interaction.response.send_message(embed=Embed(title="Введено слишком большое число", colour=0xBF1818), ephemeral=True)
            return False

        return True

    def __get_member(self, str_member: str) -> Member | None:
        if len(str_member) in [21, 22] and str_member[0:2] == "<@" and str_member[-1] == ">":
            try:
                return self.guild.get_member(int(str_member[-19:-1]))
            except ValueError:
                pass
            except AttributeError:
                return None
        for user in self.guild.members:
            if user.nick:
                if user.nick.lower() == str_member.lower():
                    return user
            elif user.name.lower() == str_member.lower():
                return user
        return None

    def __get_channel(self, str_channel) -> TextChannel | None:
        if len(str_channel) == 21 and str_channel[0:2] == "<#" and str_channel[-1] == ">":
            try:
                return self.guild.get_channel(int(str_channel[-19:-1]))
            except ValueError:
                pass
        return None

    async def send_log(self, log_type: str, info: str = "", member: Member = None, fields: list = None, color: hex = 0x3B3B3B):
        channel = utils.get(self.client.get_guild(SERVER_ID).channels, id=CHANNELS["logs"])
        print(f"[{ct()}] {member.id, log_type, info}")
        embed = Embed(title=log_type, description=f"{info}", colour=color, timestamp=datetime.fromtimestamp(time()))
        if member:
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


def setup(client):
    client.add_cog(Admin(client))
