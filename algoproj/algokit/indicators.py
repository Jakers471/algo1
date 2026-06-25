"""
Indicator library — pure functions already in use across the scripts, each
registered in INDICATORS so new ones can be added plug-and-play.

Add a new indicator by decorating it with @indicator; it lands in INDICATORS
under its function name.
"""
import numpy as np
import pandas as pd

INDICATORS = {}


def indicator(fn):
    """Register a pure indicator function in the INDICATORS registry."""
    INDICATORS[fn.__name__] = fn
    return fn


@indicator
def geom_lengths(lo, hi, n=32):
    """The ~32 geometrically-spaced MA lengths used by every fan
    (sorted, de-duplicated integers)."""
    return sorted(set(int(round(v)) for v in np.geomspace(lo, hi, n)))


@indicator
def sma(close, n):
    """Simple moving average over n bars."""
    return close.rolling(n).mean()


@indicator
def fan(close, lengths):
    """A fan of SMAs -> dict {length: SMA Series}."""
    return {n: close.rolling(n).mean() for n in lengths}


@indicator
def slope_pct(ma, L):
    """Slope of an MA as percent change over L bars: (ma/ma.shift(L)-1)*100."""
    return (ma / ma.shift(L) - 1) * 100


@indicator
def rsi(close, n=14):
    """Wilder-smoothed RSI(n). (from nq_edge_test / nq_dipbuy_filtered)."""
    delta = close.diff()
    up = delta.clip(lower=0)
    dn = -delta.clip(upper=0)
    roll_up = up.ewm(alpha=1 / n, adjust=False).mean()
    roll_dn = dn.ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + roll_up / roll_dn)


@indicator
def atr(high, low, close, n=14):
    """Wilder ATR(n) as a Series. (from the backtest scripts)."""
    prevc = close.shift(1)
    tr = np.maximum(high - low,
                    np.maximum((high - prevc).abs(), (low - prevc).abs()))
    return tr.ewm(alpha=1 / n, adjust=False).mean()


@indicator
def bollinger_bands(close, n, k=2):
    """Bollinger bands -> (mid, upper, lower). (from nq_regime_indicators)."""
    mid = close.rolling(n).mean()
    sd = close.rolling(n).std()
    return mid, mid + k * sd, mid - k * sd


@indicator
def bollinger_bandwidth(close, n, k=2):
    """Bollinger bandwidth % = (2*k*sd)/mid*100. (from nq_regime_indicators)."""
    mid = close.rolling(n).mean()
    sd = close.rolling(n).std()
    return (2 * k * sd) / mid * 100


@indicator
def adx(high, low, close, n=14):
    """Wilder ADX(n) -> (adx, plus_di, minus_di). (from nq_regime_indicators)."""
    def wilder(s):
        return s.ewm(alpha=1 / n, adjust=False).mean()
    upm = high.diff()
    dnm = -low.diff()
    plus_dm = np.where((upm > dnm) & (upm > 0), upm, 0.0)
    minus_dm = np.where((dnm > upm) & (dnm > 0), dnm, 0.0)
    prevc = close.shift(1)
    tr = np.maximum(high - low,
                    np.maximum((high - prevc).abs(), (low - prevc).abs()))
    atr_ = wilder(pd.Series(tr, index=close.index))
    plus_di = 100 * wilder(pd.Series(plus_dm, index=close.index)) / atr_
    minus_di = 100 * wilder(pd.Series(minus_dm, index=close.index)) / atr_
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
    return wilder(dx), plus_di, minus_di


@indicator
def ma_spread(mas, close):
    """Tier spread: (max-min across the given MAs)/close*100.
    ``mas`` is an iterable of MA Series. (from nq_slope_scan / nq_fractal)."""
    s = pd.concat(list(mas), axis=1)
    return (s.max(axis=1) - s.min(axis=1)) / close * 100


@indicator
def compression(spread, window=252, q=0.25):
    """Compression flag: spread below its rolling-window quantile (coiled)."""
    return spread < spread.rolling(window).quantile(q)
