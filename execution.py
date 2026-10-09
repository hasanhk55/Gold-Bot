import ccxt.pro as ccxtpro
import logging
import time
import os
import csv
from datetime import datetime
import config

logger = logging.getLogger(__name__)

class HFTExecution:
    def __init__(self):
        self.exchange = ccxtpro.bitget({
            'apiKey': config.API_KEY,
            'secret': config.API_SECRET,
            'password': config.API_PASSWORD,
            'enableRateLimit': True,
            'options': {'defaultType': 'swap'}
        })
        
        self.virtual_positions = []
        self.pending_orders = []
        self.virtual_pnl = 0.0
        self.last_trade_time = 0.0 
        
        self.contract_multiplier = 100 
        self.round_trip_fee = (config.COMMISSION_PER_LOT * 2) * config.LOT_SIZE
        
        self.csv_filename = "trade_history.csv"
        if not os.path.exists(self.csv_filename):
            with open(self.csv_filename, mode='w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(["Tarih_Saat", "Mod", "Yon", "Giris_Fiyati", "Cikis_Fiyati", "Durum", "Net_PnL", "Kasa"])
        else:
            try:
                with open(self.csv_filename, mode='r', encoding='utf-8') as file:
                    rows = list(csv.reader(file))
                if len(rows) > 1 and rows[-1]:
                    self.virtual_pnl = float(rows[-1][-1])
                    logger.info(f"📂 Mevcut CSV'den Kasa Devralındı: ${self.virtual_pnl:.2f} ({len(rows)-1} İşlem)")
            except Exception as e:
                logger.error(f"CSV Kasa Okuma Hatası: {e}")
        
        if config.PAPER_TRADING:
            filt_str = "TREND+FLOW FİLTRELİ" if getattr(config, 'USE_TREND_FILTER', False) else "SAF SÜPER-HİBRİT"
            logger.info(f"🛡️ MASTER HİBRİT v6 [{filt_str} + ERKEN KÂR KİLİDİ] | Komisyon: ${self.round_trip_fee:.2f}")
            logger.info(f"🛌 00-04 Uyku | 🌅 04-09 v1 | ☀️ 09-{config.DAY_END_HOUR} v2 | 🎯 {config.DAY_END_HOUR}-{config.STOP_TRADING_HOUR}:{config.STOP_ENTRY_MINUTE} v3")

    def get_mode_params(self, mode):
        """Her vitesin SL, Erken Kâr Kilidi, Ana Trailing, Cooldown ve Pozisyon Limitini döndürür"""
        if mode == 'ASIAN_V1':
            return (config.ASIAN_SL_DIFF, config.ASIAN_EARLY_ACT, config.ASIAN_EARLY_LOCK,
                    config.ASIAN_TRAILING_ACT, config.ASIAN_TRAILING_DIST, config.ASIAN_COOLDOWN,
                    config.ASIAN_MAX_POS, "🌅")
        elif mode == 'DAY_V2':
            return (config.DAY_SL_DIFF, config.DAY_EARLY_ACT, config.DAY_EARLY_LOCK,
                    config.DAY_TRAILING_ACT, config.DAY_TRAILING_DIST, config.DAY_COOLDOWN,
                    config.DAY_MAX_POS, "☀️")
        else:
            return (config.NIGHT_SL_DIFF, config.NIGHT_EARLY_ACT, config.NIGHT_EARLY_LOCK,
                    config.NIGHT_TRAILING_ACT, config.NIGHT_TRAILING_DIST, config.NIGHT_COOLDOWN,
                    config.NIGHT_MAX_POS, "🎯")

    def log_to_csv(self, mode, side, entry, exit_price, status, pnl, total_pnl):
        try:
            with open(self.csv_filename, mode='a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                writer.writerow([timestamp, mode, side.upper(), f"{entry:.2f}", f"{exit_price:.2f}", status, f"{pnl:.4f}", f"{total_pnl:.4f}"])
        except Exception as e:
            logger.error(f"CSV Kayıt Hatası: {e}")

    def process_pending_orders(self, orderbook):
        if not self.pending_orders:
            return

        current_time = time.time()
        best_bid = orderbook['bids'][0][0]
        best_ask = orderbook['asks'][0][0]
        spread = best_ask - best_bid

        for order in self.pending_orders[:]:
            if current_time >= order['exec_time']:
                self.pending_orders.remove(order)
                
                if spread <= 0.0 or spread > config.MAX_SPREAD:
                    logger.info(f"⚠️ [İPTAL] Geçersiz/Açık Makas ({spread:.2f}$), işlem pas geçildi.")
                    continue

                side = order['side']
                mode = order['mode']
                sl_diff, early_act, early_lock, trail_act, trail_dist, _, _, icon = self.get_mode_params(mode)

                if config.REALISTIC_MARKET_MODE:
                    fill_price = best_ask if side == 'buy' else best_bid
                else:
                    fill_price = best_bid if side == 'buy' else best_ask

                sl_price = fill_price - sl_diff if side == 'buy' else fill_price + sl_diff

                logger.info(f"{icon} [GİRİŞ-{mode}] {side.upper()} | Fiyat: {fill_price:.2f} (Makas: {spread:.2f}$) | İlk SL: {sl_price:.2f} | Açık Poz: {len(self.virtual_positions)+1}")
                self.virtual_positions.append({
                    'side': side,
                    'entry': fill_price,
                    'sl': sl_price,
                    'peak_price': fill_price,
                    'early_lock_active': False,
                    'trailing_active': False,
                    'mode': mode,
                    'early_act': early_act,
                    'early_lock': early_lock,
                    'trail_act': trail_act,
                    'trail_dist': trail_dist
                })

    def check_virtual_positions(self, orderbook):
        best_bid = orderbook['bids'][0][0]
        best_ask = orderbook['asks'][0][0]
        spread = best_ask - best_bid

        # Bozuk tahta (Crossed Book) koruması
        if spread <= 0.0 or spread > 2.0:
            return

        self.process_pending_orders(orderbook)

        if not self.virtual_positions:
            return

        now = datetime.now()
        force_close = (now.hour > config.STOP_TRADING_HOUR or 
                       (now.hour == config.STOP_TRADING_HOUR and now.minute >= config.FORCE_CLOSE_MINUTE))

        for pos in self.virtual_positions[:]:
            closed = False
            pnl = 0.0
            close_price = 0.0
            status = ""
            mode = pos.get('mode', 'DAY_V2')
            early_act = pos['early_act']
            early_lock = pos['early_lock']
            trail_act = pos['trail_act']
            trail_dist = pos['trail_dist']
            
            if force_close:
                if pos['side'] == 'buy':
                    close_price = best_bid
                    pnl = ((close_price - pos['entry']) * self.contract_multiplier * config.LOT_SIZE) - self.round_trip_fee
                else:
                    close_price = best_ask
                    pnl = ((pos['entry'] - close_price) * self.contract_multiplier * config.LOT_SIZE) - self.round_trip_fee
                closed = True
                status = "⏰ GECE KAPANIŞ"
            else:
                if pos['side'] == 'buy':
                    pos['peak_price'] = max(pos['peak_price'], best_bid)
                    move = pos['peak_price'] - pos['entry']
                    
                    # AŞAMA 1: ERKEN KÂR KİLİDİ (+0.65$'da Stopu +0.25$ kâra çeker!)
                    if getattr(config, 'USE_EARLY_LOCK', True) and not pos['early_lock_active'] and move >= early_act:
                        pos['early_lock_active'] = True
                        pos['sl'] = max(pos['sl'], pos['entry'] + early_lock)
                        logger.info(f"🔒 [{mode} KÂR KİLİDİ] BUY +{early_act}$ gördü! Stop +{early_lock}$ kâra kilitlendi.")

                    # AŞAMA 2: ANA TRAILING (+1.20$'da geniş takip başlar)
                    if not pos['trailing_active'] and move >= trail_act:
                        pos['trailing_active'] = True
                        logger.info(f"🚀 [{mode} TRAILING AKTİF] BUY ana hedefe oturdu! (+{trail_act}$)")
                    
                    if pos['trailing_active']:
                        dynamic_sl = pos['peak_price'] - trail_dist
                        pos['sl'] = max(pos['sl'], dynamic_sl)
                    
                    if best_bid <= pos['sl']:
                        close_price = best_bid  
                        pnl = ((close_price - pos['entry']) * self.contract_multiplier * config.LOT_SIZE) - self.round_trip_fee
                        closed = True
                        if pos['trailing_active']:
                            status = f"🟢 {mode} İZ SÜREN TP"
                        elif pos['early_lock_active']:
                            status = f"🟢 {mode} KÂR KİLİDİ"
                        else:
                            status = f"🔴 {mode} SL"
                
                elif pos['side'] == 'sell':
                    pos['peak_price'] = min(pos['peak_price'], best_ask)
                    move = pos['entry'] - pos['peak_price']
                    
                    # AŞAMA 1: ERKEN KÂR KİLİDİ
                    if getattr(config, 'USE_EARLY_LOCK', True) and not pos['early_lock_active'] and move >= early_act:
                        pos['early_lock_active'] = True
                        pos['sl'] = min(pos['sl'], pos['entry'] - early_lock)
                        logger.info(f"🔒 [{mode} KÂR KİLİDİ] SELL +{early_act}$ gördü! Stop +{early_lock}$ kâra kilitlendi.")

                    # AŞAMA 2: ANA TRAILING
                    if not pos['trailing_active'] and move >= trail_act:
                        pos['trailing_active'] = True
                        logger.info(f"🚀 [{mode} TRAILING AKTİF] SELL ana hedefe oturdu! (+{trail_act}$)")
                    
                    if pos['trailing_active']:
                        dynamic_sl = pos['peak_price'] + trail_dist
                        pos['sl'] = min(pos['sl'], dynamic_sl)
                    
                    if best_ask >= pos['sl']:
                        close_price = best_ask  
                        pnl = ((pos['entry'] - close_price) * self.contract_multiplier * config.LOT_SIZE) - self.round_trip_fee
                        closed = True
                        if pos['trailing_active']:
                            status = f"🟢 {mode} İZ SÜREN TP"
                        elif pos['early_lock_active']:
                            status = f"🟢 {mode} KÂR KİLİDİ"
                        else:
                            status = f"🔴 {mode} SL"
            
            if closed:
                self.virtual_pnl += pnl
                logger.info(f"[ÇIKIŞ-{mode}] {status} | Kapanış: {close_price:.2f} | Net PnL: ${pnl:.2f} | KASA: ${self.virtual_pnl:.2f}")
                self.log_to_csv(mode, pos['side'], pos['entry'], close_price, status, pnl, self.virtual_pnl)
                self.virtual_positions.remove(pos)

    async def execute_signal(self, side, price, mode='DAY_V2'):
        current_time = time.time()
        _, _, _, _, _, cooldown_sec, max_pos, _ = self.get_mode_params(mode)
        
        if current_time - self.last_trade_time < cooldown_sec:
            return 
        if (len(self.virtual_positions) + len(self.pending_orders)) >= max_pos:
            return 

        self.last_trade_time = current_time

        if config.PAPER_TRADING:
            self.pending_orders.append({
                'side': side,
                'signal_price': price,
                'mode': mode,
                'exec_time': current_time + config.LATENCY_SEC
            })
            return

        logger.info(f"Canlı Emir ({mode}): {side.upper()} | Fiyat: {price}")