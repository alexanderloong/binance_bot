import argparse
import asyncio
import pandas as pd

from config import settings
from core.logger import logger
from data.historical import HistoricalDataProvider
from strategy.supertrend_ha import SupertrendHAStrategy
from execution.live import LiveEngine

from binance import AsyncClient, BinanceSocketManager
async def run_live(client: AsyncClient, engine: LiveEngine, bs_manager: BinanceSocketManager, strategy: SupertrendHAStrategy):
    logger.info(f"=== Starting Live Trading for {settings.SYMBOL} ===")
    
    provider = HistoricalDataProvider()
    logger.info("Fetching initial historical data to seed indicators...")
    df = provider.get_historical_data(settings.SYMBOL, settings.TIMEFRAME, limit=100)
    
    kline_stream = bs_manager.kline_socket(symbol=settings.SYMBOL.lower(), interval=settings.TIMEFRAME)
    
    async with kline_stream as stream:
        logger.info("WebSocket connected. Listening for kline updates...")
        while True:
            res = await stream.recv()
            if 'e' in res and res['e'] == 'kline':
                kline = res['k']
                is_closed = kline['x']
                
                # Only execute strategy on candle close to prevent repainting issues
                if is_closed:
                    timestamp = pd.to_datetime(kline['t'], unit='ms')
                    close_price = float(kline['c'])
                    logger.info(f"Candle closed at {timestamp}. Close price: {close_price}")
                    
                    new_row = pd.DataFrame({
                        'open': [float(kline['o'])],
                        'high': [float(kline['h'])],
                        'low': [float(kline['l'])],
                        'close': [close_price],
                        'volume': [float(kline['v'])]
                    }, index=[timestamp])
                    
                    df = pd.concat([df, new_row])
                    df = df.tail(150) # Keep sliding window
                    
                    df_signals = strategy.generate_signals(df)
                    latest_signal = df_signals.iloc[-1]['signal']
                    logger.info(f"Generated Signal: {latest_signal}")
                    
                    if latest_signal == 1:
                        if engine.position == -1:
                            await engine.close_position()
                        if engine.position == 0:
                            await engine.execute_long(close_price)
                    elif latest_signal == -1:
                        if engine.position == 1:
                            await engine.close_position()
                        if engine.position == 0:
                            await engine.execute_short(close_price)

async def live_mode_entry():
    client = await AsyncClient.create(settings.API_KEY, settings.API_SECRET, testnet=settings.TESTNET)
    bsm = BinanceSocketManager(client)
    strategy = SupertrendHAStrategy()
    engine = LiveEngine(settings.SYMBOL)
    await engine.initialize()
    
    try:
        await run_live(client, engine, bsm, strategy)
    except KeyboardInterrupt:
        logger.info("Live trading stopped by user.")
    except Exception as e:
        logger.error(f"Live engine crashed: {e}")
    finally:
        await engine.cleanup()

def main():
    parser = argparse.ArgumentParser(description="Binance Futures Bot - Live Trading")
    parser.add_argument('--live', action='store_true', help='Run in live mode')
    args = parser.parse_args()

    if args.live:
        asyncio.run(live_mode_entry())
    else:
        logger.info("Please specify mode: --live")
        parser.print_help()

if __name__ == "__main__":
    main()
