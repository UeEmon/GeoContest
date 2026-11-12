"""地点（緯度経度）に周辺の地理空間情報を結び付ける特徴量関数。

距離は BallTree（haversine）で計算するので、全国規模の点群でも速い。
入力の ``lat`` / ``lon`` は度、出力の距離はメートル。
"""

from __future__ import annotations

from collections.abc import Sequence

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

EARTH_RADIUS_M = 6_371_008.8


def _rad(lat, lon) -> np.ndarray:
    return np.deg2rad(np.column_stack([np.asarray(lat, float), np.asarray(lon, float)]))


def representative_latlon(gdf: gpd.GeoDataFrame) -> tuple[np.ndarray, np.ndarray]:
    """点ならその座標、線・面なら内部の代表点の緯度経度を返す。"""
    geom = gdf.geometry
    if not (geom.geom_type == "Point").all():
        geom = geom.representative_point()
    return geom.y.to_numpy(), geom.x.to_numpy()


class PointIndex:
    """参照点群（駅・施設など）の近傍検索用インデックス。"""

    def __init__(self, lat, lon, values: pd.DataFrame | None = None):
        lat = np.asarray(lat, float)
        lon = np.asarray(lon, float)
        ok = np.isfinite(lat) & np.isfinite(lon)
        self.tree = BallTree(_rad(lat[ok], lon[ok]), metric="haversine")
        self.values = None if values is None else values.loc[ok].reset_index(drop=True)
        self.n = int(ok.sum())

    @classmethod
    def from_gdf(cls, gdf: gpd.GeoDataFrame, value_cols: Sequence[str] = ()) -> "PointIndex":
        lat, lon = representative_latlon(gdf)
        vals = gdf[list(value_cols)].reset_index(drop=True) if value_cols else None
        return cls(lat, lon, vals)

    def nearest(self, lat, lon, k: int = 1) -> tuple[np.ndarray, np.ndarray]:
        """最近傍 k 件の (距離[m], インデックス) を返す。形は (n, k)。"""
        k = min(k, self.n)
        dist, idx = self.tree.query(_rad(lat, lon), k=k)
        return dist * EARTH_RADIUS_M, idx

    def within(self, lat, lon, radius_m: float):
        """半径内の参照点インデックスのリスト（と距離）を返す。"""
        idx, dist = self.tree.query_radius(_rad(lat, lon), r=radius_m / EARTH_RADIUS_M, return_distance=True)
        return idx, [d * EARTH_RADIUS_M for d in dist]


def nearest_features(
    lat,
    lon,
    index: PointIndex,
    prefix: str,
    k: int = 1,
    value_cols: Sequence[str] = (),
) -> pd.DataFrame:
    """最近傍 k 件までの距離と、最近傍 1 件の属性値を返す。

    出力列: ``{prefix}_dist1`` ... ``{prefix}_dist{k}``, ``{prefix}_nn_{col}``
    """
    dist, idx = index.nearest(lat, lon, k=k)
    out = {f"{prefix}_dist{i + 1}": dist[:, i] for i in range(dist.shape[1])}
    for c in value_cols:
        if index.values is None or c not in index.values:
            raise KeyError(f"PointIndex に列 {c} がありません")
        out[f"{prefix}_nn_{c}"] = index.values[c].to_numpy()[idx[:, 0]]
    return pd.DataFrame(out)


def radius_features(
    lat,
    lon,
    index: PointIndex,
    prefix: str,
    radii_m: Sequence[float] = (250, 500, 1000, 2000),
    sum_cols: Sequence[str] = (),
    decay_m: float | None = None,
) -> pd.DataFrame:
    """半径ごとの件数と、指定列の合計（例: 乗降客数の合計）を返す。

    ``decay_m`` を指定すると、最大半径内で ``exp(-d/decay_m)`` で重み付けした合計
    （アクセシビリティ指標）も ``{prefix}_{col}_decay{decay_m}`` として出す。
    """
    out: dict[str, np.ndarray] = {}
    vals = {c: index.values[c].to_numpy(dtype=float) for c in sum_cols} if sum_cols else {}
    rmax = max(radii_m)
    idx_list, dist_list = index.within(lat, lon, rmax)
    n = len(idx_list)
    for r in radii_m:
        cnt = np.zeros(n)
        sums = {c: np.zeros(n) for c in sum_cols}
        for i, (ids, ds) in enumerate(zip(idx_list, dist_list)):
            m = ds <= r
            cnt[i] = m.sum()
            for c in sum_cols:
                sums[c][i] = np.nansum(vals[c][ids[m]])
        out[f"{prefix}_cnt_{int(r)}m"] = cnt
        for c in sum_cols:
            out[f"{prefix}_{c}_sum_{int(r)}m"] = sums[c]
    if decay_m:
        for c in sum_cols:
            acc = np.zeros(n)
            for i, (ids, ds) in enumerate(zip(idx_list, dist_list)):
                acc[i] = np.nansum(vals[c][ids] * np.exp(-ds / decay_m))
            out[f"{prefix}_{c}_decay{int(decay_m)}"] = acc
    return pd.DataFrame(out)


def polygon_attributes(lat, lon, polygons: gpd.GeoDataFrame, cols: Sequence[str], prefix: str) -> pd.DataFrame:
    """点が含まれるポリゴン（用途地域など）の属性を返す。含まれなければ NaN。

    ポリゴンが重なっている場合は最初に見つかった 1 件を使う。
    """
    pts = gpd.GeoDataFrame(
        {"_row": np.arange(len(np.atleast_1d(lat)))},
        geometry=gpd.points_from_xy(np.asarray(lon, float), np.asarray(lat, float)),
        crs="EPSG:4326",
    )
    poly = polygons[list(cols) + ["geometry"]].to_crs("EPSG:4326")
    joined = gpd.sjoin(pts, poly, how="left", predicate="within").drop_duplicates("_row").sort_values("_row")
    return pd.DataFrame({f"{prefix}_{c}": joined[c].to_numpy() for c in cols})


def mesh_join(lat, lon, mesh_table: pd.DataFrame, mesh_col: str, value_cols: Sequence[str], level, prefix: str) -> pd.DataFrame:
    """点のメッシュコードを計算し、メッシュ単位の表（人口など）を結合する。"""
    from .mesh import latlon_to_mesh

    codes = np.atleast_1d(latlon_to_mesh(lat, lon, level))
    tbl = mesh_table[[mesh_col, *value_cols]].copy()
    tbl[mesh_col] = pd.to_numeric(tbl[mesh_col], errors="coerce").astype("Int64")
    tbl = tbl.drop_duplicates(mesh_col).set_index(mesh_col)
    res = tbl.reindex(pd.Index(codes, dtype="Int64"))
    res.columns = [f"{prefix}_{c}" for c in value_cols]
    return res.reset_index(drop=True)
