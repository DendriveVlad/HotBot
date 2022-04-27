from decimal import Decimal
from asyncio import sleep
from random import choices, randint
from time import time

from nextcord import TextChannel, Embed, ButtonStyle, Interaction, SelectOption
from nextcord.ui import View, button, Select

from info import send_log
from image_processing.UsersInfo import challengePassed

game_costs = [10, 20, 50, 100, 500, 1000]

emoji_numbers = {
    1: "1️⃣",
    2: "2️⃣",
    3: "3️⃣",
    4: "4️⃣",
    5: "5️⃣",
    6: "6️⃣"
}

slots = {
    "7️⃣": "0.8",
    "🔔": "0.6",
    "🍒": "0.4",
    "🍌": "0.3",
    "🍎": "0.2",
    "💩": "0.1",
    "❌": "0.0"
}

default_slots_chance = ["7️⃣", "🔔", "🔔", "🍒", "🍒", "🍒", "🍌", "🍌", "🍌", "🍌", "🍎", "🍎", "🍎", "🍎", "🍎", "💩", "💩", "💩", "💩", "💩", "❌", "❌", "❌", "❌", "❌"]


class SlotsChoice(Select):
    def __init__(self, db, user_id, bot):
        self.db = db
        self.bot = bot
        user_gold = db.select("users", f"user_id == {user_id}", "gold")["gold"]
        super(SlotsChoice, self).__init__(
            placeholder="Нажмите и выберите число",
            options=[SelectOption(label=str(cost)) for cost in (filter(lambda x: x <= user_gold, game_costs))])

    async def callback(self, interaction: Interaction):
        slots_chance = default_slots_chance.copy()
        match int(self.values[0]):
            case 50:
                slots_chance.remove("❌")
            case 100:
                slots_chance.remove("❌")
                slots_chance.remove("❌")
                slots_chance.remove("💩")
            case 500:
                slots_chance.remove("❌")
                slots_chance.remove("❌")
                slots_chance.remove("❌")
                slots_chance.remove("💩")
                slots_chance.remove("💩")
                slots_chance.remove("🍎")
            case 1000:
                slots_chance.remove("❌")
                slots_chance.remove("❌")
                slots_chance.remove("❌")
                slots_chance.remove("❌")
                slots_chance.remove("💩")
                slots_chance.remove("💩")
                slots_chance.remove("💩")
                slots_chance.remove("🍎")
                slots_chance.remove("🍎")

        result = ["❓", "❓", "❓"]
        await interaction.response.send_message("Крутим.\n❓❓❓", ephemeral=True)
        intermediate = slots_chance.copy()
        for i in range(1, 10):
            intermediate = choices(intermediate, k=i % 3 + 1)
            if not i % 3:
                result[result.index("❓")] = intermediate[0]
                intermediate = slots_chance.copy()
            await interaction.edit_original_message(content=f"Крутим{'.' * (i % 3 + 1)}\n" + "".join(result))
            await sleep(0.5)
        await interaction.edit_original_message(content="".join(result))
        gold_multiply = sum(map(lambda x: Decimal(slots[x]), result)) * (3 if result.count(result[0]) == 3 else 1)
        profit = int(int(self.values[0]) * (gold_multiply - 1))
        if gold_multiply == 1:
            await interaction.followup.send(embed=Embed(title="Вы вышли в 0", colour=0xEAD445), ephemeral=True)
        elif int(gold_multiply):
            if gold_multiply == 7.2:
                await interaction.followup.send(embed=Embed(title=f"НЕВОЗМОЖНО! ДЖЕКПОТ!\n"
                                                                  f"Вы выиграли {profit} золота", colour=0x21F300), ephemeral=True)
            elif gold_multiply > 2.4:
                await interaction.followup.send(embed=Embed(title=f"Поздравляю, Вы выбили 3 в ряд!\n"
                                                                  f"Вы выиграли {profit} золота", colour=0x21F300), ephemeral=True)
            else:
                await interaction.followup.send(embed=Embed(title=f"Вы выиграли {profit} золота", colour=0x21F300), ephemeral=True)
        else:
            await interaction.followup.send(embed=Embed(title=f"Вы проиграли {abs(profit)} золота", colour=0xBF1818), ephemeral=True)
        user_db = self.db.select("users", f"user_id == {interaction.user.id}", "gold", "points", "challenge", "challenge_progress")
        self.db.update("users", f"user_id == {interaction.user.id}", gold=user_db["gold"] + profit, points=user_db["points"] + 20, last_info=int(time()))
        await send_log(interaction.guild, log_type="CasinoResult", info=f"Результат игры: {profit} золота", member=interaction.user)
        if user_db["challenge"] == 7:
            self.db.update("users", f"user_id == {interaction.user.id}", challenge_progress=user_db["challenge_progress"] + 1)
            if user_db["challenge_progress"] >= 4:
                await challengePassed(self.bot, self.db, interaction.user)
        self.view.stop()


