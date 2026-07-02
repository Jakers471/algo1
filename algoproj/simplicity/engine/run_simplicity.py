"""
run_simplicity — fire up the SIMPLICITY engine.

Walks the strategy's execution pipeline IN SEQUENCE and reports, in colored text,
which stages are actually WIRED (a real module present in engine/) vs NOT WIRED.
It inspects ONLY engine/ -- never research/. A piece counts as wired only once it
has been confirmed and promoted here; until then the runner shows the gap. That is
the point: this is the live wiring tracker for the engine.

Everything is logged in sequence to the console (colored) and to a plain-text file
in engine/logs/. Use --debug to see WHY a stage isn't wired (missing file, import
error + traceback, missing interface) and the config TBD slots.

    run_engine.bat              # normal run
    run_engine.bat --debug      # verbose: what's not properly wired up
"""
import os
import re
import sys
import argparse
import importlib.util
from datetime import datetime

os.system("")  # enable ANSI colors on Windows terminals

ENGINE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(ENGINE))  # simplicity/
LOGDIR = os.path.join(ENGINE, "logs")
os.makedirs(LOGDIR, exist_ok=True)

# ---- colors (never emojis) --------------------------------------------------------
R = "\033[0m"; B = "\033[1m"; DIM = "\033[2m"
RED = "\033[31m"; GREEN = "\033[32m"; YEL = "\033[33m"; CYAN = "\033[36m"
MAG = "\033[35m"; GREY = "\033[90m"; WHITE = "\033[97m"
_ANSI = re.compile(r"\033\[[0-9;]*m")

# ---- the engine execution pipeline (sequence). module = expected file in engine/ --
PIPELINE = [
    ("data_feed",        "market data feed (bars in)"),
    ("vol_filter",       "calendar volatility gate  --  WHEN to trade"),
    ("session_anchors",  "session high/low anchors (London / NY / Asia)"),
    ("volume_profile",   "volume profile + POC / value area  --  the zone"),
    ("shape_filter",     "profile shape / tightness rejection"),
    ("zone_calibration", "zone height% / duration -> timeframe + stop / R:R"),
    ("entry",            "entry trigger (value-area breakout + volume confirm)"),
    ("risk",             "position sizing / risk management"),
    ("execution",        "order routing / fills (commission, slippage)"),
    ("trailing_stop",    "aggressive trailing stop management"),
]


class Log:
    def __init__(self, debug):
        self.debug = debug
        self.path = os.path.join(LOGDIR, "simplicity_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".log")
        self.f = open(self.path, "w", encoding="utf-8")

    def _w(self, level, line):
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"{GREY}{ts}{R} {line}")
        self.f.write(f"{ts} {level:<5} {_ANSI.sub('', line)}\n"); self.f.flush()

    def info(self, m):  self._w("INFO", f"{CYAN}INFO {R} {m}")
    def ok(self, m):    self._w("OK",   f"{GREEN}OK   {R} {m}")
    def warn(self, m):  self._w("WARN", f"{YEL}WARN {R} {m}")
    def err(self, m):   self._w("ERR",  f"{RED}ERR  {R} {m}")
    def dbg(self, m):
        if self.debug:
            self._w("DEBUG", f"{MAG}DEBUG{R} {DIM}{m}{R}")


def _check(module):
    """Inspect engine/<module>.py: ('missing'|'error'|'wired', detail)."""
    p = os.path.join(ENGINE, module + ".py")
    if not os.path.exists(p):
        return "missing", f"engine/{module}.py not found"
    try:
        spec = importlib.util.spec_from_file_location("engine_" + module, p)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
    except Exception as e:
        return "error", f"{type(e).__name__}: {e}"
    if hasattr(m, "check"):
        try:
            return "wired", m.check()
        except Exception as e:
            return "wired", f"imported; check() FAILED: {e}"
    return "wired", getattr(m, "DESCRIBE", "imported ok")


def banner(log):
    log._w("INFO", f"{B}{CYAN}========================================================{R}")
    log._w("INFO", f"{B}{WHITE}  SIMPLICITY ENGINE{R}   {DIM}starting up{R}")
    log._w("INFO", f"{B}{CYAN}========================================================{R}")


def config_stage(log):
    log.info("stage 00  " + f"{B}config{R}  loading strategy_config (single source of truth)")
    try:
        import strategy_config as cfg
    except Exception as e:
        log.err(f"could not import strategy_config: {e}")
        return None
    log.ok(f"config loaded  |  instrument={cfg.INSTRUMENT}  era>={cfg.ERA_START_YEAR}  "
           f"vol={cfg.VOL_METRIC}/{cfg.TRAIL_WINDOW}d")
    log.dbg(f"data_dir = {cfg.DATA_DIR}")
    log.dbg(f"costs: pt=${cfg.POINT_VALUE} tick={cfg.TICK} comm=${cfg.COMMISSION_PER_SIDE}/side "
            f"slip={cfg.SLIPPAGE_TICKS}t fill={cfg.FILL_RULE}")
    # flag TBD strategy slots (config-level, not engine wiring)
    tbd = [k for k, v in [("SIGNAL", cfg.SIGNAL), ("ENTRY.trigger", cfg.ENTRY.get("trigger")),
                          ("EXIT.stop", cfg.EXIT.get("stop")), ("RISK.sizing", cfg.RISK.get("sizing"))] if v is None]
    if tbd:
        log.warn(f"config slots still TBD: {', '.join(tbd)}")
    return cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug", action="store_true", help="show why stages are not wired")
    args = ap.parse_args()

    log = Log(args.debug)
    banner(log)
    if args.debug:
        log.dbg("debug mode ON  --  reporting engine wiring only (research/ is ignored)")
    cfg = config_stage(log)

    log.info(f"walking engine pipeline  ({len(PIPELINE)} stages)")
    wired = 0
    for i, (module, purpose) in enumerate(PIPELINE, 1):
        state, detail = _check(module)
        tag = f"stage {i:02d}  {B}{module}{R}"
        pad = " " * max(1, 18 - len(module))
        if state == "wired":
            wired += 1
            log.ok(f"{tag}{pad}{GREEN}WIRED    {R} {DIM}{purpose}{R}")
            log.dbg(f"  -> {detail}")
        elif state == "error":
            log.err(f"{tag}{pad}{RED}ERROR    {R} {DIM}{purpose}{R}")
            log.dbg(f"  -> import failed: {detail}")
        else:
            log.warn(f"{tag}{pad}{YEL}NOT WIRED{R} {DIM}{purpose}{R}")
            log.dbg(f"  -> {detail}  (promote from research/ when confirmed)")

    log._w("INFO", f"{B}{CYAN}--------------------------------------------------------{R}")
    color = GREEN if wired == len(PIPELINE) else (YEL if wired else RED)
    log._w("INFO", f"{B}WIRED {color}{wired}/{len(PIPELINE)}{R}{B} engine stages{R}")
    if wired < len(PIPELINE):
        log.info("engine is a skeleton -- promote confirmed pieces from research/ into engine/ (you decide when)")
    log.info(f"log saved: {GREY}{os.path.relpath(log.path, os.path.dirname(ENGINE))}{R}")


if __name__ == "__main__":
    main()
