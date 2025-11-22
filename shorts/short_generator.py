#!/usr/bin/env python3
"""
ショート動画生成モジュール - final.mp4から時間指定で切り出して縦型動画を生成
"""

import os
import subprocess
from pathlib import Path
from typing import Dict, Optional


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


def escape_drawtext_text(text: str) -> str:
    """
    drawtextフィルター用に文字列をエスケープ
    """
    replacements = {
        '\\': r'\\\\',
        ':': r'\:',
        "'": r"\'",
        '%': r'\%',
        '[': r'\[',
        ']': r'\]'
    }
    escaped = text
    for original, replacement in replacements.items():
        escaped = escaped.replace(original, replacement)
    return escaped


def escape_filter_expr(expr: str) -> str:
    """
    FFmpegフィルター式で区切り文字になり得る記号をエスケープ
    """
    replacements = {
        '\\': r'\\\\',
        ':': r'\:',
        ',': r'\,'
    }
    escaped = expr
    for original, replacement in replacements.items():
        escaped = escaped.replace(original, replacement)
    return escaped


def build_drawtext_filter(
    text: str,
    y_expr: str,
    font: str,
    fontsize: int,
    color: str,
    box: bool,
    box_color: str,
    box_border: int,
    text_align: str = "center"
) -> str:
    """
    drawtextフィルター文字列を構築
    """
    parts = [
        f"text='{escape_drawtext_text(text)}'",
        "x=(w-text_w)/2",
        f"y={escape_filter_expr(y_expr)}",
        f"fontsize={fontsize}",
        f"fontcolor={color}",
        f"text_align={text_align}"
    ]

    if font:
        # パスが存在する場合はfontfileとして扱う
        font_path = Path(font)
        if font_path.exists():
            parts.append(f"fontfile='{escape_drawtext_text(str(font_path))}'")
        else:
            parts.append(f"font='{escape_drawtext_text(font)}'")

    if box:
        parts.append("box=1")
        parts.append(f"boxcolor={box_color}")
        parts.append(f"boxborderw={box_border}")

    return "drawtext=" + ":".join(parts)


def generate_short_video(
    input_video: str,
    output_video: str,
    start_time: str,
    end_time: str,
    overlay_settings: Optional[Dict[str, object]] = None
) -> bool:
    """
    final.mp4から時間指定で切り出して縦型ショート動画を生成

    処理内容：
    1. 指定時間で動画を切り出し
    2. 1080x1920の黒背景キャンバスを作成
    3. 元動画を中央に配置（アスペクト比維持）
    4. オプションで上下の余白にテキストを描画

    Args:
        input_video: 入力動画ファイルのパス（final.mp4）
        output_video: 出力動画ファイルのパス
        start_time: 開始時刻（hh:mm:ss）
        end_time: 終了時刻（hh:mm:ss）
        overlay_settings: 上下テキストやスタイル設定

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

        # フィルターチェーンを準備
        filters = [
            f'scale=1080:{scaled_height}',
            f'pad=1080:1920:0:{pad_top}:black'
        ]

        overlay_settings = overlay_settings or {}

        # 上部テキスト
        top_text = overlay_settings.get('top_text')
        if top_text:
            if pad_top > 0:
                top_y = f"max(20,({pad_top}-text_h)/2)"
            else:
                top_y = "20"
            top_offset = int(overlay_settings.get('top_offset_y', 0))
            if top_offset:
                top_y = f"({top_y})-({top_offset})"
            top_lines = overlay_settings.get('top_lines') or str(top_text).split('\n')
            top_line_colors = overlay_settings.get('top_line_colors', {})
            line_spacing = max(6, int(int(overlay_settings.get('top_fontsize', 72)) * 0.15))
            box_border = int(overlay_settings.get('top_box_border', 24))
            line_height = int(overlay_settings.get('top_fontsize', 72)) + line_spacing + (box_border * 2)
            total_offset = ((len(top_lines) - 1) * line_height) / 2 if top_lines else 0
            for idx, line_text in enumerate(top_lines):
                line_color = top_line_colors.get(idx + 1, str(overlay_settings.get('top_color', 'white')))
                line_y_expr = top_y
                if len(top_lines) > 1:
                    shift = -total_offset + idx * line_height
                    if shift:
                        line_y_expr = f"({top_y})+({shift})"
                if not line_text:
                    continue
                filters.append(
                    build_drawtext_filter(
                        text=str(line_text),
                        y_expr=line_y_expr,
                        font=str(overlay_settings.get('top_font') or ''),
                        fontsize=int(overlay_settings.get('top_fontsize', 72)),
                        color=line_color,
                        box=bool(overlay_settings.get('top_box', True)),
                        box_color=str(overlay_settings.get('top_box_color', 'black@0.6')),
                        box_border=box_border,
                        text_align="center"
                    )
                )

        # 下部テキスト
        bottom_text = overlay_settings.get('bottom_text')
        if bottom_text:
            if pad_bottom > 0:
                base_y = 1920 - pad_bottom
                bottom_y = f"{base_y}+max(20,({pad_bottom}-text_h)/2)"
            else:
                bottom_y = "h-text_h-20"
            bottom_offset = int(overlay_settings.get('bottom_offset_y', 0))
            if bottom_offset:
                bottom_y = f"({bottom_y})-({bottom_offset})"

            bottom_lines = overlay_settings.get('bottom_lines') or str(bottom_text).split('\n')
            bottom_line_colors = overlay_settings.get('bottom_line_colors', {})
            bottom_fontsize = int(overlay_settings.get('bottom_fontsize', 64))
            bottom_line_spacing = max(6, int(bottom_fontsize * 0.15))
            bottom_box_border = int(overlay_settings.get('bottom_box_border', 24))
            bottom_line_height = bottom_fontsize + bottom_line_spacing + (bottom_box_border * 2)
            bottom_total_offset = ((len(bottom_lines) - 1) * bottom_line_height) / 2 if bottom_lines else 0

            for idx, line_text in enumerate(bottom_lines):
                line_color = bottom_line_colors.get(idx + 1, str(overlay_settings.get('bottom_color', 'white')))
                line_y_expr = bottom_y
                if len(bottom_lines) > 1:
                    shift = -bottom_total_offset + idx * bottom_line_height
                    if shift:
                        line_y_expr = f"({bottom_y})+({shift})"
                if not line_text:
                    continue
                filters.append(
                    build_drawtext_filter(
                        text=str(line_text),
                        y_expr=line_y_expr,
                        font=str(overlay_settings.get('bottom_font') or ''),
                        fontsize=bottom_fontsize,
                        color=line_color,
                        box=bool(overlay_settings.get('bottom_box', True)),
                        box_color=str(overlay_settings.get('bottom_box_color', 'black@0.6')),
                        box_border=bottom_box_border,
                        text_align="center"
                    )
                )

        filter_chain = ",".join(filters)

        # FFmpegで時間切り出し + スケール + パディング + テキスト描画
        cmd = [
            'ffmpeg', '-y',
            '-ss', start_time,
            '-to', end_time,
            '-i', input_video,
            '-vf', filter_chain,
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
