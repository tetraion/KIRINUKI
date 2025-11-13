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
from kirinuki_processor.steps.step1_fetch_subtitles import fetch_subtitles
from kirinuki_processor.steps.step2_rebase_subtitles import rebase_subtitle_file
from kirinuki_processor.steps.step3_fetch_chat import fetch_chat
from kirinuki_processor.steps.step4_extract_chat import load_and_extract_chat
from kirinuki_processor.steps.step5_generate_overlay import (
    generate_overlay_from_file,
    OverlayConfig
)
from kirinuki_processor.steps.step6_compose_video import compose_video


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

    # ステップ1: 字幕取得
    if 1 not in skip_steps:
        print("\n[Step 1] Fetching subtitles from YouTube...")
        try:
            success = fetch_subtitles(config.video_url, subs_full_path)
            if not success:
                print("  Note: Subtitles not available, will proceed without them")
                subs_full_path = None
        except Exception as e:
            print(f"✗ Error in Step 1: {e}")
            subs_full_path = None
    else:
        print("\n[Step 1] Skipped")

    # ステップ2: 字幕リベース
    if 2 not in skip_steps and subs_full_path and os.path.exists(subs_full_path):
        print("\n[Step 2] Rebasing subtitles...")
        try:
            count = rebase_subtitle_file(
                subs_full_path,
                subs_clip_path,
                config.start_time,
                config.end_time
            )
            if count == 0:
                subs_clip_path = None
        except Exception as e:
            print(f"✗ Error in Step 2: {e}")
            subs_clip_path = None
    else:
        print("\n[Step 2] Skipped (no subtitles available)")
        subs_clip_path = None

    # ステップ3: チャット取得
    if 3 not in skip_steps:
        print("\n[Step 3] Fetching live chat from YouTube...")
        try:
            success = fetch_chat(config.video_url, chat_full_path)
            if not success:
                print("  Note: Chat replay not available, will proceed without it")
                chat_full_path = None
        except Exception as e:
            print(f"✗ Error in Step 3: {e}")
            chat_full_path = None
    else:
        print("\n[Step 3] Skipped")

    # ステップ4: チャット抽出
    if 4 not in skip_steps and chat_full_path and os.path.exists(chat_full_path):
        print("\n[Step 4] Extracting chat messages for clip...")
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
            print(f"✗ Error in Step 4: {e}")
            chat_clip_path = None
    else:
        print("\n[Step 4] Skipped (no chat available)")
        chat_clip_path = None

    # ステップ5: オーバーレイ生成
    if 5 not in skip_steps and chat_clip_path and os.path.exists(chat_clip_path):
        print("\n[Step 5] Generating chat overlay (ASS)...")
        try:
            overlay_config = OverlayConfig()
            count = generate_overlay_from_file(
                chat_clip_path,
                chat_overlay_path,
                overlay_config,
                scroll_mode=False  # 固定位置モード
            )
            if count == 0:
                chat_overlay_path = None
        except Exception as e:
            print(f"✗ Error in Step 5: {e}")
            chat_overlay_path = None
    else:
        print("\n[Step 5] Skipped (no chat available)")
        chat_overlay_path = None

    # ステップ6: 動画合成
    if 6 not in skip_steps:
        print("\n[Step 6] Composing final video...")
        try:
            success = compose_video(
                video_source_path,
                final_output_path,
                subtitle_path=subs_clip_path if subs_clip_path and os.path.exists(subs_clip_path) else None,
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
        # 字幕取得
        success = fetch_subtitles(args.url, args.output)
        return success

    elif step_num == 2:
        # 字幕リベース
        count = rebase_subtitle_file(
            args.input,
            args.output,
            args.start,
            args.end
        )
        return count > 0

    elif step_num == 3:
        # チャット取得
        success = fetch_chat(args.url, args.output)
        return success

    elif step_num == 4:
        # チャット抽出
        count = load_and_extract_chat(
            args.input,
            args.output,
            args.start,
            args.end
        )
        return count > 0

    elif step_num == 5:
        # オーバーレイ生成
        config = OverlayConfig()
        count = generate_overlay_from_file(
            args.input,
            args.output,
            config,
            scroll_mode=args.scroll if hasattr(args, 'scroll') else False
        )
        return count > 0

    elif step_num == 6:
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

    # フルパイプライン実行
    pipeline_parser = subparsers.add_parser("run", help="Run full pipeline")
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

    # Step 1
    step1_parser = subparsers.add_parser("step1", help="Fetch subtitles")
    step1_parser.add_argument("url", help="YouTube video URL")
    step1_parser.add_argument("-o", "--output", required=True, help="Output SRT file")

    # Step 2
    step2_parser = subparsers.add_parser("step2", help="Rebase subtitles")
    step2_parser.add_argument("-i", "--input", required=True, help="Input SRT file")
    step2_parser.add_argument("-o", "--output", required=True, help="Output SRT file")
    step2_parser.add_argument("-s", "--start", required=True, help="Start time (hh:mm:ss)")
    step2_parser.add_argument("-e", "--end", help="End time (hh:mm:ss)")

    # Step 3
    step3_parser = subparsers.add_parser("step3", help="Fetch live chat")
    step3_parser.add_argument("url", help="YouTube video URL")
    step3_parser.add_argument("-o", "--output", required=True, help="Output JSON file")

    # Step 4
    step4_parser = subparsers.add_parser("step4", help="Extract chat")
    step4_parser.add_argument("-i", "--input", required=True, help="Input JSON file")
    step4_parser.add_argument("-o", "--output", required=True, help="Output JSON file")
    step4_parser.add_argument("-s", "--start", required=True, help="Start time (hh:mm:ss)")
    step4_parser.add_argument("-e", "--end", help="End time (hh:mm:ss)")

    # Step 5
    step5_parser = subparsers.add_parser("step5", help="Generate overlay")
    step5_parser.add_argument("-i", "--input", required=True, help="Input JSON file")
    step5_parser.add_argument("-o", "--output", required=True, help="Output ASS file")
    step5_parser.add_argument("--scroll", action="store_true", help="Use scroll mode")

    # Step 6
    step6_parser = subparsers.add_parser("step6", help="Compose video")
    step6_parser.add_argument("-v", "--video", required=True, help="Input video file")
    step6_parser.add_argument("-o", "--output", required=True, help="Output video file")
    step6_parser.add_argument("-s", "--subtitle", help="Subtitle file (SRT)")
    step6_parser.add_argument("-c", "--overlay", help="Chat overlay file (ASS)")

    args = parser.parse_args()

    # コマンドが指定されていない場合
    if not args.command:
        parser.print_help()
        return 1

    # コマンド実行
    try:
        if args.command == "run":
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