class Dice(View):
    def __init__(self, db, user_id, bot):
        super(Dice, self).__init__()
        self.db = db
        self.bot = bot
        self.add_item(Select(placeholder="Нажмите и выберите число (золото)", options=[SelectOption(label=str(cost)) for cost in (filter(lambda x: x <= db.select("users", f"user_id == {user_id}", "gold")["gold"], game_costs))]))
        self.add_item(Select(placeholder="Нажмите и выберите число (сумма чисел на костях)", options=[SelectOption(label=str(n)) for n in range(2, 13)]))

    async def interaction_check(self, interaction: Interaction):
        children: list[Select] = self.children
        if children[0].values and children[1].values:
            gold = int(children[0].values[0])
            dice_num = int(children[1].values[0])
            await interaction.response.send_message("Бросаю кубики...", ephemeral=True)
            await sleep(1)
            dices = []
            for i in range(randint(5, 12)):
                dices = [randint(1, 6), randint(1, 6)]
                await interaction.edit_original_message(content=emoji_numbers[dices[0]] + " " + emoji_numbers[dices[1]])
                await sleep(0.35)
            difference = abs(sum(dices) - dice_num)
            win = {
                0: 1.8,
                1: 1.5,
                2: 1.0,
                3: 0.8,
                4: 0.6,
                5: 0.2
            }
            profit = int(win[difference] * gold) - gold if difference in win else -gold
            if not difference:
                await interaction.followup.send(embed=Embed(title=f"НЕ МОЖЕТ БЫТЬ! Вы точно угадали выпавшее число\n"
                                                                  f"За это вы выиграли {profit} золота", colour=0x21F300), ephemeral=True)
            elif difference < 2:
                await interaction.followup.send(embed=Embed(title=f"Разница составила {difference}\n"
                                                                  f"Вы выиграли {profit} золота", colour=0x21F300), ephemeral=True)
            elif difference == 2:
                await interaction.followup.send(embed=Embed(title=f"Разница составила {difference}\n"
                                                                  f"Вы вышли в 0", colour=0xEAD445), ephemeral=True)
            else:
                await interaction.followup.send(embed=Embed(title=f"Разница составила {difference}\n"
                                                                  f"Вы проиграли {abs(profit)} золота", colour=0xBF1818), ephemeral=True)
            user_db = self.db.select("users", f"user_id == {interaction.user.id}", "gold", "points", "challenge", "challenge_progress")
            self.db.update("users", f"user_id == {interaction.user.id}", gold=user_db["gold"] + profit, points=user_db["points"] + 20, last_info=int(time()))
            await send_log(interaction.guild, log_type="CasinoResult", info=f"Результат игры: {profit} золота", member=interaction.user)
            if user_db["challenge"] == 7:
                self.db.update("users", f"user_id == {interaction.user.id}", challenge_progress=user_db["challenge_progress"] + 1)
                if user_db["challenge_progress"] >= 4:
                    await challengePassed(self.bot, self.db, interaction.user)
            self.stop()
        else:
            await interaction.response.defer()


