"""
ステップ1（Whisper版）: 音声認識による字幕生成

切り抜き済み動画からWhisperを使って音声認識を行い、
SRT形式の字幕ファイルを生成する。
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
import whisper


def extract_audio_from_video(video_path: str, audio_path: str) -> bool:
    """
    動画ファイルから音声を抽出

    Args:
        video_path: 動画ファイルのパス
        audio_path: 出力する音声ファイルのパス（.wav）

    Returns:
        bool: 抽出に成功したかどうか
    """
    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vn",  # 動画ストリームを無視
        "-acodec", "pcm_s16le",  # PCM 16-bit
        "-ar", "16000",  # 16kHz（Whisperの推奨サンプリングレート）
        "-ac", "1",  # モノラル
        "-y",  # 上書き
        audio_path
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"✓ Audio extracted: {audio_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to extract audio: {e.stderr}")
        return False


def format_timestamp_srt(seconds: float) -> str:
    """
    秒数をSRT形式のタイムスタンプに変換

    Args:
        seconds: 秒数

    Returns:
        SRT形式のタイムスタンプ（例: 00:01:23,456）
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def format_timestamp_ass(seconds: float) -> str:
    """
    秒数をASS形式のタイムスタンプに変換

    Args:
        seconds: 秒数

    Returns:
        ASS形式のタイムスタンプ（例: 0:01:23.45）
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"


def generate_srt_from_segments(segments: list, output_path: str) -> None:
    """
    WhisperのセグメントデータからSRTファイルを生成

    Args:
        segments: Whisperの文字起こし結果のセグメントリスト
        output_path: 出力するSRTファイルのパス
    """
    with open(output_path, "w", encoding="utf-8") as f:
        for i, segment in enumerate(segments, start=1):
            start_time = format_timestamp_srt(segment["start"])
            end_time = format_timestamp_srt(segment["end"])
            text = segment["text"].strip()

            f.write(f"{i}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{text}\n\n")


def generate_ass_from_segments(segments: list, output_path: str) -> None:
    """
    WhisperのセグメントデータからASS字幕ファイルを生成
    大きく太く見やすいスタイルで、画面下部やや上に配置

    Args:
        segments: Whisperの文字起こし結果のセグメントリスト
        output_path: 出力するASSファイルのパス
    """
    # ASSヘッダー
    header = """[Script Info]
Title: Whisper Subtitles
ScriptType: v4.00+
WrapStyle: 2
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Hiragino Sans,110,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,4,2,50,50,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)

        for segment in segments:
            start_time = format_timestamp_ass(segment["start"])
            end_time = format_timestamp_ass(segment["end"])
            text = segment["text"].strip()

            # エスケープ処理（先に実行）
            text_escaped = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

            # 長い文を自動改行（約20文字で改行）
            if len(text) > 20:
                # 文の中間あたりで改行（句読点を優先）
                mid = len(text) // 2
                # 句読点を探す
                break_chars = ['、', '。', 'が', 'て', 'で', 'し', 'を', 'は', 'の', 'と']
                best_pos = mid
                min_dist = len(text)

                for char in break_chars:
                    pos = text.find(char, max(0, mid - 10), min(len(text), mid + 10))
                    if pos != -1:
                        dist = abs(pos - mid)
                        if dist < min_dist:
                            min_dist = dist
                            best_pos = pos + 1

                # 改行を挿入（ASSの改行タグは\N）
                if best_pos > 0 and best_pos < len(text):
                    text_escaped = text_escaped[:best_pos] + "\\N" + text_escaped[best_pos:]

            f.write(f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{text_escaped}\n")


def generate_subtitles_with_whisper(
    video_path: str,
    output_path: str,
    model_size: str = "large",
    language: str = "ja",
    verbose: bool = True
) -> bool:
    """
    Whisperを使って動画から字幕を生成

    Args:
        video_path: 動画ファイルのパス
        output_path: 出力するSRTファイルのパス
        model_size: Whisperモデルのサイズ（"tiny", "base", "small", "medium", "large"）
        language: 言語コード（デフォルト: "ja"）
        verbose: 詳細な出力を表示するか

    Returns:
        bool: 字幕生成に成功したかどうか
    """
    if not os.path.exists(video_path):
        print(f"✗ Video file not found: {video_path}")
        return False

    # 出力ディレクトリを作成
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    # 一時的な音声ファイルを作成
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_audio:
        temp_audio_path = temp_audio.name

    try:
        # 動画から音声を抽出
        print(f"Extracting audio from video...")
        if not extract_audio_from_video(video_path, temp_audio_path):
            return False

        # Whisperモデルを読み込み
        print(f"Loading Whisper model: {model_size}")
        model = whisper.load_model(model_size)

        # 音声認識を実行
        print(f"Transcribing audio with Whisper (this may take a while)...")
        result = model.transcribe(
            temp_audio_path,
            language=language,
            verbose=verbose,
            fp16=False  # CPU環境でも動作するようにFP16を無効化
        )

        # SRTファイルを生成
        print(f"Generating SRT file...")
        generate_srt_from_segments(result["segments"], output_path)

        # ASSファイルも生成（スタイル付き字幕用）
        ass_output_path = output_path.replace(".srt", ".ass")
        print(f"Generating ASS file (styled subtitles)...")
        generate_ass_from_segments(result["segments"], ass_output_path)

        print(f"✓ Subtitles generated:")
        print(f"  SRT: {output_path}")
        print(f"  ASS: {ass_output_path}")
        print(f"  Detected language: {result.get('language', 'unknown')}")
        print(f"  Number of segments: {len(result['segments'])}")

        return True

    except Exception as e:
        print(f"✗ Failed to generate subtitles: {e}")
        return False

    finally:
        # 一時ファイルを削除
        if os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)


def generate_subtitles_with_whisper_direct(
    video_path: str,
    output_path: str,
    model_size: str = "large",
    language: str = "ja"
) -> bool:
    """
    Whisperを使って動画から直接字幕を生成（音声抽出なし）

    Args:
        video_path: 動画ファイルのパス
        output_path: 出力するSRTファイルのパス
        model_size: Whisperモデルのサイズ
        language: 言語コード

    Returns:
        bool: 字幕生成に成功したかどうか
    """
    if not os.path.exists(video_path):
        print(f"✗ Video file not found: {video_path}")
        return False

    # 出力ディレクトリを作成
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    try:
        # Whisperモデルを読み込み
        print(f"Loading Whisper model: {model_size}")
        model = whisper.load_model(model_size)

        # 音声認識を実行（動画ファイルを直接指定）
        print(f"Transcribing video with Whisper (this may take a while)...")
        result = model.transcribe(
            video_path,
            language=language,
            verbose=True,
            fp16=False
        )

        # SRTファイルを生成
        print(f"Generating SRT file...")
        generate_srt_from_segments(result["segments"], output_path)

        print(f"✓ Subtitles generated: {output_path}")
        print(f"  Detected language: {result.get('language', 'unknown')}")
        print(f"  Number of segments: {len(result['segments'])}")

        return True

    except Exception as e:
        print(f"✗ Failed to generate subtitles: {e}")
        return False
