"""緯度経度を含む CSV に国土数値情報の特徴量を付けて parquet で保存する。

例:
    python scripts/build_features.py data/raw/train.csv data/processed/train_ksj.parquet \
        --lat-col lat --lon-col lon --prefs 13 14
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from geocontest import ksj  # noqa: E402
from geocontest.features import build_ksj_features  # noqa: E402
from geocontest.mesh import latlon_to_mesh  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--lat-col", default="lat")
    ap.add_argument("--lon-col", default="lon")
    ap.add_argument("--id-col", default=None, help="出力に残す ID 列")
    ap.add_argument("--prefs", nargs="*", default=None, help="省略時は全国")
    ap.add_argument("--data-dir", default=str(ksj.DEFAULT_DATA_DIR))
    ap.add_argument("--include", nargs="*", default=None)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    df = pd.read_csv(args.input)
    lat, lon = df[args.lat_col], df[args.lon_col]
    kw = {"include": tuple(args.include)} if args.include else {}
    feats = build_ksj_features(lat, lon, prefs=args.prefs, data_dir=args.data_dir, **kw)
    feats.insert(0, "mesh1km", latlon_to_mesh(lat, lon, "1km"))
    feats.insert(1, "mesh500m", latlon_to_mesh(lat, lon, "500m"))
    if args.id_col:
        feats.insert(0, args.id_col, df[args.id_col].to_numpy())
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    feats.to_parquet(args.output, index=False)
    print(f"{feats.shape} -> {args.output}")


if __name__ == "__main__":
    main()
