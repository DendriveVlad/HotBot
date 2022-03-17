import string
from asyncio.exceptions import TimeoutError
from asyncio import sleep
from random import choice, sample, randint, shuffle

from nextcord.errors import NotFound
from nextcord import Embed, ButtonStyle, Interaction, Message, Member, TextChannel, PermissionOverwrite
from nextcord.ui import View, Button, button

import DataBase
from config import BOT_ID, SERVER_ID


async def is_player_in_game(member, db):
    data = db.select("games", "", "players")
    if data:
        if isinstance(data, dict):
            games = [data]
        else:
            games = data
        for game in games:
            if str(member) in game["players"].split():
                return True


async def mafia_game(room, owner, bot, db, game_hub):
    game = Game(bot, room, db, game_hub, owner)

    try:
        member_gold_maximum = db.select("users", f"user_id == {owner}", "gold")["gold"]
        if member_gold_maximum > 100:
            member_gold_maximum = 100
        if member_gold_maximum:
            await room.send(f"<@{owner}>, игра создана. Осталось только её настроить.\n"
                            f"Напишите стоимость для входа в игру (0 - {member_gold_maximum}):")
        else:
            await room.send(f"<@{owner}>, ждём игроков. (1/10)")

        while member_gold_maximum:
            try:
                cost = await bot.wait_for("message", timeout=30, check=lambda m: m.author.id == owner and m.channel == room)
                game.cost = int(cost.content)
                if not (0 <= game.cost <= member_gold_maximum):
                    await room.purge()
                    await room.send(f"Напишите стоимость для входа в игру (в диапазоне 0 - {member_gold_maximum}):")
                    continue
                db.update("games", f"room_id == {room.id}", game_cost=game.cost)
                await room.purge()
                await room.send(f"Настройка завершена, ждём игроков. (1/10)")
                db.update("users", f"user_id == {owner}", gold=db.select("users", f"user_id == {owner}", "gold")["gold"] - game.cost)
                break
            except ValueError:
                await room.purge()
                await room.send(f"Напишите стоимость для входа в игру (в диапазоне 0 - {member_gold_maximum}):")

        await room.set_permissions(owner, send_message=None)

    except TimeoutError:
        await room.purge()
        await room.send("Время настройки вышло, канал удаляется.")
        await sleep(5)
        db.delete("games", f"room_id == {room.id}")
        await bot.send_log(f"[GameNotStarted] Игра <@{owner}> не началась", color=0xA927C1)
        await room.delete()
        return
    view = Connection(game)
    game.invite_message = await game_hub.send(embed=Embed(title=f"Игра \"Мафия Lite🤵🕵️‍♂️\"\n",
                                                          description=f"Стоимость входа: **{game.cost}**\n"
                                                                      f"Игроки [{game.players}/10]: <@{owner}>",
                                                          color=0xEAEA04), view=view)


