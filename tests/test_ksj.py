import zipfile

import geopandas as gpd
import shapely

from geocontest import ksj
from geocontest.ksj_catalog import DATASETS


def test_urls():
    assert DATASETS["station_passengers"].url() == "https://nlftp.mlit.go.jp/ksj/gml/data/S12/S12-25/S12-25_GML.zip"
    assert DATASETS["land_price"].url(13) == "https://nlftp.mlit.go.jp/ksj/gml/data/L01/L01-25/L01-25_13_GML.zip"
    assert DATASETS["pop_mesh500"].url("1").endswith("m500r6/m500r6-24/500m_mesh_2024_01_GEOJSON.zip")


def test_read_zip_shapefile_cp932(tmp_path):
    gdf = gpd.GeoDataFrame({"P04_002": ["東京病院"]}, geometry=[shapely.Point(139.7, 35.6)], crs="EPSG:6668")
    shp_dir = tmp_path / "shp"
    shp_dir.mkdir()
    gdf.to_file(shp_dir / "P04-20_13.shp", encoding="cp932")
    (shp_dir / "P04-20_13.cpg").unlink(missing_ok=True)
    zpath = tmp_path / "medical" / "P04-20_13_GML.zip"
    zpath.parent.mkdir()
    with zipfile.ZipFile(zpath, "w") as zf:
        for f in shp_dir.iterdir():
            zf.write(f, f"P04-20_13_GML/{f.name}")
    out = ksj.load("medical", prefs=["13"], data_dir=tmp_path, auto_download=False)
    assert out.loc[0, "name"] == "東京病院"
    assert out.crs.to_epsg() == 4326
