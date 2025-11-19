#!/usr/bin/env python3
"""
ショート動画生成モジュール - final.mp4から時間指定で切り出して縦型動画を生成
"""

import os
import subprocess
from pathlib import Path


def parse_time_to_seconds(time_str: str) -> float:
    """
    時刻文字列を秒数に変換

    Args:
        time_str: 時刻文字列（hh:mm:ss または mm:ss または ss）

    Returns:
        秒数
    """
    parts = time_str.split(':')
    if len(parts) == 3:
        h, m, s = map(float, parts)
        return h * 3600 + m * 60 + s
    elif len(parts) == 2:
        m, s = map(float, parts)
        return m * 60 + s
    else:
        return float(parts[0])


def generate_short_video(
    input_video: str,
    output_video: str,
    start_time: str,
    end_time: str
) -> bool:
    """
    final.mp4から時間指定で切り出して縦型ショート動画を生成

    処理内容：
    1. 指定時間で動画を切り出し
    2. 1080x1920の黒背景キャンバスを作成
    3. 元動画を中央に配置（アスペクト比維持）
    4. 上下の余白は黒背景のまま（後でコメントを入れる予定）

    Args:
        input_video: 入力動画ファイルのパス（final.mp4）
        output_video: 出力動画ファイルのパス
        start_time: 開始時刻（hh:mm:ss）
        end_time: 終了時刻（hh:mm:ss）

    Returns:
        成功した場合True
    """
    try:
        # 動画の解像度を取得
        cmd_probe = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=p=0',
            input_video
        ]
        result = subprocess.run(cmd_probe, capture_output=True, text=True, check=True)
        width, height = map(int, result.stdout.strip().split(','))

        print("=" * 60)
        print("Short Video Generator")
        print("=" * 60)
        print(f"\nInput: {input_video}")
        print(f"  Size: {width}x{height}")
        print(f"Output: {output_video}")
        print(f"  Size: 1080x1920 (vertical)")
        print(f"Time range: {start_time} - {end_time}")

        # 元動画を1080x1920キャンバスの中央に配置するためのscaleとpad
        # scaleで1080幅に収め、アスペクト比を維持
        # padで上下に黒背景を追加して1920の高さにする

        # 1080幅に収めた時の高さを計算
        scaled_height = int(1080 * height / width)

        # 上下のパディングを計算
        pad_top = (1920 - scaled_height) // 2
        pad_bottom = 1920 - scaled_height - pad_top

        print(f"\nProcessing:")
        print(f"  1. Extract time range: {start_time} - {end_time}")
        print(f"  2. Scale to: 1080x{scaled_height} (maintain aspect ratio)")
        print(f"  3. Add padding: top={pad_top}px, bottom={pad_bottom}px")
        print(f"  4. Final size: 1080x1920")

        # FFmpegで時間切り出し + スケール + パディング
        cmd = [
            'ffmpeg', '-y',
            '-ss', start_time,
            '-to', end_time,
            '-i', input_video,
            '-vf', f'scale=1080:{scaled_height},pad=1080:1920:0:{pad_top}:black',
            '-c:v', 'libx264',
            '-preset', 'medium',
            '-crf', '23',
            '-c:a', 'aac',
            '-b:a', '128k',
            output_video
        ]

        print(f"\nGenerating short video...")
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print(f"✗ FFmpeg error: {result.stderr}")
            return False

        print(f"✓ Short video generated: {output_video}")
        print("\n" + "=" * 60)
        print("✓ Short video generation completed!")
        print("=" * 60)

        return True

    except subprocess.CalledProcessError as e:
        print(f"✗ FFmpeg error: {e.stderr}")
        return False
    except Exception as e:
        print(f"✗ Error generating short video: {e}")
        import traceback
        traceback.print_exc()
        return False