class Snail(View):
    def __init__(self, original_interaction, cost):
        super(Snail, self).__init__()
        self.original_interaction: Interaction = original_interaction
        self.cost = cost
        self.profit = -cost
        self.place = 10
        self.chance = 10
        self.fall = False
        self.win = False
        self.places = {
            9: 0.5,
            8: 1.0,
            7: 1.1,
            6: 1.2,
            5: 1.4,
            4: 1.6,
            3: 1.8,
            2: 2.0,
            1: 2.5,
            0: 3.0
        }

    @button(label="Сделать шаг", style=ButtonStyle.success, emoji="⬅")
    async def step(self, _, interaction: Interaction):
        await interaction.response.pong()
        self.place -= 1
        if randint(1, 100) <= self.chance:
            self.fall = True
            await self.original_interaction.edit_original_message(content="✴️" * 11 + "\n🟫" + "🟦" * (self.place - 1) + "✴️" + "🟦" * (9 - self.place) + "🟫",
                                                                  embed=Embed(description=f"Вы упали", colour=0xBF1818),
                                                                  )
            self.stop()
            return
        self.chance += 5
        self.profit = int(self.cost * self.places[self.place] - self.cost)
        if self.place:
            await self.original_interaction.edit_original_message(content="✴️" * self.place + "🐌" + "✴️" * (10 - self.place) + "\n""🟫🟦🟦🟦🟦🟦🟦🟦🟦🟦🟫",
                                                                  embed=Embed(description=f"Вы получите: {self.profit} золота\n"
                                                                                          f"Шанс упасть на следующей плитке: {self.chance}%\n"
                                                                                          f"Пройдя следующую плитку Вы получите: {int(self.cost * self.places[self.place - 1] - self.cost)} золота"),
                                                                  )
        else:
            await self.original_interaction.edit_original_message(content="🐌" + "✴️" * 10 + "\n""🟫🟦🟦🟦🟦🟦🟦🟦🟦🟦🟫",
                                                                  embed=Embed(description=f"Вы прошли", colour=0x21F300))
            self.win = True
            self.stop()

    @button(label="Остановиться", style=ButtonStyle.secondary, emoji="🛑")
    async def stop_game(self, _, interaction: Interaction):
        await interaction.response.pong()
        await self.original_interaction.edit_original_message(content="✴️" * self.place + "🐌" + "✴️" * (10 - self.place) + "\n""🟫🟦🟦🟦🟦🟦🟦🟦🟦🟦🟫",
                                                              embed=Embed(description=f"Вы остановились", colour=0xEAD445))
        self.stop()


class MoneySnail(Select):
    def __init__(self, db, user_id, bot):
        super(MoneySnail, self).__init__(placeholder="Нажмите и выберите число (золото)", options=[SelectOption(label=str(cost)) for cost in (filter(lambda x: x <= db.select("users", f"user_id == {user_id}", "gold")["gold"], game_costs))])
        self.db = db
        self.bot = bot

    async def callback(self, interaction: Interaction):
        view = Snail(interaction, int(self.values[0]))
        await interaction.response.send_message("✴️✴️✴️✴️✴️✴️✴️✴️✴️✴️🐌\n"
                                                "🟫🟦🟦🟦🟦🟦🟦🟦🟦🟦🟫",
                                                embed=Embed(description=f"Вы получите: {view.profit} золота\n"
                                                                        f"Шанс упасть на следующей плитке: 10%\n"
                                                                        f"Пройдя следующую плитку Вы получите: {int(view.cost * view.places[view.place - 1] - view.cost)} золота"),
                                                view=view,
                                                ephemeral=True)
        await view.wait()
        if view.fall:
            if view.profit < view.cost // -2:
                await interaction.followup.send(embed=Embed(title=f"Вы проиграли {abs(view.profit)} золота", colour=0xBF1818), ephemeral=True)
            else:
                await interaction.followup.send(embed=Embed(title=f"Вы проиграли {view.cost // 2} золота", colour=0xBF1818), ephemeral=True)
                view.profit = view.cost // -2
        elif view.win:
            await interaction.followup.send(embed=Embed(title=f"ВЫ СМОГЛИ ПОМОЧЬ УЛИТКИ ПРОЙТИ ХРУПКИЙ ЛЁД!.\n"
                                                              f"Вы выиграли {view.profit} золота", colour=0x21F300), ephemeral=True)
        else:
            if not view.profit:
                await interaction.followup.send(embed=Embed(title=f"Вы вышли в 0", colour=0xEAD445), ephemeral=True)
            elif view.profit > 0:
                await interaction.followup.send(embed=Embed(title=f"Вы выиграли {view.profit} золота", colour=0x21F300), ephemeral=True)
            else:
                await interaction.followup.send(embed=Embed(title=f"Вы проиграли {view.profit} золота", colour=0xBF1818), ephemeral=True)
        user_db = self.db.select("users", f"user_id == {interaction.user.id}", "gold", "points", "challenge", "challenge_progress")
        self.db.update("users", f"user_id == {interaction.user.id}", gold=user_db["gold"] + view.profit, points=user_db["points"] + 20, last_info=int(time()))
        await send_log(interaction.guild, log_type="CasinoResult", info=f"Результат игры: {view.profit} золота", member=interaction.user)
        if user_db["challenge"] == 7:
            self.db.update("users", f"user_id == {interaction.user.id}", challenge_progress=user_db["challenge_progress"] + 1)
            if user_db["challenge_progress"] >= 4:
                await challengePassed(self.bot, self.db, interaction.user)
        self.view.stop()


