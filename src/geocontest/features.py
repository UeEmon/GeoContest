"""国土数値情報から地点ごとの特徴量をまとめて作る。

使い方::

    from geocontest.features import build_ksj_features
    feats = build_ksj_features(df["lat"], df["lon"], prefs=["13", "14"])

コンペのデータが公開されたら、目的変数の単位（地点・メッシュ・駅など）に合わせて
``FEATURE_SPECS`` の半径や使うデータを調整する。
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from . import ksj, spatial

log = logging.getLogger(__name__)


def station_table(data_dir=ksj.DEFAULT_DATA_DIR) -> pd.DataFrame:
    """駅別乗降客数を駅グループ（乗換駅をまとめた単位）ごとに集計した表。

    同じ駅でも路線・事業者ごとに行が分かれているので、グループコードで合算する。
    最新年の値が 0（非公表など）なら前年の値で補う。
    """
    gdf = ksj.load("station_passengers", data_dir=data_dir)
    lat, lon = spatial.representative_latlon(gdf)
    df = pd.DataFrame({"lat": lat, "lon": lon})
    years = [c for c in ["passengers_2024", "passengers_2023", "passengers_2022", "passengers_2021"] if c in gdf]
    pax = np.zeros(len(gdf))
    for c in reversed(years):  # 古い年 -> 新しい年 の順で上書き
        v = pd.to_numeric(gdf[c], errors="coerce").fillna(0).to_numpy()
        pax = np.where(v > 0, v, pax)
    df["passengers"] = pax
    df["n_lines"] = 1
    key = "station_group_code" if "station_group_code" in gdf else "station_name"
    df["group"] = gdf[key].to_numpy()
    df["station_name"] = gdf.get("station_name", pd.Series([""] * len(gdf))).to_numpy()
    return df.groupby("group", as_index=False).agg(
        lat=("lat", "mean"),
        lon=("lon", "mean"),
        passengers=("passengers", "sum"),
        n_lines=("n_lines", "sum"),
        station_name=("station_name", "first"),
    )


def _point_dataset_features(lat, lon, key, prefs, data_dir, prefix, radii, k=1) -> pd.DataFrame:
    gdf = ksj.load(key, prefs=prefs, data_dir=data_dir)
    idx = spatial.PointIndex.from_gdf(gdf)
    return pd.concat(
        [
            spatial.nearest_features(lat, lon, idx, prefix, k=k),
            spatial.radius_features(lat, lon, idx, prefix, radii_m=radii),
        ],
        axis=1,
    )


def build_ksj_features(
    lat,
    lon,
    prefs: list[str] | None = None,
    data_dir: Path | str = ksj.DEFAULT_DATA_DIR,
    include: tuple[str, ...] = ("station", "population", "land_price", "bus_stop", "medical", "school", "zoning"),
) -> pd.DataFrame:
    """地点ごとの特徴量 DataFrame を返す（行順は入力と同じ）。

    ``prefs`` は都道府県コード（"13" など）のリスト。None なら全国版ファイルを使う
    （全国版がないデータセットは全都道府県を読む）。
    """
    lat = np.asarray(lat, float)
    lon = np.asarray(lon, float)
    parts: list[pd.DataFrame] = []

    def pref_list(key):
        ds = ksj.get_dataset(key)
        if prefs is None and ds.file_national is None:
            from .ksj_catalog import PREF_CODES

            return PREF_CODES
        return prefs

    if "station" in include:
        log.info("station")
        st = station_table(data_dir)
        idx = spatial.PointIndex(st["lat"], st["lon"], st[["passengers", "n_lines"]])
        parts.append(spatial.nearest_features(lat, lon, idx, "station", k=3, value_cols=["passengers", "n_lines"]))
        parts.append(
            spatial.radius_features(
                lat, lon, idx, "station", radii_m=(500, 1000, 2000, 5000), sum_cols=["passengers"], decay_m=1000
            )
        )

    if "population" in include:
        log.info("population")
        pop = ksj.load("pop_mesh500", prefs=pref_list("pop_mesh500"), data_dir=data_dir)
        pop_cols = [c for c in ["pop_2020", "pop_2025"] if c in pop]
        parts.append(spatial.mesh_join(lat, lon, pop, "mesh_code", pop_cols, "500m", "mesh500"))
        # 周辺人口（メッシュ中心を点とみなして半径内合計）
        plat, plon = spatial.representative_latlon(pop)
        pidx = spatial.PointIndex(plat, plon, pop[pop_cols].apply(pd.to_numeric, errors="coerce").reset_index(drop=True))
        parts.append(spatial.radius_features(lat, lon, pidx, "pop", radii_m=(1000, 2000, 5000), sum_cols=pop_cols[:1]))

    if "land_price" in include:
        log.info("land_price")
        lp = ksj.load("land_price", prefs=pref_list("land_price"), data_dir=data_dir)
        lp["price_per_m2"] = pd.to_numeric(lp["price_per_m2"], errors="coerce")
        idx = spatial.PointIndex.from_gdf(lp, ["price_per_m2"])
        nn = spatial.nearest_features(lat, lon, idx, "landprice", k=3, value_cols=["price_per_m2"])
        parts.append(nn)

    for key, prefix, radii in [
        ("bus_stop", "bus", (250, 500, 1000)),
        ("medical", "medical", (500, 1000, 2000)),
        ("school", "school", (500, 1000, 2000)),
    ]:
        if key in include:
            log.info(key)
            parts.append(_point_dataset_features(lat, lon, key, pref_list(key), data_dir, prefix, radii))

    if "zoning" in include:
        log.info("zoning")
        zn = ksj.load("zoning", prefs=pref_list("zoning"), data_dir=data_dir)
        cols = [c for c in ["zoning_code", "coverage_ratio", "floor_area_ratio"] if c in zn]
        parts.append(spatial.polygon_attributes(lat, lon, zn, cols, "zoning"))

    return pd.concat(parts, axis=1)
