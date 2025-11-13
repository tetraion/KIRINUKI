"""設定読み込みのテスト"""
import unittest
import tempfile
import os
from kirinuki_processor.steps.step0_config import (
    load_config_from_file,
    ClipConfig
)


class TestConfig(unittest.TestCase):
    """設定読み込みのテストケース"""

    def test_load_valid_config(self):
        """正しい設定ファイルの読み込み"""
        config_content = """
VIDEO_URL=https://www.youtube.com/watch?v=test123
START_TIME=00:05:30
END_TIME=00:10:45
WEBM_PATH=/tmp/test.webm
"""
        # 一時ファイルを作成
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(config_content)
            config_path = f.name

        # ダミーのwebmファイルを作成
        with open('/tmp/test.webm', 'w') as f:
            f.write("dummy")

        try:
            config = load_config_from_file(config_path)
            self.assertEqual(config.video_url, "https://www.youtube.com/watch?v=test123")
            self.assertEqual(config.start_time, "00:05:30")
            self.assertEqual(config.end_time, "00:10:45")
            self.assertEqual(config.webm_path, "/tmp/test.webm")
        finally:
            os.remove(config_path)
            if os.path.exists('/tmp/test.webm'):
                os.remove('/tmp/test.webm')

    def test_config_validation(self):
        """設定のバリデーション"""
        # 無効なURL
        with self.assertRaises(ValueError):
            config = ClipConfig(
                video_url="",
                start_time="00:00:00",
                end_time=None,
                webm_path="/tmp/test.webm"
            )
            config.validate()

        # 無効な時間フォーマット
        with self.assertRaises(ValueError):
            config = ClipConfig(
                video_url="https://youtube.com/watch?v=test",
                start_time="invalid",
                end_time=None,
                webm_path="/tmp/test.webm"
            )
            config.validate()


if __name__ == "__main__":
    unittest.main()
