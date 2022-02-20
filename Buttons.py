from nextcord import ButtonStyle, Embed, Interaction, PermissionOverwrite
from nextcord.ui import View, button

from time import time


class ChoiceGame(View):
    def __init__(self, db, is_player_in_game):
        super().__init__()
        self.game_started = False
        self.db = db
        self.is_player_in_game = is_player_in_game
        self.room = None
        self.creator = None
        self.game = None
        self.game_number = None
        self.gamemode = None  # s - short, l - long

    @button(style=ButtonStyle.green, label="Горячая картошка (Быстрая)", emoji="🥔", row=0)
    async def potato_short(self, button, interaction: Interaction):
        if int(time()) - self.db.select("users", f"user_id == {interaction.user.id}", "last_info")["last_info"] <= 15:
            await interaction.response.pong()
            self.stop()
        if await self.is_player_in_game(interaction.user.id, self.db):
            await interaction.response.send_message(embed=Embed(description="Вы уже находитесь в игре", color=0xBF1818), ephemeral=True)
            self.db.update("users", f"user_id == {interaction.user.id}", last_info=int(time()))
            self.stop()
        await self.create_room("potato", interaction.channel, interaction.user)
        await interaction.response.send_message(f"Игра создана. Перейдите в канал с игрой <#{self.room.id}>.", ephemeral=True)
        self.game_started = True
        self.gamemode = "s"
        self.stop()

    @button(style=ButtonStyle.green, label="Горячая картошка (Длинная)", emoji="🥔", row=0)
    async def potato_long(self, button, interaction: Interaction):
        if int(time()) - self.db.select("users", f"user_id == {interaction.user.id}", "last_info")["last_info"] <= 15:
            await interaction.response.pong()
            self.stop()
        if await self.is_player_in_game(interaction.user.id, self.db):
            await interaction.response.send_message(embed=Embed(description="Вы уже находитесь в игре", color=0xBF1818), ephemeral=True)
            self.db.update("users", f"user_id == {interaction.user.id}", last_info=int(time()))
            self.stop()
        await self.create_room("potato", interaction.channel, interaction.user)
        await interaction.response.send_message(f"Игра создана. Перейдите в канал с игрой <#{self.room.id}>.", ephemeral=True)
        self.game_started = True
        self.gamemode = 'l'
        self.stop()

    @button(style=ButtonStyle.grey, label="Новые игры появятся позже...", emoji="🔃", row=1)
    async def nothing(self, button, interaction: Interaction):
        await interaction.response.pong()
        self.stop()

    async def create_room(self, game, channel, member):
        overwrites = {
            channel.guild.default_role: PermissionOverwrite(view_channel=False),
            member: PermissionOverwrite(view_channel=True, send_messages=True)
        }
        g = self.db.select('games', f'game_name == "{game}"')
        if g:
            game_number = g[-1]['game_number'] + 1 if isinstance(g, list) else g["game_number"] + 1
            if game_number > 99:
                game_number = 0
        else:
            game_number = 0
        room = await channel.guild.create_text_channel(f"{game}-{game_number}", category=channel.category, overwrites=overwrites)
        self.db.insert("games", room_id=room.id, game_name=game, game_number=game_number, started=0, players=f"{member.id}")
        self.room = room
        self.creator = member.id
        self.game = "potato"
        self.game_number = game_number
