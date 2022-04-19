from nextcord import Embed, ButtonStyle, Interaction
from nextcord.ui import button, View


class RolesMarket(View):
    def __init__(self, db, bot):
        super().__init__(timeout=None)
        self.db = db
        self.bot = bot

    @button(style=ButtonStyle.success, label="Создать роль", emoji="☀")
    async def create(self, button, interaction: Interaction):
        user_db = self.db.select("users", f"user_id == {interaction.user.id}", "points", "gold", "role")
        if user_db["role"]:
            await interaction.response.send_message(embed=Embed(description="У Вас уже есть собственная роль", color=0xBF1818), ephemeral=True)
            return
        if self.bot.get_level(interaction.user.id) < 5 or self.db.select("users", f"user_id == {interaction.user.id}", "gold")["gold"] < 500:
            await interaction.response.send_message(embed=Embed(description="Для создания роли необходим иметь **5-й** уровень и **500** золота", color=0xBF1818), ephemeral=True)
            return
        role = interaction.guild.create_role()
        self.db.update("users")


def rolesManager(channel, bot, db):
    await channel.purge()
    view = RolesMarket(db, bot)
    await channel.send(embed=Embed(description="Для создания собственной роли требуется 5 уровень и 500 золота", color=0x1EE575), view=view)
