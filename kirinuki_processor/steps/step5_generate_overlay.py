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
    chat_area_width: int = 500
    chat_area_x: int = 1350  # 右側に余裕を持たせた位置
    chat_area_y_start: int = 400  # 下部から開始（最も下）
    chat_area_y_spacing: int = 70  # 各コメント間の間隔

    # フォント設定
    font_name: str = "Hiragino Sans"
    font_size: int = 55  # 字幕（110px）の50%

    # 色設定（ASS形式: &HAABBGGRR）
    text_color: str = "&H00FFFFFF"  # 白
    outline_color: str = "&H00000000"  # 黒アウトライン
    background_color: str = "&H80000000"  # 半透明黒背景

    # 表示設定
    max_visible_messages: int = 7  # 同時に表示する最大メッセージ数

    # スタイル設定
    outline_width: int = 3
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


def create_slot_based_chat_event(
    message: str,
    start_time: float,
    end_time: float,
    config: OverlayConfig,
    slot: int,
    transition_time: Optional[float] = None
) -> str:
    """
    スロットベースのチャットイベントを生成

    Args:
        message: メッセージテキスト
        start_time: 開始時刻（秒）
        end_time: 終了時刻（秒）
        config: オーバーレイ設定
        slot: 表示スロット（0=最下部、上に向かって増える）
        transition_time: スロット移動のアニメーション時間（秒）、Noneの場合は移動なし

    Returns:
        ASSイベント文字列
    """
    start_str = ass_time_format(start_time)
    end_str = ass_time_format(end_time)

    # Y座標を計算（slot 0が最下部）
    y_position = config.chat_area_y_start + (slot * config.chat_area_y_spacing)
    x_pos = config.chat_area_x

    # エスケープ処理
    message_escaped = message.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

    # 固定位置で表示
    event = f"Dialogue: 0,{start_str},{end_str},ChatMessage,,0,0,0,,{{\\pos({x_pos},{y_position})}}{message_escaped}\n"

    return event


