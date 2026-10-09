import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BITGET_API_KEY", "")
API_SECRET = os.getenv("BITGET_API_SECRET", "")
API_PASSWORD = os.getenv("BITGET_API_PASSWORD", "")
PAPER_TRADING = os.getenv("PAPER_TRADING", "True").lower() == "true"

SYMBOL = "XAU/USDT:USDT"
LOT_SIZE = 0.01

# =========================================================================
# HİBRİT BOT (ASYA/GÜNDÜZ FİLTRESİZ, AKŞAM FİLTRELİ)
# =========================================================================
REALISTIC_MARKET_MODE = True  # Market/Taker emir eşleşmesi (Makas dahil)
LATENCY_SEC = 0.10            # 100 ms ağ gecikmesi
MAX_SPREAD = 0.32             # Makas 0.32$'dan açıksa girmez

USE_EARLY_LOCK = True         # Aşama 1 Erken Kâr Kilidi Aktif (%65+ Win Rate motoru)

# HİBRİT SİSTEM İÇİN DİNAMİK FİLTRELER
# (Trend ve Tape Flow filtresi sadece akşam seansında aktif olacak şekilde ayarlandı)
NIGHT_USE_TREND_FILTER = True # Akşam seansı için trend filtresi
NIGHT_USE_TAPE_FLOW = True    # Akşam seansı için tape flow filtresi
TAPE_FLOW_RATIO = 0.55

# =========================================================================
# VİTES 0: GECE UYKU MODU (00:00 - 04:00)
# =========================================================================
TRADING_START_HOUR = 4

# =========================================================================
# VİTES 1: SABAH ASYA TREND (04:00 - 09:00) -> FİLTRESİZ ŞAMPİYON
# =========================================================================
ASIAN_END_HOUR = 9
ASIAN_SL_DIFF = 0.55          # Stop-Loss (0.55$)
ASIAN_EARLY_ACT = 0.50        # +0.50$ kâr görünce...
ASIAN_EARLY_LOCK = 0.20       # ...Stopu +0.20$ kâra (+$0.14 Net) kilitler!
ASIAN_TRAILING_ACT = 0.85     # +0.85$'da ana Trailing başlar
ASIAN_TRAILING_DIST = 0.30    # 0.30$ mesafeden takip eder
ASIAN_IMBALANCE = 4.0         # 4.0x Imbalance
ASIAN_COOLDOWN = 60.0         # 60 sn bekleme
ASIAN_MAX_POS = 5             # Sabah maksimum 5 açık pozisyon

# =========================================================================
# VİTES 2: GÜNDÜZ SEÇİCİ TREND (09:00 - 18:00) -> FİLTRESİZ
# =========================================================================
DAY_END_HOUR = 18             # Londra kapanışı
DAY_SL_DIFF = 1.00            # Stop-Loss (1.00$)
DAY_EARLY_ACT = 0.65          # +0.65$ kâr görünce...
DAY_EARLY_LOCK = 0.25         # ...Stopu +0.25$ kâra (+$0.19 Net) kilitler!
DAY_TRAILING_ACT = 1.20       # +1.20$'da ana Trailing başlar
DAY_TRAILING_DIST = 0.50      # 0.50$ mesafeden takip eder
DAY_IMBALANCE = 4.3           # 4.3x Seçici Imbalance
DAY_COOLDOWN = 110.0          # 110 sn bekleme
DAY_MAX_POS = 3               # Gündüz maksimum 3 açık pozisyon

# =========================================================================
# VİTES 3: AKŞAM SNIPER MODU (18:00 - 22:50) -> FİLTRELİ ŞAMPİYON
# =========================================================================
NIGHT_SL_DIFF = 1.00          # Stop-Loss (1.00$)
NIGHT_EARLY_ACT = 0.65        # +0.65$ kâr görünce...
NIGHT_EARLY_LOCK = 0.25       # ...Stopu +0.25$ kâra (+$0.19 Net) kilitler!
NIGHT_TRAILING_ACT = 1.20     # +1.20$'da ana Trailing başlar
NIGHT_TRAILING_DIST = 0.50    # 0.50$ mesafeden takip eder
NIGHT_IMBALANCE = 5.5         # 5.5x Keskin Nişancı
NIGHT_COOLDOWN = 120.0        # 120 sn bekleme
NIGHT_MAX_POS = 4             # Akşam maksimum 4 açık pozisyon

# =========================================================================
# MALİYETLER VE ERKEN GECE KAPANIŞI (22:50 KİLİT / 22:58 KAPANIŞ)
# =========================================================================
COMMISSION_PER_LOT = 3.0      # Tam Tur = 0.06$ Komisyon
STOP_TRADING_HOUR = 22        # Saat 22:50'de yeni işlem açmayı durdurur
STOP_ENTRY_MINUTE = 50
FORCE_CLOSE_MINUTE = 58       # Saat 22:58'de açık kalan tüm işlemleri kapatır