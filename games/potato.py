import string
from asyncio.exceptions import TimeoutError
from asyncio import sleep
from random import choice, sample, randint, shuffle

from nextcord.errors import NotFound
from nextcord import Embed, ButtonStyle
from nextcord.ui import View, Button

from config import BOT_ID


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


async def potato_game(room, owner, bot, db, game_hub, gamemode):
    game = Game(bot, room, db, game_hub, owner, gamemode)

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

    except TimeoutError:
        await room.purge()
        await room.send("Время настройки вышло, канал удаляется.")
        await sleep(5)
        db.delete("games", f"room_id == {room.id}")
        await bot.send_log(f"[GameNotStarted] Игра <@{owner}> не началась", color=0xA927C1)
        await room.delete()
        return
    view = View()
    view.add_item(Button(style=ButtonStyle.green, label="Подключиться", emoji="➕", custom_id=f"potato-{db.select('games', f'room_id == {room.id}', 'game_number')['game_number']}"))
    game.invite_message = await game_hub.send(embed=Embed(title=f"Игра \"Горячая картошка ({'Быстрая' if game.mode == 's' else 'Длинная'})🔥🥔\"\n",
                                                          description=f"Стоимость входа: **{game.cost}**\n"
                                                                      f"Игроки [{game.players}/10]: <@{owner}>",
                                                          color=0xEAEA04), view=view)
    bot.loop.create_task(game.player_messages())

    try:
        await game.wait_players()
    except TimeoutError:
        if game.ready_to_start != 2:
            if len(db.select("games", f"room_id == {room.id}", "players")["players"].split()) >= 3:
                await room.send("Время ожидания вышло. Игра начинается с тем количеством игроков, которое здесь есть")
                db.update("games", f"room_id == {room.id}", started=1)
                game.ready_to_start = 1
                await game.starting_game()
            else:
                await game.invite_message.delete()
                await room.send("Время ожидания вышло. Игроки не набрались, канал удаляется")
                await sleep(5)
                db.delete("games", f"room_id == {room.id}")
                await room.delete()
                if game.cost:
                    for player in game.players_list.keys():
                        db.update("users", f"user_id == {player}", gold=db.select("users", f"user_id == {player}", "gold")["gold"] + game.cost)
                await bot.send_log(f"[GameNotStarted] Игра <@{owner}> не началась", color=0xA927C1)
                return


