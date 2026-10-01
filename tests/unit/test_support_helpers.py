import unittest
from types import SimpleNamespace

from nihao_tyan.telegram.handlers.support import message_content


class MessageContentTests(unittest.TestCase):
    def test_text(self) -> None:
        message = SimpleNamespace(text="  hello  ", photo=None, document=None)
        self.assertEqual(message_content(message, "en"), ("hello", "text", None, None))

    def test_photo(self) -> None:
        message = SimpleNamespace(
            text=None,
            caption="screen",
            photo=[SimpleNamespace(file_id="photo-id")],
            document=None,
        )
        self.assertEqual(message_content(message, "en"), ("screen", "photo", "photo-id", None))

    def test_document(self) -> None:
        message = SimpleNamespace(
            text=None,
            caption=None,
            photo=None,
            document=SimpleNamespace(file_id="document-id", file_name="log.txt"),
        )
        self.assertEqual(message_content(message, "en"), ("log.txt", "document", "document-id", "log.txt"))
