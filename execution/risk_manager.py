from config import settings

class RiskManager:
    def __init__(self, initial_capital: float = 1000.0):
        self.capital = initial_capital
        self.risk_per_trade = settings.RISK_PER_TRADE_PCNT
        self.leverage = settings.LEVERAGE

    def calculate_position_size(self, current_capital: float, entry_price: float, stop_loss: float = None) -> float:
        """
        Calculate position size based on risk and leverage.
        If stop_loss is provided, use it for position sizing,
        else just use a fixed percentage of capital with leverage.
        """
        if stop_loss is not None and entry_price != stop_loss:
            risk_amount = current_capital * self.risk_per_trade
            distance = abs(entry_price - stop_loss) / entry_price
            if distance == 0:
                return 0.0
            position_value = risk_amount / distance
            # Cap by max leverage
            max_position = current_capital * self.leverage
            position_value = min(position_value, max_position)
            return position_value / entry_price
        else:
            # Fixed capital usage if no SL is provided
            invested = current_capital * 0.1 * self.leverage
            return invested / entry_price
