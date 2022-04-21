from asyncio.exceptions import TimeoutError
from asyncio import sleep
from random import choice, randint, shuffle

from nextcord.errors import NotFound
from nextcord import Embed, ButtonStyle, Interaction, Message, Member, TextChannel, PermissionOverwrite
from nextcord.ui import View, Button, button

from config import SERVER_ID
from info import send_log


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
            await room.send(f"<@{owner}>, ждём игроков. (1/15)")

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
                await room.send(f"Настройка завершена, ждём игроков. (1/15)")
                db.update("users", f"user_id == {owner}", gold=db.select("users", f"user_id == {owner}", "gold")["gold"] - game.cost)
                break
            except ValueError:
                await room.purge()
                await room.send(f"Напишите стоимость для входа в игру (в диапазоне 0 - {member_gold_maximum}):")

        await room.set_permissions(game.get_member(owner), send_messages=None)

    except TimeoutError:
        await room.purge()
        await room.send("Время настройки вышло, канал удаляется.")
        await sleep(5)
        db.delete("games", f"room_id == {room.id}")
        await send_log(guild=room.guild, log_type="GameNotStarted", info=f"Игра не началась", member=bot.get_user(owner), color=0xA927C1)
        await room.delete()
        return
    view = Connection(game)
    game.invite_message = await game_hub.send(embed=Embed(title=f"Игра \"Мафия Lite🤵🕵️‍♂️\"\n",
                                                          description=f"Стоимость входа: **{game.cost}**\n"
                                                                      f"Игроки [{game.players}/15]: <@{owner}>",
                                                          color=0xEAEA04), view=view)


class StartGame(Button):
    def __init__(self, game_class):
        super().__init__(style=ButtonStyle.success, label="Начать игру", emoji="▶", custom_id="start")
        self.game = game_class

    async def callback(self, interaction: Interaction):
        await interaction.response.pong()
        if interaction.user.id in self.game.accepts_list:
            return
        self.game.accepts_list.append(interaction.user.id)
        self.game.accept_players += 1
        await self.game.room.send(embed=Embed(description=f"{interaction.user.mention} проголосовал за начало игры ({self.game.accept_players}/{self.game.players})"))
        if self.game.ready_to_start:
            return
        if (100 / self.game.players) * self.game.accept_players >= 65:
            self.game.ready_to_start = 1
            await self.game.starting_game()


class ConnectionButton(Button):
    def __init__(self, game_class):
        self.game = game_class
        super().__init__(style=ButtonStyle.success, label="Подключиться", emoji="➕", custom_id=f"mafia-{self.game.db.select('games', f'room_id == {self.game.room.id}', 'game_number')['game_number']}")

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
            self.game.db.update("games", f"room_id == {self.game.room.id}", players=self.game.db.select("games", f"room_id == {self.game.room.id}", "players")["players"] + f" {interaction.user.id}")
            self.game.db.update("users", f"user_id == {interaction.user.id}", gold=self.game.db.select("users", f"user_id == {interaction.user.id}", "gold")["gold"] - self.game.cost)
            await self.game.room.set_permissions(interaction.user, read_messages=True)
            if players_count == 5:
                view = View(timeout=600)
                view.add_item(StartGame(self.game))
                await self.game.room.send("К игре подключилось минимальное количество человек, чтобы не ждать других игроков нажмите ниже", view=view)
            players_count = len(self.game.db.select("games", f"room_id == {self.game.room.id}", "players")["players"].split())
            self.game.players = players_count
            await self.game.room.send(f"<@{interaction.user.id}> подключился к игре ({self.game.players}/15)")
            try:
                await interaction.response.send_message(content=f"Вы подключились к игре. Перейдите в канал с игрой <#{self.game.room.id}>.", ephemeral=True)
            except NotFound:
                return
            self.game.players_list[interaction.user.id] = ""
            self.game.active_players_list.append(interaction.user.id)
            if (100 / self.game.players) * self.game.accept_players < 65:
                self.game.ready_to_start = 0
            await self.game.invite_message.edit(embed=Embed(title=f"Игра \"Мафия Lite🤵🕵️‍♂️\"\n",
                                                            description=f"Стоимость входа: **{self.game.cost}**\n"
                                                                        f"Игроки [{self.game.players}/15]: {', '.join([f'<@{i}>' for i in self.game.players_list.keys()])}",
                                                            color=0xEAEA04))
        else:
            self.game.db.update("games", f"room_id == {self.game.room.id}", started=1)
            self.game.ready_to_start = 2
            await self.game.starting_game()


