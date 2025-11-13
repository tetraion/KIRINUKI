"""
ステップ1: YouTube字幕取得

YouTubeから日本語の字幕（公開字幕または自動生成字幕）を取得する。
yt-dlpを使用して字幕をSRT形式で取得。
"""

import os
import subprocess
import json
from pathlib import Path
from typing import Optional, List, Dict


def fetch_subtitles(
    video_url: str,
    output_path: str,
    lang: str = "ja",
    prefer_auto: bool = False
) -> bool:
    """
    YouTube動画から字幕を取得

    Args:
        video_url: YouTube動画のURL
        output_path: 出力先パス（.srt）
        lang: 取得する字幕の言語コード（デフォルト: "ja"）
        prefer_auto: 自動生成字幕を優先するか（デフォルト: False）

    Returns:
        bool: 字幕取得に成功したかどうか

    Raises:
        RuntimeError: yt-dlpの実行に失敗した場合
    """
    # 出力ディレクトリを作成
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # 出力パスから拡張子を除いたベース名を取得
    base_name = os.path.splitext(output_path)[0]

    # yt-dlpコマンドを構築
    cmd = [
        "yt-dlp",
        "--skip-download",  # 動画自体はダウンロードしない
        "--write-subs",  # 字幕をダウンロード
        "--write-auto-subs",  # 自動生成字幕もダウンロード
        "--sub-lang", lang,
        "--sub-format", "srt",
        "--convert-subs", "srt",  # SRT形式に変換
        "-o", base_name,  # 出力ファイル名
        video_url
    ]

    try:
        # yt-dlpを実行
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # 生成されたファイル名を確認
        # yt-dlpは言語コードを自動的に追加する (例: subs_full.ja.srt)
        possible_files = [
            f"{base_name}.{lang}.srt",
            f"{base_name}.ja.srt",
            f"{base_name}.srt",
        ]

        found_file = None
        for file_path in possible_files:
            if os.path.exists(file_path):
                found_file = file_path
                break

        if found_file and found_file != output_path:
            # ファイル名を指定されたものにリネーム
            os.rename(found_file, output_path)

        # 字幕ファイルが存在するか確認
        if os.path.exists(output_path):
            print(f"✓ Subtitles downloaded: {output_path}")
            return True
        else:
            print(f"✗ No subtitles found for video: {video_url}")
            return False

    except subprocess.CalledProcessError as e:
        # エラーメッセージを表示
        error_msg = e.stderr if e.stderr else str(e)
        print(f"✗ Failed to download subtitles: {error_msg}")
        return False
    except Exception as e:
        raise RuntimeError(f"Unexpected error while fetching subtitles: {e}")


def check_available_subtitles(video_url: str) -> List[Dict[str, str]]:
    """
    動画で利用可能な字幕の一覧を取得

    Args:
        video_url: YouTube動画のURL

    Returns:
        利用可能な字幕のリスト（言語コード、名前、自動生成かどうか）

    Example:
        [
            {"lang": "ja", "name": "Japanese", "auto": False},
            {"lang": "en", "name": "English", "auto": True}
        ]
    """
    cmd = [
        "yt-dlp",
        "--list-subs",
        "--skip-download",
        video_url
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # 出力から字幕情報を解析（簡易版）
        # 実際にはもっと詳細なパースが必要だが、ここでは簡略化
        print(result.stdout)
        return []

    except subprocess.CalledProcessError as e:
        print(f"Failed to list subtitles: {e}")
        return []


def has_subtitles(video_url: str, lang: str = "ja") -> bool:
    """
    指定された言語の字幕が利用可能かチェック

    Args:
        video_url: YouTube動画のURL
        lang: 言語コード

    Returns:
        字幕が利用可能かどうか
    """
    cmd = [
        "yt-dlp",
        "--list-subs",
        "--skip-download",
        video_url
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # 出力に指定言語が含まれているかチェック
        return lang in result.stdout.lower()

    except subprocess.CalledProcessError:
        return False
