"""
KIRINUKI Processor 共通定数

アプリケーション全体で使用される定数を一元管理
"""

# ============================================================================
# 動画エンコード設定
# ============================================================================

# VP9エンコード品質 (Constant Rate Factor)
# 値が小さいほど高品質（0-63、推奨: 23-33）
DEFAULT_CROP_CRF = 30

# VP9ビットレート設定（0はVBRモード、CRFを優先）
DEFAULT_CROP_BITRATE = 0

# 動画長さ取得失敗時のフォールバック値（秒）
DEFAULT_VIDEO_DURATION_FALLBACK = 90


# ============================================================================
# タイトルバー設定
# ============================================================================

# タイトルバーの高さ（ピクセル）
TITLE_BAR_HEIGHT = 120

# タイトルバーの上部マージン（ピクセル）
TITLE_BAR_MARGIN_TOP = 10

# タイトルバーのY座標（画面上端からの距離）
TITLE_BAR_Y_POSITION = TITLE_BAR_MARGIN_TOP

# タイトルバーの背景色（ASS形式: &HAABBGGRR）
# 黄色 RGB(255, 229, 0) → BGR(0, 229, 255) = 0000E5FF
TITLE_BAR_BG_COLOR = "&H0000E5FF"  # 黄色

# タイトルバーのフォントサイズ
TITLE_BAR_FONT_SIZE = 90

# タイトルバーのフォント名
TITLE_BAR_FONT_NAME = "Hiragino Sans"

# タイトルバーのスライドアニメーション時間（秒）
TITLE_BAR_SLIDE_DURATION = 1.2


# ============================================================================
# ロゴ設定
# ============================================================================

# ロゴの高さ（ピクセル）
LOGO_HEIGHT = 180

# ロゴのY座標（タイトルバー内の上部からの距離）
LOGO_Y_OFFSET = 10

# ロゴのX座標（左端からの距離）
LOGO_X_OFFSET = 15

# ロゴのアニメーション時間（秒、タイトルバーと同期）
LOGO_ANIMATION_DURATION = TITLE_BAR_SLIDE_DURATION


# ============================================================================
# チャットオーバーレイ設定
# ============================================================================

# ニコニコ動画風コメントのレーン数
CHAT_LANE_COUNT = 10

# コメント表示開始Y座標（タイトルバーと被らない位置）
CHAT_LANE_TOP = TITLE_BAR_MARGIN_TOP + TITLE_BAR_HEIGHT + 130

# 各レーンの縦間隔（ピクセル）
CHAT_LANE_SPACING = 60

# 同じレーンに再利用する際の余白時間（秒）
CHAT_LANE_GAP = 1.0

# コメントの移動速度（ピクセル/秒）
CHAT_COMMENT_SPEED = 380.0

# 画面右端からのコメント開始オフセット（ピクセル）
CHAT_HORIZONTAL_MARGIN = 80

# コメント幅の最低値（ピクセル）
CHAT_MIN_COMMENT_WIDTH = 320

# コメントのフォント名
CHAT_FONT_NAME = "Hiragino Sans"

# コメントのフォントサイズ
CHAT_FONT_SIZE = 60

# コメントの縁取り幅
CHAT_OUTLINE_WIDTH = 3


# ============================================================================
# 字幕設定
# ============================================================================

# 字幕のフォント名
SUBTITLE_FONT_NAME = "Hiragino Sans"

# 字幕のフォントサイズ
SUBTITLE_FONT_SIZE = 110

# 強調版フォントサイズ
SUBTITLE_BOLD_FONT_SIZE = 130

# 字幕の縁取り幅
SUBTITLE_OUTLINE_WIDTH = 7

# 強調版の縁取り幅
SUBTITLE_BOLD_OUTLINE_WIDTH = 10

# 字幕の影のオフセット
SUBTITLE_SHADOW_OFFSET = 4

# 強調版の影のオフセット
SUBTITLE_BOLD_SHADOW_OFFSET = 5

# 字幕の下部マージン（ピクセル）
SUBTITLE_BOTTOM_MARGIN = 40

# 強調版の下部マージン（ピクセル）
SUBTITLE_BOLD_BOTTOM_MARGIN = SUBTITLE_BOTTOM_MARGIN

# 強調版の縁取り色（紺色、AABBGGRR形式）
SUBTITLE_BOLD_OUTLINE_COLOR = "&H005C2A0F"

# 字幕の自動改行閾値（文字数）
SUBTITLE_LINE_BREAK_THRESHOLD = 20


# ============================================================================
# デフォルトディレクトリ
# ============================================================================

DEFAULT_OUTPUT_DIR = "data/output"
DEFAULT_TEMP_DIR = "data/temp"
DEFAULT_INPUT_DIR = "data/input"
