import numpy as np
import pytest

from geocontest.mesh import latlon_to_mesh, mesh_to_bounds, mesh_to_center, mesh_to_polygons, parent_mesh

TOKYO_STATION = (35.681236, 139.767125)


@pytest.mark.parametrize(
    "level,expected",
    [(1, 5339), (2, 533946), (3, 53394611), ("500m", 533946113), ("250m", 5339461132)],
)
def test_tokyo_station(level, expected):
    assert latlon_to_mesh(*TOKYO_STATION, level) == expected


def test_vectorized_and_roundtrip():
    rng = np.random.default_rng(0)
    lat = rng.uniform(24, 45, 1000)
    lon = rng.uniform(123, 146, 1000)
    for lv in (1, 2, 3, 4, 5, 6):
        codes = latlon_to_mesh(lat, lon, lv)
        minx, miny, maxx, maxy = mesh_to_bounds(codes)
        assert np.all((lon >= minx - 1e-9) & (lon < maxx + 1e-9))
        assert np.all((lat >= miny - 1e-9) & (lat < maxy + 1e-9))
        clat, clon = mesh_to_center(codes)
        np.testing.assert_array_equal(latlon_to_mesh(clat, clon, lv), codes)


def test_boundary_point_goes_north_east():
    # 3次メッシュ境界ちょうどの点は北東側のメッシュに入る
    lat, lon = 35 + 40 / 60, 139.75  # 5339 の 2次 (5,6) 南西端
    assert latlon_to_mesh(lat, lon, 3) == 53394600


def test_parent_and_polygons():
    assert parent_mesh(533946113, "1km") == 53394611
    gdf = mesh_to_polygons([53394611, 53394612])
    assert len(gdf) == 2 and gdf.geometry.is_valid.all()
