#!/usr/bin/env python3
"""
KIRINUKI Processor - メインスクリプト

ひろゆき動画の切り抜きに字幕とライブチャットを重ねるツール
"""

import os
import sys
import argparse
from pathlib import Path

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
from kirinuki_processor.steps.step3_fetch_chat import fetch_chat
from kirinuki_processor.steps.step4_extract_chat import load_and_extract_chat
from kirinuki_processor.steps.step5_generate_overlay import (
    generate_overlay_from_file,
    OverlayConfig
)
from kirinuki_processor.steps.step6_compose_video import compose_video
from kirinuki_processor.steps.step_title_bar import generate_title_bar


def run_prepare_pipeline(config_path: str) -> bool:
    """
    素材準備パイプライン（字幕生成まで、動画合成は行わない）

    Args:
        config_path: 設定ファイルのパス

    Returns:
        成功したかどうか
    """
    print("=" * 60)
    print("KIRINUKI Processor - Prepare Materials")
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
    subs_clip_path = os.path.join(config.temp_dir, "subs_clip.srt")
    chat_full_path = os.path.join(config.temp_dir, "chat_full.json")
    chat_clip_path = os.path.join(config.temp_dir, "chat_clip.json")
    chat_overlay_path = os.path.join(config.temp_dir, "chat_overlay.ass")

    # 動画ファイルのパスを決定
    if config.auto_download:
        print("\n[Step 0] Downloading and clipping video from YouTube...")
        try:
            success = download_and_clip_video(
                config.video_url,
                config.start_time,
                config.end_time,
                clip_video_path,
                download_full=False
            )
            if not success:
                print("✗ Failed to download and clip video")
                return False
            video_source_path = clip_video_path
        except Exception as e:
            print(f"✗ Error in Step 0: {e}")
            return False
    else:
        print("\n[Step 0] Using existing video file")
        if not config.webm_path:
            print("✗ WEBM_PATH is required when AUTO_DOWNLOAD=false")
            return False
        video_source_path = config.webm_path

    # ステップ1: Whisper字幕生成
    print("\n[Step 1] Generating subtitles with Whisper...")
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
        print(f"✗ Error in Step 1: {e}")

    # ステップ2: チャット取得
    print("\n[Step 2] Fetching live chat from YouTube...")
    try:
        success = fetch_chat(config.video_url, chat_full_path)
        if not success:
            print("  Note: Chat replay not available")
            chat_full_path = None
    except Exception as e:
        print(f"✗ Error in Step 2: {e}")
        chat_full_path = None

    # ステップ3: チャット抽出
    if chat_full_path and os.path.exists(chat_full_path):
        print("\n[Step 3] Extracting chat messages for clip...")
        try:
            count = load_and_extract_chat(
                chat_full_path,
                chat_clip_path,
                config.start_time,
                config.end_time
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
    if chat_clip_path and os.path.exists(chat_clip_path):
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

    print("\n" + "=" * 60)
    print("✓ Preparation completed successfully!")
    print("\nGenerated files:")
    print(f"  Video: {video_source_path}")
    if os.path.exists(subs_clip_path):
        print(f"  Subtitles: {subs_clip_path}")
    if chat_overlay_path and os.path.exists(chat_overlay_path):
        print(f"  Chat overlay: {chat_overlay_path}")
    print("\n📝 Next steps:")
    print(f"  1. Edit subtitles: {subs_clip_path}")
    print(f"  2. Run: python main.py compose {config_path}")
    print("=" * 60)

    return True


def run_compose_pipeline(config_path: str) -> bool:
    """
    動画合成パイプライン（既存の素材を使って動画を合成）

    Args:
        config_path: 設定ファイルのパス

    Returns:
        成功したかどうか
    """
    print("=" * 60)
    print("KIRINUKI Processor - Compose Video")
    print("=" * 60)

    # 設定読み込み
    print("\n[Loading configuration...]")
    try:
        config = load_config_from_file(config_path)
        print(f"✓ Configuration loaded")
    except Exception as e:
        print(f"✗ Failed to load configuration: {e}")
        return False

    # ファイルパスを定義
    clip_video_path = os.path.join(config.temp_dir, "clip.webm")
    subs_clip_path_srt = os.path.join(config.temp_dir, "subs_clip.srt")
    subs_clip_path_ass = os.path.join(config.temp_dir, "subs_clip.ass")
    chat_overlay_path = os.path.join(config.temp_dir, "chat_overlay.ass")
    title_bar_path = os.path.join(config.temp_dir, "title_bar.ass")
    final_output_path = os.path.join(config.output_dir, "final.mp4")

    # 動画ファイルのパスを決定
    if config.auto_download:
        video_source_path = clip_video_path
    else:
        video_source_path = config.webm_path

    # ファイルの存在確認
    if not os.path.exists(video_source_path):
        print(f"✗ Video file not found: {video_source_path}")
        print("  Please run 'python main.py prepare' first")
        return False

    print(f"\nUsing files:")
    print(f"  Video: {video_source_path}")

    subtitle_path = None
    if os.path.exists(subs_clip_path_srt):
        try:
            needs_regen = (not os.path.exists(subs_clip_path_ass) or
                           os.path.getmtime(subs_clip_path_ass) < os.path.getmtime(subs_clip_path_srt))
            if needs_regen:
                print("  Updating styled subtitles from edited SRT...")
                convert_srt_to_ass(subs_clip_path_srt, subs_clip_path_ass)
        except Exception as e:
            print(f"  Warning: Failed to regenerate ASS from SRT: {e}")

    if os.path.exists(subs_clip_path_ass):
        subtitle_path = subs_clip_path_ass
        print(f"  Subtitles: {subs_clip_path_ass} (styled)")
    elif os.path.exists(subs_clip_path_srt):
        subtitle_path = subs_clip_path_srt
        print(f"  Subtitles: {subs_clip_path_srt}")
    else:
        print("  Subtitles: (none)")

    overlay_path = None
    if os.path.exists(chat_overlay_path):
        overlay_path = chat_overlay_path
        print(f"  Chat overlay: {chat_overlay_path}")
    else:
        print(f"  Chat overlay: (none)")

    # タイトルバー生成（TITLEが指定されている場合）
    title_overlay_path = None
    if config.title:
        print(f"\n[Generating title bar...]")
        try:
            success = generate_title_bar(
                config.title,
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

        success = compose_video(
            video_source_path,
            final_output_path,
            subtitle_path=subtitle_path,
            overlay_path=overlay_path,
            title_overlay_path=title_overlay_path,
            logo_path=logo_path
        )
        if not success:
            print("✗ Failed to compose video")
            return False
    except Exception as e:
        print(f"✗ Error in Step 5: {e}")
        return False

    print("\n" + "=" * 60)
    print("✓ Composition completed successfully!")
    print(f"  Final output: {final_output_path}")
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
    subs_full_path = os.path.join(config.temp_dir, "subs_full.srt")
    subs_clip_path = os.path.join(config.temp_dir, "subs_clip.srt")
    chat_full_path = os.path.join(config.temp_dir, "chat_full.json")
    chat_clip_path = os.path.join(config.temp_dir, "chat_clip.json")
    chat_overlay_path = os.path.join(config.temp_dir, "chat_overlay.ass")
    final_output_path = os.path.join(config.output_dir, "final.mp4")

    # 動画ファイルのパスを決定
    if config.auto_download:
        # 自動ダウンロードモード
        if 0 not in skip_steps:
            print("\n[Step 0] Downloading and clipping video from YouTube...")
            try:
                success = download_and_clip_video(
                    config.video_url,
                    config.start_time,
                    config.end_time,
                    clip_video_path,
                    download_full=False  # 範囲指定ダウンロードを試みる
                )
                if not success:
                    print("✗ Failed to download and clip video")
                    return False
                video_source_path = clip_video_path
            except Exception as e:
                print(f"✗ Error in Step 0: {e}")
                return False
        else:
            print("\n[Step 0] Skipped (assuming video already exists)")
            video_source_path = clip_video_path
    else:
        # 既存ファイルモード
        print("\n[Step 0] Using existing video file")
        if not config.webm_path:
            print("✗ WEBM_PATH is required when AUTO_DOWNLOAD=false")
            return False
        video_source_path = config.webm_path

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
                config.end_time
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


def run_single_step(step_num: int, args: argparse.Namespace) -> bool:
    """
    単一ステップを実行

    Args:
        step_num: ステップ番号
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

    elif step_num == 1:
        # Whisper字幕生成
        success = generate_subtitles_with_whisper(
            args.input,
            args.output,
            model_size=args.model if hasattr(args, 'model') else "large",
            language=args.language if hasattr(args, 'language') else "ja"
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
            args.end
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

    # 動画合成パイプライン
    compose_parser = subparsers.add_parser("compose", help="Compose final video using prepared materials")
    compose_parser.add_argument("config", help="Configuration file path")

    # フルパイプライン実行
    pipeline_parser = subparsers.add_parser("run", help="Run full pipeline (all steps including video composition)")
    pipeline_parser.add_argument("config", help="Configuration file path")
    pipeline_parser.add_argument(
        "--skip",
        nargs="+",
        type=int,
        help="Steps to skip (e.g., --skip 1 3)"
    )

    # サンプル設定ファイル作成
    sample_parser = subparsers.add_parser("init", help="Create sample config file")
    sample_parser.add_argument(
        "-o", "--output",
        default="config.txt",
        help="Output path for sample config (default: config.txt)"
    )

    # 個別ステップ実行用のサブコマンド
    # Step 0
    step0_parser = subparsers.add_parser("step0", help="Download and clip video")
    step0_parser.add_argument("url", help="YouTube video URL")
    step0_parser.add_argument("-s", "--start", required=True, help="Start time (hh:mm:ss)")
    step0_parser.add_argument("-e", "--end", help="End time (hh:mm:ss)")
    step0_parser.add_argument("-o", "--output", required=True, help="Output video file")
    step0_parser.add_argument("--full", action="store_true", help="Download full video first (slower but more reliable)")

    # Step 1 (Whisper字幕生成)
    step1_parser = subparsers.add_parser("step1", help="Generate subtitles with Whisper")
    step1_parser.add_argument("-i", "--input", required=True, help="Input video file")
    step1_parser.add_argument("-o", "--output", required=True, help="Output SRT file")
    step1_parser.add_argument("-m", "--model", default="large", choices=["tiny", "base", "small", "medium", "large"], help="Whisper model size (default: large)")
    step1_parser.add_argument("-l", "--language", default="ja", help="Language code (default: ja)")

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

        elif args.command == "compose":
            success = run_compose_pipeline(args.config)
            return 0 if success else 1

        elif args.command == "run":
            success = run_full_pipeline(args.config, args.skip or [])
            return 0 if success else 1

        elif args.command == "init":
            create_sample_config(args.output)
            return 0

        elif args.command.startswith("step"):
            step_num = int(args.command[4:])
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
