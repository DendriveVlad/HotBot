from asyncio.exceptions import TimeoutError

import nextcord.errors
from nextcord import ButtonStyle, Embed, Interaction, Thread, Member, utils
from nextcord.ui import View, button, Button

from config import CHANNELS
from info import send_log


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
            await send_log(guild=interaction.guild, log_type="MinecraftRequestCreate", info=f"Создал заявку {thread.mention}", member=interaction.user, color=0x2B9B41)
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
    async def create(self, _, interaction: Interaction):
        buttons = (("Строительство", "🚧"), ("Квесты", "✒"), ("Дизайн", "✏"), ("Программирование", "✏"), ("Другое", "🧙"))
        view = View()
        for b in buttons:
            view.add_item(CButton(*b, self.bot))
        await interaction.response.send_message("Чем бы Вы хотели заняться на нашем проекте?", view=view, ephemeral=True)


class Confirm(View):
    def __init__(self):
        super().__init__(timeout=60)
        self.accept = True

    @button(style=ButtonStyle.success, label="Подтвердить", emoji="✅")
    async def confirm(self, _, interaction: Interaction):
        await interaction.response.pong()
        self.stop()

    @button(style=ButtonStyle.secondary, label="Отмена")
    async def cancel(self, _, interaction: Interaction):
        await interaction.response.pong()
        self.accept = False
        self.stop()


async def threadEngine(thread: Thread, member: Member, bot):
    rtype = thread.name.split("-")[0]
    try:
        q, q2, q3 = "", "", ""
        match rtype:
            case "Строительство":
                q = "Насколько хорошо Вы умеете работать с плагинами и модами для строительства?"
                q2 = "Что Вы умеете делать?"
                q3 = "Отправьте примеры своих работ (Хотя бы 3 скриншота)"
            case "Квесты":
                q = "На сколько хорошо Вы знаете русский язык?"
                q2 = "Чем бы Вы хотели заниматься на проекте?"
                q3 = "Какие из популярных аниме Вы знаете?"
            case "Дизайн":
                q = "В каких программах Вы работаете?"
                q2 = "Чем бы Вы хотели заниматься на проекте?"
                q3 = "Отправьте примеры своих работ (Хотя бы 3 скриншота)"
            case "Программирование":
                q = "Какие языки программирования Вы знаете?"
                q2 = "Чем бы Вы хотели заниматься на проекте?"
            case "Другое":
                q = "Что Вы умеете?"
                q2 = "Чем бы Вы хотели заниматься на проекте?"
        request = {}
        for mess in (("name", "Скажите, как Вас зовут?"),
                     ("age", "Сколько Вам лет?"),
                     ("about", "Расскажите немного о себе (У Вас 10 минут, иначе ветка удалится)"),
                     ("exp", "Был ли у Вас хоть какой-то опыт работы на серверах? Если да, то распишите какой."),
                     ("join_reason", "Почему Вы хотите присоединиться к нашему проекту?"),
                     ("spend_time", "Сколько Вы готовы уделять времени проекту?"),
                     ("needs", "Чего бы вы хотели от проекта?"),
                     ("skill", q),
                     ("doing", q2),
                     ("works", q3)):
            request[mess[0]] = None
            if mess[-1]:
                m = await thread.send(mess[-1])
                text = await bot.wait_for("message", timeout=300, check=lambda x: x.author.id == member.id and x.channel.id == thread.id)

                acceptation = await confirm(thread, member, bot, text)
                if acceptation:
                    text = acceptation
                await m.delete()
                await text.delete()
                request[mess[0]] = text.content

    except TimeoutError:
        await thread.delete()
        await send_log(guild=thread.guild, log_type="MinecraftRequestRemove", info="Заявка удалена", member=member, color=0x1E8031)
        return

    info = [f"**Имя:** {request['name']}",
            f"**Возраст:** {request['age']}",
            f"**Личная информация:** {request['about']}",
            f"**Опыт работы:** {request['exp']}",
            f"**Мотивы:** {request['join_reason']}",
            f"**Свободное время:** {request['spend_time']}",
            f"**Желания:** {request['needs']}",
            f"**Умения:** {request['skill']}"]
    if request['doing']:
        info.append(f"**Желаемый род занятий:** {request['doing']}")
    if request['works'] and rtype == "Квесты":
        info.append(f"**Известные аниме:** {request['works']}")

    await thread.send(f"{member.mention} создал заявку", embed=Embed(title=rtype, description="\n".join(info)))

    admin = utils.get(thread.guild.channels, id=CHANNELS["admin_requests"])
    await send_log(guild=thread.guild, log_type="MinecraftRequestComplete", info=f"Заявка заполнена {thread.mention}", member=member, color=0x2B9B41)
    await admin.send(f"<@455008287188844544> Поступила новая заявка: {thread.mention}")


async def confirm(thread, member, bot, text, last=False):
    while True:
        view = Confirm()
        m = await thread.send("Перейти к следующему вопросу?" if not last else "Завершить вопросы?", view=view)
        await view.wait()
        await m.delete()
        if not view.accept:
            if text:
                await text.delete()
            text = await bot.wait_for("message", timeout=300, check=lambda x: x.author.id == member.id and x.channel.id == thread.id)
        else:
            return text


async def requests(channel, bot):
    await channel.purge()
    view = CreateRequest(channel, bot)
    await channel.send(embed=Embed(description="Хотите стать частью нашего замечательного Minecraft-Проекта?\n"
                                               "Значит Вам сюда! (от 13 лет)", color=0x1EE575), view=view)
