from random import randint, choice

from nextcord import slash_command, Interaction, SlashOption, File
from nextcord.ext import commands

from config import *
from DataBase import DB
from info import *

db = DB()

roles_colors = {
    "Персиковый": 0xFF6B6B,
    "Красный": 0xDE4141,
    "Тёмно-красный": 0xA12929,
    "Оранжевый": 0xE67828,
    "Жёлтый": 0xE9C635,
    "Лаймовый": 0xA8D03E,
    "Зелёный": 0x49C131,
    "Тёмно-зелёный": 0x418434,
    "Бирюзовый": 0x40CFAA,
    "Голубой": 0x20CBD6,
    "Синий": 0x2C6CD5,
    "Тёмно-синий": 0x2F3089,
    "Сиреневый": 0xA28EDD,
    "Фиолетовый": 0x9D2BD6,
    "Розовый": 0xDE67F3,
    "Пурпурный": 0xC81C75,
    "HEX": 0x000000
}


class Commands(commands.Cog):
    def __init__(self, client):
        self.client = client
        self.guild = None

    @slash_command(name="help", description="Получить список всех команд", guild_ids=[SERVER_ID])
    async def help(self, interaction: Interaction):
        message = "**/создать-роль, /изменить-роль, /удалить-роль** - команды для управление персональной ролью\n" \
                  "**/передать-золото** - команда для передачи золота любому участнику\n" \
                  "**/бросить-кубик** - команда, которая даёт случайное число от 1 до 6 (работает только в <#714058786679291924>)\n" \
                  "**/ударить, /обнять, /погладить, /укусить, /признаться-в-любви** - роле-плейные команды, которые уведомляют участников, которым они адресованы (работает только в <#714058786679291924>)"
        if list(filter(lambda role: role.id in (ROLES["Admin"], ROLES["Moder"], ROLES["Owner"], ROLES["Vlad"]), interaction.user.roles)):
            message += "\n\nКоманды для модераторов:\n" \
                       "**/заблокировать-в-канале, /разблокировать-в-канале** - команды для блокировки или разблокировки участников в определённых каналах\n" \
                       "**/о-участнике** - команда выдаёт полную информацию о участнике, которая хранится в базе данных"
        if list(filter(lambda role: role.id in (ROLES["Admin"], ROLES["Owner"], ROLES["Vlad"]), interaction.user.roles)):
            message += "\n\nКоманды для администраторов:\n" \
                       "**/изменить, /удалить, /добавить** - команды изменения золота или опыта участникам"
        await interaction.response.send_message(embed=Embed(title="Команды сервера:", description=message, color=0xEAD029), ephemeral=True)

    @slash_command(name="создать-роль", description="Создать собственную роль (Нужно: 5-й уровень и 300 Золота)", guild_ids=[SERVER_ID])
    async def create_role(self, interaction: Interaction,
                          role_name: str = SlashOption(name="название", description="Название Вашей роли"),
                          role_color: str = SlashOption(name="цвет", description="Цвет Вашей роли")):
        user_db = db.select("users", f"user_id == {interaction.user.id}", "points", "gold", "role")
        if user_db["role"]:
            await interaction.response.send_message(embed=Embed(description="У Вас уже есть собственная роль", color=0xBF1818), ephemeral=True)
            return
        if await get_level(user_db["points"]) < 5 or user_db["gold"] < 300:
            await interaction.response.send_message(embed=Embed(description="Для создания роли необходим иметь **5-й** уровень и **300** золота", color=0xBF1818), ephemeral=True)
            return
        if role_color.lower() == "hex":
            await interaction.response.send_message("Вместо **HEX** и других цветов Вы можете ввести значение цвета взятого с этого сайта: https://htmlcolorcodes.com/\n"
                                                    "Подберите там для себя цвет и введите значение, которое находится под цветом рядом с знаком **#**", file=File(fp="hex.png"), ephemeral=True)
            return
        try:
            color = roles_colors[role_color]
        except KeyError:
            try:
                color = eval("0x" + role_color)
            except SyntaxError:
                await interaction.response.send_message(embed=Embed(description="Не верно задан цвет", color=0xBF1818), ephemeral=True)
                return
        role = await interaction.guild.create_role(reason="Создал приватную роль", name=role_name, colour=color)
        await role.edit(position=len(interaction.guild.roles) - 3)
        await interaction.user.add_roles(role)
        db.update("users", f"user_id == {interaction.user.id}", gold=user_db["gold"] - 300, role=role.id, role_paid_time=int(time()))
        await interaction.response.send_message(embed=Embed(title="Роль создана", description=f"Вы получили свою новую роль {role.mention}.\n"
                                                                                              f"Для поддержания роли требуется **100** золота в неделю. Первое списание будет через неделю. Если у Вас будет недостаточно золота, то роль удалится.\n"
                                                                                              f"Изменение цвета или названия роли стоит **200** золота.", color=0x21F300), ephemeral=True)

    @slash_command(name="изменить-роль", description="Изменить цвет или название роли (Нужно: 200 Золота)", guild_ids=[SERVER_ID])
    async def change_role(self, interaction: Interaction,
                          role_name: str = SlashOption(name="название", description="Название Вашей роли", default="", required=False),
                          role_color: str = SlashOption(name="цвет", description="Цвет Вашей роли", default="", required=False)):
        if not (role_color or role_name):
            await interaction.response.send_message(embed=Embed(description="Вы не задали нужных ни одного изменения", color=0xBF1818), ephemeral=True)
            return
        user_db = db.select("users", f"user_id == {interaction.user.id}", "gold", "role")
        if not user_db["role"]:
            await interaction.response.send_message(embed=Embed(description="У Вас нет собственной роли", color=0xBF1818), ephemeral=True)
            return
        if user_db["gold"] < 200:
            await interaction.response.send_message(embed=Embed(description="Для изменения роли необходим иметь **200** золота", color=0xBF1818), ephemeral=True)
            return
        color = 0
        if role_color:
            if role_color.lower() == "hex":
                await interaction.response.send_message("Вместо **HEX** и других цветов Вы можете ввести значение цвета взятого с этого сайта: https://htmlcolorcodes.com/\n"
                                                        "Подберите там для себя цвет и введите значение, которое находится под цветом рядом с знаком **#**", file=File(fp="hex.png"), ephemeral=True)
                return
            try:
                color = roles_colors[role_color]
            except KeyError:
                try:
                    color = eval("0x" + role_color)
                except SyntaxError:
                    await interaction.response.send_message(embed=Embed(description="Не верно задан цвет", color=0xBF1818), ephemeral=True)
                    return
        role = interaction.guild.get_role(user_db["role"])
        if role_color and role_name:
            await role.edit(name=role_name, colour=color)
        elif role_color:
            await role.edit(colour=color)
        else:
            await role.edit(name=role_name)
        db.update("users", f"user_id == {interaction.user.id}", gold=user_db["gold"] - 100)
        await interaction.response.send_message(embed=Embed(title="Роль изменена", color=0x21F300), ephemeral=True)

    @slash_command(name="удалить-роль", description="Удалить свою роль", guild_ids=[SERVER_ID])
    async def delete_role(self, interaction: Interaction):
        user_db = db.select("users", f"user_id == {interaction.user.id}", "role")
        if not user_db["role"]:
            await interaction.response.send_message(embed=Embed(description="У Вас нет собственной роли", color=0xBF1818), ephemeral=True)
            return
        role = interaction.guild.get_role(user_db["role"])
        await role.delete(reason="Удалена пользователем")
        db.update("users", f"user_id == {interaction.user.id}", role=0, role_paid_time=0)
        await interaction.response.send_message(embed=Embed(title="Роль удалена", color=0x21F300), ephemeral=True)

    @create_role.on_autocomplete("role_color")
    @change_role.on_autocomplete("role_color")
    async def color(self, interaction: Interaction, role_color: str):
        if not role_color:
            await interaction.response.send_autocomplete(roles_colors.keys())
            return
        await interaction.response.send_autocomplete([color for color in roles_colors.keys() if role_color.lower() in color.lower()])

    @slash_command(name="передать-золото", description="Передать участнику золото (комиссия 7%)", guild_ids=[SERVER_ID])
    async def pay(self, interaction: Interaction,
                  member: Member = SlashOption(name="кому", description="Упоминание участника"),
                  count: int = SlashOption(name="сколько", description="Количество")):
        if db.select("users", f"user_id == {interaction.user.id}", "gold")["gold"] < count:
            await interaction.response.send_message(embed=Embed(description="У Вас нет столько золота", color=0xBF1818), ephemeral=True)
            return
        elif count < 10:
            await interaction.response.send_message(embed=Embed(description="Вы не можете передать меньше 10 золота", color=0xBF1818), ephemeral=True)
            return
        db.update("users", f"user_id == {member.id}", gold=db.select("users", f"user_id == {member.id}", "gold")["gold"] + int(count * 0.93))
        db.update("users", f"user_id == {interaction.user.id}", gold=db.select("users", f"user_id == {interaction.user.id}", "gold")["gold"] - count)
        await interaction.response.send_message(embed=Embed(title="Золото передано", description=f"{member.mention} получил {int(count * 0.93)} золота", color=0x21F300), ephemeral=True)

    @slash_command(name="бросить-кубик", description="Бросить кубик и получить случайное число от 1 до 6 (стоимость: 2 золота)", guild_ids=[SERVER_ID])
    async def roll(self, interaction: Interaction):
        if interaction.channel.id != CHANNELS["Flood"]:
            await interaction.response.send_message(embed=Embed(description="Команда работает только в канале <#714058786679291924>", color=0xBF1818), ephemeral=True)
            return
        member_gold = db.select("users", f"user_id == {interaction.user.id}", "gold")["gold"]
        if member_gold < 2:
            await interaction.response.send_message(embed=Embed(description="У Вас недостаточно золота", color=0xBF1818), ephemeral=True)
            return
        db.update("users", f"user_id == {interaction.user.id}", gold=member_gold - 2)
        embed = Embed(title="Бросил кубик", description=f"Ему выпало **{randint(1, 6)}**", color=0x21F300)
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user.avatar.url if interaction.user.avatar else Embed.Empty
        )
        await interaction.response.send_message(embed=embed)

    @slash_command(name="ударить", description="Ударить участника (стоимость: 40 золота)", guild_ids=[SERVER_ID])
    async def kick(self, interaction: Interaction,
                   member: Member = SlashOption(name="кого", description="Упоминание участника")):
        if interaction.channel.id != CHANNELS["Flood"]:
            await interaction.response.send_message(embed=Embed(description="Команда работает только в канале <#714058786679291924>", color=0xBF1818), ephemeral=True)
            return
        member_gold = db.select("users", f"user_id == {interaction.user.id}", "gold")["gold"]
        if member_gold < 40:
            await interaction.response.send_message(embed=Embed(description="У Вас недостаточно золота", color=0xBF1818), ephemeral=True)
            return
        db.update("users", f"user_id == {interaction.user.id}", gold=member_gold - 40)
        embed = Embed(color=0x21F300)
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user.avatar.url if interaction.user.avatar else Embed.Empty
        )
        embed.set_image(url=choice((
            "https://c.tenor.com/SddY3UqUHOAAAAAC/kick-cartoon.gif",
            "https://c.tenor.com/7rtyWDJlCQYAAAAC/anime-kick.gif",
            "https://c.tenor.com/7NqY13faRvQAAAAC/taehyung-bts.gif",
            "https://c.tenor.com/4zwRLrLMGm8AAAAC/chifuyu-chifuyu-kick.gif",
            "https://c.tenor.com/wOCOTBGZJyEAAAAC/chikku-neesan-girl-hit-wall.gif",
            "https://c.tenor.com/ZElYwhbPYvAAAAAd/one-punch-man-suiryu.gif",
            "https://c.tenor.com/VST-qfF1wqQAAAAC/take-that-cat.gif"
        )))
        await interaction.response.send_message(f'{interaction.user.mention} {choice(("ударил", "прописал", "сломал лицо", "вдарил", "избил", "отмудохал"))} {member.mention}', embed=embed)

    @slash_command(name="обнять", description="Обнять участника (стоимость: 10 золота)", guild_ids=[SERVER_ID])
    async def hug(self, interaction: Interaction,
                  member: Member = SlashOption(name="кого", description="Упоминание участника")):
        if interaction.channel.id != CHANNELS["Flood"]:
            await interaction.response.send_message(embed=Embed(description="Команда работает только в канале <#714058786679291924>", color=0xBF1818), ephemeral=True)
            return
        member_gold = db.select("users", f"user_id == {interaction.user.id}", "gold")["gold"]
        if member_gold < 10:
            await interaction.response.send_message(embed=Embed(description="У Вас недостаточно золота", color=0xBF1818), ephemeral=True)
            return
        db.update("users", f"user_id == {interaction.user.id}", gold=member_gold - 10)
        embed = Embed(color=0x21F300)
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user.avatar.url if interaction.user.avatar else Embed.Empty
        )
        embed.set_image(url=choice((
            "https://c.tenor.com/DxMIq9-tS5YAAAAC/milk-and-mocha-bear-couple.gif",
            "https://c.tenor.com/XyMvYx1xcJAAAAAC/super-excited.gif",
            "https://c.tenor.com/jX1-mxefJ54AAAAC/cat-hug.gif",
            "https://c.tenor.com/qF7mO4nnL0sAAAAC/abra%C3%A7o-hug.gif",
            "https://c.tenor.com/Eq-j-4gF7fQAAAAC/mlp-my-little-pony.gif",
            "https://c.tenor.com/pE-DR_hXKMEAAAAC/hug-sully.gif",
            "https://c.tenor.com/IRES9fJEe3cAAAAd/cat-cute-cat.gif"
        )))
        await interaction.response.send_message(f'{interaction.user.mention} {choice(("крепко обнял(а)", "обнял(а)", "приобнял(а)", "прыгнул(а) в объятия"))} {member.mention}', embed=embed)

    @slash_command(name="погладить", description="Погладить участника по голове (стоимость: 15 золота)", guild_ids=[SERVER_ID])
    async def pat(self, interaction: Interaction,
                  member: Member = SlashOption(name="кого", description="Упоминание участника")):
        if interaction.channel.id != CHANNELS["Flood"]:
            await interaction.response.send_message(embed=Embed(description="Команда работает только в канале <#714058786679291924>", color=0xBF1818), ephemeral=True)
            return
        member_gold = db.select("users", f"user_id == {interaction.user.id}", "gold")["gold"]
        if member_gold < 15:
            await interaction.response.send_message(embed=Embed(description="У Вас недостаточно золота", color=0xBF1818), ephemeral=True)
            return
        db.update("users", f"user_id == {interaction.user.id}", gold=member_gold - 15)
        embed = Embed(color=0x21F300)
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user.avatar.url if interaction.user.avatar else Embed.Empty
        )
        embed.set_image(url=choice((
            "https://c.tenor.com/JsjHFFy5O40AAAAC/kitten-pat.gif",
            "https://c.tenor.com/svNEvYEag3QAAAAC/pat-anime-pat.gif",
            "https://c.tenor.com/jX1-mxefJ54AAAAC/cat-hug.gif",
            "https://c.tenor.com/7lSNoSmQV-UAAAAC/funny-dog.gif",
            "https://c.tenor.com/g_61F9hKhV4AAAAC/pat-head-pat.gif",
            "https://c.tenor.com/3PjRNS8paykAAAAC/pat-pat-head.gif",
            "https://c.tenor.com/f5asRSsfl-wAAAAC/good-boy-pat-on-head.gif"
        )))
        await interaction.response.send_message(f'{interaction.user.mention} {choice(("погладил(а) по голове", "погладил(а)"))} {member.mention}', embed=embed)

    @slash_command(name="укусить", description="Укусить участника (стоимость: 25 золота)", guild_ids=[SERVER_ID])
    async def bite(self, interaction: Interaction,
                  member: Member = SlashOption(name="кого", description="Упоминание участника")):
        if interaction.channel.id != CHANNELS["Flood"]:
            await interaction.response.send_message(embed=Embed(description="Команда работает только в канале <#714058786679291924>", color=0xBF1818), ephemeral=True)
            return
        member_gold = db.select("users", f"user_id == {interaction.user.id}", "gold")["gold"]
        if member_gold < 25:
            await interaction.response.send_message(embed=Embed(description="У Вас недостаточно золота", color=0xBF1818), ephemeral=True)
            return
        db.update("users", f"user_id == {interaction.user.id}", gold=member_gold - 25)
        embed = Embed(color=0x21F300)
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user.avatar.url if interaction.user.avatar else Embed.Empty
        )
        embed.set_image(url=choice((
            "https://c.tenor.com/VXqink0UhmcAAAAi/bite.gif",
            "https://c.tenor.com/sMgdnhlBl3QAAAAC/spongebob-wacky.gif",
            "https://c.tenor.com/R_Oju0Tb-iUAAAAC/rip-bite.gif",
            "https://c.tenor.com/9dOzFGFZxnoAAAAC/bite-anime.gif",
            "https://c.tenor.com/pqQRoXGfjY8AAAAC/ha-yeonsoo-pointing.gif",
            "https://c.tenor.com/Xpv7HTk-DIYAAAAC/mad-angry.gif",
            "https://c.tenor.com/OYcQ7KWydG4AAAAC/azumanga-cat-bite-anime.gif"
        )))
        await interaction.response.send_message(f'{interaction.user.mention} {choice(("укусил(а)", "куснул(а)", "впился(-ась) зубами в", "попробовал(а) на вкус"))} {member.mention}', embed=embed)

    @slash_command(name="признаться-в-любви", description="Рассказать участнику о своих чувствах (стоимость: 80 золота)", guild_ids=[SERVER_ID])
    async def love(self, interaction: Interaction,
                  member: Member = SlashOption(name="кому", description="Упоминание участника")):
        if interaction.channel.id != CHANNELS["Flood"]:
            await interaction.response.send_message(embed=Embed(description="Команда работает только в канале <#714058786679291924>", color=0xBF1818), ephemeral=True)
            return
        member_gold = db.select("users", f"user_id == {interaction.user.id}", "gold")["gold"]
        if member_gold < 80:
            await interaction.response.send_message(embed=Embed(description="У Вас недостаточно золота", color=0xBF1818), ephemeral=True)
            return
        db.update("users", f"user_id == {interaction.user.id}", gold=member_gold - 80)
        embed = Embed(color=0x21F300)
        embed.set_author(
            name=interaction.user,
            icon_url=interaction.user.avatar.url if interaction.user.avatar else Embed.Empty
        )
        embed.set_image(url=choice((
            "https://c.tenor.com/zFzhOAJ8rqwAAAAC/love.gif",
            "https://c.tenor.com/sck9cmGxe84AAAAC/te-amo.gif",
            "https://c.tenor.com/A8Q-EMt540oAAAAi/ye-lo-dil-sticker.gif",
            "https://c.tenor.com/DZll3gcSP04AAAAC/love.gif",
            "https://c.tenor.com/_OamUWxaZd0AAAAC/love-i-love-you.gif",
            "https://c.tenor.com/xzecWUs1-lUAAAAC/anime-kawaii.gif",
            "https://c.tenor.com/-er9VWbtMYwAAAAC/te-amo-heart.gif"
        )))
        await interaction.response.send_message(f'{interaction.user.mention} {choice(("влюбился(-ася)", "признаётся в любви", "любит", "не может жить без", "даёт предложение руки и сердца", "без ума от"))} {member.mention}', embed=embed)

    async def cog_application_command_before_invoke(self, interaction: Interaction) -> None:
        if not self.guild:
            self.guild = interaction.guild
        try:
            await send_log(guild=self.guild, log_type="CommandUse", info=f"Использует команду **/{' '.join((interaction.data['name'], *['<@' + i['value'] + '>' if i['name'] in ('кому', 'кого') else str(i['value']) for i in interaction.data['options']]))}**", member=interaction.user)
        except KeyError:
            await send_log(guild=self.guild, log_type="CommandUse", info=f"Использует команду **/{interaction.data['name']}**", member=interaction.user)


def setup(client):
    client.add_cog(Commands(client))
