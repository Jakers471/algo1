"""
config_panel — build the chart sidebar's config view from a config module.

ONE definition, shared by build_chart_data (bakes it into the manifest) and serve.py
(serves it LIVE at /config so editing strategy_config + reloading the page updates the
sidebar without a rebuild). Takes the config module as an arg so serve.py can reload it.

Mirrors strategy_config's TIERS + STATUS tags:
    wired   (green)  changes a backtest number today
    sensor  (amber)  measured + drawn, but does NOT gate a trade yet (waits for setup_arm)
    chart   (blue)   affects the chart display only
    fact    (grey)   a market constant / definition
    unbuilt (red)    not built yet
"""


def _it(name, value, status):
    return {"name": name, "value": str(value), "status": status}


def panel(cfg):
    fs, fh, fd = cfg.FILTER_SESSION, cfg.FILTER_HOUR, cfg.FILTER_DAY_VOL
    return [
        {"title": "Control panel — the decisions", "items": [
            _it("era start", cfg.ERA_START_YEAR, "wired"),
            _it("session filter", ("on: " + ",".join(fs["allow"])) if fs["on"] else "off", "sensor"),
            _it("hour filter", "on" if fh["on"] else "off", "sensor"),
            _it("day-vol filter", (",".join(fd["regimes"])) if fd["on"] else "off", "sensor"),
            _it("gate · shape_ok", cfg.GATE_SHAPE_OK, "sensor"),
            _it("gate · rr_min", cfg.GATE_RR_MIN, "sensor"),
            _it("entry", f"{cfg.ENTRY['type']} · tf {cfg.ENTRY['entry_tf']} · win {cfg.ENTRY['entry_window_bars']}", "wired"),
            _it("min coil %", cfg.ENTRY["min_coil_pct"], "wired"),
            _it("stop", f"{cfg.EXIT['stop']} = 1R", "wired"),
            _it("take-profit", (f"trailing · arm {cfg.EXIT['trail_arm_r']} / gap {cfg.EXIT['trail_gap_r']}"
                                if cfg.EXIT['target'] == "trailing"
                                else f"{cfg.EXIT['target']} · {cfg.EXIT['target_r']}R"), "wired"),
            _it("time stop", f"{cfg.EXIT['max_hold_bars']} bars", "wired"),
            _it("risk %/trade", f"{cfg.RISK['risk_per_trade_pct']}%", "wired")]},
        {"title": "Structure — feeds backtest (rebuild JSON after edits)", "items": [
            _it("volume_profile · 5m", f"row {cfg.PROFILE['row_size']} · va {cfg.PROFILE['va_pct']}", "wired"),
            _it("base_profile", ("on" if cfg.BASE["on"] else "off (chart)") + f" · band {cfg.BASE['band_mult']} · min {cfg.BASE['min_bars']}", "wired"),
            _it("htf_profile", ("on -> ladder targets" if cfg.HTF["on"] else "off (not used)") + f" · days {cfg.HTF['days']} · bins {cfg.HTF['bins']}", "wired" if cfg.HTF["on"] else "sensor"),
            _it("target_ladder", f"min_rr {cfg.LADDER['min_rr']} · {'+'.join(cfg.LADDER['sources'])}", "wired"),
            _it("setup_arm", ("ON · " + "+".join(cfg.SETUP.get("gates", []))) if cfg.SETUP.get("on")
                else "built · off (base rate)", "wired" if cfg.SETUP.get("on") else "sensor")]},
        {"title": "Calibration — rarely touch", "items": [
            _it("shape weights", "·".join(str(v) for v in cfg.SHAPE["weights"].values()), "sensor"),
            _it("shape curve", f"peak {cfg.SHAPE['tight_peak']} · hi {cfg.SHAPE['tight_hi']} · prom {cfg.SHAPE['prom_den']}", "sensor"),
            _it("zone tf-bands", f"{len(cfg.ZONE['tf_bands'])} bands", "sensor"),
            _it("fib zones", f"{len(cfg.FIB['edges']) - 1}", "sensor"),
            _it("day-vol regime", f"{cfg.VOL_METRIC} · {cfg.TRAIL_WINDOW}d · {cfg.REGIME_PCTILES}", "sensor")]},
        {"title": "Facts — never touch", "items": [
            _it("instrument", cfg.INSTRUMENT, "fact"),
            _it("sessions", "4 (ET)", "fact"),
            _it("costs", f"${cfg.COMMISSION_PER_SIDE}/side · {cfg.SLIPPAGE_TICKS} tick · ${cfg.POINT_VALUE}/pt", "fact")]},
    ]
