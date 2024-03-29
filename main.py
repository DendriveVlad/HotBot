import os
import threading
from asyncio import sleep
from time import time, ctime as ct
from random import choice, randint

from nextcord import Intents, utils, Member, VoiceState, errors, AuditLogAction, Guild, User, Message, DMChannel, MessageType, Embed, PermissionOverwrite
from nextcord.ext import tasks, commands

from DataBase import DB
from config import *
from info import send_log
from pv_control_panel import voice_control_panel
from image_processing.UsersInfo import top, level_up, challengePassed
from games.hub import hub
from Mine.MineReq import requests
from Casino import casino

__author__ = "Vladi4ka | DendriveVlad"

db = DB()


class Bot(commands.Bot):
    def __init__(self):
        super().__init__("/", intents=Intents.all())
        self.spam_count = []

    async def on_ready(self):
        guild = self.get_guild(SERVER_ID)
        newbie = utils.get(guild.roles, id=ROLES["Newbie"])
        old = utils.get(guild.roles, id=ROLES["Old"])
        members_id = db.select("users", "", "user_id")
        for member in guild.members:
            if {"user_id": member.id} not in members_id:
                db.insert("users", user_id=member.id, connection_date=int(time()))
            if newbie not in member.roles and old not in member.roles and not member.bot:
                await member.add_roles(newbie)

        if not self.check.is_running():
            self.check.start()
        await hub(utils.get(guild.channels, id=CHANNELS["Games"]), self, db)
        await requests(utils.get(guild.channels, id=CHANNELS["requests"]), self)
        await casino(utils.get(guild.channels, id=CHANNELS["Casino"]), db, self)
        self.loop.create_task(top(utils.get(guild.channels, id=CHANNELS["Top"]), self, db))
        print(ct(), "Hello!")

    @staticmethod
    async def on_member_join(member: Member):
        t = int(time())
        while member.pending:
            await sleep(2)
            if int(time()) - t >= 300:
                try:
                    await member.kick(reason="Не подтвердил правила")
                    return
                except errors.NotFound:
                    return
        if not db.select("users", f"user_id == {member.id}"):
            db.insert("users", user_id=member.id, connection_date=int(time()))
        await member.add_roles(utils.get(member.guild.roles, id=ROLES["Newbie"]))
        await send_log(guild=member.guild, log_type="MemberJoin", info="Подключился к серверу", member=member, color=0x21F300)

    @staticmethod
    async def on_member_remove(member: Member):
        if member.pending:
            return
        mod, reason = None, None
        async for kick in member.guild.audit_logs(limit=3, action=AuditLogAction.kick):
            if int(time()) - int(kick.created_at.timestamp()) <= 50 and kick.target.id == member.id:
                mod = kick.user
                reason = kick.reason
                break
        await send_log(guild=member.guild, log_type="MemberKick" if mod else "MemberLeave", info=f"Кикнут модератором {mod.mention}" if mod else "Покинул сервер", member=member, fields=("Причина:", reason) if reason else None, color=0xBF1818)

    @staticmethod
    async def on_member_ban(guild: Guild, user: User | Member):
        mod, reason = None, None
        async for kick in guild.audit_logs(limit=3, action=AuditLogAction.ban):
            if int(time()) - int(kick.created_at.timestamp()) <= 50 and kick.target.id == user.id:
                mod = kick.user
                reason = kick.reason
                break
        await send_log(guild=guild, log_type="MemberBan", info=f"Забанен модератором {mod.mention}" if mod else "Забанен", member=user, fields=("Причина:", reason) if reason else None, color=0xBF1818)
        db.delete("users", f"user_id == {user.id}")

    async def on_message(self, message: Message):
        if message.author.id == BOT_ID:
            return
        if type(message.channel) is DMChannel:
            await send_log(guild=self.get_guild(SERVER_ID), log_type="Гений", member=message.author, fields=("Пишет мне в ЛС следующее сообщение:", message.content), color=0x766EFF)
            async for h in message.channel.history(limit=10):
                if h.author.id == BOT_ID:
                    return
            await message.reply("Ты чё, дебил что ли? Нахер ты мне пишешь? Я РОБОТ! Я ФИЗИЧЕСКИ НЕ МОГУ ПРОЧИТАТЬ И ОТВЕТИТЬ НА ТВОЁ СООБЩЕНИЕ!")
            if db.select("users", f"user_id == {message.author.id}", "challenge")["challenge"] == 5:
                await challengePassed(self, db, self.get_guild(SERVER_ID).get_member(message.author.id))
            return

        if message.channel.id == CHANNELS["hello"] or message.channel.category_id == CATEGORIES["Minecraft"] or message.channel.id == CHANNELS["discord_updates"] or (message.channel.category_id == CATEGORIES["Bot"] and "https://" not in message.content):
            return

        print(message.author, ">", message.content)

        if utils.get(message.channel.guild.roles, id=ROLES["Newbie"]) in message.author.roles and len(message.author.roles) == 2:
            if "https://" in message.content:
                link = ".".join(message.content[message.content.index("https://"):].split("/")[2].split(".")[-2:])
                if link not in ALLOWED_LINKS:
                    await message.delete()
                    await send_log(guild=message.guild, log_type="StopSpam", member=message.author, fields=("Удалено спам-сообщение:", message.content), color=0xF9BA1C)
                    if self.spam_count.count(message.author.id) >= 2:
                        await message.author.ban(reason="Spam")
                        return
                    self.spam_count.append(message.author.id)
                    await sleep(30)
                    self.spam_count.remove(message.author.id)
                    return

        date = db.select("users", f"user_id == {message.author.id}", "points", "last_message", "challenge", "challenge_progress")
        if message.channel.id in LEVEL_ALLOWED_TEXT_CHANNELS:
            if message.type != MessageType.reply and int(time()) - date["last_message"] > 60 * 60 * 5:
                import difflib
                right_words = ("привет", "прив", "ку", "хай", "здорова", "хеллоу", "здравствуйте", "алоха", "бонжур", "hello", "hi", "bonjour")

                def get_exact_words(input_str):
                    exact_words = difflib.get_close_matches(input_str, right_words, n=1, cutoff=0.7)
                    if len(exact_words) > 0:
                        return exact_words[0]
                    else:
                        return input_str

                words = [get_exact_words(word) for word in message.content.lower().split(' ')]
                if len(words) < 5:
                    for w in right_words:
                        if w in words:
                            await message.reply(choice(("Здорова", "Алохо!", "Привет-амлет!", "Приветствую", "Ну типо привет", "Hi", "Bonjour", "おい")))
                            if db.select("users", f"user_id == {message.author.id}", "challenge")["challenge"] == 5:
                                await challengePassed(self, db, message.author)
                            break

            match date["challenge"]:
                case 1:
                    if message.channel.id == CHANNELS["Memes"]:
                        if message.attachments:
                            db.update("users", f"user_id == {message.author.id}", challenge_progress=date["challenge_progress"] + len(message.attachments))
                            date["challenge_progress"] += len(message.attachments)
                        elif "https://" in message.content or "http://" in message.content:
                            db.update("users", f"user_id == {message.author.id}", challenge_progress=date["challenge_progress"] + message.content.count("https://") + message.content.count("http://"))
                            date["challenge_progress"] += message.content.count("https://") + message.content.count("http://")
                        if date["challenge_progress"] >= 5:
                            await challengePassed(self, db, message.author)
                case 2:
                    db.update("users", f"user_id == {message.author.id}", challenge_progress=date["challenge_progress"] + 1)
                    if date["challenge_progress"] >= 49:
                        await challengePassed(self, db, message.author)
                case 3:
                    if message.type == MessageType.reply:
                        reference = await message.channel.fetch_message(message.reference.message_id)
                        if reference.author != message.author:
                            db.update("users", f"user_id == {message.author.id}", challenge_progress=date["challenge_progress"] + 1)
                            if date["challenge_progress"] >= 19:
                                await challengePassed(self, db, message.author)

            if int(time()) > date["last_message"] + 20:
                db.update("users", f"user_id == '{message.author.id}'", points=date["points"] + 10, last_message=int(time()))
                await level_up(self, date["points"], date["points"] + 10, message.author.id)
        elif message.channel.id == CHANNELS["Flood"] and date["challenge"] == 4:
            if 0 <= randint(0, 99) <= 4:
                await challengePassed(self, db, message.author)

        if message.channel.category_id == CATEGORIES["Voice channels"]:
            await message.delete()
            if message.channel.id == CHANNELS["VC_password"]:
                try:
                    channel = utils.get(message.guild.voice_channels, id=db.select("private_voices", f"password == '{message.content}'", "channel_id")["channel_id"])
                    if channel.overwrites_for(message.author).view_channel is not None:
                        return
                    await channel.set_permissions(message.author, view_channel=True, connect=True, speak=True, stream=True)
                    await message.channel.send(embed=Embed(description=f"<@{message.author.id}>, канал для вас открыт", color=0x21F300), delete_after=5)
                except TypeError:
                    return

    async def on_message_delete(self, message: Message):
        await sleep(0.1)
        if type(message.channel) is DMChannel or message.channel.category_id in CATEGORIES.values() or message.author.id in self.spam_count:
            return

        mod = None
        async for deleted_message in message.guild.audit_logs(limit=3, action=AuditLogAction.message_delete):
            if int(time()) - int(deleted_message.created_at.timestamp()) <= 60 and deleted_message.target.id == message.author.id:
                mod = deleted_message.user
                break

        await send_log(guild=message.guild, log_type="MessageRemove", info=f"Удалено сообщение в канале {message.channel.mention} {'модератором ' + mod.mention if mod else 'пользователем'}", member=message.author,
                       fields=("Сообщение:", message.content[:1000] + ("..." if len(message.content) > 1000 else "") if message.content else "--не текст--"), color=0xBF1818)

    @staticmethod
    async def on_message_edit(before: Message, after: Message):
        if type(before.channel) is DMChannel or before.channel.category_id == CATEGORIES["Bot"] or before.author.id == BOT_ID or before.content == after.content:
            return

        if len(after.content) + len(before.content) <= 256:
            await send_log(guild=before.guild, log_type="MessageEdit", info=f"Изменено сообщение в канале {after.channel.mention}", member=after.author, fields=[("До:", before.content), ("После:", after.content)], color=0x285064)
            return

        index = 0
        for char in after.content:
            if len(before.content) == index + 1:
                await send_log(guild=before.guild, log_type="MessageEdit", info=f"Изменено сообщение в канале {after.channel.mention}", member=after.author,
                               fields=[("До:", before.content[index - 20:]), ("После:", after.content[index - 20:] if len(after.content[index - 20:]) <= 256 else after.content[index - 20:index + 60] + '...')],
                               color=0x285064)
                return

            if before.content[index] != char:
                if index < 11:
                    if len(before.content) > 128:
                        old = before.content[0:128] + "..."
                    else:
                        old = before.content[0:]
                    if len(after.content) > 128:
                        new = after.content[0:128]
                    else:
                        new = after.content[0:] + "..."

                else:
                    if len(before.content) > 128 + index:
                        old = "..." + before.content[index - 10:index + 128] + "..."
                    else:
                        old = "..." + before.content[index - 10:]
                    if len(after.content) > 128 + index:
                        new = "..." + after.content[index - 10:index + 128] + "..."
                    else:
                        new = "..." + after.content[index - 10:]

                await send_log(guild=before.guild, log_type="MessageEdit", info=f"Изменено сообщение в канале {after.channel.mention}", member=after.author, fields=[("До:", old), ("После:", new)], color=0x285064)

                return
            index += 1

    async def on_voice_state_update(self, member: Member, before: VoiceState, after: VoiceState):
        if not after.channel and before.channel:
            await send_log(guild=member.guild, log_type="VoiceDisconnect", info="Вышел из голосового канала", member=member)
            date = db.select("users", f"user_id == {member.id}", "points", "talk_time", "challenge")
            new_points = date["points"] + ((int(time()) - date["talk_time"]) // 300) * 7
            db.update("users", f"user_id == {member.id}", points=new_points, talk_time=0)
            if date["challenge"] and (int(time()) - date["talk_time"]) // 1800:
                await challengePassed(self, db, member)
            await level_up(self, date["points"], new_points, member.id)
        elif after.channel != before.channel:
            if after.channel == CHANNELS["AFK"]:
                date = db.select("users", f"user_id == {member.id}", "points", "talk_time", "challenge")
                new_points = date["points"] + ((int(time()) - date["talk_time"]) // 300) * 7
                db.update("users", f"user_id == {member.id}", points=new_points, talk_time=0)
                if date["challenge"] and (int(time()) - date["talk_time"]) // 1800:
                    await challengePassed(self, db, member)
                await level_up(self, date["points"], new_points, member.id)
            await send_log(guild=member.guild, log_type="VoiceConnect", info=f"Зашёл в канал {after.channel}", member=member)
            if not before.channel:
                db.update("users", f"user_id == {member.id}", talk_time=int(time()))

        if after.channel == before.channel:
            return

        while before.channel:
            serv = member.guild
            date = db.select("private_voices", f"channel_owner == {member.id}", "channel_id", "control_id")
            if before.channel.id not in IGNORE_VC and before.channel.category_id == CATEGORIES["Voice channels"]:
                if len(before.channel.members) != 0:
                    if not (len(before.channel.members) == 1 and before.channel.members[0].bot):
                        if after.channel:
                            if after.channel.id == CHANNELS["createVC"] and date:
                                await member.move_to(channel=before.channel, reason="Возвращение в личный канал")
                                return
                            break
                        if not date:
                            return

                if date:
                    if after.channel:
                        if after.channel.id == CHANNELS["createVC"]:
                            await member.move_to(channel=utils.get(serv.voice_channels, id=date["channel_id"]), reason="Возвращение в личный канал")
                            return
                else:
                    da = db.select("private_voices", f"channel_id == {before.channel.id}", "control_id", "channel_owner")
                    date = {
                        "channel_id": before.channel.id,
                        "control_id": da["control_id"],
                    }
                    member = self.get_user(da["channel_owner"])
                db.delete("private_voices", f"channel_owner == {member.id}")
                voice, text = utils.get(serv.voice_channels, id=date["channel_id"]), utils.get(serv.text_channels, id=date["control_id"])
                await voice.delete()
                await text.delete()
                await send_log(guild=serv, log_type="RemovePrivateChannel", info=f"Приватный канал удалён", member=member)
            break
        if after.channel:
            if after.channel.id == CHANNELS["createVC"]:
                if db.select("private_voices", f"channel_owner == {member.id}"):
                    return
                serv = member.guild
                overwrites_text = {
                    serv.default_role: PermissionOverwrite(view_channel=False),
                    member: PermissionOverwrite(view_channel=True, send_messages=True)
                }
                voice = await serv.create_voice_channel(f"Канал для {member.name}", category=after.channel.category)
                await voice.set_permissions(member, view_channel=True, speak=True)
                text = await serv.create_text_channel("панель-управления-каналом", category=after.channel.category, overwrites=overwrites_text)
                await send_log(guild=serv, log_type="CreatePrivateChannel", info=f"Приватный канал создан", member=member)
                try:
                    await member.move_to(channel=voice, reason="Создал канал для себя")
                except errors.HTTPException:
                    await voice.delete()
                    await text.delete()
                    await send_log(guild=serv, log_type="RemovePrivateChannel", info=f"Приватный канал удалён", member=member)
                    return
                db.insert("private_voices", channel_id=voice.id, channel_owner=member.id, control_id=text.id)
                await text.send(f"<@{member.id}>", delete_after=1)
                while True:
                    if await voice_control_panel(text, voice, member, self, db):
                        break

    @staticmethod
    async def on_member_update(before: Member, after: Member):
        mod, reason = None, None
        async for member_update in before.guild.audit_logs(limit=3, action=AuditLogAction.member_update):
            if int(time()) - int(member_update.created_at.timestamp()) <= 50 and member_update.target.id == before.id:
                mod = member_update.user
                reason = member_update.reason
                break
        if before.roles != after.roles:
            for role in after.roles:
                if role not in before.roles:
                    await send_log(guild=before.guild, log_type="MemberRoleGet", info=f"Получил роль {role.mention} {'с помощью модератора ' + mod.mention if mod else ''}", member=after, color=0xD88A1F)
                    break
            for role in before.roles:
                if role not in after.roles:
                    await send_log(guild=before.guild, log_type="MemberRoleRemove", info=f"Потерял роль {role.mention} {'с помощью модератора ' + mod.mention if mod else ''}", member=after, color=0xD85A1F)
                    break
            new = utils.get(before.guild.roles, id=ROLES["Newbie"])
            old = utils.get(before.guild.roles, id=ROLES["Old"])
            if new in after.roles and old in after.roles:
                if new not in before.roles:
                    await after.remove_roles(old)
                elif old not in before.roles:
                    await after.remove_roles(new)
        elif before.communication_disabled_until != after.communication_disabled_until:
            if after.communication_disabled_until:
                await send_log(guild=before.guild, log_type="MemberTimeoutGet", info=f"Получил мут {'от модератора ' + mod.mention if mod else ''}", member=after, fields=[("Мут будет действовать до:", f"<t:{int(after.communication_disabled_until.timestamp())}>"), ("Причина:", reason) if reason else None], color=0xE5AE46)
            elif before.communication_disabled_until:
                await send_log(guild=before.guild, log_type="MemberTimeoutEnd", info=f"Закончился мут {'с помощью модератора ' + mod.mention if mod else ''}", member=after, color=0x8CE546)
        elif before.nick != after.nick:
            await send_log(guild=before.guild, log_type="MemberNickUpdate", info=f"Изменён ник {'модератором ' + mod.mention if mod and mod.id != before.id else ''}", member=after, fields=[("До:", before.nick if before.nick else before.name),
                                                                                                                                                                                             ("После:", after.nick if after.nick else after.name)], color=0xE5AE46)

    @tasks.loop(minutes=30)
    async def check(self):
        dt = db.select("info", "", "datetime")["datetime"]
        guild = self.get_guild(SERVER_ID)

        if int(time()) - dt >= 60 * 60 * 24 * 2:
            db.update("info", f"datetime=={dt}", datetime=dt + (60 * 60 * 24))

        channel = utils.get(guild.channels, id=CHANNELS["Online"])
        online_members = guild.member_count
        for member in guild.members:
            member_data = db.select("users", f"user_id == {member.id}", "connection_date", "points", "gold", "role", "role_paid_time")
            if str(member.status) == "offline":
                online_members -= 1
            elif utils.get(guild.roles, id=ROLES["Newbie"]) in member.roles:
                if member_data:
                    if int(time()) - member_data["connection_date"] > 60 * 60 * 24 * 30 * 6 and member_data["points"] >= 1000:
                        await member.remove_roles(utils.get(guild.roles, id=ROLES["Newbie"]))
                        await member.add_roles(utils.get(guild.roles, id=ROLES["Old"]))
            if member_data and member_data["role"] and int(time()) - member_data["role_paid_time"] > 60 * 60 * 24 * 7:
                if member_data["gold"] < 100:
                    await guild.get_role(member_data["role"]).delete(reason="Не хватает золота для списания")
                    db.update("users", f"user_id == {member.id}", role=0, role_paid_time=0)
                else:
                    db.update("users", f"user_id == {member.id}", gold=member_data["gold"] - 100, role_paid_time=member_data["role_paid_time"] + 60 * 60 * 24 * 7)
                    await send_log(guild, log_type="PrivateRolePayment", info=f"Роль продлена", member=member)

        new_name = f"ОНЛАЙН: {online_members}/{guild.member_count}"
        if new_name == channel.name:
            return
        await channel.edit(name=f"ОНЛАЙН: {online_members}/{guild.member_count}")


class BotThread(threading.Thread):
    def __init__(self, *args, **kwargs):
        super(BotThread, self).__init__(*args, **kwargs)
        self.client = None
        self._stop = threading.Event()

    def stop(self):
        self.client.loop.stop()
        self.client.close()
        self._stop.set()

    def run(self):
        self.client = Bot()
        self.client.remove_command("help")
        for file in os.listdir("./cogs"):
            if file.endswith(".py"):
                self.client.load_extension(f"cogs.{file[:-3]}")
        self.client.run(TOKEN)
