from asyncio.exceptions import TimeoutError
from time import time

from discord_components import Button, ButtonStyle
from discord import Embed, PermissionOverwrite
from discord.errors import NotFound

from games.potato import potato_game, is_player_in_game


async def hub(channel, bot, db):
    await channel.purge()
    await channel.send(embed=Embed(description="В какие игры сегодня хотите поиграть?", color=0x1EE575), components=[
        Button(style=ButtonStyle.green, label="Горячая картошка", emoji="🥔", custom_id="potato"),
        Button(style=ButtonStyle.grey, label="Новые игры появятся позже...", emoji="🔃", custom_id="-")
    ])
    while True:
        try:
            response = await bot.wait_for("button_click", timeout=60)
            if response.channel == channel:
                if int(time()) - db.select("users", f"user_id == {response.author.id}", "last_info")["last_info"] <= 15:
                    await response.respond(type=6)
                    continue

                if await is_player_in_game(response.author.id, db):
                    await response.respond(
                        type=4,
                        embed=Embed(description="Вы уже находитесь в игре", color=0xBF1818))
                    db.update("users", f"user_id == {response.author.id}", last_info=int(time()))
                    continue

                async def create_room(game):
                    overwrites = {
                        channel.guild.default_role: PermissionOverwrite(view_channel=False),
                        response.author: PermissionOverwrite(view_channel=True, send_messages=True)
                    }
                    g = db.select('games', f'game_name == "{game}"')
                    if g:
                        game_number = g[-1]['game_number'] + 1 if isinstance(g, list) else g["game_number"] + 1
                        if game_number > 99:
                            game_number = 0
                    else:
                        game_number = 0
                    room = await channel.guild.create_text_channel(f"{game}-{game_number}", category=channel.category, overwrites=overwrites)
                    db.insert("games", room_id=room.id, game_name=game, game_number=game_number, started=0, players=f"{response.author.id}")
                    bot.loop.create_task(potato_game(room, response.author.id, bot, db, channel))
                    await response.respond(content=f"[GameCreate] Игра создана. Перейдите в канал с игрой <#{room.id}>.")
                    await bot.send_log(f"<@{response.author.id}> создал игру {game}-{game_number}", color=0xE160F9)

                match response.custom_id:
                    case "-":
                        await response.respond(type=6)
                    case "potato":
                        await create_room("potato")

        except TimeoutError:
            continue
        except NotFound:
            continue
