import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import nihao_tyan.services.activity_log as activity_log
from nihao_tyan.services.activity_log import AdminErrorHandler, DailyJournal, JournalErrorHandler
from nihao_tyan.config import settings


class ErrorReportingTests(unittest.IsolatedAsyncioTestCase):
    async def test_exception_is_journaled_and_sent_as_redacted_file(self) -> None:
        bot = AsyncMock()
        with tempfile.TemporaryDirectory() as directory:
            journal = DailyJournal(Path(directory))
            reporter = AdminErrorHandler(bot, frozenset({10, 20}))
            logger = logging.getLogger("test.error_report")
            try:
                try:
                    raise RuntimeError(f"Failure with {settings.bot_token}")
                except RuntimeError:
                    record = logger.makeRecord(
                        logger.name,
                        logging.ERROR,
                        __file__,
                        1,
                        "Processing failed",
                        (),
                        sys.exc_info(),
                    )
                with patch.object(activity_log, "_active_journal", journal):
                    JournalErrorHandler().emit(record)
                reporter.emit(record)
                await reporter.queue.join()
            finally:
                await reporter.shutdown()

            self.assertEqual(bot.send_document.await_count, 2)
            self.assertEqual({call.args[0] for call in bot.send_document.await_args_list}, {10, 20})
            document = bot.send_document.await_args_list[0].args[1]
            self.assertTrue(document.filename.startswith("error-"))
            self.assertIn(b"RuntimeError", document.data)
            self.assertIn(b"Traceback", document.data)
            self.assertNotIn(settings.bot_token.encode(), document.data)
            records = [json.loads(line) for path in journal.directory.glob("*.jsonl") for line in path.read_text().splitlines()]
            self.assertEqual(records[0]["event"], "error")
            self.assertIn("RuntimeError", records[0]["details"])
            self.assertNotIn(settings.bot_token, records[0]["details"])

    async def test_one_admin_failure_does_not_block_the_next(self) -> None:
        bot = AsyncMock()
        bot.send_document.side_effect = [RuntimeError("blocked"), None]
        reporter = AdminErrorHandler(bot, frozenset({10, 20}))
        record = logging.getLogger("test.error_report").makeRecord(
            "test.error_report", logging.ERROR, __file__, 1, "Failure", (), None
        )
        try:
            reporter.emit(record)
            await reporter.queue.join()
        finally:
            await reporter.shutdown()
        self.assertEqual(bot.send_document.await_count, 2)
