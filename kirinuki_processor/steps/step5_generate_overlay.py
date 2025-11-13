"""
ステップ5: チャットオーバーレイ（ASS）生成

チャットメッセージをライブチャット風に下から上に流れる
ASS字幕ファイルとして生成する。
"""

import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from kirinuki_processor.utils.time_utils import ass_time_format


@dataclass
class OverlayConfig:
    """オーバーレイ表示設定"""
    # 動画解像度
    video_width: int = 1920
    video_height: int = 1080

    # チャット表示エリア（右側）
    chat_area_width: int = 400
    chat_area_x: int = 1520  # 右端から400pxの位置
    chat_area_y_start: int = 1000  # 下部から開始
    chat_area_y_end: int = 100  # 上部で終了

    # フォント設定
    font_name: str = "Arial"
    font_size: int = 24
    author_font_size: int = 20

    # 色設定（ASS形式: &HAABBGGRR）
    text_color: str = "&H00FFFFFF"  # 白
    author_color: str = "&H0099CCFF"  # オレンジっぽい色
    outline_color: str = "&H00000000"  # 黒アウトライン
    background_color: str = "&H80000000"  # 半透明黒背景

    # 表示時間設定
    message_display_duration: float = 8.0  # メッセージ表示時間（秒）
    scroll_duration: float = 8.0  # スクロール時間（秒）

    # スタイル設定
    outline_width: int = 2
    shadow_depth: int = 1
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
Style: ChatAuthor,{config.font_name},{config.author_font_size},{config.author_color},&H000000FF,{config.outline_color},{config.background_color},1,0,0,0,100,100,0,0,1,{config.outline_width},{config.shadow_depth},7,10,{config.margin_r},{config.margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return header


def create_scrolling_chat_event(
    message: str,
    author: str,
    start_time: float,
    config: OverlayConfig,
    slot: int = 0
) -> str:
    """
    スクロール型チャットイベントを生成

    Args:
        message: メッセージテキスト
        author: 投稿者名
        start_time: 開始時刻（秒）
        config: オーバーレイ設定
        slot: 表示スロット（0-N、同時に表示される位置）

    Returns:
        ASSイベント文字列
    """
    end_time = start_time + config.message_display_duration

    # Y座標を計算（下から上にスクロール）
    # スロットに応じて開始Y位置を調整
    y_start = config.chat_area_y_start - (slot * 80)
    y_end = config.chat_area_y_end - (slot * 80)

    # ASS形式の時間文字列
    start_str = ass_time_format(start_time)
    end_str = ass_time_format(end_time)

    # 移動アニメーション（\move）を使用
    # フォーマット: \move(x1,y1,x2,y2,t1,t2)
    x_pos = config.chat_area_x

    # エスケープ処理
    message_escaped = message.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    author_escaped = author.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

    # チャット形式: 投稿者名 + メッセージ
    # 改行で投稿者とメッセージを分ける
    chat_text = f"{{\\c{config.author_color[2:]}}}{author_escaped}{{\\c}}: {message_escaped}"

    # 移動アニメーション付きイベント
    event = f"Dialogue: 0,{start_str},{end_str},ChatMessage,,0,0,0,,{{\\pos({x_pos},{y_start})\\fad(200,200)}}{chat_text}\n"

    return event


def create_static_chat_event(
    message: str,
    author: str,
    start_time: float,
    config: OverlayConfig,
    y_position: int
) -> str:
    """
    固定位置チャットイベントを生成（スクロールなし）

    Args:
        message: メッセージテキスト
        author: 投稿者名
        start_time: 開始時刻（秒）
        config: オーバーレイ設定
        y_position: Y座標

    Returns:
        ASSイベント文字列
    """
    end_time = start_time + config.message_display_duration

    start_str = ass_time_format(start_time)
    end_str = ass_time_format(end_time)

    x_pos = config.chat_area_x

    # エスケープ処理
    message_escaped = message.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    author_escaped = author.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

    # チャット形式
    chat_text = f"{{\\c{config.author_color[2:]}}}{author_escaped}{{\\c}}: {message_escaped}"

    # フェードイン・フェードアウト付き
    event = f"Dialogue: 0,{start_str},{end_str},ChatMessage,,0,0,0,,{{\\pos({x_pos},{y_position})\\fad(200,200)}}{chat_text}\n"

    return event


def generate_chat_overlay(
    chat_messages: List[Dict[str, Any]],
    output_path: str,
    config: Optional[OverlayConfig] = None,
    scroll_mode: bool = False
) -> int:
    """
    チャットメッセージからASSオーバーレイファイルを生成

    Args:
        chat_messages: チャットメッセージのリスト
        output_path: 出力先パス（.ass）
        config: オーバーレイ設定（Noneの場合はデフォルト）
        scroll_mode: スクロールモードを使用するか（False=固定位置）

    Returns:
        生成されたイベント数
    """
    if config is None:
        config = OverlayConfig()

    # ASSファイルを生成
    with open(output_path, "w", encoding="utf-8") as f:
        # ヘッダーを書き込み
        f.write(generate_ass_header(config))

        # チャットイベントを書き込み
        slot = 0
        max_slots = 10  # 同時に表示する最大メッセージ数

        for i, msg in enumerate(chat_messages):
            message_text = msg.get("message", "")
            author = msg.get("author", "Unknown")
            time_seconds = msg.get("time_in_seconds", 0.0)

            if scroll_mode:
                # スクロールモード
                event = create_scrolling_chat_event(
                    message_text,
                    author,
                    time_seconds,
                    config,
                    slot
                )
                slot = (slot + 1) % max_slots
            else:
                # 固定位置モード（ライブチャット風）
                # Y位置を時間ベースで決定（新しいメッセージが下に表示される）
                y_position = config.chat_area_y_start - ((i % max_slots) * 60)
                event = create_static_chat_event(
                    message_text,
                    author,
                    time_seconds,
                    config,
                    y_position
                )

            f.write(event)

    event_count = len(chat_messages)
    print(f"✓ Generated ASS overlay with {event_count} chat events")
    print(f"  Output: {output_path}")
    print(f"  Mode: {'Scrolling' if scroll_mode else 'Static'}")

    return event_count


def generate_overlay_from_file(
    chat_json_path: str,
    output_path: str,
    config: Optional[OverlayConfig] = None,
    scroll_mode: bool = False
) -> int:
    """
    チャットJSONファイルからASSオーバーレイを生成

    Args:
        chat_json_path: チャットJSONファイルのパス
        output_path: 出力先パス（.ass）
        config: オーバーレイ設定
        scroll_mode: スクロールモードを使用するか

    Returns:
        生成されたイベント数
    """
    # JSONファイルを読み込み
    with open(chat_json_path, "r", encoding="utf-8") as f:
        chat_messages = json.load(f)

    # ASSファイルを生成
    return generate_chat_overlay(chat_messages, output_path, config, scroll_mode)