class ConnectionButton(Button):
    def __init__(self, game_class):
        self.game = game_class
        super().__init__(style=ButtonStyle.green, label="Подключиться", emoji="➕", custom_id=f"mafia-{self.game.db.select('games', f'room_id == {self.game.room.id}', 'game_number')['game_number']}")

    async def callback(self, interaction):
        players_count = len(self.game.db.select("games", f"room_id == {self.game.room.id}", "players")["players"].split())
        if players_count < 15:
            if await is_player_in_game(interaction.user.id, self.game.db):
                return
            if self.game.db.select("users", f"user_id == {interaction.user.id}", "gold")["gold"] < self.game.cost:
                await interaction.response.send_message(embed=Embed(description="У Вас недостаточно золота", color=0xBF1818), ephemeral=True)
                return
            if interaction.user.id in self.game.players_list.keys():
                return
            try:
                await interaction.response.send_message(content=f"Вы подключились к игре. Перейдите в канал с игрой <#{self.game.room.id}>.", ephemeral=True)
            except NotFound:
                return
            self.game.db.update("games", f"room_id == {self.game.room.id}", players=self.game.db.select("games", f"room_id == {self.game.room.id}", "players")["players"] + f" {interaction.user.id}")
            self.game.db.update("users", f"user_id == {interaction.user.id}", gold=self.game.db.select("users", f"user_id == {interaction.user.id}", "gold")["gold"] - self.game.cost)
            await self.game.room.set_permissions(interaction.user, read_messages=True)
            if players_count == 2:
                view = View()
                view.add_item(Button(style=ButtonStyle.green, label="Начать игру", emoji="▶", custom_id="start"))
                await self.game.room.send("К игре подключилось минимальное количество человек, чтобы не ждать других игроков нажмите ниже", view=view)
                self.game.bot.loop.create_task(self.game.wait_for_accept())
            players_count = len(self.game.db.select("games", f"room_id == {self.game.room.id}", "players")["players"].split())
            self.game.players = players_count
            self.game.players_list[interaction.user.id] = ""
            self.game.active_players_list.append(interaction.user.id)
            if (100 / self.game.players) * self.game.accept_players < 65:
                self.game.ready_to_start = 0
            await self.game.room.send(f"<@{interaction.user.id}> подключился к игре ({self.game.players}/10)")
            await self.game.invite_message.edit(embed=Embed(title=f"Игра \"Мафия Lite🤵🕵️‍♂️\"\n",
                                                            description=f"Стоимость входа: **{self.game.cost}**\n"
                                                                        f"Игроки [{self.game.players}/10]: {', '.join([f'<@{i}>' for i in self.game.players_list.keys()])}",
                                                            color=0xEAEA04))
        else:
            self.game.db.update("games", f"room_id == {self.game.room.id}", started=1)
            self.game.ready_to_start = 2
            await self.game.starting_game()


class Connection(View):
    def __init__(self, game_class):
        super().__init__(timeout=30)
        self.game = game_class
        self.add_item(ConnectionButton(game_class))

    async def on_timeout(self):
        if self.game.ready_to_start != 2:
            if len(self.game.db.select("games", f"room_id == {self.game.room.id}", "players")["players"].split()) >= 6:
                await self.game.room.send("Время ожидания вышло. Игра начинается с тем количеством игроков, которое здесь есть")
                self.game.db.update("games", f"room_id == {self.game.room.id}", started=1)
                self.game.ready_to_start = 1
                await self.game.starting_game()
            else:
                await self.game.invite_message.delete()
                await self.game.room.send("Время ожидания вышло. Игроки не набрались, канал удаляется")
                await sleep(5)
                self.game.db.delete("games", f"room_id == {self.game.room.id}")
                await self.game.room.delete()
                if self.game.cost:
                    for player in self.game.players_list.keys():
                        self.game.db.update("users", f"user_id == {player}", gold=self.game.db.select("users", f"user_id == {player}", "gold")["gold"] + self.game.cost)
                await self.game.bot.send_log(f"[GameNotStarted] Игра <@{list(self.game.players_list.keys())[0]}> не началась", color=0xA927C1)


class ShowRoles(View):
    def __init__(self, game_class):
        super().__init__(timeout=30)
        self.game = game_class

    @button(style=ButtonStyle.green, label="Узнать свою роль", emoji="✉", row=0)
    async def get_role(self, button, interaction: Interaction):
        interaction.response.send_message(embed=Embed(title=f"Вы {self.game.players_list[interaction.user.id]}",
                                                      description=f"{'Для общения с остальными членами Мафии используйте канал ' + self.game.mafia_room.mention if self.game.players_list[interaction.user.id] == 'Мафия' and self.game.mafia_room else ''}",
                                                      color=0xD8301F if self.game.players_list[interaction.user.id] in ("Мафия", "Маньяк") else 0x1EC623), ephemeral=True)


class GamePassTurn(View):
    def __init__(self, member):
        super().__init__(timeout=30)
        self.member = member
        self.turn = 0

    @button(style=ButtonStyle.green, label="Передать ход", emoji="➡")
    async def get_role(self, button, interaction: Interaction):
        if interaction.user.id == self.member:
            self.turn = 1
            self.stop()
        await interaction.response.pong()


class GamePlayersVoting(View):
    def __init__(self, game_class, mode, players):
        super().__init__(timeout=60)
        for p in players:
            game_class.voting[p] = list()
            self.add_item(GamePlayerButton(game_class.__get_member(p)))
        self.game = game_class
        self.mode = mode
        self.chosen = None if mode != "Мафия" else []
        if mode == "Мафия":
            self.mafia = 3 if game_class.players > 11 else 2 if game_class.players > 7 else 1
        self.vote_count = 0

    async def interaction_check(self, interaction: Interaction) -> bool:
        for v in self.game.voting:
            if interaction.user.id in v:
                await interaction.response.pong()
                return
        if self.mode != "voting":
            if self.game.players_list[interaction.user.id] != self.mode:
                return
            if self.mode == "Мафия":
                self.chosen.append(interaction.data["custom_id"])
                if self.vote_count + 1 == self.mafia:
                    self.stop()
                    return
            else:
                if self.mode == "Доктор":
                    if self.game.players_list[interaction.user.id] == self.mode:
                        if self.game.self_heal:
                            await interaction.response.send_message(embed=Embed(description="Вы не можете излечить себя ещё раз", color=0xBF1818))
                            return
                        self.game.self_heal = True
                self.chosen = interaction.data["custom_id"]
                if self.mode == "Комиссар":
                    if self.chosen in self.game.checked:
                        await interaction.response.send_message(embed=Embed(description="Вы уже проверили этого игрока", color=0xBF1818))
                        return
                    if self.game.players_list[interaction.user.id] == "Мафия":
                        interaction.response.send_message(embed=Embed(title=f"Мафия" if self.game.players_list[interaction.user.id] == 'Мафия' else "Мирный житель",
                                                                      description=f"<@{interaction.user.id}>",
                                                                      color=0xD8301F if self.game.players_list[interaction.user.id] == 'Мафия' else 0x1EC623), ephemeral=True)
                self.stop()
                return
        elif len(self.game.active_players_list) == self.vote_count + 1:
            self.stop()
            return
        if "-" in self.game.players_list[interaction.user.id]:
            return
        self.game.voting[interaction.data["custom_id"]].append(interaction.user.id)
        if self.mode == "voting":
            await interaction.response.send_message(embed=Embed(description=f"{interaction.user.mention} проголосовал против <@{interaction.data['custom_id']}>", color=0x1988B8))
        await interaction.response.pong()
        self.vote_count += 1


class GamePlayerButton(Button):
    def __init__(self, member):
        super().__init__(style=ButtonStyle.green, label=member.nick if member.nick else member.name, custom_id=member.id)


