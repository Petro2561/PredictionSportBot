from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from bot.bot import main_bot
from bot.scheduler.jokes import JOKES
from bot.utils.common import get_tour
from db.db import get_async_session
from db.models import Player, Tour, Tournament

scheduler = AsyncIOScheduler()


async def send_reminders():
    async for session in get_async_session():
        result = await session.execute(
            select(Tournament).options(
                selectinload(Tournament.players).selectinload(Player.user)
            )
        )
        tournaments = result.scalars().all()
        for tournament in tournaments:
            if tournament.players:
                players = tournament.players
                tour: Tour = await get_tour(tournament)
                if datetime.now() > tour.next_deadline:
                    continue
                reminder_time = tour.next_deadline - timedelta(hours=6)
                current_time = datetime.now()
                if current_time >= reminder_time:
                    for player in players:
                        await session.refresh(player, ["user"])
                        if player.user.username in JOKES and player.is_eliminated == False:
                            await main_bot.send_message(
                                chat_id=player.user.telegram_id,
                                text=JOKES[player.user.username],
                            )
                        else:
                            await main_bot.send_message(
                                chat_id=player.user.telegram_id,
                                text=f"Напоминание: сегодня дедлайн по прогнозам!",
                            )


scheduler.add_job(send_reminders, CronTrigger(hour="*/2"))