def generate_chat_overlay(
    chat_messages: List[Dict[str, Any]],
    output_path: str,
    config: Optional[OverlayConfig] = None
) -> int:
    """
    チャットメッセージからASSオーバーレイファイルを生成

    常に最大7件（max_visible_messages）のコメントを表示。
    新しいコメントが最下部（slot 0）に追加され、既存のコメントが一気に上（slot 1, 2, ...）にスライド。

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
    slide_duration = 0.3  # スライドアニメーションの時間（秒）

    # 各メッセージが2行かどうかを事前に判定
    # 55pxフォントで570px幅 → 約12文字が1行の限界
    is_two_line = []
    for msg in chat_messages:
        message_text = msg.get("message", "")
        is_two_line.append(len(message_text) > 12)

    # ASSファイルを生成
    with open(output_path, "w", encoding="utf-8") as f:
        # ヘッダーを書き込み
        f.write(generate_ass_header(config))

        # 各メッセージに対してイベントを生成
        for i, msg in enumerate(chat_messages):
            message_text = msg.get("message", "")
            time_seconds = msg.get("time_in_seconds", 0.0)

            # このメッセージが表示される全期間
            # 最大max_visible件後の新しいメッセージが来たら消える
            end_index = i + max_visible
            if end_index < len(chat_messages):
                end_time = chat_messages[end_index].get("time_in_seconds", time_seconds + 5.0)
            else:
                # 最後のメッセージは5秒表示
                end_time = time_seconds + 5.0

            # このメッセージのライフサイクル: 新しいコメントが来るたびにスロットを上げる（上に移動）
            for j in range(i, min(i + max_visible, len(chat_messages))):
                slot = j - i  # 0, 1, 2, ... (0=最下部)

                # この区間の開始時刻と終了時刻
                segment_start = chat_messages[j].get("time_in_seconds", 0.0)

                # slot 6（最上部）に到達したら、次のメッセージが来た瞬間に消える
                if slot == max_visible - 1 and j + 1 < len(chat_messages):
                    # 7件目は次のメッセージが来る瞬間に即座に消える
                    segment_end = chat_messages[j + 1].get("time_in_seconds", 0.0)
                elif j + 1 < len(chat_messages):
                    # 通常の場合
                    next_msg_time = chat_messages[j + 1].get("time_in_seconds", 0.0)
                    segment_end = min(next_msg_time, end_time)
                else:
                    segment_end = end_time

                if segment_end <= segment_start:
                    continue

                # Y座標を計算（slot 0が最下部、上に向かって減少）
                # 2行コメントの累積高さを考慮
                y_offset = 0
                for k in range(i, i + slot):
                    if k < len(is_two_line) and is_two_line[k]:
                        y_offset += config.chat_area_y_spacing * 2  # 2行コメントは2倍の高さ
                    else:
                        y_offset += config.chat_area_y_spacing

                y_position = config.chat_area_y_start - y_offset
                x_pos = config.chat_area_x

                # エスケープ処理
                message_escaped = message_text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

                # 長いコメントを2行に分割（約12文字以上）
                if len(message_text) > 12:
                    # 最初の12文字以内で改行位置を探す（句読点や助詞を優先）
                    break_chars = ['、', '。', 'が', 'て', 'で', 'し', 'を', 'は', 'の', 'と', ' ']
                    best_pos = 6  # デフォルトは半分

                    # 6〜12文字の範囲で改行文字を探す（後ろから優先）
                    for pos in range(min(12, len(message_text)), 5, -1):
                        if pos < len(message_text) and message_text[pos-1] in break_chars:
                            best_pos = pos
                            break

                    # 改行文字が見つからなければ12文字で強制分割
                    if best_pos < 6:
                        best_pos = min(12, len(message_text) // 2)

                    # 改行を挿入（ASSの改行タグは\N）
                    if best_pos > 0 and best_pos < len(message_text):
                        message_escaped = message_escaped[:best_pos] + "\\N" + message_escaped[best_pos:]

                start_str = ass_time_format(segment_start)
                end_str = ass_time_format(segment_end)

                # 次のメッセージが来る瞬間にスライドアニメーション（上に移動）
                if j + 1 < len(chat_messages):
                    # 次のスロット位置（上に移動）
                    # slot 6の場合は画面外に移動（さらに上）
                    next_slot = slot + 1
                    # 次の位置も2行コメントを考慮して計算
                    y_next_offset = 0
                    for k in range(i, i + next_slot):
                        if k < len(is_two_line) and is_two_line[k]:
                            y_next_offset += config.chat_area_y_spacing * 2  # 2行コメントは2倍の高さ
                        else:
                            y_next_offset += config.chat_area_y_spacing
                    y_next = config.chat_area_y_start - y_next_offset

                    # 通常のスライドアニメーション
                    # スライドアニメーションの開始時刻（次のメッセージの少し前）
                    slide_start = max(segment_start, segment_end - slide_duration)

                    if slide_start > segment_start:
                        # 静止区間
                        event = f"Dialogue: 0,{start_str},{ass_time_format(slide_start)},ChatMessage,,0,0,0,,{{\\pos({x_pos},{y_position})}}{message_escaped}\n"
                        f.write(event)

                        # スライド区間（上に移動）
                        # slot 6の場合はフェードアウト効果を追加
                        if slot == max_visible - 1:
                            # フェードアウト時間をミリ秒で計算
                            fade_duration_ms = int(slide_duration * 1000)
                            event = f"Dialogue: 0,{ass_time_format(slide_start)},{end_str},ChatMessage,,0,0,0,,{{\\move({x_pos},{y_position},{x_pos},{y_next})\\fad(0,{fade_duration_ms})}}{message_escaped}\n"
                        else:
                            event = f"Dialogue: 0,{ass_time_format(slide_start)},{end_str},ChatMessage,,0,0,0,,{{\\move({x_pos},{y_position},{x_pos},{y_next})}}{message_escaped}\n"
                        f.write(event)
                    else:
                        # 全体がスライド
                        # slot 6の場合はフェードアウト効果を追加
                        if slot == max_visible - 1:
                            fade_duration_ms = int((segment_end - segment_start) * 1000)
                            event = f"Dialogue: 0,{start_str},{end_str},ChatMessage,,0,0,0,,{{\\move({x_pos},{y_position},{x_pos},{y_next})\\fad(0,{fade_duration_ms})}}{message_escaped}\n"
                        else:
                            event = f"Dialogue: 0,{start_str},{end_str},ChatMessage,,0,0,0,,{{\\move({x_pos},{y_position},{x_pos},{y_next})}}{message_escaped}\n"
                        f.write(event)
                else:
                    # 最後の区間（次のメッセージがない場合）は静止のみ
                    event = f"Dialogue: 0,{start_str},{end_str},ChatMessage,,0,0,0,,{{\\pos({x_pos},{y_position})}}{message_escaped}\n"
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