class Connection(View):
    def __init__(self, game_class):
        super().__init__(timeout=60)
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
                await send_log(guild=self.game.room.guild, log_type="GameNotStarted", info=f"Игра не началась", member=self.game.bot.get_user(list(self.game.players_list.keys())[0]), color=0xA927C1)


class ShowRoles(View):
    def __init__(self, game_class):
        super().__init__(timeout=1200)
        self.game = game_class

    @button(style=ButtonStyle.success, label="Узнать свою роль", emoji="✉", row=0)
    async def get_role(self, button, interaction: Interaction):
        await interaction.response.send_message(embed=Embed(title=f"Вы {self.game.players_list[interaction.user.id]}",
                                                            description=f"{'Для общения с остальными членами Мафии используйте канал ' + self.game.mafia_room.mention if self.game.players_list[interaction.user.id] == 'Мафия' and self.game.mafia_room else ''}",
                                                            color=0xD8301F if self.game.players_list[interaction.user.id] in ("Мафия", "Маньяк") else 0x1EC623), ephemeral=True)


class GamePassTurn(View):
    def __init__(self, member):
        super().__init__(timeout=60)
        self.member = member
        self.turn = 0

    @button(style=ButtonStyle.success, label="Передать ход", emoji="➡")
    async def get_role(self, button, interaction: Interaction):
        if interaction.user.id == self.member:
            self.turn = 1
            self.stop()
        await interaction.response.pong()


class GamePlayersVoting(View):
    def __init__(self, game_class, mode, players):
        super().__init__(timeout=61)
        for p in players:
            game_class.voting[p] = list()
            self.add_item(GamePlayerButton(game_class.get_member(p)))
        self.game = game_class
        self.mode = mode
        self.chosen = None if mode != "Мафия" else []
        if mode == "Мафия":
            self.mafia = 3 if game_class.players > 11 else 2 if game_class.players > 7 else 1
        self.vote_count = 0


