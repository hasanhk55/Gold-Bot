import asyncio
import logging
import config
from strategy import HFTStrategy
from execution import HFTExecution

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

async def watch_orderbook_loop(execution, strategy):
    while True:
        try:
            orderbook = await execution.exchange.watch_order_book(config.SYMBOL, limit=5)
            best_bid = orderbook['bids'][0][0]
            best_ask = orderbook['asks'][0][0]
            
            # ÇÖKME KARŞITI KORUMA 1: Ters makas (Bid >= Ask) oluşursa tahtayı sıfırla!
            if best_ask <= best_bid:
                logger.warning(f"⚠️ Ters Tahta Algılandı (Bid: {best_bid} >= Ask: {best_ask})! Orderbook sıfırlanıyor...")
                execution.exchange.orderbooks.pop(config.SYMBOL, None)
                await asyncio.sleep(0.5)
                continue

            execution.check_virtual_positions(orderbook)
            
            signal, price, mode = strategy.analyze(orderbook)
            if signal:
                await execution.execute_signal(signal, price, mode)
                
        except Exception as e:
            # ÇÖKME KARŞITI KORUMA 2: Ping-pong / Timeout kopmasında asılı tahtayı sil ve yeniden bağlan!
            logger.error(f"Orderbook hatası: {e} | Bağlantı ve tahta yenileniyor...")
            execution.exchange.orderbooks.pop(config.SYMBOL, None)
            await asyncio.sleep(2)

async def watch_trades_loop(execution, strategy):
    while True:
        try:
            trades = await execution.exchange.watch_trades(config.SYMBOL)
            for trade in trades:
                strategy.on_trade(trade)
        except Exception as e:
            logger.error(f"Trade hatası: {e} | Trade akışı yenileniyor...")
            await asyncio.sleep(2)

async def main():
    logger.info(f"{config.SYMBOL} için HFT Bot Başlatılıyor...")
    strategy = HFTStrategy()
    execution = HFTExecution()

    try:
        await asyncio.gather(
            watch_orderbook_loop(execution, strategy),
            watch_trades_loop(execution, strategy)
        )
    except KeyboardInterrupt:
        logger.info("Bot kullanıcı tarafından durduruldu.")
    finally:
        await execution.exchange.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass