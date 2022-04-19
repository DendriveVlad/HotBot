from asyncio import sleep
from time import time

from nextcord import File, Embed, utils, ButtonStyle, Interaction
from nextcord.errors import NotFound, DiscordServerError
from nextcord.ui import Button, View

from image_processing.top import get_top
from image_processing.rank import get_rank
from config import LEVEL_POINTS, CHANNELS, SERVER_ID, ROLES
from info import send_log


class Click(Button):
    def __init__(self, style, label, emoji, custom_id, db, bot):
        super().__init__(style=style, label=label, emoji=emoji, custom_id=custom_id)
        self.db = db
        self.bot = bot

    async def callback(self, interaction: Interaction):
        if int(time()) - self.db.select("users", f"user_id == {interaction.user.id}", "last_info")["last_info"] <= 15:
            await interaction.response.pong()
            return
        match interaction.data["custom_id"]:
            case "get_level":
                self.db.update("users", f"user_id == {interaction.user.id}", last_info=int(time()))
                await interaction.response.defer(ephemeral=True, with_message=True)
                await interaction.followup.send(file=File(fp=get_rank(interaction.channel.guild, interaction.user.id, self.db)), ephemeral=True)
            case "get_award":
                date = self.db.select("users", f"user_id == {interaction.user.id}", "points", "gold", "last_reward", "rewards_count")
                dt = self.db.select("info", "", "datetime")["datetime"]
                if int(time()) - dt >= 60 * 60 * 24 * 2:
                    self.db.update("info", f"datetime=={dt}", datetime=dt + (60 * 60 * 24))
                    await interaction.response.send_message(embed=Embed(description=f"Данные обновлены, нажмите на получение ежедневной награды ещё раз", color=0x21F300), ephemeral=True)
                    return
                if int(time()) - date["last_reward"] <= 60 * 60 * 24:
                    await interaction.response.send_message(embed=Embed(description=f"<@{interaction.user.id}>, Вы сегодня уже получили ежедневную награду", color=0xBF1818), ephemeral=True)
                    self.db.update("users", f"user_id == {interaction.user.id}", last_info=int(time()))
                else:
                    if int(time()) - date["last_reward"] < 60 * 60 * 24 * 2:
                        date["rewards_count"] += 1
                    else:
                        date["rewards_count"] = 1
                    if date["rewards_count"] > 7:
                        date["rewards_count"] = 7
                    level = 0
                    for lvl, need_points in LEVEL_POINTS.items():
                        if date["points"] < need_points:
                            level = lvl - 1
                            break
                    plus_gold = 5 + 3 * date["rewards_count"] + (4 if date["rewards_count"] == 7 else 0)
                    bonus_gold_level = plus_gold * (0.02 * level)

                    percent = 0
                    for role in interaction.user.roles:
                        if role.id in (ROLES["Old"], ROLES["Sponsor1"]) and percent == 0:
                            percent = 0.05
                        elif role.id in (ROLES["Booster"], ROLES["Jedi"], ROLES["Sith"], ROLES["Sponsor2"]) and percent < 0.1:
                            percent = 0.1
                        elif role.id == ROLES["Sponsor3"]:
                            percent = 0.2
                            break
                        elif role.id == ROLES["Sponsor4"]:
                            percent = 0.3
                            break
                        elif role.id == ROLES["Sponsor5"]:
                            percent = 0.4
                            break
                    bonus_gold_status = plus_gold * percent

                    plus_exp = 25 + (5 * date["rewards_count"]) * ((date["rewards_count"] // 2) + 1) + (35 if date["rewards_count"] == 7 else 0)
                    self.db.update("users", f"user_id == {interaction.user.id}", points=date["points"] + plus_exp, gold=date["gold"] + plus_gold + int(bonus_gold_level + bonus_gold_status), last_reward=dt + (60 * 60 * 24), rewards_count=date["rewards_count"])
                    mess_level = f"(+{int(bonus_gold_level + bonus_gold_status)}: " \
                                 f"{('бонус за уровень ' + str(2 * level) + '%' if bonus_gold_level else '') + (', ' if bonus_gold_level and bonus_gold_status else '') + ('бонус за статус ' + str(int(percent * 100)) + '%' if bonus_gold_level else '')})" if bonus_gold_level or bonus_gold_status else ""

                    await interaction.response.send_message(
                        embed=Embed(title="Поздравляю!", description=f"<@{interaction.user.id}>, Вы получили: \n"
                                                                     f"Опыт в размере **{plus_exp}** единиц, \n"
                                                                     f"Золото в размере **{plus_gold}** единиц {mess_level}", color=0x58A3FC), ephemeral=True
                    )
                    await level_up(self.bot, date["points"], date["points"] + plus_exp, interaction.user.id)


async def top(channel, bot, db):
    top_message = None
    while True:
        top_image = File(fp=get_top(channel.guild, db))
        if top_message:
            await top_message.delete()
        else:
            await channel.purge()
            award = View(timeout=None)
            award.add_item(Click(style=ButtonStyle.primary, label="Получить ежедневную награду", emoji="💰", custom_id="get_award", db=db, bot=bot))
            await channel.send(embed=Embed(description="**Время ожидания между запросами 15 секунд** \n"
                                                       "**Топ обновляется каждые 10 минут \n**"
                                                       "Нажмите ниже, чтобы получить ежедневную награду \n"
                                                       "(**Если вы получаете ежедневную награду несколько раз подряд, то она возрастает**)"), view=award)
        try:
            level = View(timeout=None)
            level.add_item(Click(style=ButtonStyle.success, label="Узнать свой уровень", emoji="🔝", custom_id="get_level", db=db, bot=bot))
            top_message = await channel.send(file=top_image, view=level)
        except DiscordServerError:
            continue
        await sleep(600)


async def level_up(bot, old_points, new_points, member_id):
    if new_points < 1060 or old_points > 258000:
        return
    for level, points in LEVEL_POINTS.items():
        if old_points < points <= new_points:
            channel = utils.get(bot.get_guild(SERVER_ID).channels, id=CHANNELS["Top"])
            await channel.send(f"<@{member_id}>", embed=Embed(description=f"Поздравляю с достижением нового уровня!\n"
                                                                          f"Теперь Ваш уровень: **{level}**", colour=0x21F300), delete_after=20)
            await send_log(guild=channel.guild, log_type="MemberNewLevel", info=f"Получил уровень {level}", member=bot.get_user(member_id))

            if level == 30:
                await channel.send(embed=Embed(description=f"😱 <@{member_id}> достиг последнего уровня!", color=0xFF6060), delete_after=3600)
            return
