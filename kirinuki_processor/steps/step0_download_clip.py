"""
ステップ0（新版）: YouTube動画のダウンロードと切り抜き

YouTube動画IDと時刻を指定して、該当区間を直接ダウンロード・切り抜く。
KirinukiDBは不要。
"""

import os
import subprocess
from typing import Optional, Tuple
from pathlib import Path


def download_and_clip_video(
    video_url: str,
    start_time: str,
    end_time: Optional[str],
    output_path: str,
    video_format: str = "bestvideo[ext=webm]+bestaudio[ext=webm]/best[ext=webm]/best",
    download_full: bool = False
) -> bool:
    """
    YouTube動画をダウンロードして指定区間を切り抜く

    Args:
        video_url: YouTube動画のURL
        start_time: 開始時刻（hh:mm:ss 形式）
        end_time: 終了時刻（hh:mm:ss 形式、任意）
        output_path: 出力ファイルパス
        video_format: yt-dlpのフォーマット指定
        download_full: 全体をダウンロードしてから切り抜くか（False=範囲指定ダウンロード）

    Returns:
        bool: 成功したかどうか
    """
    # 出力ディレクトリを作成
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    print(f"Downloading and clipping video...")
    print(f"  URL: {video_url}")
    print(f"  Start: {start_time}")
    print(f"  End: {end_time or 'Not specified'}")
    print(f"  Output: {output_path}")

    if download_full:
        # 方法1: 全体をダウンロードしてから切り抜き
        # より確実だが、時間がかかる
        return _download_full_then_clip(
            video_url,
            start_time,
            end_time,
            output_path,
            video_format
        )
    else:
        # 方法2: yt-dlpの--download-sectionsで範囲指定ダウンロード
        # 高速だが、一部の動画では正確でない場合がある
        return _download_with_sections(
            video_url,
            start_time,
            end_time,
            output_path,
            video_format
        )


def _download_full_then_clip(
    video_url: str,
    start_time: str,
    end_time: Optional[str],
    output_path: str,
    video_format: str
) -> bool:
    """
    全体をダウンロードしてからFFmpegで切り抜く方法
    """
    import tempfile

    # 一時ファイルに全体をダウンロード
    temp_dir = tempfile.mkdtemp()
    temp_video = os.path.join(temp_dir, "full_video.webm")

    try:
        # yt-dlpで全体をダウンロード
        print("  Step 1/2: Downloading full video...")
        cmd_download = [
            "yt-dlp",
            "-f", video_format,
            "-o", temp_video,
            video_url
        ]

        result = subprocess.run(
            cmd_download,
            capture_output=True,
            text=True,
            check=True
        )

        if not os.path.exists(temp_video):
            print("✗ Failed to download video")
            return False

        print("  ✓ Download completed")

        # FFmpegで切り抜き
        print("  Step 2/2: Clipping video...")
        success = _clip_video_with_ffmpeg(
            temp_video,
            start_time,
            end_time,
            output_path
        )

        return success

    except subprocess.CalledProcessError as e:
        print(f"✗ Download failed: {e.stderr if e.stderr else str(e)}")
        return False

    finally:
        # 一時ファイルを削除
        if os.path.exists(temp_video):
            os.remove(temp_video)
        try:
            os.rmdir(temp_dir)
        except:
            pass


def _download_with_sections(
    video_url: str,
    start_time: str,
    end_time: Optional[str],
    output_path: str,
    video_format: str
) -> bool:
    """
    yt-dlpの--download-sectionsで範囲指定ダウンロード
    """
    # 時刻範囲を指定
    if end_time:
        section = f"*{start_time}-{end_time}"
    else:
        section = f"*{start_time}-inf"

    # 出力パスから拡張子を除いたベース名
    base_path = os.path.splitext(output_path)[0]

    cmd = [
        "yt-dlp",
        "-f", video_format,
        "--download-sections", section,
        "-o", base_path,
        "--force-keyframes-at-cuts",  # キーフレームで正確に切り抜き
        video_url
    ]

    try:
        print("  Downloading specified section...")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # 生成されたファイルを確認
        # yt-dlpは拡張子を自動で付ける
        possible_files = [
            output_path,
            f"{base_path}.webm",
            f"{base_path}.mp4",
        ]

        found_file = None
        for file_path in possible_files:
            if os.path.exists(file_path):
                found_file = file_path
                break

        if found_file:
            # 指定されたパスにリネーム
            if found_file != output_path:
                os.rename(found_file, output_path)

            file_size = os.path.getsize(output_path)
            file_size_mb = file_size / (1024 * 1024)
            print(f"✓ Video clipped successfully")
            print(f"  Output: {output_path}")
            print(f"  Size: {file_size_mb:.2f} MB")
            return True
        else:
            print("✗ Output file not found")
            return False

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)

        # --download-sectionsがサポートされていない場合は全体ダウンロードにフォールバック
        if "unrecognized" in error_msg.lower() or "invalid" in error_msg.lower():
            print("  Note: --download-sections not supported, falling back to full download")
            return _download_full_then_clip(
                video_url,
                start_time,
                end_time,
                output_path,
                video_format
            )

        print(f"✗ Download failed: {error_msg}")
        return False


def _clip_video_with_ffmpeg(
    input_path: str,
    start_time: str,
    end_time: Optional[str],
    output_path: str
) -> bool:
    """
    FFmpegで動画を切り抜く

    Args:
        input_path: 入力動画パス
        start_time: 開始時刻
        end_time: 終了時刻（任意）
        output_path: 出力パス

    Returns:
        成功したかどうか
    """
    cmd = [
        "ffmpeg",
        "-y",  # 上書き確認なし
        "-ss", start_time,  # 開始時刻
    ]

    # 終了時刻が指定されている場合
    if end_time:
        cmd.extend(["-to", end_time])

    cmd.extend([
        "-i", input_path,
        "-c", "copy",  # 再エンコードなし（高速）
        output_path
    ])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        if os.path.exists(output_path):
            print("  ✓ Clipping completed")
            return True
        else:
            print("  ✗ Clipping failed")
            return False

    except subprocess.CalledProcessError as e:
        print(f"  ✗ FFmpeg error: {e.stderr if e.stderr else str(e)}")
        return False


def get_video_id_from_url(url: str) -> Optional[str]:
    """
    YouTube URLから動画IDを抽出

    Args:
        url: YouTube URL

    Returns:
        動画ID（抽出できない場合はNone）

    Examples:
        >>> get_video_id_from_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        'dQw4w9WgXcQ'
        >>> get_video_id_from_url("https://youtu.be/dQw4w9WgXcQ")
        'dQw4w9WgXcQ'
    """
    import re

    # 通常のURL形式
    match = re.search(r'(?:v=|/)([0-9A-Za-z_-]{11})(?:[&?]|$)', url)
    if match:
        return match.group(1)

    # 短縮URL形式
    match = re.search(r'youtu\.be/([0-9A-Za-z_-]{11})', url)
    if match:
        return match.group(1)

    return None