class Game:
    def __init__(self, bot, room, db, game_hub, owner, mode):
        self.bot = bot
        self.room = room
        self.db = db
        self.hub = game_hub
        self.mode = mode

        self.invite_message = None

        self.ready_to_start = 0  # 0 - не готовы, 1 - игра начинается, 2 - игра уже началась
        self.players_list = {owner: 1 if mode == "s" else 3}  # Список всех действующих игроков
        self.total_players_list = []  # Список всех игроков
        self.total_players = 1  # Всего игроков в игре
        self.players = 1  # Количество действующих игроков
        self.accept_players = 0  # Количество игроков подтвердивших быстрый страт игры
        self.accepts_list = []  # Список игроков подтвердивших быстрый страт игры
        self.active_player = 0  # Игрок, у которого в данный момент картошка
        self.cost = 0  # Стоимость входа в игру
        self.total_money = 0  # Всего денег вложенных в игру
        self.difficulty = 0  # Сложность раунда
        self.rounds_results = []  # Результаты каждого раунда (0 - проигрыш, 1 - выигрыш)

    async def wait_for_accept(self):
        while 1:
            try:
                accept_click = await self.bot.wait_for("interaction", timeout=60, check=lambda c: c.type.name == "component" and  c.channel == self.room)
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
                await m.edit("Запуск игры отменён.")
                self.ready_to_start = 0
                return
            await m.edit(f"Игра начнётся через {i}...")
        await sleep(1)
        self.db.update("games", f"room_id == {self.room.id}", started=1)
        self.ready_to_start = 2
        await m.edit("Запуск игры...")
        await sleep(2)
        await self.room.purge()
        self.total_money = self.players * self.cost
        self.total_players = self.players
        self.total_money *= 0.9
        await self.invite_message.delete()
        await self.game_process()

    async def game_process(self):
        self.total_players_list = list(self.players_list.keys()).copy()
        self.active_player, ignore_players = self.get_random_player([])
        first, second, third = 0, 0, 0,

        while 1:
            next_player, ignore_players = self.get_random_player(ignore_players)
            if self.difficulty <= 3:
                wait_time = 8
            elif self.difficulty <= 5:
                wait_time = 6
            elif self.difficulty <= 7:
                wait_time = 5
            else:
                wait_time = 3.5
            await self.room.send(f"<@{self.active_player}> получает горячую картошку")
            await sleep(1.5)
            await self.room.send(f"<@{self.active_player}>, Вам нужно передать горячую картошку игроку <@{next_player}>\n"
                                 f"Для этого Вам нужно найти код этого игрока в таблице, которая скоро появится.\n"
                                 f"На это вам выделено **{wait_time} " + ("секунды" if isinstance(wait_time, float) else "секунд") + "**")
            await sleep(4)
            players_tab = self.get_random_players_list(next_player)
            await self.room.send(embed=Embed(description="\n".join([f"**{code}**: <@{player if '*' not in player else player[1:]}>" for code, player in players_tab.items()]), color=0xEAEA04))
            await self.room.send("Время пошло")

            try:
                message = await self.bot.wait_for("message", timeout=wait_time, check=lambda m: m.author.id == self.active_player and m.channel == self.room)
                try:
                    if "*" in players_tab[message.content]:
                        self.rounds_results.append(1)
                        await self.room.send(embed=Embed(description=f"<@{self.active_player}> передаёт картошку", color=0x21F300))
                        self.active_player = next_player
                        if (len(self.rounds_results) + 1) % 2:
                            self.difficulty += 1
                        chance_to_difficult_up = int(self.rounds_results.count(1) / len(self.rounds_results) * 100)
                        if len(self.rounds_results) > 6 and randint(0, 100) <= chance_to_difficult_up:
                            if len(self.rounds_results) > 15 and randint(0, 100) <= chance_to_difficult_up:
                                self.difficulty += 1
                            elif randint(0, 100) <= chance_to_difficult_up // 2:
                                self.difficulty += 1
                        if self.players <= 4:  # Если игроков меньше 5, то включается ускорение усложнения
                            self.difficulty += randint(0, 1)
                        continue
                    else:
                        await self.room.send(embed=Embed(description=f"<@{self.active_player}> передаёт картошку не тому игроку и обжигает его, в ответ этот игрок избил бросающегося до смерти", color=0xF9871C))
                except KeyError:
                    await self.room.send(embed=Embed(description=f"<@{self.active_player}> выкидывает картошку непонятно куда, из-за чего она разбивает окно, а владелиц окна решает испытать своё ружьё на игроке, который бросил картошку", color=0xF9871C))
            except TimeoutError:
                await self.room.send(embed=Embed(description=f"<@{self.active_player}> влюбляется в картошку, но картошка не разделяет эту любов и сжигает своего фаната", color=0xF9871C))

            self.rounds_results.append(0)
            self.players_list[self.active_player] -= 1

            if self.players_list[self.active_player] <= 0:
                self.players_list.pop(self.active_player)
                if self.mode == "l":
                    await self.room.send(embed=Embed(description=f"<@{self.active_player}> выбывает из игры", color=0xF9871C))
            else:
                await self.room.send(embed=Embed(description=f"у <@{self.active_player}> осталось {self.players_list[self.active_player]} ♥", color=0xF9871C))
            ignore_players = [next_player]
            self.players -= 1

            if self.players == 2 and self.total_players > 5:
                third = self.active_player
            elif self.players == 1:
                if self.total_players > 3:
                    second = self.active_player
                first = next_player
                break

            self.active_player = next_player
            if len(self.rounds_results) > 10:
                chance_upper_difficult = int(self.rounds_results.count(1) / len(self.rounds_results) * 100)
                up = randint(0, 100) < chance_upper_difficult
                if len(self.rounds_results) > 20:
                    if chance_upper_difficult > 80 and up:
                        self.difficulty //= 1.3
                        continue
                    elif chance_upper_difficult > 60 and up:
                        self.difficulty //= 1.5
                        continue
                elif chance_upper_difficult > 80 and up:
                    self.difficulty //= 1.5
                    continue
            self.difficulty //= 2

        if third:
            first_place, second_place, third_place = (80, self.total_money * 0.5), (50, self.total_money * 0.3), (30, self.total_money * 0.2)
        elif second:
            first_place, second_place, third_place = (80, self.total_money * 0.6), (50, self.total_money * 0.4), 0
        else:
            first_place, second_place, third_place = (80, self.total_money), 0, 0

        if third:
            date = self.db.select("users", f"user_id == {third}", "gold", "points")
            self.db.update("users", f"user_id == {third}", points=date["points"] + third_place[0], gold=date["gold"] + third_place[-1])
        if second:
            date = self.db.select("users", f"user_id == {second}", "gold", "points")
            self.db.update("users", f"user_id == {second}", points=date["points"] + second_place[0], gold=date["gold"] + second_place[-1])
        date = self.db.select("users", f"user_id == {first}", "gold", "points")
        self.db.update("users", f"user_id == {first}", points=date["points"] + first_place[0], gold=date["gold"] + first_place[-1])
        for p in self.total_players_list:
            if p in (third, second, first):
                continue
            self.db.update("users", f"user_id == {first}", points=self.db.select("users", f"user_id == {first}", "points")["points"] + 25)
        await self.room.send("", embed=Embed(title="Игра окончена", description=f"1 место: <@{first}>\n"
                                                                                f"+{first_place[0]} опыта, +{int(first_place[-1])} {'золото' if str(first_place[-1])[-1] == '1' else 'золота'}\n\n" +
                                                                                (f"2 место: <@{second}>\n"
                                                                                 f"+{second_place[0]} опыта, +{int(second_place[-1])} {'золото' if str(second_place[-1])[-1] == '1' else 'золота'}\n\n" +
                                                                                 (f"3 место: <@{third}>\n"
                                                                                  f"+{third_place[0]} опыта, +{int(third_place[-1])} {'золото' if str(third_place[-1])[-1] == '1' else 'золота'}\n\n" if third else "") if second else "") +
                                                                                "\nВсе остальные получили утешительный приз в размере 25 опыта", color=0xEDD50B))
        await self.room.send("Канал удалится через 30 секунд")
        self.active_player = 0
        await sleep(30)
        self.db.delete("games", f"room_id == {self.room.id}")
        await self.room.delete()
        await self.bot.send_log(f"[GameEnd] Игра закончилась, победитель: <@{first}>", color=0xE160F9)

    def get_random_player(self, ignore_players: list[int]) -> tuple[int, list[int]]:
        players = list(self.players_list.keys()).copy()
        if len(players) <= len(ignore_players):
            ignore_players = [ignore_players[-1]]
        for i in ignore_players:
            if i not in players:
                ignore_players.remove(i)
                continue
            players.remove(i)
        chosen_player = choice(players)
        ignore_players.append(chosen_player)
        return chosen_player, ignore_players

    def get_random_letter(self) -> str:
        if self.difficulty < 3:
            letters = choice((string.digits, string.ascii_lowercase))
            length = self.difficulty // 2 if self.difficulty > 1 else 1
        elif self.difficulty < 5:
            letters = choice((string.digits, string.ascii_lowercase, string.ascii_uppercase))
            length = self.difficulty // 2
        else:
            letters = string.digits + string.ascii_letters
            if self.difficulty > 15:
                length = randint(4, 6)
            elif self.difficulty > 9:
                length = randint(3, 5)
            else:
                length = self.difficulty // 2
        return ''.join(sample(letters, length))

    def get_random_players_list(self, need_player: int) -> dict[str: int]:
        players = self.total_players_list.copy()
        players.remove(self.active_player)
        shuffle(players)
        players_tab = {}
        for p in players:
            players_tab[self.get_random_letter()] = "*" + str(p) if p == need_player else str(p)

        while len(players_tab) != len(players):
            if "*" + str(need_player) not in players_tab.values():
                players_tab[self.get_random_letter()] = "*" + str(need_player)
            else:
                players_tab[self.get_random_letter()] = str(879324092732420107)
        return players_tab

    async def player_messages(self):
        while 1:
            try:
                message = await self.bot.wait_for("message", timeout=60, check=lambda m: m.channel == self.room)
                if message.author.id in (self.active_player, BOT_ID):
                    continue
                await message.delete()
            except TimeoutError:
                continue
            except NotFound:
                return
            except AttributeError:
                return

    async def wait_players(self):
        players_count = len(self.db.select("games", f"room_id == {self.room.id}", "players")["players"].split())
        while players_count < 10:
            join_button_click = await self.bot.wait_for("interaction", timeout=120,
                                                        check=lambda c: c.type.name == "component" and c.channel == self.hub and c.data["custom_id"] == f"potato-{self.db.select('games', f'room_id == {self.room.id}', 'game_number')['game_number']}")
            if await is_player_in_game(join_button_click.user.id, self.db):
                continue
            if self.db.select("users", f"user_id == {join_button_click.user.id}", "gold")["gold"] < self.cost:
                await join_button_click.response.send_message(embed=Embed(description="У Вас недостаточно золота", color=0xBF1818), ephimeral=True)
                continue
            if join_button_click.user.id in self.players_list.keys():
                continue
            try:
                await join_button_click.response.send_message(content=f"Вы подключились к игре. Перейдите в канал с игрой <#{self.room.id}>.", ephimeral=True)
            except NotFound:
                continue
            self.db.update("games", f"room_id == {self.room.id}", players=self.db.select("games", f"room_id == {self.room.id}", "players")["players"] + f" {join_button_click.user.id}")
            self.db.update("users", f"user_id == {join_button_click.user.id}", gold=self.db.select("users", f"user_id == {join_button_click.user.id}", "gold")["gold"] - self.cost)
            await self.room.set_permissions(join_button_click.user, read_messages=True, send_messages=True)
            if players_count == 2:
                view = View()
                view.add_item(Button(style=ButtonStyle.green, label="Начать игру", emoji="▶", custom_id="start"))
                await self.room.send("К игре подключилось минимальное количество человек, чтобы не ждать других игроков нажмите ниже", view=view)
                self.bot.loop.create_task(self.wait_for_accept())
            players_count = len(self.db.select("games", f"room_id == {self.room.id}", "players")["players"].split())
            self.players = players_count
            self.players_list[join_button_click.user.id] = 1 if self.mode == "s" else 3
            if (100 / self.players) * self.accept_players < 65:
                self.ready_to_start = 0
            await self.room.send(f"<@{join_button_click.user.id}> подключился к игре ({self.players}/10)")
            await self.invite_message.edit(embed=Embed(title=f"Игра \"Горячая картошка 🔥🥔\"\n",
                                                       description=f"Стоимость входа: **{self.cost}**\n"
                                                                   f"Игроки [{self.players}/10]: {', '.join([f'<@{i}>' for i in self.players_list.keys()])}",
                                                       color=0xEAEA04))
        self.db.update("games", f"room_id == {self.room.id}", started=1)
        self.ready_to_start = 2
        await self.starting_game()
