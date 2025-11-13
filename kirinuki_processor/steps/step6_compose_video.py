"""
ステップ6: 動画合成

切り抜き動画に字幕とチャットオーバーレイを合成する。
FFmpegを使用して再エンコード。
"""

import os
import subprocess
from typing import Optional, List


def compose_video(
    video_path: str,
    output_path: str,
    subtitle_path: Optional[str] = None,
    overlay_path: Optional[str] = None,
    video_codec: str = "libx264",
    audio_codec: str = "aac",
    preset: str = "medium",
    crf: int = 23,
    extra_args: Optional[List[str]] = None
) -> bool:
    """
    動画に字幕とオーバーレイを合成

    Args:
        video_path: 入力動画のパス
        output_path: 出力動画のパス
        subtitle_path: 字幕ファイルのパス（SRT、任意）
        overlay_path: オーバーレイファイルのパス（ASS、任意）
        video_codec: 動画コーデック（デフォルト: libx264）
        audio_codec: 音声コーデック（デフォルト: aac）
        preset: エンコードプリセット（デフォルト: medium）
        crf: 品質設定（デフォルト: 23、低いほど高品質）
        extra_args: 追加のFFmpegオプション

    Returns:
        bool: 合成に成功したかどうか

    Raises:
        RuntimeError: FFmpegの実行に失敗した場合
    """
    # 出力ディレクトリを作成
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # FFmpegコマンドを構築
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-y",  # 上書き確認なし
    ]

    # フィルターグラフを構築
    filters = []

    # 字幕フィルター（SRT）
    if subtitle_path and os.path.exists(subtitle_path):
        # SRT字幕を焼き込み
        # パスをエスケープ（Windowsパス対応）
        subtitle_path_escaped = subtitle_path.replace("\\", "/").replace(":", "\\:")
        filters.append(f"subtitles={subtitle_path_escaped}")

    # オーバーレイフィルター（ASS）
    if overlay_path and os.path.exists(overlay_path):
        # ASS字幕を焼き込み
        overlay_path_escaped = overlay_path.replace("\\", "/").replace(":", "\\:")
        filters.append(f"ass={overlay_path_escaped}")

    # フィルターを適用
    if filters:
        filter_complex = ",".join(filters)
        cmd.extend(["-vf", filter_complex])

    # エンコード設定
    cmd.extend([
        "-c:v", video_codec,
        "-preset", preset,
        "-crf", str(crf),
        "-c:a", audio_codec,
    ])

    # 追加オプション
    if extra_args:
        cmd.extend(extra_args)

    # 出力ファイル
    cmd.append(output_path)

    try:
        print(f"Starting video composition...")
        print(f"  Input: {video_path}")
        if subtitle_path:
            print(f"  Subtitle: {subtitle_path}")
        if overlay_path:
            print(f"  Overlay: {overlay_path}")
        print(f"  Output: {output_path}")
        print(f"  Command: {' '.join(cmd)}")

        # FFmpegを実行
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # 出力ファイルが存在するか確認
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            file_size_mb = file_size / (1024 * 1024)
            print(f"✓ Video composition completed")
            print(f"  Output file: {output_path}")
            print(f"  File size: {file_size_mb:.2f} MB")
            return True
        else:
            print(f"✗ Output file not created")
            return False

    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)

        # FFmpegが見つからない場合のエラーメッセージ
        if "not found" in error_msg or "command not found" in error_msg:
            print("✗ ffmpeg is not installed.")
            print("  Please install it: https://ffmpeg.org/download.html")
            return False

        print(f"✗ Failed to compose video: {error_msg}")
        return False

    except Exception as e:
        raise RuntimeError(f"Unexpected error while composing video: {e}")


def get_video_info(video_path: str) -> dict:
    """
    動画の情報を取得（FFprobe使用）

    Args:
        video_path: 動画ファイルのパス

    Returns:
        動画情報の辞書
    """
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        video_path
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        import json
        info = json.loads(result.stdout)
        return info

    except Exception as e:
        print(f"Warning: Failed to get video info: {e}")
        return {}


def get_video_duration(video_path: str) -> Optional[float]:
    """
    動画の長さを取得（秒）

    Args:
        video_path: 動画ファイルのパス

    Returns:
        動画の長さ（秒）、取得失敗時はNone
    """
    info = get_video_info(video_path)

    try:
        duration = float(info["format"]["duration"])
        return duration
    except Exception:
        return None


def get_video_resolution(video_path: str) -> Optional[tuple]:
    """
    動画の解像度を取得

    Args:
        video_path: 動画ファイルのパス

    Returns:
        (width, height) のタプル、取得失敗時はNone
    """
    info = get_video_info(video_path)

    try:
        for stream in info["streams"]:
            if stream["codec_type"] == "video":
                width = stream["width"]
                height = stream["height"]
                return (width, height)
    except Exception:
        return None

    return None
