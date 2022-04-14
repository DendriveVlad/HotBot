from asyncio.exceptions import TimeoutError

import nextcord.errors
from nextcord import ButtonStyle, Embed, Interaction, Thread, Member, utils
from nextcord.ui import View, button, Button

from config import CHANNELS


class CButton(Button):
    def __init__(self, label, emoji, bot):
        super().__init__(label=label, emoji=emoji)
        self.rtype = None
        self.bot = bot

    async def callback(self, interaction: Interaction):
        m = await interaction.channel.send(f"{interaction.user.mention} перейдите в созданный **Поток**")
        thread = await interaction.channel.create_thread(name=f"{self.label}-{interaction.user}", message=m)
        try:
            await interaction.response.send_message(f"Перейдите в ветку {thread.mention} и ответьте на вопросы", ephemeral=True)
        except nextcord.errors.NotFound:
            pass
        await m.delete()
        self.disabled = True
        self.view.stop()
        await threadEngine(thread, interaction.user, self.bot)


class CreateRequest(View):
    def __init__(self, channel, bot):
        super().__init__(timeout=None)
        self.channel = channel
        self.bot = bot

    @button(style=ButtonStyle.success, label="Создать заявку", emoji="📝", custom_id="create")
    async def create(self, button, interaction: Interaction):
        btns = (("Строительство", "🚧"), ("Квесты", "✒"), ("Дизайн", "✏"), ("Программирование", "✏"), ("Другое", "🧙"))
        view = View()
        for b in btns:
            view.add_item(CButton(*b, self.bot))
        await interaction.response.send_message("Чем бы Вы хотели заняться на нашем проекте?", view=view, ephemeral=True)


class Confirm(View):
    def __init__(self):
        super().__init__(timeout=60)
        self.accept = True

    @button(style=ButtonStyle.success, label="Подтвердить", emoji="✅")
    async def confirm(self, button, interaction: Interaction):
        self.stop()

    @button(style=ButtonStyle.secondary, label="Отмена")
    async def cancel(self, button, interaction: Interaction):
        self.accept = False
        self.stop()


