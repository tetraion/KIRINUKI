#!/usr/bin/env python3
"""
KIRINUKI Processor - メインスクリプト

ひろゆき動画の切り抜きに字幕とライブチャットを重ねるツール
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Any, Optional

# モジュールパスを追加
sys.path.insert(0, str(Path(__file__).parent))

from kirinuki_processor.steps.step0_config import (
    load_config_from_file,
    create_sample_config,
    ClipConfig
)
from kirinuki_processor.steps.step0_download_clip import download_and_clip_video
from kirinuki_processor.steps.step1_generate_subtitles import (
    generate_subtitles_with_whisper,
    convert_srt_to_ass
)
from kirinuki_processor.steps.step1_5_fix_subtitles import fix_subtitle_file
from kirinuki_processor.steps.step3_fetch_chat import fetch_chat
from kirinuki_processor.steps.step4_extract_chat import load_and_extract_chat
from kirinuki_processor.steps.step5_generate_overlay import (
    generate_overlay_from_file,
    OverlayConfig
)
from kirinuki_processor.steps.step6_compose_video import compose_video
from kirinuki_processor.steps.step_title_bar import generate_title_bar
from kirinuki_processor.steps.step7_generate_description import generate_youtube_description
from kirinuki_processor.utils.video_utils import get_video_duration
from kirinuki_processor.constants import (
    DEFAULT_CROP_CRF,
    DEFAULT_CROP_BITRATE,
    DEFAULT_VIDEO_DURATION_FALLBACK
)
import subprocess
import re
import glob
import shutil

# ショート動画生成モジュール（独立モジュール）
from shorts import generate_short_video


def concatenate_videos(video_paths: list, output_path: str) -> bool:
    """
    複数の動画を連結する

    Args:
        video_paths: 動画ファイルのパスリスト
        output_path: 出力ファイルのパス

    Returns:
        成功した場合True
    """
    if len(video_paths) == 1:
        # 1つだけの場合はコピー
        shutil.copy2(video_paths[0], output_path)
        return True

    # FFmpegの連結リストファイルを作成
    concat_list_path = output_path + ".concat_list.txt"
    try:
        with open(concat_list_path, 'w', encoding='utf-8') as f:
            for video_path in video_paths:
                # 絶対パスに変換
                abs_path = os.path.abspath(video_path)
                # パスにシングルクォートやスペースがある場合のエスケープ処理
                escaped_path = abs_path.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")

        # FFmpegで連結
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_list_path,
            '-c', 'copy',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr}")
            return False

        return True
    except Exception as e:
        print(f"Error concatenating videos: {e}")
        return False
    finally:
        # 一時ファイルを削除
        if os.path.exists(concat_list_path):
            os.remove(concat_list_path)


def merge_subtitle_files(subtitle_paths: list, output_path: str) -> bool:
    """
    複数のSRT字幕ファイルを時間オフセットを考慮してマージ

    Args:
        subtitle_paths: 字幕ファイルのパスリスト
        output_path: 出力ファイルのパス

    Returns:
        成功した場合True
    """
    try:
        merged_subtitles = []
        subtitle_index = 1
        time_offset = 0.0

        for i, srt_path in enumerate(subtitle_paths):
            if not os.path.exists(srt_path):
                print(f"Warning: Subtitle file not found: {srt_path}")
                continue

            # SRTファイルを読み込み
            with open(srt_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # SRT形式のエントリを解析
            # パターン: 番号\n時刻 --> 時刻\n字幕テキスト
            pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n((?:.*\n)*?)(?:\n|$)'
            matches = re.findall(pattern, content)

            for match in matches:
                _, start_time, end_time, text = match

                # 時刻をパース
                start_ms = parse_srt_time(start_time) + time_offset * 1000
                end_ms = parse_srt_time(end_time) + time_offset * 1000

                # 新しい字幕エントリを追加
                merged_subtitles.append({
                    'index': subtitle_index,
                    'start': format_srt_time(start_ms),
                    'end': format_srt_time(end_ms),
                    'text': text.strip()
                })
                subtitle_index += 1

            # 次のクリップのためのオフセットを更新
            # 対応する動画の長さを取得
            # subs_clip.srt -> clip.webm, subs_clip_1.srt -> clip_1.webm
            video_path = srt_path.replace('subs_clip', 'clip').replace('.srt', '.webm')
            if os.path.exists(video_path):
                duration = get_video_duration(video_path)
                time_offset += duration
            else:
                print(f"Warning: Could not find video file for subtitle: {video_path}")
                # デフォルト値を使用（動画長さ取得失敗時のフォールバック）
                time_offset += DEFAULT_VIDEO_DURATION_FALLBACK

        # マージした字幕をファイルに書き込み
        with open(output_path, 'w', encoding='utf-8') as f:
            for sub in merged_subtitles:
                f.write(f"{sub['index']}\n")
                f.write(f"{sub['start']} --> {sub['end']}\n")
                f.write(f"{sub['text']}\n\n")

        return True
    except Exception as e:
        print(f"Error merging subtitles: {e}")
        return False


def parse_srt_time(time_str: str) -> float:
    """SRT時刻文字列をミリ秒に変換"""
    # 00:00:00,000
    h, m, s_ms = time_str.split(':')
    s, ms = s_ms.split(',')
    return (int(h) * 3600 + int(m) * 60 + int(s)) * 1000 + int(ms)


def format_srt_time(ms: float) -> str:
    """ミリ秒をSRT時刻文字列に変換"""
    ms = int(ms)
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def merge_ass_overlays(overlay_paths: list, output_path: str, video_paths: list) -> bool:
    """
    複数のASS字幕オーバーレイを時間オフセットを考慮してマージ

    Args:
        overlay_paths: オーバーレイファイルのパスリスト
        output_path: 出力ファイルのパス
        video_paths: 対応する動画ファイルのパスリスト（時間オフセット計算用）

    Returns:
        成功した場合True
    """
    try:
        # ASSファイルのヘッダーとイベントを分離してマージ
        header = None
        all_events = []
        time_offset = 0.0

        for i, ass_path in enumerate(overlay_paths):
            if not os.path.exists(ass_path):
                print(f"Warning: Overlay file not found: {ass_path}")
                continue

            with open(ass_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # [Events]セクションを探す
            parts = content.split('[Events]')
            if len(parts) != 2:
                continue

            # 最初のファイルからヘッダーを取得
            if header is None:
                header = parts[0] + '[Events]'

            # イベント行を取得
            events_section = parts[1]
            event_lines = events_section.strip().split('\n')

            for line in event_lines:
                if line.startswith('Dialogue:'):
                    # Dialogue行のタイムスタンプを調整
                    adjusted_line = adjust_ass_dialogue_time(line, time_offset)
                    all_events.append(adjusted_line)
                elif line.startswith('Format:'):
                    # Formatは最初の1回だけ
                    if i == 0:
                        all_events.insert(0, line)

            # 次のクリップのためのオフセットを更新
            duration = get_video_duration(video_paths[i])
            time_offset += duration

        # マージしたASSファイルを書き込み
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(header)
            f.write('\n')
            for event in all_events:
                f.write(event + '\n')

        return True
    except Exception as e:
        print(f"Error merging ASS overlays: {e}")
        return False


def adjust_ass_dialogue_time(dialogue_line: str, offset_seconds: float) -> str:
    """
    ASSのDialogue行の時刻をオフセット秒だけ調整

    Args:
        dialogue_line: Dialogue行
        offset_seconds: オフセット（秒）

    Returns:
        調整後のDialogue行
    """
    # Dialogue: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
    parts = dialogue_line.split(',', 9)
    if len(parts) < 10:
        return dialogue_line

    # Start時刻とEnd時刻を調整
    start_time = parts[1]
    end_time = parts[2]

    adjusted_start = adjust_ass_time(start_time, offset_seconds)
    adjusted_end = adjust_ass_time(end_time, offset_seconds)

    parts[1] = adjusted_start
    parts[2] = adjusted_end

    return ','.join(parts)


def adjust_ass_time(time_str: str, offset_seconds: float) -> str:
    """
    ASS時刻文字列をオフセット秒だけ調整

    Args:
        time_str: ASS時刻文字列（h:mm:ss.cc形式）
        offset_seconds: オフセット（秒）

    Returns:
        調整後の時刻文字列
    """
    # h:mm:ss.cc を解析
    match = re.match(r'(\d+):(\d{2}):(\d{2})\.(\d{2})', time_str)
    if not match:
        return time_str

    h, m, s, cs = map(int, match.groups())
    total_seconds = h * 3600 + m * 60 + s + cs / 100.0
    total_seconds += offset_seconds

    # 負の値にならないようにする
    if total_seconds < 0:
        total_seconds = 0

    # 時刻文字列に戻す
    new_h = int(total_seconds // 3600)
    new_m = int((total_seconds % 3600) // 60)
    new_s = int(total_seconds % 60)
    new_cs = int((total_seconds % 1) * 100)

    return f"{new_h}:{new_m:02d}:{new_s:02d}.{new_cs:02d}"


def crop_video(input_path: str, output_path: str, crop_top: float, crop_bottom: float,
               crop_left: float, crop_right: float) -> bool:
    """
    動画をクロップする

    Args:
        input_path: 入力動画ファイルのパス
        output_path: 出力動画ファイルのパス
        crop_top: 上部クロップ率（0-100）
        crop_bottom: 下部クロップ率（0-100）
        crop_left: 左側クロップ率（0-100）
        crop_right: 右側クロップ率（0-100）

    Returns:
        成功した場合True
    """
    # クロップ設定がすべて0の場合はコピーのみ
    if crop_top == 0 and crop_bottom == 0 and crop_left == 0 and crop_right == 0:
        import shutil
        shutil.copy2(input_path, output_path)
        return True

    try:
        # 動画の解像度を取得
        cmd_probe = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=p=0',
            input_path
        ]
        result = subprocess.run(cmd_probe, capture_output=True, text=True, check=True)
        width, height = map(int, result.stdout.strip().split(','))

        # 指定のクロップ率で暫定サイズを算出
        crop_w = int(width * (1 - (crop_left + crop_right) / 100))
        crop_h = int(height * (1 - (crop_top + crop_bottom) / 100))
        crop_x = int(width * crop_left / 100)
        crop_y = int(height * crop_top / 100)

        # 高さを基準に16:9へ合わせる（余白なし）。横で調整しきれない場合のみ高さをさらに削る
        target_aspect = 16 / 9
        desired_w_from_h = int(crop_h * target_aspect)

        if desired_w_from_h <= crop_w and desired_w_from_h > 0:
            # 幅が十分あるので左右を削って16:9に
            reduce_w = crop_w - desired_w_from_h
            crop_x += reduce_w // 2
            crop_w = desired_w_from_h
        else:
            # 幅が足りない場合のみ高さ側を削って合わせる
            desired_h_from_w = int(crop_w / target_aspect)
            reduce_h = crop_h - desired_h_from_w
            crop_y += reduce_h // 2
            crop_h = desired_h_from_w

        # FFmpegでクロップ
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-vf', f'crop={crop_w}:{crop_h}:{crop_x}:{crop_y}',
            '-c:v', 'libvpx-vp9',
            '-crf', str(DEFAULT_CROP_CRF),
            '-b:v', str(DEFAULT_CROP_BITRATE),
            '-c:a', 'copy',
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"FFmpeg crop error: {result.stderr}")
            return False

        return True
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg error cropping video: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"Error: Input file not found: {input_path}")
        return False
    except Exception as e:
        print(f"Unexpected error cropping video: {e}")
        return False


def apply_crop_or_copy(raw_video_path: str, cropped_path: str, config: Any) -> Optional[str]:
    """
    クロップ設定に応じてクロップを適用し、出力パスを返す（クロップなしならコピー）
    """
    has_crop = (config.crop_top_percent != 0 or config.crop_bottom_percent != 0 or
                config.crop_left_percent != 0 or config.crop_right_percent != 0)
    try:
        if has_crop:
            print(f"\n[Crop] Applying crop settings...")
            print(f"  Top: {config.crop_top_percent}%, Bottom: {config.crop_bottom_percent}%")
            print(f"  Left: {config.crop_left_percent}%, Right: {config.crop_right_percent}%")
            success = crop_video(
                raw_video_path,
                cropped_path,
                config.crop_top_percent,
                config.crop_bottom_percent,
                config.crop_left_percent,
                config.crop_right_percent
            )
            if not success:
                print("✗ Failed to crop video")
                return None
        else:
            import shutil
            shutil.copy2(raw_video_path, cropped_path)
        return cropped_path
    except Exception as e:
        print(f"✗ Error in cropping: {e}")
        return None


def process_single_clip(config: Any, clip_index: int) -> tuple:
    """
    単一のクリップを処理する（chained config用のヘルパー関数）

    Args:
        config: ClipConfig オブジェクト
        clip_index: クリップ番号（0始まり）

    Returns:
        tuple: (video_path, subs_path, chat_overlay_path)
    """
    suffix = "" if clip_index == 0 else f"_{clip_index}"

    # ファイルパスを定義
    clip_video_path = os.path.join(config.temp_dir, f"clip{suffix}.webm")
    clip_video_raw_path = os.path.join(config.temp_dir, f"clip{suffix}_raw.webm")
    subs_clip_path = os.path.join(config.temp_dir, f"subs_clip{suffix}.srt")
    chat_full_path = os.path.join(config.temp_dir, f"chat_full{suffix}.json")
    chat_clip_path = os.path.join(config.temp_dir, f"chat_clip{suffix}.json")
    chat_overlay_path = os.path.join(config.temp_dir, f"chat_overlay{suffix}.ass")

    print(f"\n{'='*60}")
    print(f"Processing Clip {clip_index + 1}")
    print(f"{'='*60}")

    # 動画ファイルのパスを決定
    if config.auto_download:
        print(f"\n[Clip {clip_index + 1}] Downloading and clipping video from YouTube...")
        try:
            success = download_and_clip_video(
                config.video_url,
                config.start_time,
                config.end_time,
                clip_video_raw_path,
                download_full=False
            )
            if not success:
                print(f"✗ Failed to download and clip video for clip {clip_index + 1}")
                return None, None, None
            raw_video_path = clip_video_raw_path
        except Exception as e:
            print(f"✗ Error downloading clip {clip_index + 1}: {e}")
            return None, None, None
    else:
        print(f"\n[Clip {clip_index + 1}] Using existing video file")
        if not config.webm_path:
            print("✗ WEBM_PATH is required when AUTO_DOWNLOAD=false")
            return None, None, None
        raw_video_path = config.webm_path

    # クロップ処理を適用
    has_crop = (config.crop_top_percent != 0 or config.crop_bottom_percent != 0 or
                config.crop_left_percent != 0 or config.crop_right_percent != 0)

    if has_crop:
        print(f"\n[Clip {clip_index + 1}] Applying crop settings...")
        print(f"  Top: {config.crop_top_percent}%, Bottom: {config.crop_bottom_percent}%")
        print(f"  Left: {config.crop_left_percent}%, Right: {config.crop_right_percent}%")
        cropped = apply_crop_or_copy(raw_video_path, clip_video_path, config)
        if not cropped:
            print(f"✗ Failed to crop video for clip {clip_index + 1}")
            return None, None, None
        video_source_path = cropped
        print(f"✓ Video cropped successfully")
    else:
        # クロップ不要の場合はコピー
        shutil.copy2(raw_video_path, clip_video_path)
        video_source_path = clip_video_path

    # ステップ1: Whisper字幕生成
    print(f"\n[Clip {clip_index + 1}] Generating subtitles with Whisper...")
    try:
        success = generate_subtitles_with_whisper(
            video_source_path,
            subs_clip_path,
            model_size="large",
            language="ja"
        )
        if not success:
            print("  Note: Failed to generate subtitles")
    except Exception as e:
        print(f"✗ Error in subtitle generation: {e}")

    # ステップ2: チャット取得
    print(f"\n[Clip {clip_index + 1}] Fetching live chat from YouTube...")
    try:
        success = fetch_chat(config.video_url, chat_full_path)
        if not success:
            print("  Note: Chat replay not available")
            chat_full_path = None
    except Exception as e:
        print(f"✗ Error fetching chat: {e}")
        chat_full_path = None

    # ステップ3: チャット抽出
    if chat_full_path and os.path.exists(chat_full_path):
        print(f"\n[Clip {clip_index + 1}] Extracting chat messages for clip...")
        try:
            count = load_and_extract_chat(
                chat_full_path,
                chat_clip_path,
                config.start_time,
                config.end_time,
                delay_seconds=config.chat_delay_seconds,
                dedup_window_seconds=config.chat_dedup_window_seconds,
                dedup_by_author=config.chat_dedup_by_author
            )
            if count == 0:
                chat_clip_path = None
        except Exception as e:
            print(f"✗ Error extracting chat: {e}")
            chat_clip_path = None
    else:
        print(f"\n[Clip {clip_index + 1}] Skipped chat extraction (no chat available)")
        chat_clip_path = None

    # ステップ4: オーバーレイ生成
    if chat_clip_path and os.path.exists(chat_clip_path):
        print(f"\n[Clip {clip_index + 1}] Generating chat overlay (ASS)...")
        try:
            overlay_config = OverlayConfig()
            count = generate_overlay_from_file(
                chat_clip_path,
                chat_overlay_path,
                overlay_config
            )
            if count == 0:
                chat_overlay_path = None
        except Exception as e:
            print(f"✗ Error generating overlay: {e}")
            chat_overlay_path = None
    else:
        print(f"\n[Clip {clip_index + 1}] Skipped overlay generation (no chat available)")
        chat_overlay_path = None

    return video_source_path, subs_clip_path, chat_overlay_path


def run_prepare_pipeline(config_path: str) -> bool:
    """
    素材準備パイプライン（字幕生成まで、動画合成は行わない）
    NEXT_CONFIGが指定されている場合、連鎖的に複数のクリップを処理する

    Args:
        config_path: 設定ファイルのパス

    Returns:
        成功したかどうか
    """
    print("=" * 60)
    print("KIRINUKI Processor - Prepare Materials")
    print("=" * 60)

    # ステップ0: 設定読み込み（連鎖チェック）
    print("\n[Step 0] Loading configuration...")
    configs = []
    current_config_path = config_path
    visited_configs = set()

    # 連鎖設定をすべて読み込む
    while current_config_path:
        # 循環参照チェック
        if current_config_path in visited_configs:
            print(f"✗ Error: Circular reference detected in config chain: {current_config_path}")
            return False
        visited_configs.add(current_config_path)

        # 設定ファイルを読み込み
        try:
            config = load_config_from_file(current_config_path)
            configs.append(config)
            print(f"✓ Configuration loaded: {current_config_path}")
            print(f"  Video URL: {config.video_url}")
            print(f"  Start time: {config.start_time}")
            print(f"  End time: {config.end_time or 'Not specified'}")

            # 次の設定ファイルをチェック
            if config.next_config:
                print(f"  → Next config: {config.next_config}")
                current_config_path = config.next_config
            else:
                current_config_path = None
        except Exception as e:
            print(f"✗ Failed to load configuration {current_config_path}: {e}")
            return False

    print(f"\n✓ Total clips to process: {len(configs)}")

    # 出力・一時ディレクトリを作成（最初のconfigの設定を使用）
    base_config = configs[0]
    os.makedirs(base_config.output_dir, exist_ok=True)
    os.makedirs(base_config.temp_dir, exist_ok=True)

    # 各クリップを処理
    all_clips = []
    for i, config in enumerate(configs):
        result = process_single_clip(config, i)
        if result[0] is None:
            print(f"✗ Failed to process clip {i + 1}")
            return False
        all_clips.append(result)

    # 結果サマリー
    print("\n" + "=" * 60)
    print("✓ Preparation completed successfully!")
    print(f"\nProcessed {len(all_clips)} clip(s):")
    for i, (video_path, subs_path, chat_path) in enumerate(all_clips):
        suffix = "" if i == 0 else f"_{i}"
        print(f"\nClip {i + 1}:")
        print(f"  Video: clip{suffix}.webm")
        if os.path.exists(subs_path):
            print(f"  Subtitles: subs_clip{suffix}.srt")
        if chat_path and os.path.exists(chat_path):
            print(f"  Chat overlay: chat_overlay{suffix}.ass")

    print("\n📝 Next steps:")
    if len(all_clips) > 1:
        print(f"  1. Edit subtitles if needed (subs_clip.srt, subs_clip_1.srt, ...)")
        print(f"  2. Run: python main.py compose {config_path}")
        print(f"     → This will concatenate all {len(all_clips)} clips into one video")
    else:
        print(f"  1. Edit subtitles: {os.path.join(base_config.temp_dir, 'subs_clip.srt')}")
        print(f"  2. Run: python main.py compose {config_path}")
    print("=" * 60)

    return True


def run_resub_pipeline(config_path: str) -> bool:
    """
    字幕再生成パイプライン

    既にprepareが完了している状態で、Whisper字幕だけを再生成するための簡易コマンド。
    字幕が飛んでいる場合や、別のWhisperモデルで試したい場合に便利。

    実行内容：
    - Step 1: Whisper字幕生成（subs_clip.srt生成）

    Args:
        config_path: 設定ファイルのパス

    Returns:
        bool: 成功した場合True
    """
    print("=" * 60)
    print("KIRINUKI PROCESSOR - RESUB PIPELINE")
    print("=" * 60)
    print("\nThis will regenerate subtitles with Whisper")
    print("Make sure you have already run 'prepare' command.\n")

    # 設定ファイルを読み込み
    config = load_config_from_file(config_path)

    # 一時ディレクトリを確認
    if not os.path.exists(config.temp_dir):
        print(f"✗ Error: temp directory not found: {config.temp_dir}")
        print("  Please run 'prepare' command first.")
        return False

    # ファイルパスを定義
    clip_video_path = os.path.join(config.temp_dir, "clip.webm")
    subs_clip_path = os.path.join(config.temp_dir, "subs_clip.srt")

    # clip.webmの存在確認
    if not os.path.exists(clip_video_path):
        print(f"✗ Error: clip.webm not found: {clip_video_path}")
        print("  Please run 'prepare' command first.")
        return False

    # ステップ1: Whisper字幕生成
    print("\n[Step 1] Generating subtitles with Whisper...")
    try:
        success = generate_subtitles_with_whisper(
            clip_video_path,
            subs_clip_path,
            model_size="large",
            language="ja"
        )
        if not success:
            print("  ✗ Failed to generate subtitles")
            return False
    except Exception as e:
        print(f"✗ Error in Step 1: {e}")
        return False

    print("\n" + "=" * 60)
    print("RESUB PIPELINE COMPLETED!")
    print("=" * 60)
    print("\nNext steps:")
    print(f"  1. Check subtitles: {subs_clip_path}")
    print(f"  2. Run: python main.py compose {config_path}")
    print()

    return True


def run_rechat_pipeline(config_path: str) -> bool:
    """
    チャット再生成パイプライン

    既にprepareが完了している状態で、config.txtのCHAT_DELAY_SECONDSを変更した後に
    チャットだけを再生成するための簡易コマンド。

    実行内容：
    - Step 3: チャット抽出（chat_clip.json生成）
    - Step 4: オーバーレイ生成（chat_overlay.ass生成）

    Args:
        config_path: 設定ファイルのパス

    Returns:
        bool: 成功した場合True
    """
    print("=" * 60)
    print("KIRINUKI PROCESSOR - RECHAT PIPELINE")
    print("=" * 60)
    print("\nThis will regenerate chat overlay with new CHAT_DELAY_SECONDS setting")
    print("Make sure you have already run 'prepare' command.\n")

    # 設定ファイルを読み込み
    config = load_config_from_file(config_path)

    # 一時ディレクトリを確認
    if not os.path.exists(config.temp_dir):
        print(f"✗ Error: temp directory not found: {config.temp_dir}")
        print("  Please run 'prepare' command first.")
        return False

    # ファイルパスを定義
    chat_full_path = os.path.join(config.temp_dir, "chat_full.json")
    chat_clip_path = os.path.join(config.temp_dir, "chat_clip.json")
    chat_overlay_path = os.path.join(config.temp_dir, "chat_overlay.ass")

    # chat_full.jsonの存在確認
    if not os.path.exists(chat_full_path):
        print(f"✗ Error: chat_full.json not found: {chat_full_path}")
        print("  Please run 'prepare' command first, or this video has no live chat.")
        return False

    # ステップ3: チャット抽出
    print("\n[Step 3] Extracting chat messages for clip...")
    print(f"  Chat delay: {config.chat_delay_seconds}s")
    try:
        count = load_and_extract_chat(
            chat_full_path,
            chat_clip_path,
            config.start_time,
            config.end_time,
            delay_seconds=config.chat_delay_seconds,
            dedup_window_seconds=config.chat_dedup_window_seconds,
            dedup_by_author=config.chat_dedup_by_author
        )
        if count == 0:
            print("  Warning: No chat messages in the specified time range")
            chat_clip_path = None
    except Exception as e:
        print(f"✗ Error in Step 3: {e}")
        return False

    # ステップ4: オーバーレイ生成
    if chat_clip_path:
        print("\n[Step 4] Generating chat overlay...")
        try:
            overlay_config = OverlayConfig()
            count = generate_overlay_from_file(
                chat_clip_path,
                chat_overlay_path,
                overlay_config
            )
            if count == 0:
                print("  Warning: No chat messages were added to overlay")
        except Exception as e:
            print(f"✗ Error in Step 4: {e}")
            return False
    else:
        print("\n[Step 4] Skipped (no chat messages)")

    print("\n" + "=" * 60)
    print("RECHAT PIPELINE COMPLETED!")
    print("=" * 60)
    print("\nNext step:")
    print(f"  python main.py compose {config_path}")
    print()

    return True


def run_clear_pipeline(config_path: str, keep_videos: bool = False) -> bool:
    """
    一時ファイル削除パイプライン

    次の動画作成のために不要な一時ファイルを削除します。
    削除対象：
    - 字幕ファイル（*.srt, *.ass）
    - チャットファイル（*.json）
    - オーバーレイファイル（chat_overlay*.ass）
    - タイトルバー（title_bar.ass）
    - 連結ファイル（concatenated.webm, *_merged.*)
    - 動画ファイル（--keep-videosオプションで保持可能）

    保持されるファイル：
    - data/output/final.mp4
    - data/output/description.txt

    Args:
        config_path: 設定ファイルのパス
        keep_videos: 動画ファイル（clip*.webm）を保持するか

    Returns:
        bool: 成功した場合True
    """
    print("=" * 60)
    print("KIRINUKI PROCESSOR - CLEAR TEMP FILES")
    print("=" * 60)
    print(f"\nThis will delete temporary files from {config_path}")
    if keep_videos:
        print("  Videos (clip*.webm) will be kept")
    else:
        print("  All temporary files including videos will be deleted")
    print()

    # 設定ファイルを読み込み
    config = load_config_from_file(config_path)

    # 一時ディレクトリの存在確認
    if not os.path.exists(config.temp_dir):
        print(f"✓ Temp directory does not exist: {config.temp_dir}")
        print("  Nothing to clear")
        return True

    # 削除対象のパターン
    patterns_to_delete = [
        "subs_clip*.srt",
        "subs_clip*.ass",
        "chat_full*.json",
        "chat_clip*.json",
        "chat_overlay*.ass",
        "title_bar.ass",
        "concatenated.webm",
        "*_merged.*",
    ]

    if not keep_videos:
        patterns_to_delete.extend([
            "clip*.webm",
            "clip*_raw.webm",
        ])

    deleted_count = 0

    for pattern in patterns_to_delete:
        full_pattern = os.path.join(config.temp_dir, pattern)
        matched_files = glob.glob(full_pattern)
        for file_path in matched_files:
            try:
                os.remove(file_path)
                print(f"✓ Deleted: {os.path.basename(file_path)}")
                deleted_count += 1
            except Exception as e:
                print(f"✗ Failed to delete {os.path.basename(file_path)}: {e}")

    print("\n" + "=" * 60)
    print("CLEAR COMPLETED!")
    print("=" * 60)
    print(f"\nDeleted {deleted_count} file(s)")

    if keep_videos:
        print("\nNote: Video files (clip*.webm) were kept")
        print("  Use 'python main.py clear config.txt' to delete them")

    print()
    return True


def run_output_pipeline(config_path: str) -> bool:
    """
    出力パイプライン（完成動画と設定ファイルをタイトル名のフォルダに保存）

    動画タイトル名でフォルダを作成し、以下をコピー：
    - final.mp4 → {TITLE}/final.mp4
    - description.txt → {TITLE}/description.txt
    - config.txt → {TITLE}/config.txt

    Args:
        config_path: 設定ファイルのパス

    Returns:
        bool: 成功した場合True
    """
    print("=" * 60)
    print("KIRINUKI PROCESSOR - OUTPUT PIPELINE")
    print("=" * 60)
    print("\nThis will copy final.mp4, description.txt, and config to a titled folder\n")

    # 設定ファイルを読み込み
    config = load_config_from_file(config_path)

    # タイトルチェック
    if not config.title:
        print("✗ Error: TITLE is not set in config.txt")
        print("  Please set TITLE parameter in your config file.")
        return False

    # ファイルパスを定義
    final_mp4_path = os.path.join(config.output_dir, "final.mp4")
    description_path = os.path.join(config.output_dir, "description.txt")

    # final.mp4の存在確認
    if not os.path.exists(final_mp4_path):
        print(f"✗ Error: final.mp4 not found: {final_mp4_path}")
        print("  Please run 'compose' command first.")
        return False

    # タイトル名からフォルダ名を作成（ファイルシステムで使えない文字を置換）
    import re
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', config.title)
    output_folder = os.path.join(config.output_dir, safe_title)

    # フォルダ作成
    os.makedirs(output_folder, exist_ok=True)
    print(f"✓ Created output folder: {output_folder}")

    # 1. final.mp4をコピー
    dest_mp4 = os.path.join(output_folder, "final.mp4")
    shutil.copy2(final_mp4_path, dest_mp4)
    print(f"✓ Copied: final.mp4")

    # 2. description.txtをコピー（存在する場合）
    if os.path.exists(description_path):
        dest_description = os.path.join(output_folder, "description.txt")
        shutil.copy2(description_path, dest_description)
        print(f"✓ Copied: description.txt")

    # 3. config.txtをコピー
    dest_config = os.path.join(output_folder, "config.txt")
    shutil.copy2(config_path, dest_config)
    print(f"✓ Copied: config.txt")

    print("\n" + "=" * 60)
    print("OUTPUT PIPELINE COMPLETED!")
    print("=" * 60)
    print(f"\nOutput folder: {output_folder}")
    print("Files saved:")
    print(f"  - final.mp4")
    print(f"  - config.txt")
    if os.path.exists(description_path):
        print(f"  - description.txt")
    print()

    return True


def run_compose_pipeline(config_path: str) -> bool:
    """
    動画合成パイプライン（既存の素材を使って動画を合成）
    NEXT_CONFIGが指定されている場合、複数のクリップを連結する

    Args:
        config_path: 設定ファイルのパス

    Returns:
        成功したかどうか
    """
    print("=" * 60)
    print("KIRINUKI Processor - Compose Video")
    print("=" * 60)

    # 設定読み込み（連鎖チェック）
    print("\n[Loading configuration...]")
    configs = []
    current_config_path = config_path
    visited_configs = set()

    while current_config_path:
        if current_config_path in visited_configs:
            print(f"✗ Error: Circular reference detected")
            return False
        visited_configs.add(current_config_path)

        try:
            config = load_config_from_file(current_config_path)
            configs.append(config)
            current_config_path = config.next_config
        except Exception as e:
            print(f"✗ Failed to load configuration: {e}")
            return False

    base_config = configs[0]
    print(f"✓ Loaded {len(configs)} config(s)")

    # ファイルパスをチェック
    clip_count = len(configs)
    video_paths = []
    subs_paths_srt = []
    subs_paths_ass = []
    chat_overlay_paths = []

    print(f"\nChecking files for {clip_count} clip(s)...")
    for i in range(clip_count):
        suffix = "" if i == 0 else f"_{i}"

        # 動画ファイル
        clip_video_path = os.path.join(base_config.temp_dir, f"clip{suffix}.webm")
        if not os.path.exists(clip_video_path):
            print(f"✗ Video file not found: {clip_video_path}")
            print("  Please run 'python main.py prepare' first")
            return False
        video_paths.append(clip_video_path)

        # 字幕ファイル（SRT）
        subs_srt = os.path.join(base_config.temp_dir, f"subs_clip{suffix}.srt")
        if os.path.exists(subs_srt):
            subs_paths_srt.append(subs_srt)
        else:
            subs_paths_srt.append(None)

        # 字幕ファイル（ASS）
        subs_ass = os.path.join(base_config.temp_dir, f"subs_clip{suffix}.ass")
        subs_paths_ass.append(subs_ass)

        # チャットオーバーレイ
        chat_overlay = os.path.join(base_config.temp_dir, f"chat_overlay{suffix}.ass")
        if os.path.exists(chat_overlay):
            chat_overlay_paths.append(chat_overlay)
        else:
            chat_overlay_paths.append(None)

    # 複数クリップの場合は連結処理
    final_output_path = os.path.join(base_config.output_dir, "final.mp4")

    if clip_count > 1:
        print(f"\n[Concatenating {clip_count} clips...]")

        # 動画を連結
        concatenated_video_path = os.path.join(base_config.temp_dir, "concatenated.webm")
        print("  Concatenating videos...")
        success = concatenate_videos(video_paths, concatenated_video_path)
        if not success:
            print("✗ Failed to concatenate videos")
            return False
        video_source_path = concatenated_video_path

        # 字幕をマージ（SRT）
        merged_subs_srt = os.path.join(base_config.temp_dir, "subs_clip_merged.srt")
        valid_subs_srt = [s for s in subs_paths_srt if s and os.path.exists(s)]
        if valid_subs_srt:
            print("  Merging subtitles...")
            success = merge_subtitle_files(valid_subs_srt, merged_subs_srt)
            if success:
                subs_clip_path_srt = merged_subs_srt
            else:
                subs_clip_path_srt = None
        else:
            subs_clip_path_srt = None

        # チャットオーバーレイをマージ（ASS）
        merged_chat_overlay = os.path.join(base_config.temp_dir, "chat_overlay_merged.ass")
        valid_chat_overlays = [c for c in chat_overlay_paths if c and os.path.exists(c)]
        if valid_chat_overlays:
            print("  Merging chat overlays...")
            success = merge_ass_overlays(valid_chat_overlays, merged_chat_overlay, video_paths)
            if success:
                chat_overlay_path = merged_chat_overlay
            else:
                chat_overlay_path = None
        else:
            chat_overlay_path = None

        print("✓ Concatenation completed")
    else:
        # 単一クリップの場合（従来の処理）
        video_source_path = video_paths[0]
        subs_clip_path_srt = subs_paths_srt[0]
        chat_overlay_path = chat_overlay_paths[0]

    print(f"\nUsing files:")
    print(f"  Video: {video_source_path}")

    # 字幕ファイルの処理（SRT→ASS変換）
    subs_clip_path_ass = None
    subtitle_path = None

    if subs_clip_path_srt and os.path.exists(subs_clip_path_srt):
        # マージされた字幕 or 単一字幕のASS変換
        if clip_count > 1:
            subs_clip_path_ass = os.path.join(base_config.temp_dir, "subs_clip_merged.ass")
        else:
            subs_clip_path_ass = os.path.join(base_config.temp_dir, "subs_clip.ass")

        try:
            bold_variant = subs_clip_path_ass.replace(".ass", "_bold.ass")
            needs_regen = (
                not os.path.exists(subs_clip_path_ass)
                or (base_config.subtitle_style == "bold" and not os.path.exists(bold_variant))
                or os.path.getmtime(subs_clip_path_ass) < os.path.getmtime(subs_clip_path_srt)
                or (os.path.exists(bold_variant) and os.path.getmtime(bold_variant) < os.path.getmtime(subs_clip_path_srt))
            )
            if needs_regen:
                print("  Updating styled subtitles from edited SRT...")
                convert_srt_to_ass(subs_clip_path_srt, subs_clip_path_ass)
        except Exception as e:
            print(f"  Warning: Failed to regenerate ASS from SRT: {e}")

    if subs_clip_path_ass and os.path.exists(subs_clip_path_ass):
        subtitle_candidate = subs_clip_path_ass
        if base_config.subtitle_style == "bold":
            bold_path = subs_clip_path_ass.replace(".ass", "_bold.ass")
            if os.path.exists(bold_path):
                subtitle_candidate = bold_path
        subtitle_path = subtitle_candidate
        print(f"  Subtitles: {subtitle_path} (styled)")
    elif subs_clip_path_srt and os.path.exists(subs_clip_path_srt):
        subtitle_path = subs_clip_path_srt
        print(f"  Subtitles: {subs_clip_path_srt}")
    else:
        print("  Subtitles: (none)")

    overlay_path = None
    if chat_overlay_path and os.path.exists(chat_overlay_path):
        overlay_path = chat_overlay_path
        print(f"  Chat overlay: {chat_overlay_path}")
    else:
        print(f"  Chat overlay: (none)")

    # タイトルバー生成（TITLEが指定されている場合）
    title_bar_path = os.path.join(base_config.temp_dir, "title_bar.ass")
    title_overlay_path = None
    if base_config.title:
        print(f"\n[Generating title bar...]")
        try:
            success = generate_title_bar(
                base_config.title,
                title_bar_path,
                video_width=1920,
                video_height=1080,
                slide_duration=1.2,
                display_duration=None  # 動画終了まで表示
            )
            if success:
                title_overlay_path = title_bar_path
                print(f"  Title bar: {title_bar_path}")
        except Exception as e:
            print(f"✗ Error generating title bar: {e}")

    # ロゴファイルのパス（固定）
    logo_path = "data/input/ひろゆき視点【切り抜き】.png"
    if not os.path.exists(logo_path):
        logo_path = None
        print(f"  Logo file not found: {logo_path}")

    # ステップ5: 動画合成
    print("\n[Step 5] Composing final video...")
    try:
        # オーバーレイを結合（chat + title）
        overlays = []
        if overlay_path:
            overlays.append(overlay_path)
        if title_overlay_path:
            overlays.append(title_overlay_path)

        # すべてのクリップが既にStep0でクロップ済みのため、compose時は再クロップしない
        crop_top = crop_bottom = crop_left = crop_right = 0.0

        success = compose_video(
            video_source_path,
            final_output_path,
            subtitle_path=subtitle_path,
            overlay_path=overlay_path,
            title_overlay_path=title_overlay_path,
            logo_path=logo_path,
            crop_top_percent=crop_top,
            crop_bottom_percent=crop_bottom,
            crop_left_percent=crop_left,
            crop_right_percent=crop_right
        )
        if not success:
            print("✗ Failed to compose video")
            return False
    except Exception as e:
        print(f"✗ Error in Step 5: {e}")
        return False

    # ステップ6: YouTube説明欄生成（字幕が存在する場合）
    description_output_path = os.path.join(base_config.output_dir, "description.txt")
    if subs_clip_path_srt and os.path.exists(subs_clip_path_srt):
        print("\n[Step 6] Generating YouTube description...")
        try:
            success = generate_youtube_description(
                subs_clip_path_srt,
                description_output_path,
                prompt_template_path="data/input/setumei",
                video_url=base_config.video_url
            )
            if success:
                print(f"  Description: {description_output_path}")
        except Exception as e:
            print(f"  Note: Failed to generate description: {e}")
    else:
        print("\n[Step 6] Skipped (no subtitles available)")

    print("\n" + "=" * 60)
    print("✓ Composition completed successfully!")
    print(f"  Final output: {final_output_path}")
    if os.path.exists(description_output_path):
        print(f"  Description: {description_output_path}")
    print("=" * 60)

    return True


def run_full_pipeline(config_path: str, skip_steps: list = None) -> bool:
    """
    全ステップを実行するパイプライン

    Args:
        config_path: 設定ファイルのパス
        skip_steps: スキップするステップのリスト（例: [1, 3]）

    Returns:
        成功したかどうか
    """
    if skip_steps is None:
        skip_steps = []

    print("=" * 60)
    print("KIRINUKI Processor - Full Pipeline")
    print("=" * 60)

    # ステップ0: 設定読み込み
    print("\n[Step 0] Loading configuration...")
    try:
        config = load_config_from_file(config_path)
        print(f"✓ Configuration loaded")
        print(f"  Video URL: {config.video_url}")
        print(f"  Start time: {config.start_time}")
        print(f"  End time: {config.end_time or 'Not specified'}")
        print(f"  Auto download: {config.auto_download}")
        if config.webm_path:
            print(f"  WebM path: {config.webm_path}")
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        return False

    # 出力・一時ディレクトリを作成
    os.makedirs(config.output_dir, exist_ok=True)
    os.makedirs(config.temp_dir, exist_ok=True)

    # ファイルパスを定義
    clip_video_path = os.path.join(config.temp_dir, "clip.webm")
    clip_video_raw_path = os.path.join(config.temp_dir, "clip_raw.webm")
    subs_full_path = os.path.join(config.temp_dir, "subs_full.srt")
    subs_clip_path = os.path.join(config.temp_dir, "subs_clip.srt")
    chat_full_path = os.path.join(config.temp_dir, "chat_full.json")
    chat_clip_path = os.path.join(config.temp_dir, "chat_clip.json")
    chat_overlay_path = os.path.join(config.temp_dir, "chat_overlay.ass")
    final_output_path = os.path.join(config.output_dir, "final.mp4")

    # 動画ファイルのパスを決定（raw→crop→clip.webm に統一）
    if config.auto_download:
        if 0 not in skip_steps:
            print("\n[Step 0] Downloading and clipping video from YouTube...")
            try:
                success = download_and_clip_video(
                    config.video_url,
                    config.start_time,
                    config.end_time,
                    clip_video_raw_path,
                    download_full=False
                )
                if not success:
                    print("✗ Failed to download and clip video")
                    return False
            except Exception as e:
                print(f"✗ Error in Step 0: {e}")
                return False
        else:
            print("\n[Step 0] Skipped download (assuming raw clip already exists)")
        raw_video_path = clip_video_raw_path
    else:
        print("\n[Step 0] Using existing video file")
        if not config.webm_path:
            print("✗ WEBM_PATH is required when AUTO_DOWNLOAD=false")
            return False
        raw_video_path = config.webm_path

    # クロップ適用（skipしていてもクロップは行う）
    cropped = apply_crop_or_copy(raw_video_path, clip_video_path, config)
    if not cropped:
        return False
    video_source_path = cropped

    # ステップ1: Whisper字幕生成
    if 1 not in skip_steps:
        print("\n[Step 1] Generating subtitles with Whisper...")
        try:
            success = generate_subtitles_with_whisper(
                video_source_path,
                subs_clip_path,
                model_size="large",
                language="ja"
            )
            if not success:
                print("  Note: Failed to generate subtitles, will proceed without them")
                subs_clip_path = None
        except Exception as e:
            print(f"✗ Error in Step 1: {e}")
            subs_clip_path = None
    else:
        print("\n[Step 1] Skipped")

    # ステップ2: チャット取得
    if 2 not in skip_steps:
        print("\n[Step 2] Fetching live chat from YouTube...")
        try:
            success = fetch_chat(config.video_url, chat_full_path)
            if not success:
                print("  Note: Chat replay not available, will proceed without it")
                chat_full_path = None
        except Exception as e:
            print(f"✗ Error in Step 2: {e}")
            chat_full_path = None
    else:
        print("\n[Step 2] Skipped")

    # ステップ3: チャット抽出
    if 3 not in skip_steps and chat_full_path and os.path.exists(chat_full_path):
        print("\n[Step 3] Extracting chat messages for clip...")
        try:
            count = load_and_extract_chat(
                chat_full_path,
                chat_clip_path,
                config.start_time,
                config.end_time,
                delay_seconds=config.chat_delay_seconds,
                dedup_window_seconds=config.chat_dedup_window_seconds,
                dedup_by_author=config.chat_dedup_by_author
            )
            if count == 0:
                chat_clip_path = None
        except Exception as e:
            print(f"✗ Error in Step 3: {e}")
            chat_clip_path = None
    else:
        print("\n[Step 3] Skipped (no chat available)")
        chat_clip_path = None

    # ステップ4: オーバーレイ生成
    if 4 not in skip_steps and chat_clip_path and os.path.exists(chat_clip_path):
        print("\n[Step 4] Generating chat overlay (ASS)...")
        try:
            overlay_config = OverlayConfig()
            count = generate_overlay_from_file(
                chat_clip_path,
                chat_overlay_path,
                overlay_config
            )
            if count == 0:
                chat_overlay_path = None
        except Exception as e:
            print(f"✗ Error in Step 4: {e}")
            chat_overlay_path = None
    else:
        print("\n[Step 4] Skipped (no chat available)")
        chat_overlay_path = None

    subtitle_for_compose = None
    if subs_clip_path and os.path.exists(subs_clip_path):
        subs_clip_path_ass = subs_clip_path.replace(".srt", ".ass")
        try:
            needs_regen = (not os.path.exists(subs_clip_path_ass) or
                           os.path.getmtime(subs_clip_path_ass) < os.path.getmtime(subs_clip_path))
            if needs_regen:
                print("  Updating styled subtitles from edited SRT...")
                convert_srt_to_ass(subs_clip_path, subs_clip_path_ass)
        except Exception as e:
            print(f"  Warning: Failed to regenerate ASS from SRT: {e}")

        if os.path.exists(subs_clip_path_ass):
            subtitle_for_compose = subs_clip_path_ass
        else:
            subtitle_for_compose = subs_clip_path

    # ステップ5: 動画合成
    if 5 not in skip_steps:
        print("\n[Step 5] Composing final video...")
        try:
            success = compose_video(
                video_source_path,
                final_output_path,
                subtitle_path=subtitle_for_compose,
                overlay_path=chat_overlay_path if chat_overlay_path and os.path.exists(chat_overlay_path) else None
            )
            if not success:
                print("✗ Failed to compose video")
                return False
        except Exception as e:
            print(f"✗ Error in Step 6: {e}")
            return False
    else:
        print("\n[Step 6] Skipped")

    print("\n" + "=" * 60)
    print("✓ Pipeline completed successfully!")
    print(f"  Final output: {final_output_path}")
    print("=" * 60)

    return True


def run_crop_step(config_path: str) -> bool:
    """
    Step0.5: 既存のclip_raw.webmにクロップを適用してclip.webmを生成する。
    clip_raw.webmが無ければStep0同様にダウンロードしてからクロップする。
    """
    try:
        config = load_config_from_file(config_path)
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        return False

    os.makedirs(config.temp_dir, exist_ok=True)
    clip_raw_path = os.path.join(config.temp_dir, "clip_raw.webm")
    clip_cropped_path = os.path.join(config.temp_dir, "clip.webm")

    # ソース動画を準備
    if os.path.exists(clip_raw_path):
        print(f"✓ Found existing raw clip: {clip_raw_path}")
        raw_video_path = clip_raw_path
    else:
        if config.auto_download:
            print("\n[Step0.5] Downloading video section (Step0 equivalent)...")
            success = download_and_clip_video(
                config.video_url,
                config.start_time,
                config.end_time,
                clip_raw_path,
                download_full=False
            )
            if not success:
                print("✗ Failed to download video")
                return False
            raw_video_path = clip_raw_path
        else:
            if not config.webm_path or not os.path.exists(config.webm_path):
                print("✗ clip_raw.webm not found and WEBM_PATH is invalid. Please run step0 or set WEBM_PATH.")
                return False
            raw_video_path = config.webm_path
            import shutil
            shutil.copy2(raw_video_path, clip_raw_path)

    print("\n[Step0.5] Applying crop...")
    print(f"  Top: {config.crop_top_percent}%, Bottom: {config.crop_bottom_percent}%")
    print(f"  Left: {config.crop_left_percent}%, Right: {config.crop_right_percent}%")
    cropped = apply_crop_or_copy(
        raw_video_path,
        clip_cropped_path,
        config
    )
    if not cropped:
        print("✗ Crop failed")
        return False

    print(f"✓ Cropped clip saved: {clip_cropped_path}")
    print("Next: run step1/prepare/compose as needed.")
    return True


SHORT_OVERLAY_DEFAULTS = {
    'TOP_TEXT': '',
    'BOTTOM_TEXT': '',
    'TOP_TEXT_COLOR': 'white',
    'BOTTOM_TEXT_COLOR': 'white',
    'TOP_TEXT_SIZE': '72',
    'BOTTOM_TEXT_SIZE': '64',
    'TOP_TEXT_FONT': '',
    'BOTTOM_TEXT_FONT': '',
    'TOP_TEXT_BOX_COLOR': 'black@0.65',
    'BOTTOM_TEXT_BOX_COLOR': 'black@0.65',
    'TOP_TEXT_BOX_BORDER': '28',
    'BOTTOM_TEXT_BOX_BORDER': '28',
    'TOP_TEXT_BOX': '1',
    'BOTTOM_TEXT_BOX': '1',
    'TOP_TEXT_WRAP': '1',
    'BOTTOM_TEXT_WRAP': '0',
    'TOP_TEXT_WRAP_WIDTH': '14',
    'BOTTOM_TEXT_WRAP_WIDTH': '20',
    'TOP_TEXT_OFFSET_Y': '0',
    'BOTTOM_TEXT_OFFSET_Y': '0'
}


def load_short_config(config_path: str) -> dict:
    """
    ショート動画設定ファイルを読み込む

    複数シーン対応：
    SCENE1_START, SCENE1_END, SCENE2_START, SCENE2_END... の形式で記述可能

    Args:
        config_path: 設定ファイルのパス

    Returns:
        設定辞書（scenesキーに複数シーンのリストを含む）
    """
    config = {
        'INPUT_VIDEO': 'data/output/final.mp4',
        'OUTPUT': 'data/output/short.mp4',
        'scenes': []  # 複数シーンを格納
    }
    config.update(SHORT_OVERLAY_DEFAULTS)

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")

    scene_data = {}  # SCENE1_START, SCENE1_END などを一時保存

    with open(config_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip()

                # SCENEn_START, SCENEn_END を検出
                if key.startswith('SCENE') and ('_START' in key or '_END' in key):
                    scene_data[key] = value
                else:
                    config[key] = value

    # シーンデータを整理
    if scene_data:
        # SCENEの番号を抽出してソート
        scene_numbers = set()
        for key in scene_data.keys():
            # SCENE1_START → 1 を抽出
            match = re.match(r'SCENE(\d+)_', key)
            if match:
                scene_numbers.add(int(match.group(1)))

        # 番号順にシーンを構築
        for num in sorted(scene_numbers):
            start_key = f'SCENE{num}_START'
            end_key = f'SCENE{num}_END'

            if start_key in scene_data and end_key in scene_data:
                config['scenes'].append({
                    'start': scene_data[start_key],
                    'end': scene_data[end_key]
                })
    else:
        # 従来の形式（START_TIME, END_TIME）もサポート
        if 'START_TIME' in config and 'END_TIME' in config:
            config['scenes'].append({
                'start': config['START_TIME'],
                'end': config['END_TIME']
            })

    return config


def _clean_str_value(value: Any, default: str = '') -> str:
    """設定値を文字列としてクリーンアップ"""
    if value is None:
        return default
    return str(value).strip()


def _parse_int_value(value: Any, default: int) -> int:
    """設定値を整数としてパース"""
    if value is None:
        return default
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def _parse_bool_value(value: Any, default: bool) -> bool:
    """設定値を真偽値としてパース"""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ('1', 'true', 'yes', 'on')


def _decode_overlay_text(value: str) -> str:
    """\\nなどのエスケープシーケンスを実文字に展開"""
    if not value:
        return value
    return value.replace('\\n', '\n').replace('\\r', '')


def _auto_wrap_text(text: str, max_chars: int) -> str:
    """指定文字数で自動改行"""
    if not text or max_chars <= 0:
        return text
    result_lines = []
    for segment in text.split('\n'):
        if not segment:
            result_lines.append('')
            continue
        line = ''
        for ch in segment:
            line += ch
            if len(line) >= max_chars:
                result_lines.append(line)
                line = ''
        if line:
            result_lines.append(line)
    return '\n'.join(result_lines)


def build_overlay_settings(config: dict) -> dict:
    """
    ショート動画用の上下テキスト設定を構築
    """
    top_text = _decode_overlay_text(_clean_str_value(config.get('TOP_TEXT')))
    bottom_text = _decode_overlay_text(_clean_str_value(config.get('BOTTOM_TEXT')))

    overlay = {
        'top_text': top_text,
        'bottom_text': bottom_text,
        'top_font': _clean_str_value(config.get('TOP_TEXT_FONT')),
        'bottom_font': _clean_str_value(config.get('BOTTOM_TEXT_FONT')),
        'top_color': _clean_str_value(config.get('TOP_TEXT_COLOR'), 'white') or 'white',
        'bottom_color': _clean_str_value(config.get('BOTTOM_TEXT_COLOR'), 'white') or 'white',
        'top_fontsize': _parse_int_value(config.get('TOP_TEXT_SIZE'), 72),
        'bottom_fontsize': _parse_int_value(config.get('BOTTOM_TEXT_SIZE'), 64),
        'top_box_color': _clean_str_value(config.get('TOP_TEXT_BOX_COLOR'), 'black@0.7') or 'black@0.7',
        'bottom_box_color': _clean_str_value(config.get('BOTTOM_TEXT_BOX_COLOR'), 'black@0.7') or 'black@0.7',
        'top_box_border': _parse_int_value(config.get('TOP_TEXT_BOX_BORDER'), 28),
        'bottom_box_border': _parse_int_value(config.get('BOTTOM_TEXT_BOX_BORDER'), 28),
        'top_wrap': _parse_bool_value(config.get('TOP_TEXT_WRAP'), True),
        'bottom_wrap': _parse_bool_value(config.get('BOTTOM_TEXT_WRAP'), False),
        'top_wrap_chars': _parse_int_value(config.get('TOP_TEXT_WRAP_WIDTH'), 14),
        'bottom_wrap_chars': _parse_int_value(config.get('BOTTOM_TEXT_WRAP_WIDTH'), 20),
        'top_offset_y': _parse_int_value(config.get('TOP_TEXT_OFFSET_Y'), 0),
        'bottom_offset_y': _parse_int_value(config.get('BOTTOM_TEXT_OFFSET_Y'), 0)
    }
    overlay['top_box'] = _parse_bool_value(
        config.get('TOP_TEXT_BOX'),
        bool(overlay['top_text'])
    )
    overlay['bottom_box'] = _parse_bool_value(
        config.get('BOTTOM_TEXT_BOX'),
        bool(overlay['bottom_text'])
    )

    if overlay['top_wrap'] and overlay['top_text']:
        overlay['top_text'] = _auto_wrap_text(overlay['top_text'], overlay['top_wrap_chars'])
    if overlay['bottom_wrap'] and overlay['bottom_text']:
        overlay['bottom_text'] = _auto_wrap_text(overlay['bottom_text'], overlay['bottom_wrap_chars'])

    overlay['top_lines'] = overlay['top_text'].split('\n') if overlay['top_text'] else []
    overlay['bottom_lines'] = overlay['bottom_text'].split('\n') if overlay['bottom_text'] else []

    overlay['top_line_colors'] = {}
    for idx, _ in enumerate(overlay['top_lines'], start=1):
        key = f'TOP_TEXT_LINE{idx}_COLOR'
        color = _clean_str_value(config.get(key))
        if color:
            overlay['top_line_colors'][idx] = color

    overlay['bottom_line_colors'] = {}
    for idx, _ in enumerate(overlay['bottom_lines'], start=1):
        key = f'BOTTOM_TEXT_LINE{idx}_COLOR'
        color = _clean_str_value(config.get(key))
        if color:
            overlay['bottom_line_colors'][idx] = color

    return overlay


def run_short_pipeline(config_path: str) -> bool:
    """
    ショート動画生成パイプライン（複数シーン対応）

    Args:
        config_path: 設定ファイルのパス

    Returns:
        成功した場合True
    """
    print("=" * 60)
    print("KIRINUKI PROCESSOR - SHORT VIDEO GENERATOR")
    print("=" * 60)

    # 設定読み込み
    try:
        config = load_short_config(config_path)
        print(f"\n✓ Configuration loaded: {config_path}")
        print(f"  Input video: {config['INPUT_VIDEO']}")
        print(f"  Scenes: {len(config['scenes'])}")
        overlay_settings = build_overlay_settings(config)
        for i, scene in enumerate(config['scenes'], 1):
            print(f"    Scene {i}: {scene['start']} - {scene['end']}")
        print(f"  Output: {config['OUTPUT']}")
        if overlay_settings.get('top_text'):
            print(f"  Top text: {overlay_settings['top_text']}")
        if overlay_settings.get('bottom_text'):
            print(f"  Bottom text: {overlay_settings['bottom_text']}")
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        return False

    # シーンが定義されているか確認
    if not config['scenes']:
        print(f"\n✗ Error: No scenes defined in configuration")
        print(f"  Please define SCENE1_START, SCENE1_END, etc. in {config_path}")
        return False

    # 入力動画の存在確認
    input_video = config['INPUT_VIDEO']
    if not os.path.exists(input_video):
        print(f"\n✗ Error: Input video not found: {input_video}")
        print(f"  Please run 'python main.py compose config.txt' first to create final.mp4")
        return False

    # 出力ディレクトリを作成
    output_path = config['OUTPUT']
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 一時ディレクトリを作成
    temp_dir = 'data/temp'
    os.makedirs(temp_dir, exist_ok=True)

    # 各シーンを個別に生成
    scene_files = []
    try:
        for i, scene in enumerate(config['scenes'], 1):
            scene_output = os.path.join(temp_dir, f'short_scene_{i}.mp4')
            print(f"\n[Scene {i}/{len(config['scenes'])}] Generating: {scene['start']} - {scene['end']}")

            success = generate_short_video(
                input_video,
                scene_output,
                scene['start'],
                scene['end'],
                overlay_settings=overlay_settings
            )

            if not success:
                print(f"✗ Failed to generate scene {i}")
                return False

            scene_files.append(scene_output)

        # 複数シーンを連結
        if len(scene_files) == 1:
            # シーンが1つだけの場合はそのままコピー
            shutil.copy2(scene_files[0], output_path)
            print(f"\n✓ Short video created: {output_path}")
        else:
            # 複数シーンを連結
            print(f"\n[Concatenating {len(scene_files)} scenes...]")
            success = concatenate_videos(scene_files, output_path)
            if not success:
                print("✗ Failed to concatenate scenes")
                return False
            print(f"✓ Scenes concatenated: {output_path}")

    except Exception as e:
        print(f"✗ Error generating short video: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # 一時ファイルを削除
        for scene_file in scene_files:
            if os.path.exists(scene_file):
                os.remove(scene_file)

    print("\n" + "=" * 60)
    print("✓ SHORT VIDEO GENERATION COMPLETED!")
    print("=" * 60)
    print(f"\nOutput: {output_path}")
    print(f"Total scenes: {len(config['scenes'])}")
    print()

    return True


def run_single_step(step_num: float, args: argparse.Namespace) -> bool:
    """
    単一ステップを実行

    Args:
        step_num: ステップ番号（1.5などの小数も可）
        args: コマンドライン引数

    Returns:
        成功したかどうか
    """
    print(f"\n[Step {step_num}] Running single step...")

    if step_num == 0:
        # 動画ダウンロード・切り抜き
        success = download_and_clip_video(
            args.url,
            args.start,
            args.end,
            args.output,
            download_full=args.full if hasattr(args, 'full') else False
        )
        return success

    elif step_num == 0.5:
        # クロップのみ（configを読み、clip_raw→clipに適用）
        success = run_crop_step(args.config)
        return success

    elif step_num == 1:
        # Whisper字幕生成
        success = generate_subtitles_with_whisper(
            args.input,
            args.output,
            model_size=args.model if hasattr(args, 'model') else "large",
            language=args.language if hasattr(args, 'language') else "ja"
        )
        return success

    elif step_num == 1.5:
        # 字幕修正
        method = args.method if hasattr(args, 'method') else "rule-based"

        if method == "ai":
            # AIベースで修正
            from kirinuki_processor.steps.step1_5_fix_subtitles_ai import fix_subtitle_file_ai
            success = fix_subtitle_file_ai(
                args.input,
                args.output,
                model=args.model if hasattr(args, 'model') else "llama-3.3-70b-versatile"
            )
        else:
            # ルールベースで修正
            success = fix_subtitle_file(
                args.input,
                args.output,
                model="rule-based"
            )
        return success

    elif step_num == 2:
        # チャット取得
        success = fetch_chat(args.url, args.output)
        return success

    elif step_num == 3:
        # チャット抽出
        count = load_and_extract_chat(
            args.input,
            args.output,
            args.start,
            args.end,
            delay_seconds=args.delay if hasattr(args, 'delay') else 0.0
        )
        return count > 0

    elif step_num == 4:
        # オーバーレイ生成
        config = OverlayConfig()
        count = generate_overlay_from_file(
            args.input,
            args.output,
            config
        )
        return count > 0

    elif step_num == 5:
        # 動画合成
        success = compose_video(
            args.video,
            args.output,
            subtitle_path=args.subtitle if hasattr(args, 'subtitle') else None,
            overlay_path=args.overlay if hasattr(args, 'overlay') else None
        )
        return success

    elif step_num == 6:
        # YouTube説明欄生成
        success = generate_youtube_description(
            args.input,
            args.output,
            prompt_template_path=args.prompt if hasattr(args, 'prompt') else "data/input/setumei",
            model=args.model if hasattr(args, 'model') else "llama-3.3-70b-versatile"
        )
        return success

    else:
        print(f"Unknown step: {step_num}")
        return False


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description="KIRINUKI Processor - ひろゆき動画切り抜き処理ツール"
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # 素材準備パイプライン
    prepare_parser = subparsers.add_parser("prepare", help="Prepare materials (download, subtitles, chat) - stops before composing video")
    prepare_parser.add_argument("config", help="Configuration file path")

    # 字幕再生成パイプライン
    resub_parser = subparsers.add_parser("resub", help="Regenerate subtitles only (useful when Whisper subtitles have issues)")
    resub_parser.add_argument("config", help="Configuration file path")

    # チャット再生成パイプライン
    rechat_parser = subparsers.add_parser("rechat", help="Regenerate chat overlay only (useful for adjusting CHAT_DELAY_SECONDS)")
    rechat_parser.add_argument("config", help="Configuration file path")

    # 動画合成パイプライン
    compose_parser = subparsers.add_parser("compose", help="Compose final video using prepared materials")
    compose_parser.add_argument("config", help="Configuration file path")

    # 出力パイプライン
    output_parser = subparsers.add_parser("output", help="Copy final.mp4, description.txt, and config to a titled folder")
    output_parser.add_argument("config", help="Configuration file path")

    # 一時ファイル削除パイプライン
    clear_parser = subparsers.add_parser("clear", help="Delete temporary files to prepare for next video")
    clear_parser.add_argument("config", help="Configuration file path")
    clear_parser.add_argument("--keep-videos", action="store_true", help="Keep video files (clip*.webm) and only delete subtitles/chat files")

    # フルパイプライン実行（prepare→composeの順に全ステップ実行）
    pipeline_parser = subparsers.add_parser("run", help="Run full pipeline (prepare then compose)")
    pipeline_parser.add_argument("config", help="Configuration file path")

    # サンプル設定ファイル作成
    sample_parser = subparsers.add_parser("init", help="Create sample config file")
    sample_parser.add_argument(
        "-o", "--output",
        default="config.txt",
        help="Output path for sample config (default: config.txt)"
    )

    # ショート動画生成パイプライン
    short_parser = subparsers.add_parser("short", help="Generate vertical short video from clip.webm or concatenated.webm")
    short_parser.add_argument("config", help="Short config file path (e.g., short_config.txt)")

    # 個別ステップ実行用のサブコマンド
    # Step 0
    step0_parser = subparsers.add_parser("step0", help="Download and clip video")
    step0_parser.add_argument("url", help="YouTube video URL")
    step0_parser.add_argument("-s", "--start", required=True, help="Start time (hh:mm:ss)")
    step0_parser.add_argument("-e", "--end", help="End time (hh:mm:ss)")
    step0_parser.add_argument("-o", "--output", required=True, help="Output video file")
    step0_parser.add_argument("--full", action="store_true", help="Download full video first (slower but more reliable)")

    # Step 0.5 (クロップのみ)
    step0_5_parser = subparsers.add_parser("step0.5", help="Apply crop to clip_raw.webm (download if missing) to create clip.webm")
    step0_5_parser.add_argument("config", help="Configuration file path")

    # Step 1 (Whisper字幕生成)
    step1_parser = subparsers.add_parser("step1", help="Generate subtitles with Whisper")
    step1_parser.add_argument("-i", "--input", required=True, help="Input video file")
    step1_parser.add_argument("-o", "--output", required=True, help="Output SRT file")
    step1_parser.add_argument("-m", "--model", default="large", choices=["tiny", "base", "small", "medium", "large"], help="Whisper model size (default: large)")
    step1_parser.add_argument("-l", "--language", default="ja", help="Language code (default: ja)")

    # Step 1.5 (字幕修正)
    step1_5_parser = subparsers.add_parser("step1.5", help="Fix subtitles")
    step1_5_parser.add_argument("-i", "--input", required=True, help="Input SRT file")
    step1_5_parser.add_argument("-o", "--output", required=True, help="Output SRT file")
    step1_5_parser.add_argument("--method", choices=["rule-based", "ai"], default="rule-based", help="Correction method: rule-based (fast, safe) or ai (smarter, requires API)")
    step1_5_parser.add_argument("-m", "--model", default="llama-3.3-70b-versatile", help="Groq model name for AI method (default: llama-3.3-70b-versatile)")

    # Step 2 (チャット取得)
    step2_parser = subparsers.add_parser("step2", help="Fetch live chat")
    step2_parser.add_argument("url", help="YouTube video URL")
    step2_parser.add_argument("-o", "--output", required=True, help="Output JSON file")

    # Step 3 (チャット抽出)
    step3_parser = subparsers.add_parser("step3", help="Extract chat")
    step3_parser.add_argument("-i", "--input", required=True, help="Input JSON file")
    step3_parser.add_argument("-o", "--output", required=True, help="Output JSON file")
    step3_parser.add_argument("-s", "--start", required=True, help="Start time (hh:mm:ss)")
    step3_parser.add_argument("-e", "--end", help="End time (hh:mm:ss)")
    step3_parser.add_argument("-d", "--delay", type=float, default=0.0, help="Chat display delay in seconds (default: 0)")

    # Step 4 (オーバーレイ生成)
    step4_parser = subparsers.add_parser("step4", help="Generate overlay")
    step4_parser.add_argument("-i", "--input", required=True, help="Input JSON file")
    step4_parser.add_argument("-o", "--output", required=True, help="Output ASS file")

    # Step 5 (動画合成)
    step5_parser = subparsers.add_parser("step5", help="Compose video")
    step5_parser.add_argument("-v", "--video", required=True, help="Input video file")
    step5_parser.add_argument("-o", "--output", required=True, help="Output video file")
    step5_parser.add_argument("-s", "--subtitle", help="Subtitle file (SRT)")
    step5_parser.add_argument("-c", "--overlay", help="Chat overlay file (ASS)")

    # Step 6 (YouTube説明欄生成)
    step6_parser = subparsers.add_parser("step6", help="Generate YouTube description")
    step6_parser.add_argument("-i", "--input", required=True, help="Input SRT file")
    step6_parser.add_argument("-o", "--output", required=True, help="Output text file")
    step6_parser.add_argument("-p", "--prompt", default="data/input/setumei", help="Prompt template file (default: data/input/setumei)")
    step6_parser.add_argument("-m", "--model", default="llama-3.3-70b-versatile", help="Groq model name (default: llama-3.3-70b-versatile)")

    args = parser.parse_args()

    # コマンドが指定されていない場合
    if not args.command:
        parser.print_help()
        return 1

    # コマンド実行
    try:
        if args.command == "prepare":
            success = run_prepare_pipeline(args.config)
            return 0 if success else 1

        elif args.command == "resub":
            success = run_resub_pipeline(args.config)
            return 0 if success else 1

        elif args.command == "rechat":
            success = run_rechat_pipeline(args.config)
            return 0 if success else 1

        elif args.command == "compose":
            success = run_compose_pipeline(args.config)
            return 0 if success else 1

        elif args.command == "output":
            success = run_output_pipeline(args.config)
            return 0 if success else 1

        elif args.command == "clear":
            success = run_clear_pipeline(args.config, keep_videos=args.keep_videos)
            return 0 if success else 1

        elif args.command == "run":
            success = run_full_pipeline(args.config, [])
            return 0 if success else 1

        elif args.command == "init":
            create_sample_config(args.output)
            return 0

        elif args.command == "short":
            success = run_short_pipeline(args.config)
            return 0 if success else 1

        elif args.command == "step0.5":
            success = run_crop_step(args.config)
            return 0 if success else 1

        elif args.command.startswith("step"):
            step_str = args.command[4:]
            step_num = float(step_str) if '.' in step_str else int(step_str)
            success = run_single_step(step_num, args)
            return 0 if success else 1

        else:
            print(f"Unknown command: {args.command}")
            return 1

    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 1
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
