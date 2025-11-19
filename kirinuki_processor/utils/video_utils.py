"""
動画関連のユーティリティ関数

FFmpegを使用した動画情報取得、解像度取得などの共通処理を提供
"""

import subprocess
from typing import Optional


def get_video_duration(video_path: str) -> float:
    """
    動画の長さを取得（秒）

    Args:
        video_path: 動画ファイルのパス

    Returns:
        動画の長さ（秒）。エラー時は0.0を返す

    Raises:
        FileNotFoundError: 動画ファイルが存在しない場合
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        print(f"Warning: FFprobe error for {video_path}: {e.stderr}")
        return 0.0
    except FileNotFoundError:
        print(f"Warning: Video file not found: {video_path}")
        return 0.0
    except ValueError as e:
        print(f"Warning: Invalid duration value for {video_path}: {e}")
        return 0.0


def get_video_resolution(video_path: str) -> Optional[tuple]:
    """
    動画の解像度を取得

    Args:
        video_path: 動画ファイルのパス

    Returns:
        (width, height)のタプル。エラー時はNone

    Raises:
        FileNotFoundError: 動画ファイルが存在しない場合
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=p=0',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        width, height = map(int, result.stdout.strip().split(','))
        return (width, height)
    except subprocess.CalledProcessError as e:
        print(f"Warning: FFprobe error for {video_path}: {e.stderr}")
        return None
    except (ValueError, FileNotFoundError) as e:
        print(f"Warning: Failed to get resolution for {video_path}: {e}")
        return None


def get_video_info(video_path: str) -> dict:
    """
    動画の詳細情報を取得

    Args:
        video_path: 動画ファイルのパス

    Returns:
        動画情報の辞書（width, height, duration, fps など）
        エラー時は空の辞書
    """
    info = {}

    # 解像度取得
    resolution = get_video_resolution(video_path)
    if resolution:
        info['width'], info['height'] = resolution

    # 長さ取得
    duration = get_video_duration(video_path)
    if duration > 0:
        info['duration'] = duration

    return info
