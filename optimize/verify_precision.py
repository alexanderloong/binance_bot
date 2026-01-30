import logging
import sys
import os

# Add the current directory to path so we can import bot
sys.path.append(os.getcwd())

from bot.exchange_client import ExchangeClient
from config import SYMBOL

def test_precision():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("BinanceBot")
    
    print("--- Testing Precision Fetching ---")
    try:
        client = ExchangeClient()
        print(f"Symbol: {client.symbol}")
        print(f"Quantity Precision: {client.qty_precision}")
        print(f"Price Precision: {client.price_precision}")
        
        test_amount = 0.00294567
        rounded_amount = round(test_amount, client.qty_precision)
        print(f"Test Amount: {test_amount}")
        print(f"Rounded Amount (Qty): {rounded_amount}")
        
        if client.symbol == "BTCUSDT":
            # For BTCUSDT, precision is usually 3
            if client.qty_precision == 3:
                print("SUCCESS: Quantity precision for BTCUSDT is correctly identified as 3.")
            else:
                print(f"NOTE: Quantity precision for BTCUSDT is {client.qty_precision} (typical is 3).")
                
    except Exception as e:
        print(f"Error during verification: {e}")

if __name__ == "__main__":
    test_precision()
