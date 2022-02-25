from nextcord import slash_command, Embed, Interaction, Member, SlashOption, TextChannel
from nextcord.ext import commands
from nextcord.errors import NotFound

from config import *
from DataBase import DB

db = DB()


class Admin(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.guild = None
        self.channel = None

    @slash_command(name="ban", description="Заблокировать участника сервера", guild_ids=[SERVER_ID])
    async def ban(self, interaction: Interaction, str_member: str, reason: str):
        self.__check_data(interaction.guild)
        member = self.__get_member(str_member)
        if not member:
            await interaction.response.send_message(embed=Embed(title="Не верно задан пользователь", colour=0xBF1818), ephemeral=True)
            return
        if member.bot:
            await interaction.response.send_message(embed=Embed(title="Использование команд на ботов отключено", colour=0xBF1818), ephemeral=True)
            return
        await member.ban(reason=reason)
        await interaction.response.send_message(embed=Embed(title="Участник заблокирован", colour=0x21F300), ephemeral=False)

    @slash_command(name="unban", description="Разблокировать участника сервера", guild_ids=[SERVER_ID])
    async def unban(self, interaction: Interaction, str_member: str):
        self.__check_data(interaction.guild)
        member = self.__get_member(str_member)
        if not member:
            await interaction.response.send_message(embed=Embed(title="Не верно задан пользователь", colour=0xBF1818), ephemeral=True)
            return
        if member.bot:
            await interaction.response.send_message(embed=Embed(title="Использование команд на ботов отключено", colour=0xBF1818), ephemeral=True)
            return
        try:
            await member.unban()
            await interaction.response.send_message(embed=Embed(title="Участник разблокирован", colour=0x21F300), ephemeral=False)
        except NotFound:
            await interaction.response.send_message(embed=Embed(title="Участник НЕ заблокирован", colour=0xBF1818), ephemeral=False)

    @slash_command(name="channel-ban", description="Заблокировать участника в определённом канале", guild_ids=[SERVER_ID])
    async def channel_ban(self, interaction: Interaction, str_member: str, str_channel: str):
        self.__check_data(interaction.guild)
        member = self.__get_member(str_member)
        ban_channel = self.__get_channel(str_channel)
        if not member:
            await interaction.response.send_message(embed=Embed(title="Не верно задан пользователь", colour=0xBF1818), ephemeral=True)
            return
        if member.bot:
            await interaction.response.send_message(embed=Embed(title="Использование команд на ботов отключено", colour=0xBF1818), ephemeral=True)
            return
        if not ban_channel:
            await interaction.response.send_message(embed=Embed(title="Не верно задан канал", colour=0xBF1818), ephemeral=True)
            return
        await ban_channel.set_permissions(member, read_messages=False)
        await interaction.response.send_message(embed=Embed(title=f"Участник заблокирован в канале {ban_channel}", colour=0x21F300), ephemeral=False)

    @slash_command(name="channel-unban", description="Разблокировать  участника в определённом канале", guild_ids=[SERVER_ID])
    async def channel_unban(self, interaction: Interaction, str_member: str, str_channel: str):
        self.__check_data(interaction.guild)
        member = self.__get_member(str_member)
        ban_channel = self.__get_channel(str_channel)
        if not member:
            await interaction.response.send_message(embed=Embed(title="Не верно задан пользователь", colour=0xBF1818), ephemeral=True)
            return
        if member.bot:
            await interaction.response.send_message(embed=Embed(title="Использование команд на ботов отключено", colour=0xBF1818), ephemeral=True)
            return
        if not ban_channel:
            await interaction.response.send_message(embed=Embed(title="Не верно задан канал", colour=0xBF1818), ephemeral=True)
            return
        await ban_channel.set_permissions(member, read_messages=None)
        await interaction.response.send_message(embed=Embed(title=f"Участник разблокирован в канале {ban_channel}", colour=0x21F300), ephemeral=False)

    @slash_command(name="set", description="Изменить количество золота или опыта участника но новое значение", guild_ids=[SERVER_ID])
    async def set(self, interaction: Interaction, thing: str = SlashOption(name="thing", description="gold/points", choices={"gold": "gold", "points": "points"}),
                  str_member: str = None, count: int = 0):
        self.__check_data(interaction.guild)
        member = self.__get_member(str_member)
        if not member:
            await interaction.response.send_message(embed=Embed(title="Не верно задан пользователь", colour=0xBF1818), ephemeral=True)
            return
        if member.bot:
            await interaction.response.send_message(embed=Embed(title="Использование команд на ботов отключено", colour=0xBF1818), ephemeral=True)
            return
        if thing not in ("gold", "points"):
            await interaction.response.send_message(embed=Embed(title="Можно изменять только золото или очки (gold/points)", colour=0xBF1818), ephemeral=True)
            return
        try:
            if int(count) < 0:
                await interaction.response.send_message(embed=Embed(title="Участник не может иметь отрицательное количество золота или очков", colour=0xBF1818), ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message(embed=Embed(title="Не верно задано число", colour=0xBF1818), ephemeral=True)
            return
        eval(f"db.update('users', 'user_id == {member.id}', {thing}={int(count)})")
        await interaction.response.send_message(embed=Embed(title=f"Данные участника {member} обновлены", colour=0x21F300), ephemeral=False)

    @slash_command(name="remove", description="Удалить определённое количество золота или опыта у участника", guild_ids=[SERVER_ID])
    async def remove(self, interaction: Interaction, thing: str = SlashOption(name="thing", description="gold/points", choices={"gold": "gold", "points": "points"}),
                     str_member: str = None, count: int = 0):
        self.__check_data(interaction.guild)
        member = self.__get_member(str_member)
        if not member:
            await interaction.response.send_message(embed=Embed(title="Не верно задан пользователь", colour=0xBF1818), ephemeral=True)
            return
        if member.bot:
            await interaction.response.send_message(embed=Embed(title="Использование команд на ботов отключено", colour=0xBF1818), ephemeral=True)
            return
        if thing not in ("gold", "points"):
            await interaction.response.send_message(embed=Embed(title="Можно изменять только золото или очки (gold/points)", colour=0xBF1818), ephemeral=True)
            return
        try:
            if int(count) < 0:
                await interaction.response.send_message(embed=Embed(title="Участник не может иметь отрицательное количество золота или очков", colour=0xBF1818), ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message(embed=Embed(title="Не верно задано число", colour=0xBF1818), ephemeral=True)
            return
        eval(f"db.update('users', 'user_id == {member.id}', {thing}={db.select('users', f'user_id == {member.id}', thing)[thing] - int(count)})")
        await interaction.response.send_message(embed=Embed(title=f"Данные участника {member} обновлены", colour=0x21F300), ephemeral=False)

    @slash_command(name="add", description="Добавить определённое количество золота или опыта участнику", guild_ids=[SERVER_ID])
    async def add(self, interaction: Interaction, thing: str = SlashOption(name="thing", description="gold/points", choices={"gold": "gold", "points": "points"}),
                  str_member: str = None, count: int = 0):
        self.__check_data(interaction.guild)
        member = self.__get_member(str_member)
        if not member:
            await interaction.response.send_message(embed=Embed(title="Не верно задан пользователь", colour=0xBF1818), ephemeral=True)
            return
        if member.bot:
            await interaction.response.send_message(embed=Embed(title="Использование команд на ботов отключено", colour=0xBF1818), ephemeral=True)
            return
        if thing not in ("gold", "points"):
            await interaction.response.send_message(embed=Embed(title="Можно изменять только золото или очки (gold/points)", colour=0xBF1818), ephemeral=True)
            return
        try:
            if int(count) < 0:
                await interaction.response.send_message(embed=Embed(title="Участник не может иметь отрицательное количество золота или очков", colour=0xBF1818), ephemeral=True)
                return
        except ValueError:
            await interaction.response.send_message(embed=Embed(title="Не верно задано число", colour=0xBF1818), ephemeral=True)
            return
        eval(f"db.update('users', 'user_id == {member.id}', {thing}={db.select('users', f'user_id == {member.id}', thing)[thing] + int(count)})")
        await interaction.response.send_message(embed=Embed(title=f"Данные участника {member} обновлены", colour=0x21F300), ephemeral=False)

    def __check_data(self, guild):
        if not self.guild:
            self.guild = guild
        if not self.channel:
            self.channel = self.guild.get_channel(CHANNELS["staff"])

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


def setup(client):
    client.add_cog(Admin(client))
