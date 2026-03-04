# Binance Trading Bot - v1.16.0 (Production Stable Release 2026)
import time
from datetime import datetime
from bot.exchange_client import ExchangeClient
from bot.strategy import Strategy
from bot.notifier import Notifier
from bot.utils import setup_logger, parse_timeframe_to_seconds, get_public_ip
from config import SYMBOL, TIMEFRAME, LARK_WEBHOOK_URL

def main():
    logger = setup_logger()
    logger.info("Binance Bot Starting...")
    
    # Identify the public IP address (crucial for Railway whitelist)
    public_ip = get_public_ip()
    logger.info(f"Public IP: {public_ip}")
    
    # Initialize Lark Notifier
    notifier = Notifier(LARK_WEBHOOK_URL, logger)
    notifier.send_lark_message(f"🚀 **Binance Bot Started**\nSymbol: {SYMBOL}\nTimeframe: {TIMEFRAME}\nIP: {public_ip}")
    
    logger.info(f"Target: {SYMBOL} on {TIMEFRAME} timeframe")
    
    client = ExchangeClient()
    
    strategy = Strategy(client, logger, notifier)
    
    tf_seconds = parse_timeframe_to_seconds(TIMEFRAME)

    # Daily Report Tracking
    last_report_date = None 

    logger.info("Bot is running. Press Ctrl+C to stop.")
    
    # Run initial analysis once on startup
    logger.info("Performing initial market analysis...")
    strategy.run_analysis()
    
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
            
            should_sleep = pre_close_buffer < seconds_remaining < (tf_seconds - post_open_buffer)

            if should_sleep:
                sleep_duration = seconds_remaining - pre_close_buffer
                logger.info(f"Waiting {int(sleep_duration)}s until next candle close area...")
                
                # Sleep in small chunks to keep Ctrl+C responsive
                wake_time = now + sleep_duration
                while time.time() < wake_time:
                    time.sleep(1)
            
            # 3. Daily Report Check (at 9:00 AM)
            now_dt = datetime.now()
            if now_dt.hour >= 9 and last_report_date != now_dt.date():
                logger.info("Time for daily report (>= 9:00 AM). Sending...")
                strategy.send_daily_report()
                last_report_date = now_dt.date()

            # 4. Execution Zone: detailed polling (every 1s)
            # Strategy handles deduplication (only processes new candle once)
            strategy.run_analysis()
            
            # Poll every 1 second when we are close to the candle boundary
            time.sleep(1) 
            
        except KeyboardInterrupt:
            logger.info("Bot stopped by user.")
            notifier.send_lark_message("🛑 **Binance Bot Stopped (User / KeyboardInterrupt)**")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            notifier.send_lark_message(f"⚠️ **Binance Bot Error**\nException: {e}")
            time.sleep(5)
        except BaseException as be:
            logger.critical(f"CRITICAL: Bot process is crashing: {type(be).__name__}: {be}")
            notifier.send_lark_message(f"💥 **CRITICAL CRASH**\nException: {type(be).__name__}: {be}")
            raise

if __name__ == "__main__":
    main()
