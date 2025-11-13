"""時間変換ユーティリティ"""
from datetime import timedelta
from typing import Union


def parse_time(time_str: str) -> float:
    """
    時間文字列（hh:mm:ss）を秒数（float）に変換

    Args:
        time_str: "hh:mm:ss" または "mm:ss" 形式の時間文字列

    Returns:
        秒数（float）

    Examples:
        >>> parse_time("01:23:45")
        5025.0
        >>> parse_time("23:45")
        1425.0
    """
    parts = time_str.strip().split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    elif len(parts) == 2:
        minutes, seconds = parts
        return float(minutes) * 60 + float(seconds)
    else:
        raise ValueError(f"Invalid time format: {time_str}")


def format_time(seconds: float, include_ms: bool = True) -> str:
    """
    秒数を時間文字列に変換

    Args:
        seconds: 秒数
        include_ms: ミリ秒を含めるかどうか

    Returns:
        "hh:mm:ss" または "hh:mm:ss.mmm" 形式の文字列

    Examples:
        >>> format_time(5025.5)
        '01:23:45.500'
        >>> format_time(5025.5, include_ms=False)
        '01:23:45'
    """
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if include_ms:
        ms = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"
    else:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def srt_time_format(seconds: float) -> str:
    """
    SRT字幕フォーマット用の時間文字列を生成

    Args:
        seconds: 秒数

    Returns:
        "hh:mm:ss,mmm" 形式の文字列（SRT形式ではカンマ使用）

    Examples:
        >>> srt_time_format(5025.5)
        '01:23:45,500'
    """
    time_str = format_time(seconds, include_ms=True)
    return time_str.replace(".", ",")


def ass_time_format(seconds: float) -> str:
    """
    ASS字幕フォーマット用の時間文字列を生成

    Args:
        seconds: 秒数

    Returns:
        "h:mm:ss.cc" 形式の文字列（ASSは1/100秒単位）

    Examples:
        >>> ass_time_format(5025.5)
        '1:23:45.50'
    """
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    centisecs = int((seconds - int(seconds)) * 100)

    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"
