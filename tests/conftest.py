"""本物の配布 zip と同じ構造（UTF-8/Shift-JIS の二重格納、\\ 区切りのパスなど）を持つ小さな偽データを作る。"""

import json
import zipfile
from pathlib import Path

import pytest

from geocontest.ksj_catalog import DATASETS
from geocontest.mesh import latlon_to_mesh, mesh_to_bounds

CENTER = (35.681236, 139.767125)  # 東京駅


def _fc(features):
    return json.dumps(
        {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::6668"}},
            "features": features,
        },
        ensure_ascii=False,
    )


def _pt(lat, lon, props):
    return {"type": "Feature", "properties": props, "geometry": {"type": "Point", "coordinates": [lon, lat]}}


def _line(lat, lon, props):
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "LineString", "coordinates": [[lon - 0.001, lat], [lon + 0.001, lat]]},
    }


def _box(minx, miny, maxx, maxy, props):
    ring = [[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny]]
    return {"type": "Feature", "properties": props, "geometry": {"type": "Polygon", "coordinates": [ring]}}


def _write(data_dir: Path, key: str, members: dict[str, str], pref="13"):
    ds = DATASETS[key]
    url = ds.url(pref if ds.file_pref else None)
    out = data_dir / key / url.rsplit("/", 1)[-1]
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w") as zf:
        for name, text in members.items():
            zf.writestr(name, text.encode("utf-8"))


@pytest.fixture
def fake_ksj(tmp_path) -> Path:
    lat0, lon0 = CENTER
    st = [
        _line(lat0, lon0, {"S12_001": "東京", "S12_001g": "g1", "S12_003": "A線", "S12_057": 400000, "S12_061": 0}),
        _line(lat0, lon0 + 0.0005, {"S12_001": "東京", "S12_001g": "g1", "S12_003": "B線", "S12_057": 1, "S12_061": 100000}),
        _line(lat0 + 0.01, lon0, {"S12_001": "神田", "S12_001g": "g2", "S12_003": "A線", "S12_057": 5, "S12_061": 50000}),
    ]
    fc = _fc(st)
    _write(tmp_path, "station_passengers", {
        "S12-25_GML/UTF-8/S12-25_NumberOfPassengers.geojson": fc,
        "S12-25_GML/Shift-JIS/S12-25_NumberOfPassengers.geojson": fc,  # 重複して読まないこと
    })
    code = latlon_to_mesh(lat0, lon0, "500m")
    minx, miny, maxx, maxy = mesh_to_bounds(code)
    _write(tmp_path, "pop_mesh500", {
        "500m_mesh_2024_13_GEOJSON/500m_mesh_2024_13.geojson": _fc(
            [_box(minx, miny, maxx, maxy, {"MESH_ID": str(code), "SHICODE": "13101", "PTN_2020": 123.0, "PTN_2025": 120.0})]
        )
    })
    _write(tmp_path, "land_price", {
        "L01-25_13_GML/L01-25_13.geojson": _fc([_pt(lat0 + 0.001, lon0, {"L01_001": "13101", "L01_008": 3960000})])
    })
    _write(tmp_path, "bus_stop", {"P11-22_13_SHP/P11-22_13.geojson": _fc([_pt(lat0, lon0 + 0.001, {"P11_001": "駅前"})])})
    _write(tmp_path, "medical", {"P04-20_13_GML\\P04-20_13.geojson": _fc([_pt(lat0, lon0 - 0.002, {"P04_001": 1})])})
    _write(tmp_path, "school", {"P29-23_13_GML/P29-23_13.geojson": _fc([_pt(lat0 - 0.003, lon0, {"P29_003": "16011"})])})
    _write(tmp_path, "zoning", {
        "A29-19_13_GML/A29-19_13101.geojson": _fc(
            [_box(lon0 - 0.01, lat0 - 0.01, lon0 + 0.01, lat0 + 0.01, {"A29_004": 9, "A29_006": 80, "A29_007": 800})]
        )
    })
    return tmp_path
