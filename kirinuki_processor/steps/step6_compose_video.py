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
    title_overlay_path: Optional[str] = None,
    logo_path: Optional[str] = None,
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
    ]

    # ロゴ画像を入力として追加
    has_logo = logo_path and os.path.exists(logo_path)
    if has_logo:
        cmd.extend(["-i", logo_path])

    cmd.append("-y")  # 上書き確認なし

    # フィルターグラフを構築
    logo_y = 10  # タイトルバー内の上部から10px
    logo_x = 15  # 左端から15px
    logo_height = 180  # ロゴの高さ（より大きく）
    animation_duration = 1.2  # アニメーション時間（タイトルバーと同じ）

    # ロゴがある場合はfilter_complexを使用
    if has_logo:
        filter_parts = []

        # 字幕、チャット、タイトルバーを全て先に適用
        ass_filters = []
        if subtitle_path and os.path.exists(subtitle_path):
            subtitle_path_escaped = subtitle_path.replace("\\", "/").replace(":", "\\:")
            if subtitle_path.endswith(".ass"):
                ass_filters.append(f"ass={subtitle_path_escaped}")
            else:
                ass_filters.append(f"subtitles={subtitle_path_escaped}")

        if overlay_path and os.path.exists(overlay_path):
            overlay_path_escaped = overlay_path.replace("\\", "/").replace(":", "\\:")
            ass_filters.append(f"ass={overlay_path_escaped}")

        if title_overlay_path and os.path.exists(title_overlay_path):
            title_overlay_path_escaped = title_overlay_path.replace("\\", "/").replace(":", "\\:")
            ass_filters.append(f"ass={title_overlay_path_escaped}")

        # まず動画に全てのASSを適用
        if ass_filters:
            filter_parts.append(f"[0:v]{','.join(ass_filters)}[v_base]")
            base_stream = "v_base"
        else:
            base_stream = "0:v"

        # ロゴを円形にして処理（太い白縁付き）
        border_width = 12  # 白縁の太さ（ピクセル、サイズに合わせて調整）
        filter_parts.append(
            f"[1:v]scale={logo_height}:{logo_height},"
            f"format=rgba,"
            f"geq="
            f"r='if(lte(hypot(X-W/2,Y-H/2),W/2-{border_width}),r(X,Y),255)':"
            f"g='if(lte(hypot(X-W/2,Y-H/2),W/2-{border_width}),g(X,Y),255)':"
            f"b='if(lte(hypot(X-W/2,Y-H/2),W/2-{border_width}),b(X,Y),255)':"
            f"a='if(lte(hypot(X-W/2,Y-H/2),W/2),255,0)'"
            f"[logo]"
        )

        # ロゴを左上にオーバーレイ
        filter_parts.append(f"[{base_stream}][logo]overlay={logo_x}:{logo_y}")

        filter_complex = ";".join(filter_parts)
        cmd.extend(["-filter_complex", filter_complex])
    else:
        # ロゴがない場合は通常のvfフィルター
        filters = []

        if subtitle_path and os.path.exists(subtitle_path):
            subtitle_path_escaped = subtitle_path.replace("\\", "/").replace(":", "\\:")
            if subtitle_path.endswith(".ass"):
                filters.append(f"ass={subtitle_path_escaped}")
            else:
                filters.append(f"subtitles={subtitle_path_escaped}")

        if overlay_path and os.path.exists(overlay_path):
            overlay_path_escaped = overlay_path.replace("\\", "/").replace(":", "\\:")
            filters.append(f"ass={overlay_path_escaped}")

        if title_overlay_path and os.path.exists(title_overlay_path):
            title_overlay_path_escaped = title_overlay_path.replace("\\", "/").replace(":", "\\:")
            filters.append(f"ass={title_overlay_path_escaped}")

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
        if logo_path:
            print(f"  Logo: {logo_path}")
        if subtitle_path:
            print(f"  Subtitle: {subtitle_path}")
        if overlay_path:
            print(f"  Chat overlay: {overlay_path}")
        if title_overlay_path:
            print(f"  Title overlay: {title_overlay_path}")
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
