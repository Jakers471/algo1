"""
build_chart_data — cache OHLCV for the fresh tv chart (fast multi-timeframe loads).

Exports the last MAX_BARS bars of each timeframe (NQ + ES) to JSON so the chart loads
instantly and never touches the big parquets at view time. Also writes a manifest with
the strategy_config snapshot + the ACTIVE_FILTER's selected days (for the overlay).

Run:  python research/chart/build_chart_data.py
Out:  research/chart/data/<INST>_<tf>.json  +  manifest.json
"""
import os
import sys
import json
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, SIM)
sys.path.insert(0, os.path.join(SIM, "research", "gates", "volatility_filter"))
sys.path.insert(0, os.path.join(SIM, "research", "gates", "profile_shape_filter"))
sys.path.insert(0, os.path.join(SIM, "research", "gates", "zone_calibration"))
sys.path.insert(0, os.path.join(SIM, "research", "structure", "base_profile"))
sys.path.insert(0, os.path.join(SIM, "research", "structure", "htf_profile"))
sys.path.insert(0, os.path.join(SIM, "research", "setup", "target_ladder"))
sys.path.insert(0, os.path.join(SIM, "research", "setup", "setup_arm"))
import strategy_config as cfg
import research_config as rcfg
import vol_filter as vf
import filter_variants as fvar
import shape_filter as sf
import zone_calibration as zc
import base_profile as bpm
import htf_profile as htfm
import target_ladder as tlm
import setup_arm as sarm
import config_panel as cpanel

DATA = os.path.join(HERE, "data")
os.makedirs(DATA, exist_ok=True)
MAX_BARS = 6000  # ~3x for more visible examples


