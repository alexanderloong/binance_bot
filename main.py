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
    
    # Run once immediately
    strategy.run_analysis()
    
    # Schedule to run every day (matches candle size)
    # Note: Ideally you want to run slightly after the candle close (UTC 00:00).
    # For simplicity, we'll run every 1 minute to check (in a real scenario, you sync with clock).
    # The strategy has simple state tracking to avoid double trading on same signal.
    
    schedule.every(30).seconds.do(strategy.run_analysis)
    
    logger.info("Bot is running. Press Ctrl+C to stop.")
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user.")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
