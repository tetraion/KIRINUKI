"""
ステップ4: チャット区間抽出・整形

フルチャットから切り抜き区間に該当するチャットを抽出し、
切り抜き0秒基準に時間を調整する。
"""

import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

from kirinuki_processor.utils.time_utils import parse_time


@dataclass
class ChatMessage:
    """チャットメッセージ"""
    time_in_seconds: float  # 動画内での秒数
    author: str
    message: str
    timestamp: Optional[int] = None  # 元のタイムスタンプ（ミリ秒）

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return asdict(self)


def extract_chat_messages(
    messages: List[Dict[str, Any]],
    start_offset: float,
    end_time: Optional[float] = None,
    delay_seconds: float = 0.0
) -> List[ChatMessage]:
    """
    チャットメッセージから必要な区間を抽出し、時間を調整

    Args:
        messages: 元のチャットメッセージリスト（chat-downloader形式）
        start_offset: 開始オフセット（秒）。この時間を0秒とする
        end_time: 終了時刻（秒）。指定された場合、これ以降のメッセージを削除
        delay_seconds: チャット表示のオフセット（秒）。正の値でチャットを早く、負の値でチャットを遅く表示

    Returns:
        抽出・調整後のチャットメッセージリスト
    """
    extracted = []

    for msg in messages:
        # chat-downloaderの出力形式から必要な情報を抽出
        # time_in_seconds: 動画開始からの秒数
        # message: メッセージテキスト
        # author.name: 投稿者名

        # 時間情報を取得（time_in_seconds または time_text から）
        time_seconds = msg.get("time_in_seconds")
        if time_seconds is None:
            # time_textから取得を試みる（フォールバック）
            time_text = msg.get("time_text")
            if time_text:
                try:
                    time_seconds = parse_time(time_text)
                except Exception:
                    continue
            else:
                continue

        # 時間を調整（start_offsetで0秒基準にし、delay_secondsでずらす）
        # 正の値でチャットを早く、負の値でチャットを遅く表示
        adjusted_time = time_seconds - start_offset - delay_seconds

        # 範囲外のメッセージをスキップ
        if adjusted_time < 0:
            continue
        if end_time is not None and adjusted_time >= end_time:
            break

        # メッセージテキストを取得
        message_text = msg.get("message", "")
        if not message_text:
            continue

        # 投稿者名を取得
        author_name = "Unknown"
        if "author" in msg:
            author_info = msg["author"]
            if isinstance(author_info, dict):
                author_name = author_info.get("name", "Unknown")
            else:
                author_name = str(author_info)

        # タイムスタンプを取得（任意）
        timestamp = msg.get("timestamp")

        extracted.append(ChatMessage(
            time_in_seconds=adjusted_time,
            author=author_name,
            message=message_text,
            timestamp=timestamp
        ))

    return extracted


def deduplicate_messages(
    messages: List[ChatMessage],
    window_seconds: float = 0.0,
    by_author: bool = False
) -> List[ChatMessage]:
    """
    短時間に連投された同一コメントを除外する

    Args:
        messages: 調整済みチャットメッセージ
        window_seconds: この秒数以内に同じコメントがあればスキップ（0以下で無効）
        by_author: Trueなら投稿者も含めて比較
    """
    if window_seconds <= 0 or not messages:
        return messages

    last_seen: Dict[str, float] = {}
    filtered: List[ChatMessage] = []

    for msg in messages:
        key = (msg.message, msg.author) if by_author else msg.message
        last_time = last_seen.get(key)
        if last_time is not None and (msg.time_in_seconds - last_time) < window_seconds:
            continue
        last_seen[key] = msg.time_in_seconds
        filtered.append(msg)

    return filtered


def load_and_extract_chat(
    input_path: str,
    output_path: str,
    start_time: str,
    end_time: Optional[str] = None,
    delay_seconds: float = 0.0,
    dedup_window_seconds: float = 0.0,
    dedup_by_author: bool = False
) -> int:
    """
    チャットファイルを読み込み、区間抽出して保存

    Args:
        input_path: 入力チャットJSONファイルのパス
        output_path: 出力チャットJSONファイルのパス
        start_time: 切り抜き開始時刻（"hh:mm:ss" 形式）
        end_time: 切り抜き終了時刻（"hh:mm:ss" 形式、任意）
        delay_seconds: チャット表示のオフセット（秒）。正の値でチャットを早く、負の値でチャットを遅く表示

    Returns:
        抽出されたチャットメッセージの数

    Raises:
        FileNotFoundError: 入力ファイルが見つからない
        ValueError: 時間フォーマットが不正
    """
    # チャットファイルを読み込み
    messages = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
                messages.append(msg)
            except json.JSONDecodeError:
                continue

    if not messages:
        print(f"Warning: No chat messages found in {input_path}")
        return 0

    # 時間を秒数に変換
    start_offset = parse_time(start_time)
    # end_timeは動画全体のタイムスタンプなので、クリップ長に変換する
    end_offset = parse_time(end_time) - start_offset if end_time else None
    if end_offset is not None and end_offset < 0:
        # クリップ長が負になるのは不正なので無効化
        end_offset = None

    # 区間抽出
    extracted = extract_chat_messages(messages, start_offset, end_offset, delay_seconds)
    # 重複コメントの抑制
    extracted = deduplicate_messages(extracted, window_seconds=dedup_window_seconds, by_author=dedup_by_author)

    # JSON形式で保存（整形して読みやすく）
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(
            [msg.to_dict() for msg in extracted],
            f,
            ensure_ascii=False,
            indent=2
        )

    print(f"✓ Extracted {len(extracted)} chat messages")
    print(f"  Input: {input_path}")
    print(f"  Output: {output_path}")
    print(f"  Start offset: {start_time} ({start_offset}s)")
    if end_time:
        print(f"  End time: {end_time} ({end_offset}s)")
    if delay_seconds != 0:
        print(f"  Chat delay: {delay_seconds}s")
    if dedup_window_seconds > 0:
        mode = "author+message" if dedup_by_author else "message"
        print(f"  Dedup: {dedup_window_seconds}s window ({mode})")

    return len(extracted)


def filter_messages(
    messages: List[ChatMessage],
    min_length: int = 1,
    max_length: Optional[int] = None,
    exclude_authors: Optional[List[str]] = None
) -> List[ChatMessage]:
    """
    チャットメッセージをフィルタリング

    Args:
        messages: チャットメッセージリスト
        min_length: 最小文字数
        max_length: 最大文字数（任意）
        exclude_authors: 除外する投稿者名のリスト（任意）

    Returns:
        フィルタリング後のメッセージリスト
    """
    filtered = []

    for msg in messages:
        # 文字数チェック
        msg_len = len(msg.message)
        if msg_len < min_length:
            continue
        if max_length is not None and msg_len > max_length:
            continue

        # 投稿者チェック
        if exclude_authors and msg.author in exclude_authors:
            continue

        filtered.append(msg)

    return filtered
