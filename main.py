import time
import schedule
from bot.exchange_client import ExchangeClient
from bot.strategy import Strategy
from bot.utils import setup_logger
from config import SYMBOL, TIMEFRAME

def main():
    logger = setup_logger()
    logger.info("Binance Bot Starting...")
    logger.info(f"Target: {SYMBOL} on {TIMEFRAME} timeframe")
    
    client = ExchangeClient()
    strategy = Strategy(client, logger)
    
    logger.info("Bot is running. Press Ctrl+C to stop.")
    
    while True:
        try:
            # Strategy now handles deduplication (only runs once per candle)
            strategy.run_analysis()
            
            # Poll every 10 seconds to catch the candle close quickly
            time.sleep(10) 
            
        except KeyboardInterrupt:
            logger.info("Bot stopped by user.")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
