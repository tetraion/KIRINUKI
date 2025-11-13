"""時間ユーティリティのテスト"""
import unittest
from kirinuki_processor.utils.time_utils import (
    parse_time,
    format_time,
    srt_time_format,
    ass_time_format
)


class TestTimeUtils(unittest.TestCase):
    """時間ユーティリティのテストケース"""

    def test_parse_time_hhmmss(self):
        """hh:mm:ss形式のパース"""
        self.assertEqual(parse_time("01:23:45"), 5025.0)
        self.assertEqual(parse_time("00:00:00"), 0.0)
        self.assertEqual(parse_time("02:30:15"), 9015.0)

    def test_parse_time_mmss(self):
        """mm:ss形式のパース"""
        self.assertEqual(parse_time("23:45"), 1425.0)
        self.assertEqual(parse_time("00:00"), 0.0)
        self.assertEqual(parse_time("05:30"), 330.0)

    def test_format_time(self):
        """秒数から時間文字列への変換"""
        self.assertEqual(format_time(5025.5, include_ms=False), "01:23:45")
        self.assertEqual(format_time(0, include_ms=False), "00:00:00")
        self.assertEqual(format_time(3661, include_ms=False), "01:01:01")

    def test_format_time_with_ms(self):
        """ミリ秒付き時間文字列"""
        result = format_time(5025.5, include_ms=True)
        self.assertTrue(result.startswith("01:23:45."))

    def test_srt_time_format(self):
        """SRT形式の時間文字列"""
        result = srt_time_format(5025.5)
        self.assertEqual(result, "01:23:45,500")

    def test_ass_time_format(self):
        """ASS形式の時間文字列"""
        result = ass_time_format(5025.5)
        self.assertEqual(result, "1:23:45.50")


if __name__ == "__main__":
    unittest.main()
