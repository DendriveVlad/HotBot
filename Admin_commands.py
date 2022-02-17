from discord import Embed


async def get_command(command, channel, db):
    match command:
        case "ban", str_member, reason:
            member = __get_member(str_member, channel)
            if not member:
                await channel.send(embed=Embed(description="Не верно задана пользователь", colour=0xBF1818))
                return
            if member.bot:
                await channel.send(embed=Embed(description="Использование команд на ботов отключено", colour=0xBF1818))
                return
            await member.ban(reason=reason)
            await channel.send(embed=Embed(description="Участник заблокирован", colour=0x21F300))
        case "unban", str_member:
            member = __get_member(str_member, channel)
            if not member:
                await channel.send(embed=Embed(description="Не верно задан пользователь", colour=0xBF1818))
                return
            if member.bot:
                await channel.send(embed=Embed(description="Использование команд на ботов отключено", colour=0xBF1818))
                return
            await member.unban()
            await channel.send(embed=Embed(description="Участник разблокирован", colour=0x21F300))
        case "channel-ban", str_member, str_channel:
            member = __get_member(str_member, channel)
            ban_channel = __get_channel(str_channel, channel)
            if not member:
                await channel.send(embed=Embed(description="Не верно задан пользователь", colour=0xBF1818))
                return
            if member.bot:
                await channel.send(embed=Embed(description="Использование команд на ботов отключено", colour=0xBF1818))
                return
            if not ban_channel:
                await channel.send(embed=Embed(description="Не верно задан канал", colour=0xBF1818))
                return
            await ban_channel.set_permissions(member, read_messages=False)
            await channel.send(embed=Embed(description=f"Участник заблокирован в канале {ban_channel.mention}", colour=0x21F300))
        case "channel-unban", str_member, str_channel:
            member = __get_member(str_member, channel)
            ban_channel = __get_channel(str_channel, channel)
            if not member:
                await channel.send(embed=Embed(description="Не верно задан пользователь", colour=0xBF1818))
                return
            if member.bot:
                await channel.send(embed=Embed(description="Использование команд на ботов отключено", colour=0xBF1818))
                return
            if not ban_channel:
                await channel.send(embed=Embed(description="Не верно задан канал", colour=0xBF1818))
                return
            await ban_channel.set_permissions(member, read_messages=None)
            await channel.send(embed=Embed(description=f"Участник разблокирован в канале {ban_channel.mention}", colour=0x21F300))
        case "set", thing, str_member, count:
            member = __get_member(str_member, channel)
            if not member:
                await channel.send(embed=Embed(description="Не верно задан пользователь", colour=0xBF1818))
                return
            if member.bot:
                await channel.send(embed=Embed(description="Использование команд на ботов отключено", colour=0xBF1818))
                return
            if thing not in ("gold", "points"):
                await channel.send(embed=Embed(description="Можно изменять только золото или очки (gold/points)", colour=0xBF1818))
                return
            try:
                if int(count) < 0:
                    await channel.send(embed=Embed(description="Участник не может иметь отрицательное количество золота или очков", colour=0xBF1818))
                    return
            except ValueError:
                await channel.send(embed=Embed(description="Не верно задано число", colour=0xBF1818))
                return
            eval(f"db.update('users', 'user_id == {member.id}', {thing}={int(count)})")
            await channel.send(embed=Embed(description=f"Данные участника {member.mention} обновлены", colour=0x21F300))
        case "remove", thing, str_member, count:
            member = __get_member(str_member, channel)
            if not member:
                await channel.send(embed=Embed(description="Не верно задан пользователь", colour=0xBF1818))
                return
            if member.bot:
                await channel.send(embed=Embed(description="Использование команд на ботов отключено", colour=0xBF1818))
                return
            if thing not in ("gold", "points"):
                await channel.send(embed=Embed(description="Можно изменять только золото или очки (gold/points)", colour=0xBF1818))
                return
            try:
                if int(count) > db.select("users", f"user_id == {member.id}", thing)[thing]:
                    await channel.send(embed=Embed(description="Участник не может иметь отрицательное количество золота или очков", colour=0xBF1818))
                    return
            except ValueError:
                await channel.send(embed=Embed(description="Не верно задано число", colour=0xBF1818))
                return
            eval(f"db.update('users', 'user_id == {member.id}', {thing}={db.select('users', f'user_id == {member.id}', thing)[thing] - int(count)})")
            await channel.send(embed=Embed(description=f"Данные участника {member.mention} обновлены", colour=0x21F300))
        case "add", thing, str_member, count:
            member = __get_member(str_member, channel)
            if not member:
                await channel.send(embed=Embed(description="Не верно задан пользователь", colour=0xBF1818))
                return
            if member.bot:
                await channel.send(embed=Embed(description="Использование команд на ботов отключено", colour=0xBF1818))
                return
            if thing not in ("gold", "points"):
                await channel.send(embed=Embed(description="Можно изменять только золото или очки (gold/points)", colour=0xBF1818))
                return
            try:
                if db.select("users", f"user_id == {member.id}", thing)[thing] > 300000 or int(count) > 300000:
                    await channel.send(embed=Embed(description="У участника уже слишком много золота или очков, либо вы выдаёте слишком много", colour=0xBF1818))
                    return
            except ValueError:
                await channel.send(embed=Embed(description="Не верно задано число", colour=0xBF1818))
                return
            eval(f"db.update('users', 'user_id == {member.id}', {thing}={db.select('users', f'user_id == {member.id}', thing)[thing] + int(count)})")
            await channel.send(embed=Embed(description=f"Данные участника {member.mention} обновлены", colour=0x21F300))
        case _:
            await channel.send(embed=Embed(description="Не верно задана команда", colour=0xBF1818))


def __get_member(str_member, channel):
    if len(str_member) in [21, 22] and str_member[0:2] == "<@" and str_member[-1] == ">":
        try:
            return channel.guild.get_member(int(str_member[-19:-1]))
        except ValueError:
            pass
    return ""


def __get_channel(str_channel, channel):
    if len(str_channel) == 21 and str_channel[0:2] == "<#" and str_channel[-1] == ">":
        try:
            return channel.guild.get_сhannel(int(str_channel[-19:-1]))
        except ValueError:
            pass
    return ""
