from asyncio.exceptions import TimeoutError

import discord
from discord_components import Button, ButtonStyle
from discord import Embed, utils
from discord.errors import NotFound

from config import ROLES


async def member_control(text, view_permission, bot):
    components = [
        Button(style=ButtonStyle.green, label="Открыть канал", emoji="🌐") if not view_permission else "",
        Button(style=ButtonStyle.red, label="Закрыть канал", emoji="⛔") if view_permission else "",
        Button(style=ButtonStyle.red, label="Забанить участника", emoji="🚷"),
        Button(style=ButtonStyle.green, label="Разбанить участника", emoji="🚹"),
        Button(style=ButtonStyle.blue, label="Установить пароль", emoji="📕") if not view_permission else "",
        Button(style=ButtonStyle.green, label="Пригласить участника", emoji="👥") if not view_permission else "",
    ]
    for _ in range(components.count("")):
        components.remove("")
    m = await text.send(embed=Embed(description="Выберите, что вы хотите сделать:", color=0xF3E400),
                        components=components, delete_after=60.0)
    response = await bot.wait_for("button_click", timeout=60)
    while response.channel != text:
        response = await bot.wait_for("button_click", timeout=60)
    await m.delete()
    return response


async def voice_control_panel(text, voice, member, bot, db):
    async def get_message(mess):
        send = await text.send(mess, delete_after=60.0)
        message = await bot.wait_for("message", timeout=60, check=lambda m: m.author == member and m.channel == text)
        await send.delete()
        return message.content

    m = ""
    channel_overwrites = utils.get(voice.guild.channels, id=voice.id).overwrites_for(utils.get(voice.guild.roles, id=ROLES["everyone"]))
    view_permission = channel_overwrites.view_channel
    speak_permission = channel_overwrites.speak
    try:
        components = [
            Button(style=ButtonStyle.green, label="Изменить название канала", emoji="📝") if voice.name == "Канал для " + member.name else "",
            Button(style=ButtonStyle.green, label="Установить лимит участников", emoji="⭕"),
            Button(style=ButtonStyle.red, label="Замутить всех участников", emoji="😶") if speak_permission or speak_permission is None else
            Button(style=ButtonStyle.green, label="Размутить всех участников", emoji="😄"),
            Button(style=ButtonStyle.blue, label="Замутить/размутить участника", emoji="🎤"),
            Button(style=ButtonStyle.grey, label="Управление приватностью", emoji="🔐")
        ]
        for _ in range(components.count("")):
            components.remove("")
        password = db.select('private_voices', f'channel_owner == {member.id}', 'password')['password']
        password_message = f"\n Пароль: **{password.replace('_', '*_*')}**" if password else ""
        m = await text.send(embed=Embed(description="Панель управления голосовым каналом: \n"
                                                    "Нажимайте на кнопочки и настраивайте Ваш канал под себя."
                                                    f"{password_message}"
                                                    "\nP.S. **Чтобы удалить канал нужно с него выйти**", color=0xF3E400),
                            components=components)
        response = await bot.wait_for("button_click", timeout=300)
        while response.channel != text:
            response = await bot.wait_for("button_click", timeout=300)
        await m.delete()
        m = ""
        if response.component.label == "Управление приватностью":
            response = await member_control(text, view_permission, bot)
        c = Commands(text, voice, member, db)
        match response.component.label:
            case "Открыть канал":
                await c.open()
            case "Закрыть канал":
                await c.close()
            case "Забанить участника":
                await c.ban(await get_message("Упомяните участника или напишите его ник здесь:"))
            case "Разбанить участника":
                await c.unban(await get_message("Упомяните участника или напишите его ник здесь:"))
            case "Изменить название канала":
                await c.name(await get_message("Напишите новое название канала здесь:"))
            case "Установить пароль":
                await c.password(await get_message("Напишите новый пароль для канала здесь:"))
            case "Пригласить участника":
                await c.invite(await get_message("Упомяните участника или напишите его ник здесь:"))
            case "Установить лимит участников":
                await c.limit(await get_message("Напишите число, которое будет ограничением по участникам здесь:"))
            case "Замутить/размутить участника":
                await c.mute(await get_message("Упомяните участника или напишите его ник здесь:"))
            case "Замутить всех участников":
                await c.mute_all()
            case "Размутить всех участников":
                await c.unmute_all()

        return False
    except TimeoutError:
        if m:
            try:
                await m.delete()
            except NotFound:
                return True
        return False
    except NotFound:
        return True
    except AttributeError:
        return True


