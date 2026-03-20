"""
finance.py — Centralized financial calculation utilities.

All PnL, ROI, fee, and position-sizing math lives here.
Single source of truth — no duplicated formulas across the codebase.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------------------------
# Fee helpers
# ---------------------------------------------------------------------------

def calc_fee(price: float, quantity: float, fee_rate: float) -> float:
    """
    Taker fee for ONE leg (open OR close).

    Binance Futures formula:
        fee = notional_value * fee_rate
            = price * quantity * fee_rate

    Args:
        price:    Fill price (USDT).
        quantity: Contract quantity (BTC for BTCUSDT).
        fee_rate: Taker fee rate, e.g. 0.0005 for 0.05%.

    Returns:
        Fee in USDT (always positive).
    """
    return abs(price * quantity * fee_rate)


def calc_round_trip_fee(
    entry_price: float,
    exit_price: float,
    quantity: float,
    fee_rate: float,
) -> float:
    """
    Total fee for a full round-trip (open + close).

        total_fee = fee_open + fee_close
                  = entry * qty * rate + exit * qty * rate
                  = (entry + exit) * qty * rate

    This is algebraically identical to the original code — but the
    *intent* is now explicit and each leg is traceable.
    """
    fee_open  = calc_fee(entry_price, quantity, fee_rate)
    fee_close = calc_fee(exit_price,  quantity, fee_rate)
    return fee_open + fee_close


# ---------------------------------------------------------------------------
# PnL helpers
# ---------------------------------------------------------------------------

def calc_gross_pnl(
    entry_price: float,
    exit_price: float,
    quantity: float,
    is_long: bool,
) -> float:
    """
    Gross PnL (before fees).

    LONG:  (exit - entry) * qty
    SHORT: (entry - exit) * qty
    """
    if is_long:
        return (exit_price - entry_price) * abs(quantity)
    else:
        return (entry_price - exit_price) * abs(quantity)


def calc_net_pnl(
    entry_price: float,
    exit_price: float,
    quantity: float,
    fee_rate: float,
    is_long: bool,
) -> float:
    """Net PnL after round-trip fees."""
    gross = calc_gross_pnl(entry_price, exit_price, quantity, is_long)
    fee   = calc_round_trip_fee(entry_price, exit_price, quantity, fee_rate)
    return gross - fee


# ---------------------------------------------------------------------------
# ROI helpers
# ---------------------------------------------------------------------------

def calc_roi(
    net_pnl: float,
    entry_price: float,
    quantity: float,
    leverage: int,
) -> float:
    """
    Net ROI as a percentage of margin actually deployed.

        margin = notional / leverage
               = entry_price * qty / leverage

        roi% = net_pnl / margin * 100

    Args:
        net_pnl:     Already-net PnL (fees deducted).
        entry_price: Entry fill price.
        quantity:    Contract quantity.
        leverage:    Active leverage.

    Returns:
        ROI in percent (e.g. 2.35 means +2.35%).
    """
    margin = entry_price * abs(quantity) / leverage
    if margin == 0:
        return 0.0
    return (net_pnl / margin) * 100.0


# ---------------------------------------------------------------------------
# Breakeven price
# ---------------------------------------------------------------------------

def calc_breakeven_price(
    entry_price: float,
    fee_rate: float,
    is_long: bool,
) -> float:
    """
    Exact breakeven exit price where net PnL == 0.

    Derivation for LONG:
        gross_pnl  = (BE - entry) * qty
        total_fee  = (entry + BE) * qty * rate
        net_pnl    = 0
        => (BE - entry) = (entry + BE) * rate
        => BE(1 - rate) = entry(1 + rate)
        => BE = entry * (1 + rate) / (1 - rate)

    SHORT is the mirror image:
        => BE = entry * (1 - rate) / (1 + rate)

    Note: the original code used `entry * (1 ± rate*2)` which is a
    first-order Taylor approximation — accurate to ~0.0001% but
    mathematically imprecise.
    """
    if is_long:
        return entry_price * (1.0 + fee_rate) / (1.0 - fee_rate)
    else:
        return entry_price * (1.0 - fee_rate) / (1.0 + fee_rate)


# ---------------------------------------------------------------------------
# Position sizing
# ---------------------------------------------------------------------------

def calc_trade_quantity(
    balance: float,
    pos_size_pct: float,
    leverage: int,
    price: float,
    fee_rate: float,
    qty_precision: int,
) -> tuple[float, float]:
    """
    Calculates the trade quantity, reserving enough margin so that the
    opening fee does not push the account into insufficient-margin.

    Formula:
        notional_budget = balance * pos_size_pct * leverage
        # Opening fee is paid from free margin, not from the position itself,
        # but we scale down slightly so the order + fee fits within balance.
        notional_safe   = notional_budget / (1 + fee_rate)
        quantity        = notional_safe / price

    Args:
        balance:       Wallet balance in USDT.
        pos_size_pct:  Fraction of balance to risk, e.g. 1.0 = 100%.
        leverage:      Active leverage multiplier.
        price:         Entry price estimate (last close).
        fee_rate:      Taker fee rate.
        qty_precision: Exchange quantity precision (decimal places).

    Returns:
        Tuple of (rounded_quantity, notional_usdt).
    """
    notional_raw  = balance * pos_size_pct * leverage
    # Reserve room for the open-leg fee
    notional_safe = notional_raw / (1.0 + fee_rate)
    quantity_raw  = notional_safe / price
    quantity      = round(quantity_raw, qty_precision)
    notional_final = quantity * price
    return quantity, notional_final


# ---------------------------------------------------------------------------
# Structured result for notifications
# ---------------------------------------------------------------------------

@dataclass
class TradeResult:
    """
    Immutable snapshot of a closed trade's financials.
    Used to build notification messages with consistent formatting.
    """
    side: str            # 'LONG' or 'SHORT'
    entry_price: float
    exit_price: float
    quantity: float
    leverage: int
    fee_rate: float

    @property
    def is_long(self) -> bool:
        return self.side.upper() == "LONG"

    @property
    def gross_pnl(self) -> float:
        return calc_gross_pnl(self.entry_price, self.exit_price, self.quantity, self.is_long)

    @property
    def total_fee(self) -> float:
        return calc_round_trip_fee(self.entry_price, self.exit_price, self.quantity, self.fee_rate)

    @property
    def net_pnl(self) -> float:
        return self.gross_pnl - self.total_fee

    @property
    def roi_pct(self) -> float:
        return calc_roi(self.net_pnl, self.entry_price, self.quantity, self.leverage)

    def format_summary(self, label: str = "TRADE CLOSED") -> str:
        pnl_emoji = "🟢" if self.net_pnl >= 0 else "🔴"
        sign = "+" if self.net_pnl >= 0 else ""
        return (
            f"{pnl_emoji} **{label}**\n"
            f"Side: {self.side}\n"
            f"Entry: {self.entry_price:.2f} → Exit: {self.exit_price:.2f}\n"
            f"Gross PnL: {sign}{self.gross_pnl:.2f} USDT\n"
            f"Fee:      -{self.total_fee:.4f} USDT\n"
            f"Net PnL:   {sign}{self.net_pnl:.2f} USDT\n"
            f"ROI:       {sign}{self.roi_pct:.2f}% (on margin)"
        )
