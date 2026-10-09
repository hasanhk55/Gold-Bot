from collections import deque
from datetime import datetime
import config

class HFTStrategy:
    def __init__(self):
        self.recent_trades = deque(maxlen=40)
        self.mid_prices = deque(maxlen=30)

    def on_trade(self, trade):
        self.recent_trades.append(trade)

    def check_tape_flow(self, side, is_night_mode=False):
        """Son gerçekleşen (Taker) işlemlerin yönünü kontrol eder"""
        # Sadece gece modunda ve tape flow açıksa kontrol et, yoksa Asya ve Gündüz için doğrudan onayla
        if not is_night_mode or not getattr(config, 'NIGHT_USE_TAPE_FLOW', True):
            return True 
            
        if len(self.recent_trades) < 10:
            return True

        buy_vol = sum(t.get('amount', 0) for t in self.recent_trades if t.get('side') == 'buy')
        sell_vol = sum(t.get('amount', 0) for t in self.recent_trades if t.get('side') == 'sell')
        total_vol = buy_vol + sell_vol

        if total_vol == 0:
            return True

        if side == 'buy':
            return (buy_vol / total_vol) >= config.TAPE_FLOW_RATIO
        else:
            return (sell_vol / total_vol) >= config.TAPE_FLOW_RATIO

    def analyze(self, orderbook):
        if not orderbook.get('bids') or not orderbook.get('asks'):
            return None, None, None

        best_bid = orderbook['bids'][0][0]
        best_ask = orderbook['asks'][0][0]
        spread = best_ask - best_bid

        # 1. ÇİFT YÖNLÜ MAKAS KORUMASI
        if spread <= 0.0 or spread > config.MAX_SPREAD:
            return None, None, None

        # Mikro-Trend için orta fiyatı kaydet
        mid_price = (best_bid + best_ask) / 2.0
        self.mid_prices.append(mid_price)

        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute

        # 2. GECE UYKU MODU
        if (current_hour < config.TRADING_START_HOUR or 
            current_hour > config.STOP_TRADING_HOUR or 
            (current_hour == config.STOP_TRADING_HOUR and current_minute >= config.STOP_ENTRY_MINUTE)):
            return None, None, None

        bid_vol = sum(bid[1] for bid in orderbook['bids'][:5])
        ask_vol = sum(ask[1] for ask in orderbook['asks'][:5])

        if ask_vol == 0 or bid_vol == 0:
            return None, None, None

        buy_imbalance = bid_vol / ask_vol
        sell_imbalance = ask_vol / bid_vol
        
        # Akşam seansında mıyız kontrolü (Saat 18:00 ve sonrası)
        is_night_mode = (current_hour >= config.DAY_END_HOUR)

        # 3. MİKRO-TREND YÖN FİLTRESİ (SADECE AKŞAM AKTİF)
        trend_buy_ok = True
        trend_sell_ok = True
        
        if is_night_mode and getattr(config, 'NIGHT_USE_TREND_FILTER', True) and len(self.mid_prices) >= 15:
            avg_price = sum(self.mid_prices) / len(self.mid_prices)
            trend_buy_ok = (mid_price >= avg_price - 0.05)
            trend_sell_ok = (mid_price <= avg_price + 0.05)

        buy_entry_price = best_ask if config.REALISTIC_MARKET_MODE else best_bid
        sell_entry_price = best_bid if config.REALISTIC_MARKET_MODE else best_ask

        # VİTES 1: SABAH ASYA TREND (04:00 - 09:00) - FİLTRESİZ
        if config.TRADING_START_HOUR <= current_hour < config.ASIAN_END_HOUR:
            if buy_imbalance >= config.ASIAN_IMBALANCE:
                return 'buy', buy_entry_price, 'ASIAN_V1'
            elif sell_imbalance >= config.ASIAN_IMBALANCE:
                return 'sell', sell_entry_price, 'ASIAN_V1'

        # VİTES 2: GÜNDÜZ SEÇİCİ TREND (09:00 - 18:00) - FİLTRESİZ
        elif config.ASIAN_END_HOUR <= current_hour < config.DAY_END_HOUR:
            if buy_imbalance >= config.DAY_IMBALANCE:
                return 'buy', buy_entry_price, 'DAY_V2'
            elif sell_imbalance >= config.DAY_IMBALANCE:
                return 'sell', sell_entry_price, 'DAY_V2'

        # VİTES 3: AKŞAM SNIPER (18:00 - 22:50) - FİLTRELİ (Trend + Tape Flow)
        else:
            if buy_imbalance >= config.NIGHT_IMBALANCE and trend_buy_ok and self.check_tape_flow('buy', is_night_mode=True):
                return 'buy', buy_entry_price, 'NIGHT_V3'
            elif sell_imbalance >= config.NIGHT_IMBALANCE and trend_sell_ok and self.check_tape_flow('sell', is_night_mode=True):
                return 'sell', sell_entry_price, 'NIGHT_V3'

        return None, None, None