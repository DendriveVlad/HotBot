from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from requests import get

from config import LEVEL_POINTS


def get_rank(guild, member_id, db):
    back = Image.open("/home/nehot/Bot/image_processing/exod.png")

    user = guild.get_member(member_id)
    try:
        avatar = Image.open(BytesIO(get(str(user.avatar.url), stream=True).content)).convert("RGBA").resize((300, 300), Image.ANTIALIAS)
    except AttributeError | UnidentifiedImageError:
        avatar = Image.open("default_avatar.png")

    front = Image.open("/home/nehot/Bot/image_processing/front.png")

    draw = ImageDraw.Draw(back)
    # аватарка
    for i in range(160, 481):
        for j in range(140, 461):
            if back.getpixel((j, i)) != (16, 26, 42, 255):
                m = [i for i in avatar.getpixel((j - 153, i - 469))]
                if front.getpixel((j, i))[-1] != 255:
                    if m[-1] == 0:
                        m = (16, 26, 42, 255 - front.getpixel((j, i))[-1])
                    elif m[-1] > 80:
                        m[-1] = front.getpixel((j, i))[-1]
                draw.point((j, i), tuple(m))

    date = db.select("users", f"user_id == {member_id}", "points", "gold")

    previous_points, points, points_to_next_level, level = 0, date["points"], 0, 0
    for lvl, need_points in LEVEL_POINTS.items():
        if points < need_points:
            points_to_next_level = need_points
            break
        level = lvl
        previous_points = need_points

    one_percent = (points_to_next_level - previous_points) / 100  # Один процент
    percents = (points - previous_points) / one_percent  # Всего процентов

    # полоска уровня
    d = -1
    for i in range(295, 346):
        if i % 2:
            d += 1
        last = 1355 * (percents / 100) + 475
        for j in range(475, 1356):
            one_part = (1355 - 475) / 100  # одна часть
            parts = (j - 475) // one_part  # сколько всего частей сейчас
            s = j - (i - 295) + d
            if s > last:
                break
            if (percents > 99.4 or level == 30) and back.getpixel((j, i)) != (16, 26, 42, 255):
                draw.point((j, i), (0, 255, 0, 255))
            elif (percents >= parts) and back.getpixel((s, i)) != (16, 26, 42, 255) and s > 475:
                draw.point((s, i), (0, 255, 0, 255))

    level_font = ImageFont.truetype("/home/nehot/Bot/image_processing/GOST_B.TTF", 80)
    name_font = ImageFont.truetype("/home/nehot/Bot/image_processing/GOST_B.TTF", 60)
    gold_lvl_font = ImageFont.truetype("/home/nehot/Bot/image_processing/bahnschrift.ttf", 45)

    name = user.nick if user.nick else user.name
    draw.text((480, 235), name, font=name_font, fill=(220, 220, 220))  # name
    draw.text((500, 390), f"Уровень {level}", font=level_font, fill=(155, 202, 227))  # Level
    draw.text((920, 375), f"Опыт: {points}", font=gold_lvl_font, fill=(67, 120, 211))  # points
    draw.text((920, 425), f"Золота: {date['gold']}", font=gold_lvl_font, fill=(169, 149, 17))  # gold

    back.save("rank.png")
    return "rank.png"
