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
def ema(close, n):
    """Exponential moving average, span n (adjust=False, same as LEAN/TradingView)."""
    return close.ewm(span=int(n), adjust=False).mean()


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
def frama(high, low, n=16, long_period=198):
    """Ehlers' Fractal Adaptive Moving Average (FRAMA).

    Ported from QuantConnect LEAN's FractalAdaptiveMovingAverage. The smoothing
    ``alpha`` adapts to the fractal dimension of the last ``n`` bars (``n`` must
    be even): trending -> fast, choppy -> slow. ``long_period`` sets the slowest
    MA. The first ``n`` bars return the median price (warm-up identity).
    """
    if n % 2:
        raise ValueError(f"FRAMA n must be even, got {n}")
    h = pd.Series(np.asarray(high, dtype=float))
    l = pd.Series(np.asarray(low, dtype=float))
    price = ((h + l) / 2.0).to_numpy()
    half = n // 2
    # three box-count "lengths" over the recent half, older half, and full window
    hh1, ll1 = h.rolling(half).max().to_numpy(), l.rolling(half).min().to_numpy()
    hh2 = h.rolling(half).max().shift(half).to_numpy()
    ll2 = l.rolling(half).min().shift(half).to_numpy()
    hhN, llN = h.rolling(n).max().to_numpy(), l.rolling(n).min().to_numpy()
    n1 = (hh1 - ll1) / half
    n2 = (hh2 - ll2) / half
    n3 = (hhN - llN) / n
    w = np.log(2.0 / (1 + long_period))
    with np.errstate(divide="ignore", invalid="ignore"):
        dimen = np.where((n1 + n2 > 0) & (n3 > 0), np.log((n1 + n2) / n3) / np.log(2), 0.0)
    dimen = np.nan_to_num(dimen, nan=0.0)
    alpha = np.clip(np.exp(w * (dimen - 1)), 0.01, 1.0)
    out = np.full(len(price), np.nan)
    for i in range(len(price)):
        out[i] = price[i] if i < n else alpha[i] * price[i] + (1 - alpha[i]) * out[i - 1]
    return pd.Series(out, index=high.index)


@indicator
def frama_channel(high, low, n=26, distance=1.5, smooth=5, vol_len=200):
    """FRAMA Channel (BigBeluga) -> (mid, upper, lower).

    Ported from BigBeluga's TradingView Pine v5 "FRAMA Channel". A recursive
    FRAMA on hl2 with a fixed -4.6 alpha constant, additionally smoothed by a
    ``smooth``-bar SMA (the recursion feeds on the smoothed prior value), then
    wrapped in a volatility channel at +/- ``distance`` * SMA(high-low, vol_len).

    Attribution: © BigBeluga, CC BY-NC-SA 4.0
    (https://creativecommons.org/licenses/by-nc-sa/4.0/).
    """
    if n % 2:
        raise ValueError(f"FRAMA Channel n must be even, got {n}")
    h = pd.Series(np.asarray(high, dtype=float))
    l = pd.Series(np.asarray(low, dtype=float))
    price = ((h + l) / 2.0).to_numpy()                       # hl2
    half = n // 2
    hh1, ll1 = h.rolling(half).max().to_numpy(), l.rolling(half).min().to_numpy()
    hh2 = h.rolling(half).max().shift(half).to_numpy()
    ll2 = l.rolling(half).min().shift(half).to_numpy()
    hhN, llN = h.rolling(n).max().to_numpy(), l.rolling(n).min().to_numpy()
    n1 = (hh1 - ll1) / half
    n2 = (hh2 - ll2) / half
    n3 = (hhN - llN) / n
    with np.errstate(divide="ignore", invalid="ignore"):
        dimen = np.where((n1 > 0) & (n2 > 0) & (n3 > 0),
                         (np.log(n1 + n2) - np.log(n3)) / np.log(2), 0.0)
    dimen = np.nan_to_num(dimen, nan=0.0)
    alpha = np.clip(np.exp(-4.6 * (dimen - 1)), 0.01, 1.0)   # fixed -4.6 (BigBeluga)

    L = len(price)
    final = np.full(L, np.nan)   # the smoothed FRAMA that the recursion feeds on
    src = np.full(L, np.nan)     # raw recursive value (pre-smoothing), = price during warm-up
    for i in range(L):
        raw = price[i] if (i == 0 or np.isnan(final[i - 1])) \
            else alpha[i] * price[i] + (1 - alpha[i]) * final[i - 1]
        src[i] = price[i] if i < n + 1 else raw
        if i >= smooth - 1:
            final[i] = src[i - smooth + 1:i + 1].mean()

    mid = pd.Series(final, index=high.index)
    vol = (h - l).rolling(vol_len).mean()
    vol.index = high.index
    return mid, mid + vol * distance, mid - vol * distance


@indicator
def vwap(high, low, close, volume, k=1.0, anchor="D"):
    """Session-anchored VWAP with volume-weighted std bands -> (vwap, upper, lower).

    Typical price (H+L+C)/3 weighted by volume, cumulative within each session and
    reset at every ``anchor`` boundary (default "D" = UTC day). ``k`` sets the band
    width in volume-weighted standard deviations. Requires a DatetimeIndex.
    """
    tp = (high + low + close) / 3.0
    grp = high.index.floor(anchor)                      # session id (resets the cumsum)
    v = volume.astype(float)
    cum_v = v.groupby(grp).cumsum()
    vwap_ = (tp * v).groupby(grp).cumsum() / cum_v
    var = (tp * tp * v).groupby(grp).cumsum() / cum_v - vwap_ ** 2
    std = np.sqrt(var.clip(lower=0))
    return vwap_, vwap_ + k * std, vwap_ - k * std


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
