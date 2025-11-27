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
    crop_top_percent: float = 0.0,
    crop_bottom_percent: float = 0.0,
    crop_left_percent: float = 0.0,
    crop_right_percent: float = 0.0,
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
    filters = []

    # 入力解像度（スケールは基本せず、クロップ後の高さを基準に16:9へ切り出す）
    target_width = target_height = None
    if os.path.exists(video_path):
        res = get_video_resolution(video_path)
        if res:
            target_width, target_height = res
    if not target_width:
        target_width = 1920
    if not target_height:
        target_height = 1080

    video_filters = []

    crop_params = [crop_top_percent, crop_bottom_percent, crop_left_percent, crop_right_percent]
    crop_applied = False
    if any(param > 0 for param in crop_params):
        left_frac = max(0.0, crop_left_percent / 100.0)
        right_frac = max(0.0, crop_right_percent / 100.0)
        top_frac = max(0.0, crop_top_percent / 100.0)
        bottom_frac = max(0.0, crop_bottom_percent / 100.0)

        width_factor = 1.0 - left_frac - right_frac
        height_factor = 1.0 - top_frac - bottom_frac
        if width_factor <= 0 or height_factor <= 0:
            raise ValueError("Crop percentages remove the entire frame. Please reduce crop values.")
        final_width_factor = width_factor
        final_height_factor = height_factor

        # ここから16:9に合わせてさらにクロップ（高さ基準で左右を削る方針、余白は作らない）
        target_aspect = 16 / 9  # 目標アスペクト
        input_aspect = target_width / target_height  # 入力映像のアスペクト
        target_ratio = target_aspect / input_aspect  # final_width_factor / final_height_factor に求める比

        desired_width_factor = final_height_factor * target_ratio

        if desired_width_factor <= final_width_factor and desired_width_factor > 0:
            # 十分な横幅があるので左右を削る
            reduce = final_width_factor - desired_width_factor
            left_frac += reduce / 2
            right_frac += reduce / 2
            final_width_factor = desired_width_factor
        else:
            # 高さ基準で足りない場合は、幅基準に切り替えて上下を削る
            desired_height_factor = final_width_factor / target_ratio
            reduce = final_height_factor - desired_height_factor
            top_frac += reduce / 2
            bottom_frac += reduce / 2
            final_height_factor = desired_height_factor

        if final_width_factor <= 0 or final_height_factor <= 0:
            raise ValueError("Invalid crop ratios after aspect adjustment. Please check crop settings.")

        crop_expr = (
            "crop="
            f"iw*{final_width_factor:.6f}:"
            f"ih*{final_height_factor:.6f}:"
            f"iw*{left_frac:.6f}:"
            f"ih*{top_frac:.6f}"
        )
        video_filters.append(crop_expr)
        crop_applied = True

    # スケールは行わず、元解像度ベースのまま出力する
    # 出力では常にピクセルアスペクト比を1:1に固定し、表示倍率の誤差を防ぐ
    video_filters.append("setsar=1")

    # 字幕、チャット、タイトルバーはクロップ/スケール後の映像に適用
    if subtitle_path and os.path.exists(subtitle_path):
        subtitle_path_escaped = subtitle_path.replace("\\", "/").replace(":", "\\:")
        if subtitle_path.endswith(".ass"):
            video_filters.append(f"ass={subtitle_path_escaped}")
        else:
            video_filters.append(f"subtitles={subtitle_path_escaped}")

    if overlay_path and os.path.exists(overlay_path):
        overlay_path_escaped = overlay_path.replace("\\", "/").replace(":", "\\:")
        video_filters.append(f"ass={overlay_path_escaped}")

    if title_overlay_path and os.path.exists(title_overlay_path):
        title_overlay_path_escaped = title_overlay_path.replace("\\", "/").replace(":", "\\:")
        video_filters.append(f"ass={title_overlay_path_escaped}")

    if video_filters:
        filters.append(",".join(video_filters))

    filter_parts = []
    if filters:
        filter_parts.append(f"[0:v]{','.join(filters)}[v_base]")
        base_stream = "v_base"
    else:
        base_stream = "0:v"

    if has_logo:
        border_width = 12
        filter_parts.extend([
            f"[1:v]scale={logo_height}:{logo_height},format=rgba,"
            f"geq=r='if(lte(hypot(X-W/2,Y-H/2),W/2-{border_width}),r(X,Y),255)':"
            f"g='if(lte(hypot(X-W/2,Y-H/2),W/2-{border_width}),g(X,Y),255)':"
            f"b='if(lte(hypot(X-W/2,Y-H/2),W/2-{border_width}),b(X,Y),255)':"
            f"a='if(lte(hypot(X-W/2,Y-H/2),W/2),255,0)'[logo]",
            f"[{base_stream}][logo]overlay={logo_x}:{logo_y}"
        ])
        cmd.extend(["-filter_complex", ";".join(filter_parts)])
    else:
        if filters:
            cmd.extend(["-vf", ",".join(filters)])

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
