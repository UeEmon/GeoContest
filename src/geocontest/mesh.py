"""地域メッシュコード（JIS X 0410）の変換。

レベル:
    1: 1次メッシュ（約80km, 4桁）
    2: 2次メッシュ（約10km, 6桁）
    3: 3次メッシュ（約1km, 8桁）
    4: 2分の1メッシュ（約500m, 9桁）
    5: 4分の1メッシュ（約250m, 10桁）
    6: 8分の1メッシュ（約125m, 11桁）

分割メッシュの末尾番号は 1=南西, 2=南東, 3=北西, 4=北東。
入力はスカラーでも配列でもよい（numpy でベクトル化している）。
"""

from __future__ import annotations

import numpy as np

# 各レベルのメッシュ 1 辺の大きさ（度）: (緯度, 経度)
_SIZE = {
    1: (40 / 60, 1.0),
    2: (5 / 60, 7.5 / 60),
    3: (30 / 3600, 45 / 3600),
}
for _lv in (4, 5, 6):
    _SIZE[_lv] = (_SIZE[_lv - 1][0] / 2, _SIZE[_lv - 1][1] / 2)

_DIGITS = {1: 4, 2: 6, 3: 8, 4: 9, 5: 10, 6: 11}
LEVEL_BY_NAME = {"1km": 3, "500m": 4, "250m": 5, "125m": 6, "10km": 2, "80km": 1}


def _level(level: int | str) -> int:
    lv = LEVEL_BY_NAME.get(level, level) if isinstance(level, str) else level
    if lv not in _DIGITS:
        raise ValueError(f"未対応のメッシュレベル: {level}")
    return lv


def latlon_to_mesh(lat, lon, level: int | str = 3):
    """緯度経度からメッシュコード（int64）を求める。"""
    lv = _level(level)
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    # 浮動小数点誤差でメッシュ境界上の点が南西側にずれないよう、ごく小さい値を足す
    eps = 1e-12
    p = lat * 1.5 + eps
    u = lon - 100 + eps
    p1 = np.floor(p)
    u1 = np.floor(u)
    code = (p1 * 100 + u1).astype(np.int64)
    if lv >= 2:
        q = (p - p1) * 8
        v = (u - u1) * 8
        q2, v2 = np.floor(q), np.floor(v)
        code = code * 100 + (q2 * 10 + v2).astype(np.int64)
    if lv >= 3:
        r = (q - q2) * 10
        w = (v - v2) * 10
        r3, w3 = np.floor(r), np.floor(w)
        code = code * 100 + (r3 * 10 + w3).astype(np.int64)
        fr, fw = r - r3, w - w3
        for _ in range(lv - 3):
            fr *= 2
            fw *= 2
            n = np.floor(fr)
            e = np.floor(fw)
            code = code * 10 + (n * 2 + e + 1).astype(np.int64)
            fr -= n
            fw -= e
    return code if code.ndim else int(code)


def mesh_level(code) -> int:
    n = len(str(int(code)))
    for lv, d in _DIGITS.items():
        if d == n:
            return lv
    raise ValueError(f"メッシュコードの桁数が不正: {code}")


def mesh_to_sw(code):
    """メッシュの南西端の (lat, lon) を返す。同じレベルのコード配列に対応。"""
    codes = np.atleast_1d(np.asarray(code, dtype=np.int64))
    lv = mesh_level(codes[0])
    s = codes.astype(str)
    lat = np.array([int(x[0:2]) for x in s], dtype=float) / 1.5
    lon = np.array([int(x[2:4]) for x in s], dtype=float) + 100
    if lv >= 2:
        lat += np.array([int(x[4]) for x in s]) * _SIZE[2][0]
        lon += np.array([int(x[5]) for x in s]) * _SIZE[2][1]
    if lv >= 3:
        lat += np.array([int(x[6]) for x in s]) * _SIZE[3][0]
        lon += np.array([int(x[7]) for x in s]) * _SIZE[3][1]
    for i, sub in enumerate(range(4, lv + 1)):
        d = np.array([int(x[8 + i]) for x in s]) - 1
        lat += (d // 2) * _SIZE[sub][0]
        lon += (d % 2) * _SIZE[sub][1]
    if np.ndim(code) == 0:
        return float(lat[0]), float(lon[0])
    return lat, lon


def mesh_to_center(code):
    """メッシュ中心の (lat, lon) を返す。"""
    lv = mesh_level(np.atleast_1d(code)[0])
    lat, lon = mesh_to_sw(code)
    return lat + _SIZE[lv][0] / 2, lon + _SIZE[lv][1] / 2


def mesh_to_bounds(code):
    """(min_lon, min_lat, max_lon, max_lat) を返す（shapely.box にそのまま渡せる順）。"""
    lv = mesh_level(np.atleast_1d(code)[0])
    lat, lon = mesh_to_sw(code)
    return lon, lat, lon + _SIZE[lv][1], lat + _SIZE[lv][0]


def mesh_to_polygons(codes, crs: str = "EPSG:4326"):
    """メッシュコード配列から GeoDataFrame（mesh_code, geometry）を作る。"""
    import geopandas as gpd
    import shapely

    codes = np.asarray(codes, dtype=np.int64)
    minx, miny, maxx, maxy = mesh_to_bounds(codes)
    geom = shapely.box(minx, miny, maxx, maxy)
    return gpd.GeoDataFrame({"mesh_code": codes}, geometry=geom, crs=crs)


def parent_mesh(code, level: int | str):
    """上位レベルのメッシュコードに切り詰める。"""
    lv = _level(level)
    codes = np.asarray(code, dtype=np.int64)
    cur = mesh_level(np.atleast_1d(codes)[0])
    if lv > cur:
        raise ValueError("下位レベルへの変換はできません")
    out = codes // (10 ** (_DIGITS[cur] - _DIGITS[lv]))
    return out if out.ndim else int(out)
