from __future__ import annotations

from typing import List, Optional

from bot.core.models import Bar, MarketState, Signal, OrderSide, OrderType
from bot.utils.indicators import atr, ema, rsi, rolling_high_low


class ScalperMomentumStrategy:
    name = "scalper_momentum"

    def __init__(
        self,
        fast_ema_period: int = 9,
        slow_ema_period: int = 21,
        rr: float = 1.2,
        breakout_lookback: int = 8,
    ) -> None:
        self.fast_ema_period = fast_ema_period
        self.slow_ema_period = slow_ema_period
        self.rr = rr
        self.breakout_lookback = breakout_lookback

    def generate(
        self,
        state: MarketState,
        bars_m15: List[Bar],
        bars_h1: List[Bar],
        context: Optional[dict] = None,
    ) -> Optional[Signal]:
        min_bars = max(self.slow_ema_period + 3, self.breakout_lookback + 3)
        if len(bars_m15) < min_bars:
            return None

        closes = [b.close for b in bars_m15]
        last = bars_m15[-1]
        prev = bars_m15[-2]
        atr_val = atr(bars_m15)
        if atr_val <= 0:
            return None

        ema_fast = ema(closes, self.fast_ema_period)
        ema_slow = ema(closes, self.slow_ema_period)
        prev_fast = ema(closes[:-1], self.fast_ema_period)
        prev_slow = ema(closes[:-1], self.slow_ema_period)
        last_rsi = rsi(closes, 14)
        recent_high, recent_low = rolling_high_low(bars_m15[:-1], self.breakout_lookback)

        bullish_alignment = ema_fast > ema_slow and prev_fast >= prev_slow
        bearish_alignment = ema_fast < ema_slow and prev_fast <= prev_slow

        buy_pullback = bullish_alignment and prev.close <= prev_fast and last.close >= ema_fast and 52 <= last_rsi <= 74
        buy_breakout = bullish_alignment and last.close > (recent_high + atr_val * 0.05) and last_rsi >= 55
        sell_pullback = bearish_alignment and prev.close >= prev_fast and last.close <= ema_fast and 26 <= last_rsi <= 48
        sell_breakout = bearish_alignment and last.close < (recent_low - atr_val * 0.05) and last_rsi <= 45

        if buy_pullback or buy_breakout:
            entry = last.close
            stop = min(last.low, ema_slow) - (atr_val * 0.25)
            if stop >= entry:
                stop = entry - (atr_val * 0.45)
            risk = entry - stop
            if risk <= atr_val * 0.25:
                stop = entry - (atr_val * 0.35)
                risk = entry - stop
            take = entry + (risk * self.rr)
            confidence = 0.56 + min(0.18, abs(state.trend_strength) * 450)
            if buy_breakout:
                confidence += 0.08
            rationale = ["scalper", "ema_alignment", "buy_breakout" if buy_breakout else "buy_pullback"]
            return Signal(
                symbol=state.symbol,
                time=last.time,
                strategy=self.name,
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                entry_price=entry,
                stop_loss=stop,
                take_profit=take,
                max_hold_minutes=90,
                confidence=min(1.0, confidence),
                rationale=rationale,
            )

        if sell_pullback or sell_breakout:
            entry = last.close
            stop = max(last.high, ema_slow) + (atr_val * 0.25)
            if stop <= entry:
                stop = entry + (atr_val * 0.45)
            risk = stop - entry
            if risk <= atr_val * 0.25:
                stop = entry + (atr_val * 0.35)
                risk = stop - entry
            take = entry - (risk * self.rr)
            confidence = 0.56 + min(0.18, abs(state.trend_strength) * 450)
            if sell_breakout:
                confidence += 0.08
            rationale = ["scalper", "ema_alignment", "sell_breakout" if sell_breakout else "sell_pullback"]
            return Signal(
                symbol=state.symbol,
                time=last.time,
                strategy=self.name,
                side=OrderSide.SELL,
                order_type=OrderType.MARKET,
                entry_price=entry,
                stop_loss=stop,
                take_profit=take,
                max_hold_minutes=90,
                confidence=min(1.0, confidence),
                rationale=rationale,
            )

        return None
