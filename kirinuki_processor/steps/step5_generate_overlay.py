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
    chat_area_y_start: int = 950  # 下部から開始
    chat_area_y_spacing: int = 70  # 各コメント間の間隔

    # フォント設定
    font_name: str = "Arial"
    font_size: int = 22

    # 色設定（ASS形式: &HAABBGGRR）
    text_color: str = "&H00FFFFFF"  # 白
    outline_color: str = "&H00000000"  # 黒アウトライン
    background_color: str = "&H80000000"  # 半透明黒背景

    # 表示設定
    max_visible_messages: int = 7  # 同時に表示する最大メッセージ数

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

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    return header


def create_slot_based_chat_event(
    message: str,
    start_time: float,
    end_time: float,
    config: OverlayConfig,
    slot: int
) -> str:
    """
    スロットベースのチャットイベントを生成

    Args:
        message: メッセージテキスト
        start_time: 開始時刻（秒）
        end_time: 終了時刻（秒）
        config: オーバーレイ設定
        slot: 表示スロット（0=最下部、max_visible_messages-1=最上部）

    Returns:
        ASSイベント文字列
    """
    start_str = ass_time_format(start_time)
    end_str = ass_time_format(end_time)

    # Y座標を計算（slot 0が最下部）
    y_position = config.chat_area_y_start - (slot * config.chat_area_y_spacing)
    x_pos = config.chat_area_x

    # エスケープ処理
    message_escaped = message.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

    # フェードイン・フェードアウト付き（短めの200ms）
    event = f"Dialogue: 0,{start_str},{end_str},ChatMessage,,0,0,0,,{{\\pos({x_pos},{y_position})\\fad(200,200)}}{message_escaped}\n"

    return event


def generate_chat_overlay(
    chat_messages: List[Dict[str, Any]],
    output_path: str,
    config: Optional[OverlayConfig] = None
) -> int:
    """
    チャットメッセージからASSオーバーレイファイルを生成

    常に最大7件（max_visible_messages）のコメントを表示。
    新しいコメントが追加されると、古いコメントが消える仕組み。

    Args:
        chat_messages: チャットメッセージのリスト
        output_path: 出力先パス（.ass）
        config: オーバーレイ設定（Noneの場合はデフォルト）

    Returns:
        生成されたイベント数
    """
    if config is None:
        config = OverlayConfig()

    max_visible = config.max_visible_messages

    # ASSファイルを生成
    with open(output_path, "w", encoding="utf-8") as f:
        # ヘッダーを書き込み
        f.write(generate_ass_header(config))

        # 各メッセージに対してスロットベースのイベントを生成
        for i, msg in enumerate(chat_messages):
            message_text = msg.get("message", "")
            time_seconds = msg.get("time_in_seconds", 0.0)

            # 次のメッセージが来るまで、または動画の最後まで表示
            if i + 1 < len(chat_messages):
                next_time = chat_messages[i + 1].get("time_in_seconds", time_seconds + 5.0)
            else:
                # 最後のメッセージは5秒表示
                next_time = time_seconds + 5.0

            # このメッセージが表示されるスロットを決定
            # 新しいメッセージは常にslot 0（最下部）に追加
            # 古いメッセージは上にシフトしていく
            slot = 0

            # このメッセージの表示開始時刻
            start_time = time_seconds

            # 終了時刻：次のメッセージが来るまで、または最大max_visible件目まで表示
            # max_visible件後の新しいメッセージが来たら消える
            end_index = i + max_visible
            if end_index < len(chat_messages):
                end_time = chat_messages[end_index].get("time_in_seconds", next_time)
            else:
                end_time = next_time

            # スロットを決定（このメッセージより後に来たメッセージの数）
            # i番目のメッセージは、i+1, i+2, ... のメッセージが来ると上にシフト
            for j in range(i + 1, min(i + max_visible, len(chat_messages))):
                msg_j_time = chat_messages[j].get("time_in_seconds", 0.0)

                # j番目のメッセージが表示されている間、i番目のメッセージのスロット
                slot_j = j - i

                # j番目のメッセージの表示開始時刻
                start_j = msg_j_time

                # j番目のメッセージの次のメッセージ、または終了時刻
                if j + 1 < len(chat_messages):
                    end_j = chat_messages[j + 1].get("time_in_seconds", msg_j_time + 5.0)
                else:
                    end_j = msg_j_time + 5.0

                # この区間でi番目のメッセージをslot_jに表示
                event = create_slot_based_chat_event(
                    message_text,
                    max(start_time, start_j),
                    min(end_time, end_j),
                    config,
                    slot_j
                )
                f.write(event)

            # i番目のメッセージが最初に表示される区間（slot 0）
            first_end = chat_messages[i + 1].get("time_in_seconds", next_time) if i + 1 < len(chat_messages) else next_time
            event = create_slot_based_chat_event(
                message_text,
                start_time,
                min(end_time, first_end),
                config,
                0
            )
            f.write(event)

    event_count = len(chat_messages)
    print(f"✓ Generated ASS overlay with {event_count} chat messages")
    print(f"  Output: {output_path}")
    print(f"  Max visible: {max_visible} messages at a time")

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
