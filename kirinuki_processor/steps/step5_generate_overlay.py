"""
ステップ5: チャットオーバーレイ（ASS）生成

チャットメッセージをニコニコ動画風に右→左へ流れる
ASS字幕ファイルとして生成する。
"""

import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from kirinuki_processor.utils.time_utils import ass_time_format
from kirinuki_processor.constants import (
    CHAT_LANE_COUNT,
    CHAT_LANE_TOP,
    CHAT_LANE_SPACING,
    CHAT_LANE_GAP,
    CHAT_COMMENT_SPEED,
    CHAT_HORIZONTAL_MARGIN,
    CHAT_MIN_COMMENT_WIDTH,
    CHAT_FONT_NAME,
    CHAT_FONT_SIZE,
    CHAT_OUTLINE_WIDTH
)


@dataclass
class OverlayConfig:
    """オーバーレイ表示設定"""
    # 動画解像度
    video_width: int = 1920
    video_height: int = 1080

    # ニコ動風の横スクロールコメント設定
    lane_count: int = CHAT_LANE_COUNT
    lane_top: int = CHAT_LANE_TOP
    lane_spacing: int = CHAT_LANE_SPACING
    lane_gap: float = CHAT_LANE_GAP

    # タイムオフセット
    visible_start_offset: float = 5.0  # 切り抜き冒頭から表示

    # 移動パラメータ
    comment_speed: float = CHAT_COMMENT_SPEED
    horizontal_margin: int = CHAT_HORIZONTAL_MARGIN
    min_comment_width: int = CHAT_MIN_COMMENT_WIDTH

    # フォント設定
    font_name: str = CHAT_FONT_NAME
    font_size: int = CHAT_FONT_SIZE

    # 色設定（ASS形式: &HAABBGGRR）
    text_color: str = "&H00FFFFFF"  # 白
    outline_color: str = "&H00000000"  # 黒アウトライン
    background_color: str = "&H80000000"  # 半透明黒背景

    # 表示設定
    max_visible_messages: int = 7  # 互換用（未使用）

    # スタイル設定
    outline_width: int = CHAT_OUTLINE_WIDTH
    shadow_depth: int = 2
    margin_v: int = 10  # 垂直マージン
    margin_r: int = 20  # 右マージン


def generate_ass_header(config: OverlayConfig) -> str:
    """
    ASSファイルのヘッダーを生成

    Args:
        config: オーバーレイ設定

    Returns:
        ASSヘッダー文字列
    """
    header = f"""[Script Info]
Title: Chat Overlay
ScriptType: v4.00+
WrapStyle: 0
PlayResX: {config.video_width}
PlayResY: {config.video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: ChatMessage,{config.font_name},{config.font_size},{config.text_color},&H000000FF,{config.outline_color},{config.background_color},0,0,0,0,100,100,0,0,1,{config.outline_width},{config.shadow_depth},7,10,{config.margin_r},{config.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return header


def estimate_text_width(text: str, font_size: int, min_width: int) -> float:
    """
    字数からおおよその表示幅(px)を推定

    Hiragino Sansは概ね等幅0.55〜0.6em程度なので、簡易的に0.6を係数として使用する。
    """
    approx_width = len(text) * font_size * 0.6
    return max(min_width, approx_width)


def generate_chat_overlay(
    chat_messages: List[Dict[str, Any]],
    output_path: str,
    config: Optional[OverlayConfig] = None
) -> int:
    """
    チャットメッセージからニコニコ動画風の横スクロールASSを生成

    Args:
        chat_messages: チャットメッセージのリスト
        output_path: 出力先パス（.ass）
        config: オーバーレイ設定（Noneの場合はデフォルト）

    Returns:
        生成されたイベント数
    """
    if config is None:
        config = OverlayConfig()

    start_x = config.video_width + config.horizontal_margin
    lane_available_times = [0.0 for _ in range(config.lane_count)]
    event_count = 0

    with open(output_path, "w", encoding="utf-8") as f:
        # ヘッダーを書き込み
        f.write(generate_ass_header(config))

        # 各メッセージを横スクロールで描画
        for msg in chat_messages:
            message_text = (msg.get("message") or "").strip()
            if not message_text:
                continue

            base_time = float(msg.get("time_in_seconds", 0.0))
            if base_time < config.visible_start_offset:
                continue
            text_escaped = message_text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

            text_width = estimate_text_width(
                message_text,
                config.font_size,
                config.min_comment_width
            )
            end_x = -text_width
            travel_distance = start_x - end_x
            duration = travel_distance / config.comment_speed

            # 使用するレーンを決定（最も早く空くものを選択）
            best_lane = 0
            best_start = float("inf")
            for lane_idx in range(config.lane_count):
                # lane_available_times は「先行コメントの頭出しから、自身の幅分進むまで + gap」の時刻
                candidate_start = max(base_time, lane_available_times[lane_idx])
                if candidate_start < best_start:
                    best_start = candidate_start
                    best_lane = lane_idx

            start_time = best_start
            end_time = start_time + duration
            # 次のコメントが同じレーンを使えるのは、現在のコメントが自分の幅を移動した後
            lane_available_times[best_lane] = start_time + (text_width / config.comment_speed) + config.lane_gap

            y_position = config.lane_top + (config.lane_spacing * best_lane)
            start_str = ass_time_format(start_time)
            end_str = ass_time_format(end_time)

            event = (
                f"Dialogue: 0,{start_str},{end_str},ChatMessage,,0,0,0,,"
                f"{{\\move({start_x},{y_position},{end_x},{y_position})}}{text_escaped}\n"
            )
            f.write(event)
            event_count += 1

    print(f"✓ Generated ASS overlay with {event_count} chat messages")
    print(f"  Output: {output_path}")
    print(f"  Mode: Nico-style horizontal scroll ({config.lane_count} lanes)")

    return event_count


def generate_overlay_from_file(
    chat_json_path: str,
    output_path: str,
    config: Optional[OverlayConfig] = None
) -> int:
    """
    チャットJSONファイルからASSオーバーレイを生成

    Args:
        chat_json_path: チャットJSONファイルのパス
        output_path: 出力先パス（.ass）
        config: オーバーレイ設定

    Returns:
        生成されたイベント数
    """
    # JSONファイルを読み込み
    with open(chat_json_path, "r", encoding="utf-8") as f:
        chat_messages = json.load(f)

    # ASSファイルを生成
    return generate_chat_overlay(chat_messages, output_path, config)
