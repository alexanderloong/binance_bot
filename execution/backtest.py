import pandas as pd
from execution.engine import ExecutionEngine
from execution.risk_manager import RiskManager
from core.logger import logger

class BacktestEngine(ExecutionEngine):
    def __init__(self, initial_capital: float = 1000.0, maker_fee: float = 0.0002, taker_fee: float = 0.0004):
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.risk_manager = RiskManager(initial_capital)
        self.maker_fee = maker_fee
        self.taker_fee = taker_fee
        
        self.position = 0 # 1 for Long, -1 for Short, 0 for flat
        self.entry_price = 0.0
        self.position_size = 0.0
        
        self.trades = []
        self.equity_curve = []
        
    def run(self, df: pd.DataFrame):
        logger.info(f"Starting backtest with {self.initial_capital} USDT")
        
        for index, row in df.iterrows():
            current_price = row['close']
            signal = row.get('signal', 0)
            
            if signal == 1:
                if self.position == -1:
                    self.close_position(current_price, timestamp=index, reason="Close Short")
                if self.position == 0:
                    self.execute_long(current_price, timestamp=index)
            elif signal == -1:
                if self.position == 1:
                    self.close_position(current_price, timestamp=index, reason="Close Long")
                if self.position == 0:
                    self.execute_short(current_price, timestamp=index)
            
            unrealized_pnl = 0
            if self.position == 1:
                unrealized_pnl = (current_price - self.entry_price) * self.position_size
            elif self.position == -1:
                unrealized_pnl = (self.entry_price - current_price) * self.position_size
                
            self.equity_curve.append({
                'timestamp': index,
                'equity': self.capital + unrealized_pnl
            })
            
        if self.position != 0:
            last_idx = df.index[-1]
            last_price = df['close'].iloc[-1]
            self.close_position(last_price, timestamp=last_idx, reason="End of Backtest")
            
        self.generate_report()
            
    def execute_long(self, price: float, **kwargs):
        timestamp = kwargs.get('timestamp')
        size = self.risk_manager.calculate_position_size(self.capital, price)
        fee = price * size * self.taker_fee
        self.capital -= fee
        
        self.position = 1
        self.entry_price = price
        self.position_size = size
        
        self.trades.append({
            'timestamp': timestamp,
            'action': 'LONG',
            'price': price,
            'size': size,
            'fee': fee,
            'pnl': 0
        })
        
    def execute_short(self, price: float, **kwargs):
        timestamp = kwargs.get('timestamp')
        size = self.risk_manager.calculate_position_size(self.capital, price)
        fee = price * size * self.taker_fee
        self.capital -= fee
        
        self.position = -1
        self.entry_price = price
        self.position_size = size
        
        self.trades.append({
            'timestamp': timestamp,
            'action': 'SHORT',
            'price': price,
            'size': size,
            'fee': fee,
            'pnl': 0
        })
        
    def close_position(self, price: float, **kwargs):
        timestamp = kwargs.get('timestamp')
        reason = kwargs.get('reason', '')
        
        fee = price * self.position_size * self.taker_fee
        pnl = 0
        if self.position == 1:
            pnl = (price - self.entry_price) * self.position_size - fee
        elif self.position == -1:
            pnl = (self.entry_price - price) * self.position_size - fee
            
        self.capital += pnl
        
        self.trades.append({
            'timestamp': timestamp,
            'action': 'CLOSE',
            'price': price,
            'size': self.position_size,
            'fee': fee,
            'pnl': pnl,
            'reason': reason
        })
        
        self.position = 0
        self.entry_price = 0
        self.position_size = 0
        
    def generate_report(self):
        trades_df = pd.DataFrame(self.trades)
        close_trades = trades_df[trades_df['action'] == 'CLOSE']
        
        if len(close_trades) == 0:
            logger.info("No trades were closed during the backtest.")
            return
            
        total_pnl = close_trades['pnl'].sum()
        win_trades = close_trades[close_trades['pnl'] > 0]
        
        winrate = len(win_trades) / len(close_trades) * 100 if len(close_trades) > 0 else 0
        
        equity_df = pd.DataFrame(self.equity_curve)
        peak = equity_df['equity'].cummax()
        drawdown = (equity_df['equity'] - peak) / peak * 100
        max_drawdown = drawdown.min()
        
        logger.info("=== BACKTEST REPORT ===")
        logger.info(f"Initial Capital: {self.initial_capital:.2f} USDT")
        logger.info(f"Final Capital: {self.capital:.2f} USDT")
        logger.info(f"Total PnL: {total_pnl:.2f} USDT ({(self.capital/self.initial_capital - 1)*100:.2f}%)")
        logger.info(f"Total Trades: {len(close_trades)}")
        logger.info(f"Winrate: {winrate:.2f}%")
        logger.info(f"Max Drawdown: {max_drawdown:.2f}%")
        logger.info("=======================")
