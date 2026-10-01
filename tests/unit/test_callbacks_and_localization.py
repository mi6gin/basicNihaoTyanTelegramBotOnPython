import string
import unittest

from nihao_tyan.telegram.callbacks import Callback
from nihao_tyan.i18n import _load_language, translate


class CallbackTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        callback = Callback("adminappeal", 42, "15.new.0")
        self.assertEqual(Callback.unpack(callback.pack()), callback)

    def test_invalid_callback_is_rejected(self) -> None:
        self.assertIsNone(Callback.unpack(None))
        self.assertIsNone(Callback.unpack("main:not-a-number"))


class LocalizationTests(unittest.TestCase):
    def test_languages_have_identical_keys(self) -> None:
        self.assertEqual(set(_load_language("ru")), set(_load_language("en")))

    def test_all_placeholders_match_between_languages(self) -> None:
        formatter = string.Formatter()
        ru = _load_language("ru")
        en = _load_language("en")
        for key in ru:
            ru_fields = {field for _, field, _, _ in formatter.parse(ru[key]) if field}
            en_fields = {field for _, field, _, _ in formatter.parse(en[key]) if field}
            self.assertEqual(ru_fields, en_fields, key)

    def test_unknown_language_falls_back_to_russian(self) -> None:
        self.assertEqual(translate("command.start", "kk"), translate("command.start", "ru"))
