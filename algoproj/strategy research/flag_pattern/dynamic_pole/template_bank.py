"""
Parametric flag template BANK — many shape variations for SEED_MODE="bank".

Instead of one perfect template, generate a bank of slightly-tweaked flag SHAPES and let each
window keep its BEST (min) distance across the bank, so a flag that matches ANY variation seeds.
We vary only SHAPE — pole:flag ratio, pole curvature, flag drift — NOT size (magnitude-free norm
already covers it) nor total length (the dynamic trace covers it). Each template is WINDOW bars in
"% from window open" space, same as the hand-drawn one.
"""
import numpy as np

POLE_H = 0.005   # nominal pole height; normalized away at match time, just sets shape proportions
WICK = 0.0007    # small wick/body so templates read as candles


def make_flag(pole_bars, flag_bars, pole_curve, flag_slope):
    """One (pole_bars+flag_bars, 4) OHLC template. pole rises 0->H with curvature; flag drifts."""
    t = np.linspace(0.0, 1.0, pole_bars)
    pole = POLE_H * (t ** pole_curve)                     # rise to H, curved (concave/convex)
    ft = np.linspace(0.0, 1.0, flag_bars)
    flag = POLE_H + flag_slope * POLE_H * ft              # drift from the pole top
    close = np.concatenate([pole, flag])
    o = np.concatenate([[0.0], close[:-1]])               # open = previous close
    hi = np.maximum(o, close) + WICK * 0.5
    lo = np.minimum(o, close) - WICK * 0.5
    return np.stack([o, hi, lo, close], axis=1)


def make_bank(window, pole_bars_list, curve_list, slope_list):
    """Cartesian sweep of the shape knobs -> a list of variation dicts (bull + mirrored bear)."""
    bank = []
    for pb in pole_bars_list:
        for curve in curve_list:
            for slope in slope_list:
                bull = make_flag(pb, window - pb, curve, slope)
                bear = -bull[:, [0, 2, 1, 3]]             # mirror: down move, high/low swapped
                bank.append({"name": f"p{pb}/c{curve}/s{slope:+.2f}", "pole_bars": pb,
                             "curve": curve, "slope": slope, "bull": bull, "bear": bear})
    return bank
