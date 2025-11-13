"""
ステップ2: 字幕のリベース（時間合わせ）

フル字幕を切り抜き区間に合わせて調整する:
1. STARTを0秒基準に変換
2. END以降の字幕を削除（ENDが指定されている場合）
3. 調整後の字幕をSRT形式で保存
"""

import re
from typing import List, Optional, Tuple
from dataclasses import dataclass

from kirinuki_processor.utils.time_utils import parse_time, srt_time_format


@dataclass
class SubtitleEntry:
    """字幕エントリ"""
    index: int
    start_time: float  # 秒数
    end_time: float  # 秒数
    text: str

    def to_srt(self) -> str:
        """SRT形式の文字列に変換"""
        start_str = srt_time_format(self.start_time)
        end_str = srt_time_format(self.end_time)
        return f"{self.index}\n{start_str} --> {end_str}\n{self.text}\n"


def parse_srt_file(srt_path: str) -> List[SubtitleEntry]:
    """
    SRTファイルを読み込んでパースする

    Args:
        srt_path: SRTファイルのパス

    Returns:
        字幕エントリのリスト
    """
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read()

    # SRTエントリを正規表現で抽出
    # SRT形式:
    # 1
    # 00:00:01,000 --> 00:00:03,000
    # テキスト
    pattern = r"(\d+)\s*\n(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})\s*\n((?:.*\n?)+?)(?=\n\d+\s*\n|\Z)"

    entries = []
    for match in re.finditer(pattern, content, re.MULTILINE):
        index = int(match.group(1))
        start_str = match.group(2).replace(",", ".")  # カンマをドットに変換
        end_str = match.group(3).replace(",", ".")
        text = match.group(4).strip()

        # 時間を秒数に変換
        start_time = parse_time(start_str)
        end_time = parse_time(end_str)

        entries.append(SubtitleEntry(
            index=index,
            start_time=start_time,
            end_time=end_time,
            text=text
        ))

    return entries


def rebase_subtitles(
    entries: List[SubtitleEntry],
    start_offset: float,
    end_time: Optional[float] = None
) -> List[SubtitleEntry]:
    """
    字幕エントリの時間をリベース（調整）する

    Args:
        entries: 元の字幕エントリリスト
        start_offset: 開始オフセット（秒）。この時間を0秒とする
        end_time: 終了時刻（秒）。指定された場合、これ以降のエントリを削除

    Returns:
        調整後の字幕エントリリスト
    """
    rebased_entries = []
    new_index = 1

    for entry in entries:
        # 時間を調整
        new_start = entry.start_time - start_offset
        new_end = entry.end_time - start_offset

        # 開始時刻がマイナスの場合はスキップ
        if new_end < 0:
            continue

        # 終了時刻を超える場合は処理を終了
        if end_time is not None and new_start >= end_time:
            break

        # 開始時刻がマイナスの場合は0に調整
        if new_start < 0:
            new_start = 0

        # 終了時刻が指定範囲を超える場合は切り詰め
        if end_time is not None and new_end > end_time:
            new_end = end_time

        rebased_entries.append(SubtitleEntry(
            index=new_index,
            start_time=new_start,
            end_time=new_end,
            text=entry.text
        ))
        new_index += 1

    return rebased_entries


def save_srt_file(entries: List[SubtitleEntry], output_path: str) -> None:
    """
    字幕エントリをSRTファイルとして保存

    Args:
        entries: 字幕エントリのリスト
        output_path: 出力先パス
    """
    with open(output_path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(entry.to_srt())
            f.write("\n")


def rebase_subtitle_file(
    input_path: str,
    output_path: str,
    start_time: str,
    end_time: Optional[str] = None
) -> int:
    """
    字幕ファイルをリベースして保存

    Args:
        input_path: 入力SRTファイルのパス
        output_path: 出力SRTファイルのパス
        start_time: 切り抜き開始時刻（"hh:mm:ss" 形式）
        end_time: 切り抜き終了時刻（"hh:mm:ss" 形式、任意）

    Returns:
        処理した字幕エントリの数

    Raises:
        FileNotFoundError: 入力ファイルが見つからない
        ValueError: 時間フォーマットが不正
    """
    # SRTファイルを読み込み
    entries = parse_srt_file(input_path)

    if not entries:
        print(f"Warning: No subtitle entries found in {input_path}")
        return 0

    # 時間を秒数に変換
    start_offset = parse_time(start_time)
    end_offset = parse_time(end_time) if end_time else None

    # リベース処理
    rebased_entries = rebase_subtitles(entries, start_offset, end_offset)

    # 保存
    save_srt_file(rebased_entries, output_path)

    print(f"✓ Rebased {len(rebased_entries)} subtitle entries")
    print(f"  Input: {input_path}")
    print(f"  Output: {output_path}")
    print(f"  Start offset: {start_time} ({start_offset}s)")
    if end_time:
        print(f"  End time: {end_time} ({end_offset}s)")

    return len(rebased_entries)