def _series(df):
    t = (df.index.view("int64") // 1_000_000_000).tolist()
    o, h, l, c = df["open"].tolist(), df["high"].tolist(), df["low"].tolist(), df["close"].tolist()
    v = df["volume"].tolist()
    candles = [{"time": t[i], "open": o[i], "high": h[i], "low": l[i], "close": c[i], "volume": v[i]} for i in range(len(t))]
    up = "rgba(25,158,112,0.5)"; dn = "rgba(230,103,103,0.5)"
    vol = [{"time": t[i], "value": v[i], "color": up if c[i] >= o[i] else dn} for i in range(len(t))]
    return candles, vol


def main():
    series_meta = []
    data_range = None
    for inst, src in (("NQ", cfg.TF_SOURCES), ("ES", cfg.ES_SOURCES)):
        for tf, fname in src.items():
            p = os.path.join(cfg.DATA_DIR, fname)
            if not os.path.exists(p):
                continue
            df = pd.read_parquet(p)
            df.index = pd.DatetimeIndex(df.index)
            if inst == "NQ" and tf == "5m":         # TRUE full data range (before tailing) -> the run-window picker floor
                data_range = {"first": str(df.index[0])[:10], "last": str(df.index[-1])[:10]}
            df = df.tail(MAX_BARS)
            candles, vol = _series(df)
            key = f"{inst}_{tf}"
            json.dump({"candles": candles, "volume": vol},
                      open(os.path.join(DATA, key + ".json"), "w"))
            series_meta.append({"key": key, "instrument": inst, "tf": tf, "bars": len(df),
                                "first": str(df.index[0]), "last": str(df.index[-1])})

    # --- per-config day selection (vol-day overlay) so the chart can SELECT its config ---
    # REAL (strategy_config): the gate's day-vol regimes.  RESEARCH (research_config): ACTIVE_FILTER variant.
    base = vf.daily_frame()  # ordered daily regime table

    def _days_runs(sel_bool):
        b = base.assign(sel=sel_bool.to_numpy())
        days = b.loc[b["sel"], "date"].tolist()
        runs, run = [], None
        for r in b.itertuples():
            if r.sel:
                run = run or {"start": r.date, "end": r.date}
                run["end"] = r.date
            elif run:
                runs.append(run); run = None
        if run:
            runs.append(run)
        return days, runs

    real_days, real_runs = _days_runs(base["regime"].isin(cfg.FILTER_DAY_VOL["regimes"]))
    rsch_days, rsch_runs = _days_runs(base["regime"].isin(fvar.PRESETS[rcfg.ACTIVE_FILTER]))

    manifest = {
        "max_bars": MAX_BARS,
        "series": series_meta,
        "default_config": "research",
        # shared concrete snapshot (same for both configs)
        "config": {
            "instrument": cfg.INSTRUMENT, "clock": cfg.CLOCK,
            "era_start": cfg.ERA_START_YEAR, "vol_metric": cfg.VOL_METRIC,
            "trail_window": cfg.TRAIL_WINDOW, "regime_pctiles": list(cfg.REGIME_PCTILES),
            "sessions": {k: list(v) for k, v in cfg.SESSIONS.items()},
            "filter_session": cfg.FILTER_SESSION, "filter_hour": cfg.FILTER_HOUR,
            "filter_day_vol": cfg.FILTER_DAY_VOL,
            "point_value": cfg.POINT_VALUE, "tick": cfg.TICK,
            "commission_per_side": cfg.COMMISSION_PER_SIDE, "slippage_ticks": cfg.SLIPPAGE_TICKS,
            # gate params injected so the chart's JS recompute (replay/scoring) stays in sync with config
            "gates": {"SHAPE": cfg.SHAPE, "ZONE": cfg.ZONE, "BASE": cfg.BASE, "HTF": cfg.HTF,
                      "PROFILE": cfg.PROFILE, "LADDER": cfg.LADDER},
        },
        # per-config: what its vol-day overlay selects + its distinguishing knobs
        "configs": {
            "real": {"label": "real . strategy_config",
                     "note": "vol-days = FILTER_DAY_VOL regimes " + str(cfg.FILTER_DAY_VOL["regimes"]),
                     "selected_days": real_days, "selected_runs": real_runs},
            "research": {"label": "research . research_config",
                         "note": "variant=" + rcfg.ACTIVE_FILTER + "  |  start $" + f"{rcfg.STARTING_BALANCE:,}",
                         "selected_days": rsch_days, "selected_runs": rsch_runs},
        },
    }
    # session anchors overlay (from research/session_anchors; drawn on 1m/5m where times align)
    anc_path = os.path.join(HERE, "..", "structure", "session_anchors", "output", "session_anchors.json")
    levels, sessions, scolors, data_end = [], [], {}, 0
    if os.path.exists(anc_path):
        aj = json.load(open(anc_path))
        scolors = aj["colors"]; data_end = aj.get("data_end", 0)
        m5 = next((s for s in series_meta if s["key"] == "NQ_5m"), None)
        cutoff = int(pd.Timestamp(m5["first"]).timestamp()) if m5 else 0
        levels = [L for L in aj["levels"] if L["start"] >= cutoff]  # formed within the loaded window
        sessions = [S for S in aj.get("sessions", []) if S["open"] >= cutoff]
    manifest["levels"] = levels
    manifest["sessions"] = sessions
    manifest["session_colors"] = scolors
    manifest["data_end"] = data_end

    # volume profiles (Phase 3): per-session POC / value area, in the loaded window
    vp_path = os.path.join(HERE, "..", "structure", "volume_profile", "output", "volume_profile.json")
    profiles = []
    if os.path.exists(vp_path):
        m5 = next((s for s in series_meta if s["key"] == "NQ_5m"), None)
        cut = int(pd.Timestamp(m5["first"]).timestamp()) if m5 else 0
        profiles = [P for P in json.load(open(vp_path))["profiles"] if P["start"] >= cut]
        # enrich each session with shape + zone scores + timing (so a per-session module can show it)
        profiles.sort(key=lambda P: P["start"])
        for i, P in enumerate(profiles):
            P["shape"] = sf.score(P) or {}
            P["zone"] = zc.calibrate(P) or {}
            nxt = profiles[i + 1] if i + 1 < len(profiles) else None
            P["next_session"] = nxt["session"] if nxt else None
            P["next_open"] = nxt["start"] if nxt else None
            P["duration_sec"] = int(P["end"] - P["start"])
        # base_profile scale — OPT-IN: only load when strategy_config.BASE["on"] (else 5m session only)
        if cfg.BASE.get("on"):
            try:
                base_list, _ = bpm.compute(tail=8000)
                base_by = {b["sid"]: b for b in base_list}
                for P in profiles:
                    b = base_by.get(P["sid"])
                    if b:
                        b["shape"] = sf.score(b) or {}
                        b["zone"] = zc.calibrate(b) or {}
                        P["base"] = b
            except Exception as e:
                print("  base scale skipped:", e)
        # htf_profile scale — OPT-IN: only load when strategy_config.HTF["on"]
        if cfg.HTF.get("on"):
            try:
                htf_by = {h["sid"]: h for h in htfm.compute(since_ts=cut)}
                for P in profiles:
                    h = htf_by.get(P["sid"])
                    if h:
                        h["shape"] = sf.score(h) or {}
                        h["zone"] = zc.calibrate(h) or {}
                        P["htf"] = h
            except Exception as e:
                print("  htf scale skipped:", e)
        # multi-scale target ladder — needs the base scale (1R = the coil); only when BASE is on
        if cfg.BASE.get("on"):
            for P in profiles:
                L = tlm.ladder({"base": P.get("base"), "session": P, "htf": P.get("htf")})
                if L:
                    P["ladder"] = L
        n_base = sum(1 for P in profiles if P.get("base")); n_htf = sum(1 for P in profiles if P.get("htf"))
        print(f"  scales: session (5m) always · base {'ON ('+str(n_base)+')' if cfg.BASE.get('on') else 'off'}"
              f" · htf {'ON ('+str(n_htf)+')' if cfg.HTF.get('on') else 'off'}")
    manifest["profiles"] = profiles
    manifest["config_panel"] = cpanel.panel(cfg)
    manifest["data_range"] = data_range          # true full data range (for the run-window picker floor)

    # THE HUNT: every coil the strategy evaluated in the loaded window + its setup_arm verdict (armed vs rejected)
    hunt = []
    bp_path = os.path.join(HERE, "..", "structure", "base_profile", "output", "base_profile.json")
    if os.path.exists(bp_path):
        m5 = next((s for s in series_meta if s["key"] == "NQ_5m"), None)
        hcut = int(pd.Timestamp(m5["first"]).timestamp()) if m5 else 0
        for b in json.load(open(bp_path))["profiles"]:
            if int(b.get("start", 0)) < hcut:
                continue
            armed, why = sarm.decide(b, cfg=cfg)
            shp = sf.score(b) or {}
            zn = zc.calibrate(b) or {}
            hunt.append({"session": b["session"], "date": b["date"], "sid": b["sid"],
                         "start": int(b["start"]), "end": int(b["end"]),
                         "hi": round(b["high"], 2), "lo": round(b["low"], 2),
                         "shape": shp.get("shape_score"), "rr": zn.get("rr"),
                         "armed": bool(armed), "trade_open": why.get("trade_open"), "gates": why.get("gates")})
    manifest["hunt"] = hunt

    json.dump(manifest, open(os.path.join(DATA, "manifest.json"), "w"))
    print(f"wrote {len(series_meta)} series + manifest to {DATA}")
    for s in series_meta:
        print(f"  {s['key']:<8} {s['bars']:>5} bars  {s['first'][:10]}..{s['last'][:10]}")
    print(f"  real vol-days={len(real_days)} | research(active={rcfg.ACTIVE_FILTER}) vol-days={len(rsch_days)}")


if __name__ == "__main__":
    main()
