from games.potato import potato_game, is_player_in_game
from Buttons import *


async def hub(channel, bot, db):
    await channel.purge()
    view = ChoiceGame(db, is_player_in_game)
    await channel.send(embed=Embed(description="В какие игры сегодня хотите поиграть?", color=0x1EE575), view=view)
    while True:
        await view.wait()
        if view.game_started:
            bot.loop.create_task(potato_game(view.room, view.creator, bot, db, channel, view.gamemode))
            await bot.send_log(f"[GameCreate] <@{view.creator}> создал игру {view.game}-{view.game_number}", color=0xE160F9)
