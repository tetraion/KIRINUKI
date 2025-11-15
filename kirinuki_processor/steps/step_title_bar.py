"""
タイトルバー生成

動画の上部にスライドインアニメーション付きのタイトルバーを生成する。
"""

from typing import Optional
from kirinuki_processor.utils.time_utils import ass_time_format


def generate_title_bar(
    title: str,
    output_path: str,
    video_width: int = 1920,
    video_height: int = 1080,
    slide_duration: float = 1.2,
    display_duration: float = None,  # Noneの場合は動画終了まで表示
    channel_name: str = "ひろゆき視点",  # チャンネル名
    logo_height: int = 180  # ロゴの高さ（step6_compose_video.pyと同期）
) -> bool:
    """
    タイトルバーのASS字幕ファイルを生成

    Args:
        title: タイトルテキスト
        output_path: 出力先パス（.ass）
        video_width: 動画の幅
        video_height: 動画の高さ
        slide_duration: スライドインアニメーションの時間（秒）
        display_duration: タイトルバーの表示時間（秒、Noneの場合は動画終了まで表示）

    Returns:
        bool: 生成に成功したかどうか
    """
    # タイトルバーの設定
    bar_height = 120
    bar_y_position = 10  # ロゴの頂点に合わせる

    # フォント設定
    font_name = "Hiragino Sans"
    # チャンネル名はより視認性の高い太字フォントとする
    channel_font_name = "Hiragino Sans W9"
    font_size = 90  # 65→90に拡大

    # 色設定（ASS形式: &HAABBGGRR、BGRの順）
    text_color = "&H00000000"  # 黒（黄色背景に対して）
    outline_color = "&H00FFFFFF"  # 白アウトライン
    channel_outline_color = "&H00404040"  # チャンネル名は濃いめの縁取りで視認性アップ
    # 黄色 RGB(255, 229, 0) → BGR(0, 229, 255) = 00E5FF
    bar_bg_color = "&H0000E5FF"  # 黄色（完全不透明、AA=00）
    # 青色 RGB(0, 120, 215) → BGR(215, 120, 0) = D77800
    channel_bg_color = "&H00D77800"  # 青色（完全不透明、AA=00）

    # タイトルバーの開始・終了位置（左から右にスライド）
    start_y = bar_y_position  # Y位置は固定
    end_y = bar_y_position  # Y位置は固定

    # ロゴの中心位置
    logo_x = 15
    logo_center_x = logo_x + 180 // 2  # 105px

    # タイムスタンプ
    slide_start = 0.0
    slide_end = slide_duration
    # 表示終了時刻（Noneの場合は9:59:59.99 = 実質無限）
    total_end = display_duration + slide_duration if display_duration else 9*3600 + 59*60 + 59.99

    # ASSヘッダー
    header = f"""[Script Info]
Title: Title Bar
ScriptType: v4.00+
WrapStyle: 0
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: TitleText,{font_name},{font_size},{text_color},&H000000FF,{outline_color},&H00000000,-1,0,0,0,100,100,0,0,1,5,3,7,30,30,0,1
Style: TitleBar,Arial,20,{bar_bg_color},&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1
Style: ChannelName,{channel_font_name},48,&H00FFFFFF,&H000000FF,{channel_outline_color},&H00000000,-1,0,0,0,100,100,0,0,1,4,2,7,30,30,0,1
Style: ChannelBg,Arial,20,{channel_bg_color},&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # タイトルテキストのエスケープ処理
    title_escaped = title.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

    # タイトルバーの背景（矩形）をロゴ中心から右端まで描画
    # 背景の幅: ロゴ中心から画面右端まで
    bar_bg_width = video_width - logo_center_x
    drawing = f"m 0 0 l {bar_bg_width} 0 l {bar_bg_width} {bar_height} l 0 {bar_height}"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)

        # Layer 0: タイトルバー背景（スライドインアニメーション：左から右）
        # クリップを使って右に伸びていく効果
        # 初期状態: ロゴ中心から1px（ほぼ見えない）
        # 終了状態: 画面右端まで表示
        f.write(f"Dialogue: 0,{ass_time_format(slide_start)},{ass_time_format(slide_end)},TitleBar,,0,0,0,,{{\\pos({logo_center_x},{start_y})\\clip({logo_center_x},{bar_y_position},{logo_center_x + 1},{bar_y_position + bar_height})\\t(0,{int(slide_duration*1000)},\\clip({logo_center_x},{bar_y_position},{video_width},{bar_y_position + bar_height}))\\p1}}{drawing}\\N\n")
        # 背景（静止）
        f.write(f"Dialogue: 0,{ass_time_format(slide_end)},{ass_time_format(total_end)},TitleBar,,0,0,0,,{{\\pos({logo_center_x},{end_y})\\p1}}{drawing}\\N\n")

        # Layer 1: タイトルテキスト
        # テキストの中央配置（Y座標はバーの中央）
        text_y = bar_y_position + bar_height // 2

        # タイトルテキスト（スライドインアニメーション：左から右）
        text_end_x = 210  # 最終位置（ロゴX15px + 幅180px + マージン15px）

        # タイトル文字の概算幅
        title_text_width = len(title) * font_size

        # スライドイン中（左揃えで表示、左から右に移動）
        # 初期状態: ロゴ中心から1pxのクリップ（ほぼ見えない）
        # 終了状態: ロゴ中心から文字全体が見える範囲までクリップ
        f.write(f"Dialogue: 1,{ass_time_format(slide_start)},{ass_time_format(slide_end)},TitleText,,0,0,0,,{{\\an4\\pos({text_end_x},{text_y})\\clip({logo_center_x},{bar_y_position},{logo_center_x + 1},{bar_y_position + bar_height})\\t(0,{int(slide_duration*1000)},\\clip({logo_center_x},{bar_y_position},{text_end_x + title_text_width},{bar_y_position + bar_height}))}}{title_escaped}\\N\n")

        # 静止中（左揃えで表示）
        f.write(f"Dialogue: 1,{ass_time_format(slide_end)},{ass_time_format(total_end)},TitleText,,0,0,0,,{{\\an4\\pos({text_end_x},{text_y})}}{title_escaped}\\N\n")

        # Layer 2: チャンネル名背景と文字（タイトルバー下、ロゴとの差分空間に表示）
        # タイトルバー下端: bar_y_position + bar_height = 10 + 120 = 130
        # ロゴ下端: bar_y_position + logo_height = 10 + 180 = 190
        # チャンネル名のY位置: タイトルバー下端とロゴ下端の中間
        channel_area_height = logo_height - bar_height  # 60px
        channel_y_top = bar_y_position + bar_height  # 130
        channel_y = channel_y_top + channel_area_height // 2  # 160

        # チャンネル名の背景矩形（ロゴ中心から文字の終わりまで）
        # 文字幅を概算：「ひろゆきのつぶやき」= 10文字 × 45px ≈ 450px
        channel_text_width = len(channel_name) * 45
        channel_bg_x_start = logo_center_x  # ロゴの中心から開始
        channel_bg_x_end = text_end_x + channel_text_width + 30  # 文字の終わり + マージン
        channel_bg_width = channel_bg_x_end - channel_bg_x_start

        # 背景矩形の描画（相対座標で描画）
        channel_bg_drawing = f"m 0 0 l {channel_bg_width} 0 l {channel_bg_width} {channel_area_height} l 0 {channel_area_height}"

        # チャンネル名背景（スライドインアニメーション：左から右、Y位置固定）
        # クリップを使って右に伸びていく効果
        # 初期状態: ロゴ中心から1px（ほぼ見えない）
        # 終了状態: 背景の右端まで表示
        f.write(f"Dialogue: 2,{ass_time_format(slide_start)},{ass_time_format(slide_end)},ChannelBg,,0,0,0,,{{\\pos({channel_bg_x_start},{channel_y_top})\\clip({logo_center_x},{channel_y_top},{logo_center_x + 1},{channel_y_top + channel_area_height})\\t(0,{int(slide_duration*1000)},\\clip({logo_center_x},{channel_y_top},{channel_bg_x_end},{channel_y_top + channel_area_height}))\\p1}}{channel_bg_drawing}\\N\n")
        # 背景（静止）
        f.write(f"Dialogue: 2,{ass_time_format(slide_end)},{ass_time_format(total_end)},ChannelBg,,0,0,0,,{{\\pos({channel_bg_x_start},{channel_y_top})\\p1}}{channel_bg_drawing}\\N\n")

        # チャンネル名のエスケープ処理
        channel_escaped = channel_name.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")

        # チャンネル名テキスト（スライドイン中、左揃えで表示、左から右に移動）
        # 初期状態: ロゴ中心から1pxのクリップ（ほぼ見えない）
        # 終了状態: ロゴ中心から文字全体が見える範囲までクリップ
        channel_font_size = 45
        channel_full_width = len(channel_name) * channel_font_size
        f.write(f"Dialogue: 3,{ass_time_format(slide_start)},{ass_time_format(slide_end)},ChannelName,,0,0,0,,{{\\an4\\pos({text_end_x},{channel_y})\\clip({logo_center_x},{channel_y_top},{logo_center_x + 1},{channel_y_top + channel_area_height})\\t(0,{int(slide_duration*1000)},\\clip({logo_center_x},{channel_y_top},{text_end_x + channel_full_width},{channel_y_top + channel_area_height}))}}{channel_escaped}\\N\n")

        # 静止中（左揃えで表示）
        f.write(f"Dialogue: 3,{ass_time_format(slide_end)},{ass_time_format(total_end)},ChannelName,,0,0,0,,{{\\an4\\pos({text_end_x},{channel_y})}}{channel_escaped}\\N\n")

    print(f"✓ Generated title bar ASS file")
    print(f"  Title: {title}")
    print(f"  Output: {output_path}")
    print(f"  Slide duration: {slide_duration}s")
    print(f"  Display duration: {display_duration}s")

    return True
