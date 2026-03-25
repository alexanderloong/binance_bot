import pandas as pd
import itertools
from typing import Dict, List, Any
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

from strategy.supertrend_ha import SupertrendHAStrategy
from execution.backtest import BacktestEngine
from core.logger import logger
from core.trading_metrics import (
    score_bot,
    profit_factor,
    max_drawdown,
    win_rate,
    expectancy
)

def evaluate_params(args: tuple) -> Dict[str, Any]:
    """Evaluates a single set of parameters."""
    df, params = args
    
    strategy = SupertrendHAStrategy(
        period=params.get('st_period'),
        multiplier=params.get('st_multiplier'),
        atr_period=params.get('atr_period'),
        ema_period=params.get('ema_period'),
        use_ema=params.get('use_ema', True),
        use_adx=params.get('use_adx', True),
        adx_period=params.get('adx_period'),
        adx_threshold=params.get('adx_threshold')
    )
    
    try:
        df_signals = strategy.generate_signals(df.copy())
        
        engine = BacktestEngine(
            initial_capital=1000.0,
            sl_atr_multiplier=params.get('sl_atr_multiplier', 0.0)
        )
        
        engine.run(df_signals, silent=True)
        
        trades_df = pd.DataFrame(engine.trades)
        if len(trades_df) == 0:
            return None
            
        close_trades = trades_df[trades_df["action"] == "CLOSE"]
        trades_count = len(close_trades)
        
        if trades_count < params.get('min_trades', 0):
            return None
            
        trades_pnl = close_trades["pnl"].tolist()
        total_pnl = sum(trades_pnl)
        
        equity_df = pd.DataFrame(engine.equity_curve)
        if len(equity_df) == 0:
            return None
            
        equity_curve_list = equity_df["equity"].tolist()
        returns = equity_df["equity"].pct_change().fillna(0).tolist()
        
        scores = score_bot(returns, trades_pnl, equity_curve_list)
        
        return {
            "params": params,
            "trades": trades_count,
            "total_pnl": total_pnl,
            "win_rate": win_rate(trades_pnl) * 100,
            "profit_factor": profit_factor(trades_pnl),
            "max_drawdown": max_drawdown(equity_curve_list) * 100,
            "expectancy": expectancy(trades_pnl),
            "total_score": scores['total_score']
        }
    except Exception as e:
        # Silently fail for multiprocess cleanliness
        return None

class GridSearchOptimizer:
    """
    SOLID Optimizer using Strategy pattern for bot configurations.
    """
    def __init__(self, data: pd.DataFrame, param_grid: Dict[str, List], min_trades: int = 1000):
        self.data = data
        self.param_grid = param_grid
        self.min_trades = min_trades
        
    def _generate_combinations(self) -> List[Dict[str, Any]]:
        keys, values = zip(*self.param_grid.items())
        combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
        for combo in combinations:
            combo['min_trades'] = self.min_trades
        return combinations

    def optimize(self, workers: int = None) -> List[Dict[str, Any]]:
        combinations = self._generate_combinations()
        logger.info(f"Starting Grid Search with {len(combinations)} parameter combinations.")
        logger.info(f"Condition: Minimum {self.min_trades} trades per configuration to be trustworthy.")
        
        results = []
        tasks = [(self.data, combo) for combo in combinations]
        
        if workers is None:
            workers = max(1, multiprocessing.cpu_count() - 1)
            
        logger.info(f"Executing parallel backtests via {workers} Process Workers...")
        
        with ProcessPoolExecutor(max_workers=workers) as executor:
            for idx, res in enumerate(executor.map(evaluate_params, tasks)):
                if res is not None:
                    results.append(res)
                
                # Feedback hook every roughly 10%
                step = max(1, len(combinations) // 10)
                if (idx + 1) % step == 0 or (idx + 1) == len(combinations):
                    logger.info(f"Processed {idx + 1}/{len(combinations)} configurations...")
                    
        # Sort best configurations by our proprietary total composite score
        results.sort(key=lambda x: x['total_score'], reverse=True)
        return results
