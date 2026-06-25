import os
# project-relative so the whole algoproj/ folder is self-contained / portable
_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_ROOT, "NQdata")
VIX_CSV  = os.path.join(DATA_DIR, "VIX_History.csv")
OUTPUT_DIR = os.path.join(_ROOT, "output")
def data(name):   # convenience: absolute path to a data parquet
    return os.path.join(DATA_DIR, name)
def out(name):    # convenience: absolute path under output/
    return os.path.join(OUTPUT_DIR, name)
