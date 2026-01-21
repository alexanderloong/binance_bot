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
    
    tf_seconds = 60 # Default
    try:
        val = int(''.join(c for c in TIMEFRAME if c.isdigit()))
        unit = ''.join(c for c in TIMEFRAME if c.isalpha()).lower()
        if unit == 'm': tf_seconds = val * 60
        elif unit == 'h': tf_seconds = val * 3600
        elif unit == 'd': tf_seconds = val * 86400
    except:
        logger.warning(f"Could not parse TIMEFRAME '{TIMEFRAME}', defaulting to 60s")

    logger.info("Bot is running. Press Ctrl+C to stop.")
    
    while True:
        try:
            # 1. Calculate time remaining until next candle close
            now = time.time()
            next_candle_close = ((int(now) // tf_seconds) + 1) * tf_seconds
            seconds_remaining = next_candle_close - now
            
            # 2. Smart Sleep: 
            # We ONLY sleep if we are in the "boring" middle part of the candle.
            # - Must be > 10s before the NEXT close (Pre-Close Buffer)
            # - Must be < (TF - 60s) remaining (Post-Open Buffer), meaning we are past the first 60s of the new candle
            # This ensures we keep scanning for ~60s after the new candle opens to catch the data update
            
            pre_close_buffer = 10
            post_open_buffer = 60
            
            should_sleep = (seconds_remaining > pre_close_buffer) and \
                           (seconds_remaining < (tf_seconds - post_open_buffer))

            if should_sleep:
                sleep_duration = seconds_remaining - pre_close_buffer
                logger.info(f"Waiting {int(sleep_duration)}s until next candle close area...")
                
                # Sleep in small chunks to keep Ctrl+C responsive
                wake_time = now + sleep_duration
                while time.time() < wake_time:
                    time.sleep(1)
            
            # 3. Execution Zone: detailed polling (every 1s)
            # Strategy handles deduplication (only processes new candle once)
            strategy.run_analysis()
            
            # Poll every 1 second when we are close to the candle boundary
            time.sleep(1) 
            
        except KeyboardInterrupt:
            logger.info("Bot stopped by user.")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
