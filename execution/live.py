import asyncio
from binance.client import AsyncClient
from binance.exceptions import BinanceAPIException
from execution.engine import ExecutionEngine
from execution.risk_manager import RiskManager
from core.logger import logger
from core.exceptions import ExecutionError
from config import settings

class LiveEngine(ExecutionEngine):
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.risk_manager = RiskManager()
        self.client = None
        self.position = 0 # 1=Long, -1=Short, 0=Flat
        
    async def initialize(self):
        self.client = await AsyncClient.create(
            settings.API_KEY, 
            settings.API_SECRET, 
            testnet=settings.TESTNET
        )
        await self.sync_position()

    async def sync_position(self):
        """Fetch current actual position from Binance to sync state."""
        try:
            positions = await self.client.futures_position_information(symbol=self.symbol)
            for pos in positions:
                if (pos['symbol'] == self.symbol):
                    amt = float(pos['positionAmt'])
                    if amt > 0:
                        self.position = 1
                    elif amt < 0:
                        self.position = -1
                    else:
                        self.position = 0
                    logger.info(f"Synced position: {self.position} (Amt: {amt})")
        except BinanceAPIException as e:
            logger.error(f"Error syncing position: {e}")

    async def get_balance(self) -> float:
        try:
            balances = await self.client.futures_account_balance()
            for bal in balances:
                if bal['asset'] == 'USDT':
                    return float(bal['balance'])
            return 0.0
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return 0.0

    async def get_exchange_info(self):
        """Get qty precision for step size"""
        info = await self.client.futures_exchange_info()
        for s in info['symbols']:
            if s['symbol'] == self.symbol:
                return s
        return None

    async def execute_long(self, price: float, **kwargs):
        logger.info(f"Executing LONG at {price}")
        balance = await self.get_balance()
        size = self.risk_manager.calculate_position_size(balance, price)
        
        # In a real bot, precision should come from exchange_info
        size = round(size, 3) 
        if size <= 0:
            logger.warning("Calculated order size is 0. Aborting trade.")
            return

        try:
            order = await self.client.futures_create_order(
                symbol=self.symbol, side='BUY', type='MARKET', quantity=size
            )
            logger.info(f"LONG Order placed: {order['orderId']}")
            self.position = 1
        except BinanceAPIException as e:
            logger.error(f"Error executing LONG: {e}")
            raise ExecutionError(str(e))

    async def execute_short(self, price: float, **kwargs):
        logger.info(f"Executing SHORT at {price}")
        balance = await self.get_balance()
        size = self.risk_manager.calculate_position_size(balance, price)
        
        size = round(size, 3) 
        if size <= 0:
            logger.warning("Calculated order size is 0. Aborting trade.")
            return

        try:
            order = await self.client.futures_create_order(
                symbol=self.symbol, side='SELL', type='MARKET', quantity=size
            )
            logger.info(f"SHORT Order placed: {order['orderId']}")
            self.position = -1
        except BinanceAPIException as e:
            logger.error(f"Error executing SHORT: {e}")
            raise ExecutionError(str(e))

    async def close_position(self, price: float = None, **kwargs):
        logger.info("Closing current position")
        try:
            positions = await self.client.futures_position_information(symbol=self.symbol)
            amt = 0.0
            for pos in positions:
                if pos['symbol'] == self.symbol:
                    amt = float(pos['positionAmt'])
                    break
            
            if amt == 0:
                logger.info("No position to close.")
                self.position = 0
                return
                
            side = 'SELL' if amt > 0 else 'BUY'
            order = await self.client.futures_create_order(
                symbol=self.symbol, side=side, type='MARKET', quantity=abs(amt)
            )
            logger.info(f"Close Position Order placed: {order['orderId']}")
            self.position = 0
        except BinanceAPIException as e:
            logger.error(f"Error closing position: {e}")
            raise ExecutionError(str(e))
            
    async def cleanup(self):
        if self.client:
            await self.client.close_connection()
