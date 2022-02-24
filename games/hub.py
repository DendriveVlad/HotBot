from time import time

from nextcord import ButtonStyle, Embed, PermissionOverwrite, Interaction
from nextcord.ui import View, button

from games.potato import potato_game, is_player_in_game


class ChoiceGame(View):
    def __init__(self, db, bot):
        super().__init__(timeout=None)
        self.db = db
        self.bot = bot

    @button(style=ButtonStyle.green, label="Горячая картошка (Быстрая)", emoji="🥔", row=0, custom_id="potato_short")
    async def potato_short(self, button, interaction: Interaction):
        await self.create_room("potato", interaction)

    @button(style=ButtonStyle.green, label="Горячая картошка (Длинная)", emoji="🥔", row=0, custom_id="potato_long")
    async def potato_long(self, button, interaction: Interaction):
        await self.create_room("potato", interaction)

    @button(style=ButtonStyle.grey, label="Новые игры появятся позже...", emoji="🔃", row=1)
    async def nothing(self, button, interaction: Interaction):
        await interaction.response.pong()

    async def create_room(self, game, interaction: Interaction):
        if int(time()) - self.db.select("users", f"user_id == {interaction.user.id}", "last_info")["last_info"] <= 15:
            await interaction.response.pong()
            return
        if await is_player_in_game(interaction.user.id, self.db):
            await interaction.response.send_message(embed=Embed(description="Вы уже находитесь в игре", color=0xBF1818), ephemeral=True)
            self.db.update("users", f"user_id == {interaction.user.id}", last_info=int(time()))
            return

        overwrites = {
            interaction.channel.guild.default_role: PermissionOverwrite(view_channel=False),
            interaction.user: PermissionOverwrite(view_channel=True, send_messages=True)
        }
        g = self.db.select('games', f'game_name == "{game}"')
        if g:
            game_number = g[-1]['game_number'] + 1 if isinstance(g, list) else g["game_number"] + 1
            if game_number > 99:
                game_number = 0
        else:
            game_number = 0
        room = await interaction.channel.guild.create_text_channel(f"{game}-{game_number}", category=interaction.channel.category, overwrites=overwrites)
        self.db.insert("games", room_id=room.id, game_name=game, game_number=game_number, started=0, players=f"{interaction.user.id}")
        self.bot.loop.create_task(potato_game(room, interaction.user.id, self.bot, self.db, interaction.channel, "s" if interaction.data["custom_id"] == "potato_short" else "l"))  # только для картошко-игры
        await interaction.response.send_message(f"Игра создана. Перейдите в канал с игрой <#{room.id}>.", ephemeral=True)
        await self.bot.send_log(f"[GameCreate] <@{interaction.user.id}> создал игру {game}-{game_number}", color=0xE160F9)


async def hub(channel, bot, db):
    await channel.purge()
    view = ChoiceGame(db, bot)
    await channel.send(embed=Embed(description="В какие игры сегодня хотите поиграть?", color=0x1EE575), view=view)
