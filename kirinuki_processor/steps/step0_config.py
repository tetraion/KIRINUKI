"""
ステップ0: 設定ファイル読み込み

設定ファイルから必要な情報を取得する:
- 動画URL
- 切り抜き開始時刻（START）
- 切り抜き終了時刻（END）
- webmファイルパス
"""

import os
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class ClipConfig:
    """切り抜き処理の設定"""
    video_url: str
    start_time: str  # hh:mm:ss 形式
    end_time: Optional[str]  # hh:mm:ss 形式（任意）
    title: Optional[str] = None  # 動画タイトル（任意）
    webm_path: Optional[str] = None  # 既存のwebmファイル（任意、指定しない場合は自動ダウンロード）
    output_dir: str = "data/output"
    temp_dir: str = "data/temp"
    auto_download: bool = True  # 動画を自動ダウンロードするか

    def validate(self) -> None:
        """設定の妥当性をチェック"""
        if not self.video_url:
            raise ValueError("video_url is required")
        if not self.start_time:
            raise ValueError("start_time is required")

        # webm_pathが指定されている場合のみファイル存在チェック
        if self.webm_path and not os.path.exists(self.webm_path):
            raise ValueError(f"webm file not found: {self.webm_path}")

        # 時間フォーマットの簡易チェック
        self._validate_time_format(self.start_time, "start_time")
        if self.end_time:
            self._validate_time_format(self.end_time, "end_time")

    @staticmethod
    def _validate_time_format(time_str: str, field_name: str) -> None:
        """時間フォーマットの妥当性チェック"""
        parts = time_str.strip().split(":")
        if len(parts) not in [2, 3]:
            raise ValueError(
                f"{field_name} must be in 'hh:mm:ss' or 'mm:ss' format, got: {time_str}"
            )


def load_config_from_file(config_path: str) -> ClipConfig:
    """
    設定ファイルから設定を読み込む

    設定ファイル形式（シンプルなkey=value形式）:
        VIDEO_URL=https://www.youtube.com/watch?v=xxxxx
        START_TIME=01:23:45
        END_TIME=01:30:00
        WEBM_PATH=data/input/clip.webm

    Args:
        config_path: 設定ファイルのパス

    Returns:
        ClipConfig: 読み込んだ設定

    Raises:
        FileNotFoundError: 設定ファイルが見つからない
        ValueError: 設定が不正
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    config_dict: Dict[str, str] = {}

    with open(config_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()

            # 空行やコメント行をスキップ
            if not line or line.startswith("#"):
                continue

            # key=value 形式で分割
            if "=" not in line:
                raise ValueError(
                    f"Invalid format at line {line_num}: {line}. "
                    "Expected 'KEY=VALUE' format"
                )

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            if not key or not value:
                raise ValueError(
                    f"Empty key or value at line {line_num}: {line}"
                )

            config_dict[key] = value

    # 必須項目のチェック（WEBM_PATHは任意に変更）
    required_keys = ["VIDEO_URL", "START_TIME"]
    missing_keys = [key for key in required_keys if key not in config_dict]
    if missing_keys:
        raise ValueError(f"Missing required config keys: {', '.join(missing_keys)}")

    # AUTO_DOWNLOADのパース
    auto_download = True
    if "AUTO_DOWNLOAD" in config_dict:
        auto_download = config_dict["AUTO_DOWNLOAD"].lower() in ["true", "yes", "1"]

    # ClipConfigオブジェクトを作成
    config = ClipConfig(
        video_url=config_dict["VIDEO_URL"],
        start_time=config_dict["START_TIME"],
        end_time=config_dict.get("END_TIME"),
        title=config_dict.get("TITLE"),  # 任意
        webm_path=config_dict.get("WEBM_PATH"),  # 任意
        output_dir=config_dict.get("OUTPUT_DIR", "data/output"),
        temp_dir=config_dict.get("TEMP_DIR", "data/temp"),
        auto_download=auto_download,
    )

    # バリデーション
    config.validate()

    return config


def create_sample_config(output_path: str = "config.txt") -> None:
    """
    サンプル設定ファイルを作成

    Args:
        output_path: 出力先パス
    """
    sample_content = """# KIRINUKI Processor 設定ファイル
# key=value 形式で記述してください

# YouTube動画URL（必須）
VIDEO_URL=https://www.youtube.com/watch?v=xxxxxxxxxxxxx

# 切り抜き開始時刻（必須、hh:mm:ss または mm:ss 形式）
START_TIME=00:05:30

# 切り抜き終了時刻（任意、hh:mm:ss または mm:ss 形式）
END_TIME=00:10:45

# 動画タイトル（任意、指定すると画面上部にタイトルバーが表示されます）
# TITLE=高市氏になっても政治は変わらない

# 動画を自動ダウンロード・切り抜きするか（任意、デフォルト: true）
# true の場合、YouTubeから直接ダウンロードして切り抜きます
# false の場合、WEBM_PATH で指定した既存ファイルを使用します
AUTO_DOWNLOAD=true

# 切り抜き済みwebmファイルのパス（任意、AUTO_DOWNLOAD=false の場合に必要）
# AUTO_DOWNLOAD=true の場合、この設定は無視されます
# WEBM_PATH=data/input/clip.webm

# 出力先ディレクトリ（任意、デフォルト: data/output）
OUTPUT_DIR=data/output

# 一時ファイル用ディレクトリ（任意、デフォルト: data/temp）
TEMP_DIR=data/temp
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(sample_content)

    print(f"Sample config file created: {output_path}")
