from datetime import datetime
from time import time, ctime as ct

from nextcord import slash_command, Embed, Interaction, Member, SlashOption, TextChannel, utils
from nextcord.ext import commands

from config import *
from DataBase import DB
from info import send_log

db = DB()


class Admin(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.guild = None
        self.channel = None

    @slash_command(name="заблокировать-в-канале", description="Заблокировать участника в определённом канале", guild_ids=[SERVER_ID])
    async def channel_ban(self, interaction: Interaction,
                          member: Member = SlashOption(name="кого", description="Упоминание участника"),
                          use_channel: str = SlashOption(name="где", description="Упоминание канала")):
        channel = self.__get_channel(use_channel)
        if not await self.__checks(interaction, "23456", member=member, channel=channel):
            return

        await channel.set_permissions(member, read_messages=False)
        await interaction.response.send_message(embed=Embed(title=f"Участник заблокирован в канале {channel}", colour=0x21F300), ephemeral=False)

    @slash_command(name="разблокировать-в-канале", description="Разблокировать  участника в определённом канале", guild_ids=[SERVER_ID])
    async def channel_unban(self, interaction: Interaction,
                            member: Member = SlashOption(name="кого", description="Упоминание участника"),
                            use_channel: str = SlashOption(name="где", description="Упоминание канала")):
        channel = self.__get_channel(use_channel)
        if not await self.__checks(interaction, "23456", member=member, channel=channel):
            return

        await channel.set_permissions(member, read_messages=None)
        await interaction.response.send_message(embed=Embed(title=f"Участник разблокирован в канале {channel}", colour=0x21F300), ephemeral=False)

    @slash_command(name="изменить", description="Изменить количество золота или опыта участника но новое значение", guild_ids=[SERVER_ID])
    async def set(self, interaction: Interaction,
                  thing: str = SlashOption(name="что", description="Золото/Очки", choices={"Золото": "gold", "Очки": "points"}),
                  member: Member = SlashOption(name="кому", description="Упоминание пользователя"),
                  count: int = SlashOption(name="сколько", description="Количество")):
        if not await self.__checks(interaction, "13457", member=member, count=count):
            return

        eval(f"db.update('users', 'user_id == {member.id}', {thing}={int(count)})")
        await interaction.response.send_message(embed=Embed(title=f"Данные участника {member} обновлены", colour=0x21F300), ephemeral=False)

    @slash_command(name="удалить", description="Удалить определённое количество золота или опыта у участника", guild_ids=[SERVER_ID])
    async def remove(self, interaction: Interaction,
                     thing: str = SlashOption(name="что", description="Золото/Очки", choices={"Золото": "gold", "Очки": "points"}),
                     member: Member = SlashOption(name="кому", description="Упоминание пользователя"),
                     count: int = SlashOption(name="сколько", description="Количество")):
        if not await self.__checks(interaction, "13457", member=member, count=count):
            return

        eval(f"db.update('users', 'user_id == {member.id}', {thing}={db.select('users', f'user_id == {member.id}', thing)[thing] - int(count)})")
        await interaction.response.send_message(embed=Embed(title=f"Данные участника {member} обновлены", colour=0x21F300), ephemeral=False)

    @slash_command(name="добавить", description="Добавить определённое количество золота или опыта участнику", guild_ids=[SERVER_ID])
    async def add(self, interaction: Interaction,
                  thing: str = SlashOption(name="что", description="Золото/Очки", choices={"Золото": "gold", "Очки": "points"}),
                  member: Member = SlashOption(name="кому", description="Упоминание пользователя"),
                  count: int = SlashOption(name="сколько", description="Количество")):
        if not await self.__checks(interaction, "13457", member=member, count=count):
            return

        eval(f"db.update('users', 'user_id == {member.id}', {thing}={db.select('users', f'user_id == {member.id}', thing)[thing] + int(count)})")
        await interaction.response.send_message(embed=Embed(title=f"Данные участника {member} обновлены", colour=0x21F300), ephemeral=False)

    async def cog_application_command_before_invoke(self, interaction: Interaction) -> None:
        if not self.guild:
            self.guild = interaction.guild
        if not self.channel:
            self.channel = self.guild.get_channel(CHANNELS["staff"])

        await send_log(guild=self.guild, log_type="CommandUse", info=f"Использует команду **/{' '.join((interaction.data['name'], *['<@' + i['value'] + '>' if i['name'] in ('кому', 'кого') else str(i['value']) for i in interaction.data['options']]))}**", member=interaction.user)

    async def __checks(self, interaction: Interaction, checks, **other) -> bool:
        """
        :param checks:
            1 - Проверка на права администратора
            2 - Проверка на права модератора
            3 - Проверка на админ-бот канал
            4 - Проверка на заданного бота-пользователя
            5 - Проверка на правильность заданного канала
            6 - Проверка на отрицательное значение в count
            7 - Проверка на слишком большое значение в count
        """
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

        if "3" in checks and interaction.channel != self.channel:
            await interaction.response.send_message(embed=Embed(title=f"Данное действие разрешено только в канале #{self.channel.name}", colour=0xBF1818), ephemeral=True)
            return False

        if "4" in checks and other["member"].bot:
            await interaction.response.send_message(embed=Embed(title="Использование команд на ботов отключено", colour=0xBF1818), ephemeral=True)
            return False

        if "5" in checks and not other["channel"]:
            await interaction.response.send_message(embed=Embed(title="Не верно задан канал", colour=0xBF1818), ephemeral=True)
            return False

        if "6" in checks and int(other["count"]) < 0:
            await interaction.response.send_message(embed=Embed(title="Участник не может иметь отрицательное количество золота или очков", colour=0xBF1818), ephemeral=True)
            return False

        if "7" in checks and (int(other["count"]) > 500000):
            await interaction.response.send_message(embed=Embed(title="Введено слишком большое число", colour=0xBF1818), ephemeral=True)
            return False

        return True

    def __get_channel(self, str_channel) -> TextChannel | None:
        if len(str_channel) == 21 and str_channel[0:2] == "<#" and str_channel[-1] == ">":
            try:
                return self.guild.get_channel(int(str_channel[-19:-1]))
            except ValueError:
                pass
        return None


def setup(client):
    client.add_cog(Admin(client))
