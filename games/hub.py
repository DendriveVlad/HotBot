from time import time

from nextcord import ButtonStyle, Embed, PermissionOverwrite, Interaction
from nextcord.ui import View, button

from games.potato import potato_game
from games.mafia import mafia_game
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


class ChoiceGame(View):
    def __init__(self, db, bot):
        super().__init__(timeout=None)
        self.db = db
        self.bot = bot

    @button(style=ButtonStyle.success, label="Горячая картошка (Быстрая)", emoji="🥔", row=0, custom_id="potato_short")
    async def potato_short(self, _, interaction: Interaction):
        await self.create_room("potato", interaction)

    @button(style=ButtonStyle.success, label="Горячая картошка (Длинная)", emoji="🥔", row=0, custom_id="potato_long")
    async def potato_long(self, _, interaction: Interaction):
        await self.create_room("potato", interaction)

    @button(style=ButtonStyle.success, label="Мафия Lite", emoji="🤵", row=1, custom_id="mafia")
    async def mafia(self, _, interaction: Interaction):
        await self.create_room("mafia", interaction)

    async def create_room(self, game, interaction: Interaction):
        if int(time()) - self.db.select("users", f"user_id == {interaction.user.id}", "last_info")["last_info"] <= 15:
            await interaction.response.pong()
            return
        if await is_player_in_game(interaction.user.id, self.db):
            await interaction.response.send_message(embed=Embed(description="Вы уже находитесь в игре", color=0xBF1818), ephemeral=True)
            self.db.update("users", f"user_id == {interaction.user.id}", last_info=int(time()))
            return

        overwrites = {
            interaction.channel.guild.default_role: PermissionOverwrite(view_channel=False, send_messages=True if game == "potato" else False),
            interaction.user: PermissionOverwrite(view_channel=True, send_messages=True)
        }
        g = self.db.select('games', f'game_name == "{game}"')
        if g:
            game_number = g[-1]['game_number'] + 1 if isinstance(g, list) else g["game_number"] + 1
            if game_number > 99:
                game_number = 0
        else:
            game_number = 0
        room = await interaction.channel.guild.create_text_channel(f"{game}-{game_number}", category=interaction.channel.category, overwrites=overwrites, slowmode_delay=2)
        self.db.insert("games", room_id=room.id, game_name=game, game_number=game_number, started=0, players=f"{interaction.user.id}")
        match game:
            case "potato":
                self.bot.loop.create_task(potato_game(room, interaction.user.id, self.bot, self.db, interaction.channel, "s" if interaction.data["custom_id"] == "potato_short" else "l"))
            case "mafia":
                self.bot.loop.create_task(mafia_game(room, interaction.user.id, self.bot, self.db, interaction.channel))
        await interaction.response.send_message(f"Игра создана. Перейдите в канал с игрой <#{room.id}>.", ephemeral=True)
        await send_log(guild=interaction.guild, log_type="GameCreate", info=f"Создал игру {game}-{game_number}", member=interaction.user, color=0xE160F9)


async def hub(channel, bot, db):
    await channel.purge()
    view = ChoiceGame(db, bot)
    await channel.send(embed=Embed(description="В какие игры сегодня хотите поиграть?", color=0x1EE575), view=view)
