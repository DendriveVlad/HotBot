from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from requests import get
from requests.exceptions import ConnectionError

from config import LEVEL_POINTS


def get_top(guild, db):
    top = Image.new("RGBA", (1600, 560), (0, 0, 0, 0))
    draw = ImageDraw.Draw(top)

    level_font = ImageFont.truetype("/home/nehot/Bot/image_processing/bahnschrift.ttf", 20)
    name_font = ImageFont.truetype("/home/nehot/Bot/image_processing/bahnschrift.ttf", 40)
    place_font = ImageFont.truetype("/home/nehot/Bot/image_processing/bahnschrift.ttf", 30)
    title_font = ImageFont.truetype("/home/nehot/Bot/image_processing/GOST_B.TTF", 60)

    draw.text((10, 10), "ТОП ПО ОПЫТУ", font=title_font, fill=(67, 120, 211))
    draw.text((1165, 10), "ТОП ПО ЗОЛОТУ", font=title_font, fill=(228, 180, 30))

    user_level = []
    container = {}
    for date in db.select("users", f"", "user_id", "points"):
        container[date["user_id"]] = date["points"]
    for id, points in sorted(container.items(), key=lambda item: item[1], reverse=True):
        user_level.append((id, points))

    place = 0
    for h in range(51, 560):
        if h > 100 and h % 50 == 1 and place < 10:
            level = 0
            for lvl, need_points in LEVEL_POINTS.items():
                if user_level[place][-1] < need_points:
                    break
                level = lvl
            while 1:
                try:
                    user = guild.get_member(user_level[place][0])
                    top.paste(Image.open(BytesIO(get(str(user.avatar.url), stream=True).content)).convert("RGBA").resize((41, 41), Image.ANTIALIAS), (52, h - 40))  # картинка
                    break
                except:
                    top.paste(Image.open("default_avatar.png"))
            draw.ellipse((72, h - 20, 95, h + 3), fill=(223, 233, 252), outline=(120, 144, 193))  # level sphere
            draw.text((79 if level < 10 else 74, h - 17), str(level), font=level_font, fill=(196, 61, 255))  # level
            draw.text((105, h - 42), user.nick if user.nick else user.name, font=name_font, fill=user.color.to_rgb())  # name
            draw.text((115 + name_font.getsize(str(user.nick if user.nick else user.name))[0], h - 42), str(user_level[place][-1]), font=name_font, fill=(67, 120, 211))  # points
            draw.text((10, h - 35), (" " if place != 9 else "") + str(place + 1) + ")", font=place_font, fill=(67, 120, 211))  # rank
            place += 1

    user_gold = []
    container = {}
    for date in db.select("users", f"", "user_id", "gold"):
        container[date["user_id"]] = date["gold"]
    for id, gold in sorted(container.items(), key=lambda item: item[1], reverse=True):
        user_gold.append((id, gold))

    place = 0
    for h in range(51, 560):
        if h > 100 and h % 50 == 1 and place < 10:
            user = guild.get_member(user_gold[place][0])
            top.paste(Image.open(BytesIO(get(str(user.avatar.url), stream=True).content)).convert("RGBA").resize((41, 41), Image.ANTIALIAS), (1510, h - 40))  # картинка
            draw.text((1490 - name_font.getsize(str(user_gold[place][-1]))[0] - name_font.getsize(user.nick if user.nick else user.name)[0], h - 42), str(user_gold[place][-1]), font=name_font, fill=(228, 180, 30), align="right")  # gold
            draw.text(((1599 - name_font.getsize(user.nick if user.nick else user.name)[0]) - 100, h - 42), user.nick if user.nick else user.name, font=name_font, fill=user.color.to_rgb(), align="right")  # name
            draw.text((1560, h - 35), "(" + str(place + 1), font=place_font, fill=(228, 180, 30), align="right")  # rank
            place += 1

    top.save("top.png")
    return "top.png"