class GamePlayerButton(Button):
    def __init__(self, member):
        super().__init__(style=ButtonStyle.success, label=member.nick if member.nick else member.name)
        self.member = member.id

    async def callback(self, interaction: Interaction):
        for v in list(self.view.game.voting.values()):
            if interaction.user.id in v:
                await interaction.response.pong()
                return
        if self.view.mode != "voting":
            if self.view.game.players_list[interaction.user.id] != self.view.mode:
                await interaction.response.pong()
                return
            if self.view.mode == "Мафия":
                self.view.chosen.append(self.member)
                if self.view.vote_count + 1 == self.view.mafia:
                    self.view.stop()
                    await interaction.response.pong()
                    return
            else:
                if self.view.mode == "Доктор":
                    if self.view.game.players_list[interaction.user.id] == self.view.mode:
                        if self.view.game.self_heal:
                            await interaction.response.send_message(embed=Embed(description="Вы не можете излечить себя ещё раз", color=0xBF1818), ephemeral=True)
                            return
                        self.view.game.self_heal = True
                self.view.chosen = self.member
                if self.view.mode == "Комиссар":
                    if self.view.chosen in self.view.game.checked:
                        await interaction.response.send_message(embed=Embed(description="Вы уже проверили этого игрока", color=0xBF1818), ephemeral=True)
                        return
                    await interaction.response.send_message(embed=Embed(title=f"Мафия" if self.view.game.players_list[self.member] == 'Мафия' else "Мирный житель",
                                                                        description=f"<@{self.member}>",
                                                                        color=0xD8301F if self.view.game.players_list[self.member] == 'Мафия' else 0x1EC623), ephemeral=True)
                self.view.stop()
                return
        elif len(self.view.game.active_players_list) == self.view.vote_count + 1:
            self.view.stop()
            return
        if "-" in self.view.game.players_list[interaction.user.id]:
            return
        self.view.game.voting[self.member].append(interaction.user.id)
        if self.view.mode == "voting":
            await interaction.response.send_message(embed=Embed(description=f"{interaction.user.mention} проголосовал против <@{self.member}>", color=0x1988B8))
            self.view.vote_count += 1
            return
        await interaction.response.pong()
        self.view.vote_count += 1


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
        self.win = None  # Кто победил
        self.players = 1  # Количество действующих игроков
        self.accept_players = 0  # Количество игроков подтвердивших быстрый страт игры
        self.accepts_list = []  # Список игроков подтвердивших быстрый страт игры
        self.cost = 0  # Стоимость входа в игру
        self.total_money = 0  # Всего денег вложенных в игру

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
        roles = ["Мафия", "Маньяк", "Доктор", "Комиссар"]
        shuffle(roles)
        if self.players < 10:
            roles.remove("Маньяк")

        if self.players > 7:
            overwrites = {
                self.bot.get_guild(SERVER_ID).default_role: PermissionOverwrite(view_channel=False, send_messages=True)
            }
            self.mafia_room = await self.bot.get_guild(SERVER_ID).create_text_channel(f"мафия", category=self.room.category, overwrites=overwrites)
        shuffle(self.active_players_list)
        for player in self.active_players_list:
            if not roles:
                self.players_list[player] = "Мирный житель"
                continue
            role = choice(roles)
            if role == "Комиссар":
                self.checked.append(player)
                roles.remove(role)

            elif role == "Мафия":
                if self.players > 11 and list(self.players_list.values()).count("Мафия") == 2:
                    roles.remove(role)
                elif self.players > 7 and list(self.players_list.values()).count("Мафия"):
                    roles.remove(role)
                else:
                    roles.remove(role)
                if self.mafia_room:
                    await self.mafia_room.set_permissions(self.get_member(player), view_channel=True)
            else:
                roles.remove(role)
            self.players_list[player] = role

        view = ShowRoles(self)
        await m.edit(content="Нажмите, чтобы узнать свою роль", view=view)
        await sleep(15)

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
                player = self.get_member(p)
                await self.room.set_permissions(player, view_channel=True, send_messages=True)
                view = GamePassTurn(p)
                pm: Message = await self.room.send(f"<@{p}>, у Вас 60 секунд.", view=view)
                for i in range(59, 0, -1):
                    await sleep(1)
                    if view.turn:
                        break
                    await pm.edit(content=f"<@{p}>, у Вас {i} секунд{('', 'а', 'ы')[1 if i % 10 == 1 and i != 11 else 2 if 2 <= i % 10 <= 4 and i // 10 != 1 else 0]}.")
                await pm.delete()
                await self.room.set_permissions(player, view_channel=True, send_messages=None)

            if round:
                await self.room.set_permissions(self.bot.get_guild(SERVER_ID).default_role, view_channel=False, send_messages=None)
                await self.room.send("Всеобщее обсуждение на 60 секунд")
                await sleep(50)
                await self.room.send("Осталось 10 секунд")
                await sleep(10)
                await self.room.set_permissions(self.bot.get_guild(SERVER_ID).default_role, view_channel=False, send_messages=False)

                view = GamePlayersVoting(self, "voting", self.active_players_list)
                await self.room.send("Время вышло, начинается голосование за исключение игрока", view=view)
                await view.wait()
                max_votes = len(max(self.voting.values(), key=len))
                pv = list(self.voting.items())
                for p, v in pv:
                    if len(v) < max_votes:
                        self.voting.pop(p)

                if len(self.voting) != 1:
                    await self.room.send(f"По итогам голосования с одинаковым количеством голосов остались {len(self.voting)} {'игрока' if len(self.voting) < 5 else 'игроков'}\n"
                                         f"Каждый из этих игроков получит по 60 секунд на оправдание, после чего пройдёт повторное голосование.")
                    for p in self.voting.keys():
                        player = self.get_member(p)
                        await self.room.set_permissions(player, view_channel=True, send_messages=True)
                        view = GamePassTurn(p)
                        pm: Message = await self.room.send(f"<@{p}>, у Вас 60 секунд.", view=view)
                        for i in range(59, 0, -1):
                            await sleep(1)
                            if view.turn:
                                break
                            await pm.edit(content=f"<@{p}>, у Вас {i} секунд{('', 'а', 'ы')[1 if i % 10 == 1 and i != 11 else 2 if 2 <= i % 10 <= 4 and i // 10 != 1 else 0]}.")
                        await pm.delete()
                        await self.room.set_permissions(player, view_channel=True, send_messages=None)
                    view = GamePlayersVoting(self, "voting", list(self.voting.keys()))
                    await self.room.send("Начинается второй этап голосования за исключение игрока. Если здесь игроки не будут однозначны, то будет выбран случайный игрок.", view=view)
                    await view.wait()
                    max_votes = len(max(self.voting.values(), key=len))
                    pv = list(self.voting.items())
                    for p, v in pv:
                        if len(v) < max_votes:
                            self.voting.pop(p)
                    while len(self.voting) != 1:
                        self.voting.pop(choice(list(self.voting.keys())))
                kicked_player = list(self.voting.keys())[0]
                await self.__removePlayer(kicked_player)
                await self.room.send(f"По итогам голосования был исключён игрок <@{kicked_player}>")
                if self.__checkEndGame():
                    break

            await self.room.send("Собрание заканчивается, игроки расходятся по домам и начинается ночь.")
            await sleep(2)

            viewv = GamePlayersVoting(self, "Мафия", self.active_players_list)
            await self.room.send("Просыпается **мафия** и думает кого она убьёт этой ночью...", view=viewv)
            if "Мафия" in list(self.players_list.values()):
                await viewv.wait()

                if len(set(viewv.chosen)) == len(viewv.chosen):
                    if len(viewv.chosen):
                        killed = viewv.chosen[0]
                    else:
                        while len(self.voting) != 1:
                            self.voting.pop(choice(list(self.voting.keys())))
                        killed = list(self.voting.keys())[0]
                else:
                    if viewv.chosen[0] in viewv.chosen[1:]:
                        killed = viewv.chosen[0]
                    else:
                        killed = viewv.chosen[1]
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

            if not murdered:
                if killed == cured:
                    dead = None
                else:
                    dead = f"<@{killed}>."
                    await self.__removePlayer(killed)
            elif killed == murdered:
                dead = f"<@{killed}>."
                await self.__removePlayer(killed)
            elif killed == cured != murdered:
                dead = f"<@{murdered}>."
                await self.__removePlayer(murdered)
            elif killed != cured:
                dead = f"<@{killed}> и <@{murdered}>."
                await self.__removePlayer(killed, murdered)
            else:
                dead = None

            await self.room.send(f"Наступает утро. Все игроки просыпаются{', кроме ' + dead if dead else '.'}")

            if self.__checkEndGame():
                break
            round += 1
        if self.mafia_room:
            await self.mafia_room.delete()

        roles = {"Мафия": [],
                 "Маньяк": [],
                 "Комиссар": [],
                 "Доктор": [],
                 "Мирные жители": []}
        wins = []
        for p, r in self.players_list.items():
            rol = r.replace("-", "")
            if rol == "Мирный житель":
                rol = "Мирные жители"
            roles[rol].append(f"<@{p}>")
            if self.win == "Маньяк" and rol == "Маньяк":
                wins.append(p)
            elif self.win == "Мафия" and rol == "Мафия":
                wins.append(p)
            elif self.win not in ("Мафия", "Маньяк") and rol not in ("Мафия", "Маньяк"):
                wins.append(p)
        fm = ""
        for r, p in roles.items():
            fm += f"**{r}**: {', '.join(p)}\n"

        gold = int(self.total_money // len(wins))
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
        await send_log(log_type="GameEnd", info=f"Игра закончилась", member=self.bot.get_user(list(self.players_list.keys())[0]), fields=("Победитель(и):", '>\n<@'.join(wins)), color=0xE160F9)

    async def __removePlayer(self, *players):
        for player in players:
            self.active_players_list.remove(player)
            self.players_list[player] = "-" + self.players_list[player]
            if self.players_list[player] == "Мафия":
                await self.mafia_room.set_permissions(self.get_member(player), view_channel=True, send_messages=False)

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

    def get_member(self, member_id: int) -> Member | None:
        member = self.bot.get_guild(SERVER_ID).get_member(member_id)
        if not member:
            self.players_list.pop(member_id)
            self.players -= 1
            if member_id in self.active_players_list:
                self.active_players_list.remove(member_id)
            return self.bot.get_guild(SERVER_ID).get_member(879324092732420107)
        return member
