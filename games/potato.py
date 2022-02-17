import string
from asyncio.exceptions import TimeoutError
from asyncio import sleep
from random import choice, sample, randint, shuffle

from discord_components import Button, ButtonStyle
from discord.errors import NotFound
from discord import Embed

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


async def potato_game(room, owner, bot, db, game_hub):
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

    except TimeoutError:
        await room.purge()
        await room.send("Время настройки вышло, канал удаляется.")
        await sleep(5)
        db.delete("games", f"room_id == {room.id}")
        await bot.send_log(f"[GameNotStarted] Игра <@{owner}> не началась", color=0xA927C1)
        await room.delete()
        return

    game.invite_message = await game_hub.send(embed=Embed(title=f"Игра \"Горячая картошка 🔥🥔\"\n",
                                                          description=f"Стоимость входа: **{game.cost}**\n"
                                                                      f"Игроки [{game.players}/10]: <@{owner}>",
                                                          color=0xEAEA04),
                                              components=[Button(style=ButtonStyle.green, label="Подключиться", emoji="➕", custom_id=f"potato-{db.select('games', f'room_id == {room.id}', 'game_number')['game_number']}")])
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
                    for player in game.players_list:
                        db.update("users", f"user_id == {player}", gold=db.select("users", f"user_id == {player}", "gold")["gold"] + game.cost)
                await bot.send_log(f"[GameNotStarted] Игра <@{owner}> не началась", color=0xA927C1)
                return


class Game:
    def __init__(self, bot, room, db, game_hub, owner):
        self.bot = bot
        self.room = room
        self.db = db
        self.hub = game_hub

        self.invite_message = None

        self.ready_to_start = 0  # 0 - не готовы, 1 - игра начинается, 2 - игра уже началась
        self.players_list = [owner]  # Список всех действующих игроков
        self.total_players_list = []  # Список всех действующих игроков
        self.total_players = 1  # Всего игроков в игре
        self.players = 1  # Количество действующих игроков
        self.accept_players = 0  # Количество игроков подтвердивших быстрый страт игры
        self.accepts_list = []  # Список игроков подтвердивших быстрый страт игры
        self.active_player = 0  # Игрок, у которого в данный момент картошка
        self.cost = 0  # Стоимость входа в игру
        self.total_money = 0  # Всего денег вложенных в игру
        self.difficulty = 0  # Сложность раунда

    async def wait_for_accept(self):
        while 1:
            try:
                accept_click = await self.bot.wait_for("button_click", timeout=60, check=lambda c: c.channel == self.room)
                await accept_click.respond(type=6)
                if accept_click.author.id in self.accepts_list:
                    continue
                self.accepts_list.append(accept_click.author.id)
                self.accept_players += 1
                await self.room.send(embed=Embed(description=f"{accept_click.author.mention} проголосовал за начало игры ({self.accept_players}/{self.players})"))
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
        self.total_players_list = self.players_list.copy()
        self.active_player, ignore_players = self.get_random_player([])
        passed_rounds = False  # служит для обновления сложности (False - означает, что предыдущий раунд был на сложности ниже раунда до этого или проигрышным, или игра только началась; True - значит, что следующий раунд будет на сложности +1)
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
                        await self.room.send(embed=Embed(description=f"<@{self.active_player}> передаёт картошку", color=0x21F300))
                        self.active_player = next_player
                        if passed_rounds:
                            self.difficulty += 1
                        if self.players <= 4:  # Если игроков меньше 5, то включается ускорение усложнения
                            self.difficulty += randint(0, 1)
                        passed_rounds = not passed_rounds
                        continue
                    else:
                        await self.room.send(embed=Embed(description=f"<@{self.active_player}> передаёт картошку не тому игроку и обжигает его, в ответ этот игрок избил бросающегося до смерти", color=0xF9871C))
                except KeyError:
                    await self.room.send(embed=Embed(description=f"<@{self.active_player}> выкидывает картошку непонятно куда, из-за чего она разбивает окно, а владелиц окна решает испытать своё ружьё на игроке, который бросил картошку", color=0xF9871C))
            except TimeoutError:
                await self.room.send(embed=Embed(description=f"<@{self.active_player}> влюбляется в картошку, но картошка не разделяет эту любов и сжигает своего фаната", color=0xF9871C))

            self.players_list.remove(self.active_player)
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
            passed_rounds = False
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
        players = self.players_list.copy()
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
            join_button_click = await self.bot.wait_for("button_click", timeout=120,
                                                        check=lambda c: c.channel == self.hub and c.custom_id == f"potato-{self.db.select('games', f'room_id == {self.room.id}', 'game_number')['game_number']}")
            if await is_player_in_game(join_button_click.author.id, self.db):
                continue
            if self.db.select("users", f"user_id == {join_button_click.author.id}", "gold")["gold"] < self.cost:
                await join_button_click.respond(embed=Embed(description="У Вас недостаточно золота", color=0xBF1818))
                continue
            if join_button_click.author.id in self.players_list:
                continue
            try:
                await join_button_click.respond(content=f"Вы подключились к игре. Перейдите в канал с игрой <#{self.room.id}>.")
            except NotFound:
                continue
            self.db.update("games", f"room_id == {self.room.id}", players=self.db.select("games", f"room_id == {self.room.id}", "players")["players"] + f" {join_button_click.author.id}")
            self.db.update("users", f"user_id == {join_button_click.author.id}", gold=self.db.select("users", f"user_id == {join_button_click.author.id}", "gold")["gold"] - self.cost)
            await self.room.set_permissions(join_button_click.author, read_messages=True, send_messages=True)
            if players_count == 2:
                await self.room.send("К игре подключилось минимальное количество человек, чтобы не ждать других игроков нажмите ниже",
                                     components=[Button(style=ButtonStyle.green, label="Начать игру", emoji="▶", custom_id="start")]
                                     )
                self.bot.loop.create_task(self.wait_for_accept())
            players_count = len(self.db.select("games", f"room_id == {self.room.id}", "players")["players"].split())
            self.players = players_count
            self.players_list.append(join_button_click.author.id)
            if (100 / self.players) * self.accept_players < 65:
                self.ready_to_start = 0
            await self.room.send(f"<@{join_button_click.author.id}> подключился к игре ({self.players}/10)")
            await self.invite_message.edit(embed=Embed(title=f"Игра \"Горячая картошка 🔥🥔\"\n",
                                                       description=f"Стоимость входа: **{self.cost}**\n"
                                                                   f"Игроки [{self.players}/10]: {', '.join([f'<@{i}>' for i in self.players_list])}",
                                                       color=0xEAEA04))
        self.db.update("games", f"room_id == {self.room.id}", started=1)
        self.ready_to_start = 2
        await self.starting_game()