class Commands:
    def __init__(self, text, voice, member, db):
        self.text = text
        self.voice = voice
        self.member = member
        self.everyone = utils.get(self.voice.guild.roles, id=ROLES["everyone"])
        self.db = db

    async def open(self):
        speak = self.voice.overwrites_for(self.everyone).speak
        await self.voice.set_permissions(self.everyone, view_channel=True, connect=True, speak=speak)
        await self.text.send(embed=Embed(description="Канал открыт для всех", color=0x21F300), delete_after=5.0)

    async def close(self):
        speak = self.voice.overwrites_for(self.everyone).speak
        await self.voice.set_permissions(self.everyone, view_channel=False, connect=True, speak=speak)
        await self.text.send(embed=Embed(description="Канал закрыт для всех", color=0x21F300), delete_after=5.0)

    async def ban(self, ban_member: str):
        member = self.__get_member(ban_member)
        if self.member == member:
            await self.text.send(embed=Embed(description="Вы не можете заблокировать себя", color=0xBF1818), delete_after=5.0)
            return
        if not member:
            await self.text.send(embed=Embed(description="Не верно задан пользователь", color=0xBF1818), delete_after=5.0)
            return
        if self.voice.overwrites_for(member).view_channel is False:
            await self.text.send(embed=Embed(description="Пользователь уже заблокирован", color=0xBF1818), delete_after=5.0)
            return
        if member in self.voice.members:
            await member.move_to(channel=None, reason="Забанен пользователем")
        await self.voice.set_permissions(member, view_channel=False)
        await self.text.send(embed=Embed(description=f"<@{member.id}> заблокирован", color=0x21F300), delete_after=5.0)

    async def unban(self, unban_member):
        member = self.__get_member(unban_member)
        if not member:
            await self.text.send(embed=Embed(description="Не верно задан пользователь", color=0xBF1818), delete_after=5.0)
            return
        if self.voice.overwrites_for(member).view_channel is None:
            await self.text.send(embed=Embed(description="Пользователь не заблокирован", color=0xBF1818), delete_after=5.0)
            return
        await self.voice.set_permissions(member, view_channel=True)
        await self.text.send(embed=Embed(description=f"<@{member.id}> разблокирован", color=0x21F300), delete_after=5.0)

    async def name(self, name):
        if name == " " or name == "":
            await self.text.send(embed=Embed(description="Название не должно быть пустым", color=0xBF1818), delete_after=5.0)
            return
        if len(name) > 100:
            name = name[0:100]
        await self.voice.edit(name=name)
        await self.text.send(embed=Embed(description=f"Название изменено на **{name}**", color=0x21F300), delete_after=5.0)

    async def password(self, password):
        if len(password) <= 10:
            self.db.update("private_voices", f"channel_owner == {self.member.id}", password=password)
        else:
            await self.text.send(embed=Embed(description="Пароль должен состоять из 10 или менее символов", color=0xBF1818), delete_after=5.0)
            return
        await self.text.send(embed=Embed(description=f"Пароль **{password}** установлен", color=0x21F300), delete_after=5.0)

    async def invite(self, invited_member):
        member = self.__get_member(invited_member)
        if self.member == member:
            await self.text.send(embed=Embed(description="Вы не можете пригласить себя", color=0xBF1818), delete_after=5.0)
            return
        if not member:
            await self.text.send(embed=Embed(description="Не верно задан пользователь", color=0xBF1818), delete_after=5.0)
            return
        await self.voice.set_permissions(member, view_channel=True)
        await self.text.send(embed=Embed(description=f"Теперь <@{member.id}> может подключиться к каналу", color=0x21F300), delete_after=5.0)

    async def limit(self, number):
        try:
            lim = int(number)
            if lim < 2:
                await self.text.send(embed=Embed(description="Лимит пользователей не может быть меньше двух", color=0xBF1818), delete_after=5.0)
            elif lim > 99:
                await self.voice.edit(user_limit=False)
                await self.text.send(embed=Embed(description="Лимит пользователей сброшен", color=0x21F300), delete_after=5.0)
            else:
                await self.voice.edit(user_limit=lim)
                await self.text.send(embed=Embed(description=f"Лимит пользователей установлен на **{str(lim)}**", color=0x21F300), delete_after=5.0)
        except ValueError:
            await self.text.send(embed=Embed(description="Не верное значение. Должно быть указано число", color=0xBF1818), delete_after=5.0)

    async def mute(self, mute_member):
        member = self.__get_member(mute_member)
        if self.member == member:
            await self.text.send(embed=Embed(description="Вы не можете замутить себя", color=0xBF1818), delete_after=5.0)
            return
        view_channel = await self.voice.overwrites_for(member).view_channel
        if self.voice.overwrites_for(member).speak is False:
            await self.voice.set_permissions(member, speak=True, view_channel=view_channel)
            await self.text.send(embed=Embed(description=f"<@{member.id}> размучен", color=0x21F300), delete_after=5.0)
        else:
            await self.voice.set_permissions(member, speak=False, view_channel=view_channel)
            await self.text.send(embed=Embed(description=f"<@{member.id}> замучен", color=0x21F300), delete_after=5.0)

    async def mute_all(self):
        view_channel = self.voice.overwrites_for(self.everyone).view_channel
        connect = self.voice.overwrites_for(self.everyone).connect
        await self.voice.set_permissions(utils.get(self.voice.guild.roles, id=ROLES["everyone"]), speak=False, view_channel=view_channel, connect=connect)
        await self.text.send(embed=Embed(description="Все участники замучены", color=0x21F300), delete_after=5.0)

    async def unmute_all(self):
        view_channel = self.voice.overwrites_for(self.everyone).view_channel
        connect = self.voice.overwrites_for(self.everyone).connect
        await self.voice.set_permissions(utils.get(self.voice.guild.roles, id=ROLES["everyone"]), speak=True, view_channel=view_channel, connect=connect)
        await self.text.send(embed=Embed(description="Все участники размучены", color=0x21F300), delete_after=5.0)

    def __get_member(self, str_member: str) -> discord.Member | None:
        if len(str_member) in [21, 22] and str_member[0:2] == "<@" and str_member[-1] == ">":
            try:
                return self.voice.guild.get_member(int(str_member[-19:-1]))
            except ValueError:
                pass
        for user in self.voice.guild.members:
            if user.nick:
                if user.nick.lower() == str_member.lower():
                    return user
            elif user.name.lower() == str_member.lower():
                return user
        return ""