async def threadEngine(thread: Thread, member: Member, bot):
    rtype = thread.name.split("-")[0]
    try:
        m = await thread.send(f"Cкажите, как Вас зовут?")
        text = await bot.wait_for("message", timeout=300, check=lambda m: m.author.id == member.id and m.channel.id == thread.id)

        acceptation = await confirm(thread, member, bot, text)
        if acceptation:
            text = acceptation
        await m.delete()
        await text.delete()
        name = text.content

        m = await thread.send("Сколько Вам лет?")
        text = await bot.wait_for("message", timeout=300, check=lambda m: m.author.id == member.id and m.channel.id == thread.id)

        acceptation = await confirm(thread, member, bot, text)
        if acceptation:
            text = acceptation
        await m.delete()
        await text.delete()
        age = text.content

        m = await thread.send("Расскажите немного о себе (У Вас 10 минут, иначе ветка удалится)")
        text = await bot.wait_for("message", timeout=600, check=lambda m: m.author.id == member.id and m.channel.id == thread.id)

        acceptation = await confirm(thread, member, bot, text)
        if acceptation:
            text = acceptation
        await m.delete()
        await text.delete()
        about = text.content

        if rtype == "Другое":
            m = await thread.send("Был ли у Вас хоть какой-то опыт работы на серверах? Если да, то распишите какой.")
        else:
            m = await thread.send("Какой у вас опыт работы в данной сфере?")
        text = await bot.wait_for("message", timeout=600, check=lambda m: m.author.id == member.id and m.channel.id == thread.id)

        acceptation = await confirm(thread, member, bot, text)
        if acceptation:
            text = acceptation
        await m.delete()
        await text.delete()
        exp = text.content

        m = await thread.send("Почему Вы хотите присоединиться к нашему проекту?")
        text = await bot.wait_for("message", timeout=600, check=lambda m: m.author.id == member.id and m.channel.id == thread.id)

        acceptation = await confirm(thread, member, bot, text)
        if acceptation:
            text = acceptation
        await m.delete()
        await text.delete()
        join_reason = text.content

        m = await thread.send("Сколько Вы готовы уделять времени проекту?")
        text = await bot.wait_for("message", timeout=300, check=lambda m: m.author.id == member.id and m.channel.id == thread.id)

        acceptation = await confirm(thread, member, bot, text)
        if acceptation:
            text = acceptation
        await m.delete()
        await text.delete()
        spend_time = text.content

        m = await thread.send("Чего бы вы хотели от проекта?")
        text = await bot.wait_for("message", timeout=600, check=lambda m: m.author.id == member.id and m.channel.id == thread.id)

        acceptation = await confirm(thread, member, bot, text)
        if acceptation:
            text = acceptation
        await m.delete()
        await text.delete()
        needs = text.content

        match rtype:
            case "Строительство":
                m = await thread.send("Насколько хорошо Вы умеете работать с плагинами и модами для строительства?")
            case "Квесты":
                m = await thread.send("На сколько хорошо Вы знаете русский язык?")
            case "Дизайн":
                m = await thread.send("В каких программах Вы работаете?")
            case "Программирование":
                m = await thread.send("Какие языки программирования Вы знаете?")
            case "Другое":
                m = await thread.send("Что Вы умеете?")
        text = await bot.wait_for("message", timeout=600, check=lambda m: m.author.id == member.id and m.channel.id == thread.id)

        acceptation = await confirm(thread, member, bot, text)
        if acceptation:
            text = acceptation
        await m.delete()
        await text.delete()
        skill = text.content

        doing = None
        if rtype != "Строительство":
            if rtype == "Программирование":
                m = await thread.send("Что Вы умеете делать?")
            else:
                m = await thread.send("Чем бы Вы хотели заниматься на проекте?")
            text = await bot.wait_for("message", timeout=600, check=lambda m: m.author.id == member.id and m.channel.id == thread.id)

            acceptation = await confirm(thread, member, bot, text, last=True if rtype not in ("Дизайн", "Квесты") else False)
            if acceptation:
                text = acceptation
            await m.delete()
            await text.delete()
            doing = text.content

        works = None
        if rtype in ("Строительство", "Дизайн"):
            m = await thread.send("Скиньте примеры своих работ (Хотя бы 3 скриншота)")
            text = await bot.wait_for("message", timeout=600, check=lambda m: m.author.id == member.id and m.channel.id == thread.id)

            acceptation = await confirm(thread, member, bot, text, last=True)
            if acceptation:
                text = acceptation
            await m.delete()
        if rtype == "Квесты":
            m = await thread.send("Какие из популярных аниме Вы знаете?")
            text = await bot.wait_for("message", timeout=600, check=lambda m: m.author.id == member.id and m.channel.id == thread.id)

            acceptation = await confirm(thread, member, bot, text, last=True)
            if acceptation:
                text = acceptation
            await text.delete()
            await m.delete()
            works = text.content
    except TimeoutError:
        await thread.delete()
        return

    info = [f"**Имя:** {name}", f"**Возраст:** {age}", f"**Личная информация:** {about}", f"**Опыт работы:** {exp}", f"**Мотивы:** {join_reason}", f"**Свободное время:** {spend_time}", f"**Желания:** {needs}", f"**Умения:** {skill}"]
    if doing:
        info.append(f"**Желаемый род занятий:** {doing}")
    if works and rtype == "Квесты":
        info.append(f"**Известные аниме:** {works}")

    await thread.send(f"{member.mention} создал заявку", embed=Embed(title=rtype, description="\n".join(info)))

    admin = utils.get(thread.guild.channels, id=CHANNELS["admin_requests"])
    await admin.send(f"@everyone Поступила новая заявка: {thread.mention}")


async def confirm(thread, member, bot, text, last=False):
    while True:
        view = Confirm()
        m = await thread.send("Перейти к следующему вопросу?" if not last else "Завершить вопросы?", view=view)
        await view.wait()
        await m.delete()
        if not view.accept:
            if text:
                await text.delete()
            text = await bot.wait_for("message", timeout=300, check=lambda m: m.author.id == member.id and m.channel.id == thread.id)
        else:
            return text


async def requests(channel, bot):
    await channel.purge()
    view = CreateRequest(channel, bot)
    await channel.send(embed=Embed(description="Хотите стать частью нашего замечательного Minecraft-Проекта?\n"
                                               "Значит Вам сюда! (от 13 лет)", color=0x1EE575), view=view)