class CasinoChoices(View):
    def __init__(self, db, bot):
        super(CasinoChoices, self).__init__(timeout=None)
        self.db = db
        self.bot = bot

    @button(label="Игровой автомат", style=ButtonStyle.success, emoji="🎰")
    async def slots(self, _, interaction: Interaction):
        if int(time()) - self.db.select("users", f"user_id == {interaction.user.id}", "last_info")["last_info"] <= 15:
            await interaction.response.pong()
            return
        if self.db.select("users", f"user_id == {interaction.user.id}", "gold")["gold"] < 10:
            await interaction.response.send_message(embed=Embed(title="У Вас недостаточно золота для игры в казино", colour=0xBF1818), ephemeral=True)
            return
        view = View()
        view.add_item(SlotsChoice(self.db, interaction.user.id, self.bot))
        await interaction.response.send_message("Выберите сколько Вы хотите поставить золота (Чем больше золота, тем выше шанс победить!)", ephemeral=True, view=view)
        await send_log(interaction.guild, log_type="CasinoPlay", info="Запустил Игровой автомат", member=interaction.user)

    @button(label="Кости удачи", style=ButtonStyle.success, emoji="🎲")
    async def dice(self, _, interaction: Interaction):
        if int(time()) - self.db.select("users", f"user_id == {interaction.user.id}", "last_info")["last_info"] <= 15:
            await interaction.response.pong()
            return
        if self.db.select("users", f"user_id == {interaction.user.id}", "gold")["gold"] < 10:
            await interaction.response.send_message(embed=Embed(title="У Вас недостаточно золота для игры в казино", colour=0xBF1818), ephemeral=True)
            return
        view = Dice(self.db, interaction.user.id, self.bot)
        await interaction.response.send_message("Выберите сколько Вы хотите поставить золота и на какое число Вы ставите.\n"
                                                "(Чем ближе Ваше число будет к выпавшему, тем больше Вы получите золота)", ephemeral=True, view=view)
        await send_log(interaction.guild, log_type="CasinoPlay", info="Запустил Кости удачи", member=interaction.user)

    @button(label="Неуклюжая улитка", style=ButtonStyle.success, emoji="🐌")
    async def snail(self, _, interaction: Interaction):
        if int(time()) - self.db.select("users", f"user_id == {interaction.user.id}", "last_info")["last_info"] <= 15:
            await interaction.response.pong()
            return
        if self.db.select("users", f"user_id == {interaction.user.id}", "gold")["gold"] < 10:
            await interaction.response.send_message(embed=Embed(title="У Вас недостаточно золота для игры в казино", colour=0xBF1818), ephemeral=True)
            return
        view = View()
        view.add_item(MoneySnail(self.db, interaction.user.id, self.bot))
        await interaction.response.send_message("**Суть игры:** Помочь улитке пройти по хрупкому льду. Чем дальше вы пройдёте, тем больше шанс, что лёд треснет и улитка провалится. "
                                                "Если улитка упадёт, то вы получите только половину от вложенного золота\n"
                                                "Выберите сколько Вы хотите поставить золота", ephemeral=True, view=view)
        await send_log(interaction.guild, log_type="CasinoPlay", info="Запустил Неуклюжую улитку", member=interaction.user)


async def casino(channel: TextChannel, db, bot):
    await channel.purge()
    view = CasinoChoices(db, bot)
    await channel.send(embed=Embed(description="Готовы испытать свою удачу?", color=0x1EE575), view=view)