class Game:
    def __init__(self, bot, room, db, game_hub, owner):
        self.bot = bot
        self.room: TextChannel = room
        self.db = db
        self.hub = game_hub

        self.invite_message: Message = None
        self.mafia_room: TextChannel = None

        self.ready_to_start = 0  # 0 - не готовы, 1 - игра начинается, 2 - игра уже началась
        self.players_list = {owner: ""}  # Список всех игроков
        self.active_players_list = [owner]  # Список всех живых игроков
        self.voting = {}
        self.self_heal = False  # Для доктора
        self.checked = []  # Для комиссара
        self.win = None
        # self.total_players = 1  # Всего игроков в игре
        self.players = 1  # Количество действующих игроков
        self.accept_players = 0  # Количество игроков подтвердивших быстрый страт игры
        self.accepts_list = []  # Список игроков подтвердивших быстрый страт игры
        # self.active_player = 0  # Игрок, у которого в данный момент картошка
        self.cost = 0  # Стоимость входа в игру
        self.total_money = 0  # Всего денег вложенных в игру
        # self.difficulty = 0  # Сложность раунда
        # self.rounds_results = []  # Результаты каждого раунда (0 - проигрыш, 1 - выигрыш)

    async def wait_for_accept(self):
        while 1:
            if self.ready_to_start == 2:
                return
            try:
                accept_click = await self.bot.wait_for("interaction", timeout=60, check=lambda c: c.type.name == "component" and c.channel == self.room)
                await accept_click.response.pong()
                if accept_click.user.id in self.accepts_list:
                    continue
                self.accepts_list.append(accept_click.user.id)
                self.accept_players += 1
                await self.room.send(embed=Embed(description=f"{accept_click.user.mention} проголосовал за начало игры ({self.accept_players}/{self.players})"))
                if (100 / self.players) * self.accept_players >= 65:
                    self.ready_to_start = 1
                    await self.starting_game()
            except TimeoutError:
                if self.ready_to_start == 2:
                    return
            except NotFound:
                return
            except AttributeError:
                return

    async def starting_game(self):
        if self.ready_to_start == 2:
            return
        players = self.players
        m = await self.room.send("Игра начнётся через 5...")
        for i in range(4, 0, -1):
            await sleep(1)
            if players != self.players and self.ready_to_start == 0:
                await m.edit(content="Запуск игры отменён.")
                self.ready_to_start = 0
                return
            await m.edit(content=f"Игра начнётся через {i}...")
        await sleep(1)
        self.db.update("games", f"room_id == {self.room.id}", started=1)
        self.ready_to_start = 2
        await m.edit(content="@everyone Запуск игры...")
        await sleep(2)
        await self.room.purge()
        self.total_money = self.players * self.cost
        self.total_money *= 0.9
        await self.invite_message.delete()
        await self.game_process()

    async def game_process(self):
        m: Message = await self.room.send("Распределение ролей...")
        roles = ["Мафия", "Маньяк", "Доктор", "Комиссар", "Мирный житель"]
        shuffle(roles)
        if self.players < 10:
            roles.remove("Маньяк")

        if self.players > 7:
            overwrites = {
                self.bot.get_guild(SERVER_ID).default_role: PermissionOverwrite(view_channel=False, send_message=True)
            }
            self.mafia_room = await self.bot.get_guild(SERVER_ID).create_text_channel(f"мафия", category=self.room.category, overwrites=overwrites)
        for player in self.players_list.keys():
            role = choice(roles)
            if role == "Комиссар":
                self.checked.append(player)
            if role in ("Маньяк", "Доктор", "Комиссар"):
                roles.remove(role)
            elif role == "Мафия":
                if self.players > 11 and list(self.players_list.values()).count("Мафия") == 2:
                    roles.remove(role)
                elif self.players > 7 and list(self.players_list.values()).count("Мафия"):
                    roles.remove(role)
                if self.mafia_room:
                    await self.mafia_room.set_permissions(self.__get_member(player), view_channel=True)
            self.players_list[player] = role

        view = ShowRoles(self)
        await m.edit(content="Нажмите, чтобы узнать свою роль", view=view)
        await sleep(30)
        await m.delete()

        m: Message = await self.room.send("Приготовьтесь...")
        await sleep(2)
        await m.delete()

        round = 0
        killed = None  # убит мафией
        cured = None  # вылечен
        murdered = None  # убит маньяком
        while True:
            if round:
                await self.room.send("У каждого игрока будет по 60 секунд на высказывание своего мнения")
            else:
                await self.room.send("У каждого игрока будет по 60 секунд на то, чтобы представить себя")
            for p in self.active_players_list:
                player = self.__get_member(p)
                await self.room.set_permissions(self.__get_member(player), send_message=True)
                view = GamePassTurn(p)
                pm: Message = await self.room.send(f"<@{p}>, у Вас 60 секунд.", view=view)
                for i in range(59, 0, -1):
                    await sleep(1)
                    if view.turn:
                        break
                    await pm.edit(content=f"<@{p}>, у Вас {i} секунд{('', 'а', 'ы')[1 if i % 10 == 1 and i != 11 else 2 if 2 <= i % 10 <= 4 and i // 10 != 1 else 0]}.")
                await pm.delete()
                await self.room.set_permissions(self.__get_member(player), send_message=None)

            if round:
                await self.room.set_permissions(self.bot.get_guild(SERVER_ID).default_role, send_message=None)
                await self.room.send("Всеобщее обсуждение на 60 секунд")
                await sleep(50)
                await self.room.send("Осталось 10 секунд")
                await sleep(10)
                await self.room.set_permissions(self.bot.get_guild(SERVER_ID).default_role, send_message=False)

                view = GamePlayersVoting(self, "voting", self.active_players_list)
                await self.room.send("Время вышло, начинается голосование за исключение игрока", view=view)
                await view.wait()
                max_votes = max(self.voting.values(), key=len)
                for p, v in self.voting.items():
                    if len(v) < max_votes:
                        self.voting.pop(p)

                if len(self.voting) != 1:
                    await self.room.send(f"По итогам голосования с одинаковым количеством голосов остались {len(self.voting)} {'игрока' if len(self.voting) < 5 else 'игроков'}\n"
                                         f"Каждый из этих игроков получит по 60 секунд на оправдание, после чего пройдёт повторное голосование.")
                    for p in self.voting.keys():
                        player = self.__get_member(p)
                        await self.room.set_permissions(self.__get_member(player), send_message=True)
                        view = GamePassTurn(p)
                        pm: Message = await self.room.send(f"<@{p}>, у Вас 60 секунд.", view=view)
                        for i in range(59, 0, -1):
                            await sleep(1)
                            if view.turn:
                                break
                            await pm.edit(content=f"<@{p}>, у Вас {i} секунд{('', 'а', 'ы')[1 if i % 10 == 1 and i != 11 else 2 if 2 <= i % 10 <= 4 and i // 10 != 1 else 0]}.")
                        await pm.delete()
                        await self.room.set_permissions(self.__get_member(player), send_message=None)
                    view = GamePlayersVoting(self, "voting", list(self.voting.keys()))
                    await self.room.send("Начинается второй этап голосования за исключение игрока. Если здесь игроки не будут однозначны, то будет выбран случайный игрок.", view=view)
                    await view.wait()
                    max_votes = max(self.voting.values(), key=len)
                    for p, v in self.voting.items():
                        if len(v) < max_votes:
                            self.voting.pop(p)
                    while len(self.voting) != 1:
                        self.voting.pop(choice(list(self.voting.keys())))
                kicked_player = list(self.voting.keys())[0]
                self.__removePlayer(kicked_player)
                await self.room.send(f"По итогам голосования был исключён игрок <@{kicked_player}>")
                if self.__checkEndGame():
                    break

            await self.room.send("Собрание заканчивается, игроки расходятся по домам и начинается ночь.")
            await sleep(2)

            view = GamePlayersVoting(self, "Мафия", self.active_players_list)
            await self.room.send("Просыпается **мафия** и думает кого она убьёт этой ночью...", view=view)
            if "Мафия" in list(self.players_list.values()):
                await view.wait()

                if len(set(view.chosen)) == len(view.chosen):
                    if len(view.chosen):
                        killed = view.chosen[0]
                    else:
                        while len(self.voting) != 1:
                            self.voting.pop(choice(list(self.voting.keys())))
                        killed = list(self.voting.keys())[0]
                else:
                    if view.chosen[0] in view.chosen[1:]:
                        killed = view.chosen[0]
                    else:
                        killed = view.chosen[1]
            else:
                await sleep(randint(10, 50))

            await self.room.send("**Мафия** сделала выбор. **Мафия** засыпает.")

            if self.players >= 10:
                view = GamePlayersVoting(self, "Маньяк", self.active_players_list)
                await self.room.send("Просыпается **маньяк** и ищет свою жертву...", view=view)
                if "Маньяк" in list(self.players_list.values()):
                    await view.wait()
                    if view.chosen:
                        murdered = view.chosen
                    else:
                        while len(self.voting) != 1:
                            self.voting.pop(choice(list(self.voting.keys())))
                        murdered = list(self.voting.keys())[0]
                else:
                    await sleep(randint(5, 30))

                await self.room.send("**Маньяк** сделал выбор. **Маньяк** засыпает.")

            view = GamePlayersVoting(self, "Доктор", self.active_players_list)
            await self.room.send("Просыпается **доктор** и выбирает кого сегодня он вылечит...", view=view)
            if "Доктор" in list(self.players_list.values()):
                await view.wait()
                if view.chosen:
                    cured = view.chosen
                else:
                    while len(self.voting) != 1:
                        self.voting.pop(choice(list(self.voting.keys())))
                    cured = list(self.voting.keys())[0]
            else:
                await sleep(randint(5, 30))

            await self.room.send("**Доктор** сделал выбор. **Доктор** засыпает.")

            view = GamePlayersVoting(self, "Комиссар", self.active_players_list)
            await self.room.send("Просыпается **комиссар** и пытается найти мафию...", view=view)
            if "Комиссар" in list(self.players_list.values()):
                await view.wait()
            else:
                await sleep(randint(5, 30))

            await self.room.send("**Комиссар** сделал выбор. **Комиссар** засыпает.")
            await sleep(2)

            if killed == murdered:
                dead = f"<@{killed}>."
                self.__removePlayer(killed)
            elif killed == cured != murdered:
                dead = f"<@{murdered}>."
                self.__removePlayer(murdered)
            elif killed != cured:
                dead = f"<@{killed}> и <@{murdered}>."
                self.__removePlayer(killed, murdered)
            else:
                dead = None

            await self.room.send(f"Наступает утро. Все игроки просыпаются{', кроме ' + dead if dead else '.'}")

            if self.__checkEndGame():
                break
            round += 1

        await self.mafia_room.delete()

        roles = {"Мафия": [],
                 "Маньяк": [],
                 "Комиссар": [],
                 "Доктор": [],
                 "Мирные жители": []}
        wins = []
        for p, r in self.players_list:
            roles[r.replace("-", "")].append(f"<@{p}>")
            if self.win == "Маньяк" == r:
                wins.append(p)
            elif self.win == "Мафия" and p in roles[self.win]:
                wins.append(p)
            else:
                wins.append(p)
        fm = ""
        for r, p in roles:
            fm += f"**{r}**: {', '.join(p)}\n"

        gold = self.total_money // len(wins)
        award = ""
        for p in list(self.players_list.keys()):
            points = 50
            player = self.db.select("users", f"user_id == {p}", "points", "gold")
            if p in wins:
                points = 120
                award += f"<@{p}> получает **{points}** опыта и **{gold}** золота\n"
                self.db.update("users", f"user_id == {p}", points=player["points"] + points, gold=player["gold"] + gold)
                continue
            self.db.update("users", f"user_id == {p}", points=player["points"] + points)
        award += "\nВсе остальные получили утешительный приз в размере 50 опыта"

        await self.room.send(f"Игра окончена.", embeds=[Embed(title="Побеждает", description=self.win, color=0x1EC623 if self.win == "Мирные жители" else 0xD8301F),
                                                        Embed(title="Роли", description=fm, color=0xF9BA1C),
                                                        Embed(title="Награда", description=award, color=0xEDD50B)])

        await self.room.send("Канал удалится через 30 секунд")
        await sleep(30)
        self.db.delete("games", f"room_id == {self.room.id}")
        await self.room.delete()
        await self.bot.send_log(f"[GameEnd] Игра закончилась, победитель(и): {'>, <@'.join(wins)}", color=0xE160F9)

    def __removePlayer(self, *players):
        for player in players:
            self.active_players_list.remove(player)
            self.players_list[player] = "-" + self.players_list[player]
            if self.players_list[player] == "Мафия":
                await self.mafia_room.set_permissions(self.__get_member(player), view_channel=False)

    def __checkEndGame(self) -> bool:
        active_roles = list(self.players_list.values())
        if "Мафия" not in active_roles and "Маньяк" not in active_roles:
            self.win = "Мирные жители"
            return True
        for i in active_roles:
            if "-" in i:
                active_roles.remove(i)
        mafia_count = active_roles.count("Мафия")
        murderer = "Маньяк" in active_roles
        if mafia_count >= len(active_roles) - mafia_count:
            self.win = "Мафия"
            return True
        if murderer and len(active_roles) - 1 <= 1:
            self.win = "Маньяк"
            return True
        return False

    def __get_member(self, member_id: int) -> Member | None:
        return self.bot.get_guild(SERVER_ID).get_member(member_id)
