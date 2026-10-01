"""Deliver administrator broadcasts to known bot users at a moderate rate."""

import asyncio
import logging
from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardMarkup

from nihao_tyan.services.activity_log import record_event
from nihao_tyan.storage.users import get_broadcast_recipients

logger = logging.getLogger(__name__)
broadcast_lock = asyncio.Lock()
SEND_INTERVAL_SECONDS = 0.1


@dataclass(frozen=True, slots=True)
class BroadcastResult:
    sent: int
    unavailable: int
    failed: int


async def recipient_batches(through_id: int, explicit_ids: tuple[int, ...] | None):
    if explicit_ids is not None:
        for offset in range(0, len(explicit_ids), 200):
            yield explicit_ids[offset : offset + 200]
        return
    last_id = 0
    while recipients := await get_broadcast_recipients(last_id, through_id):
        yield recipients
        last_id = recipients[-1]


async def deliver_broadcast(
    bot: Bot,
    admin_id: int,
    kind: str,
    text: str,
    through_id: int,
    target_count: int,
    audience: str,
    explicit_ids: tuple[int, ...] | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> BroadcastResult:
    sent = unavailable = failed = 0
    record_event("broadcast_started", admin_id=admin_id, kind=kind, audience=audience, recipients=target_count)
    async for recipients in recipient_batches(through_id, explicit_ids):
        for user_id in recipients:
            for attempt in range(3):
                try:
                    await bot.send_message(user_id, text, reply_markup=reply_markup)
                    sent += 1
                    break
                except TelegramRetryAfter as error:
                    if attempt == 2:
                        failed += 1
                        logger.warning("Рассылка: превышен лимит при отправке пользователю %s", user_id)
                        break
                    await asyncio.sleep(error.retry_after + 1)
                except (TelegramForbiddenError, TelegramBadRequest):
                    unavailable += 1
                    break
                except TelegramAPIError as error:
                    failed += 1
                    logger.warning("Рассылка: не удалось отправить пользователю %s: %s", user_id, error)
                    break
            await asyncio.sleep(SEND_INTERVAL_SECONDS)
    result = BroadcastResult(sent=sent, unavailable=unavailable, failed=failed)
    record_event(
        "broadcast_finished",
        admin_id=admin_id,
        kind=kind,
        audience=audience,
        sent=result.sent,
        unavailable=result.unavailable,
        failed=result.failed,
    )
    return result
