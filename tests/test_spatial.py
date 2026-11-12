import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from geocontest import spatial
from geocontest.mesh import latlon_to_mesh


def test_nearest_and_radius():
    # 基準点 (35, 139) から北へ約 111m, 1110m の 2 点
    ref = pd.DataFrame({"lat": [35.001, 35.01], "lon": [139.0, 139.0], "pax": [100.0, 1000.0]})
    idx = spatial.PointIndex(ref["lat"], ref["lon"], ref[["pax"]])
    nn = spatial.nearest_features([35.0], [139.0], idx, "st", k=2, value_cols=["pax"])
    assert abs(nn.loc[0, "st_dist1"] - 111.2) < 1
    assert abs(nn.loc[0, "st_dist2"] - 1111.9) < 2
    assert nn.loc[0, "st_nn_pax"] == 100
    rf = spatial.radius_features([35.0], [139.0], idx, "st", radii_m=(500, 2000), sum_cols=["pax"], decay_m=1000)
    assert rf.loc[0, "st_cnt_500m"] == 1 and rf.loc[0, "st_cnt_2000m"] == 2
    assert rf.loc[0, "st_pax_sum_2000m"] == 1100
    assert 0 < rf.loc[0, "st_pax_decay1000"] < 1100


def test_polygon_attributes():
    poly = gpd.GeoDataFrame({"code": [1, 2]}, geometry=[shapely.box(0, 0, 1, 1), shapely.box(1, 0, 2, 1)], crs="EPSG:4326")
    out = spatial.polygon_attributes([0.5, 0.5, 5.0], [0.5, 1.5, 5.0], poly, ["code"], "z")
    assert out["z_code"].tolist()[:2] == [1, 2]
    assert pd.isna(out["z_code"].iloc[2])


def test_mesh_join():
    lat, lon = [35.681236, 35.0], [139.767125, 139.0]
    code = latlon_to_mesh(lat[0], lon[0], "500m")
    tbl = pd.DataFrame({"MESH_ID": [str(code)], "pop": [1234]})
    out = spatial.mesh_join(lat, lon, tbl, "MESH_ID", ["pop"], "500m", "m")
    assert out["m_pop"].iloc[0] == 1234 and pd.isna(out["m_pop"].iloc[1])
