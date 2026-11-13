import numpy as np

from geocontest import ksj
from geocontest.features import build_ksj_features, station_table

from .conftest import CENTER


def test_utf8_preferred_and_backslash_paths(fake_ksj):
    st = ksj.load("station_passengers", data_dir=fake_ksj, auto_download=False)
    assert len(st) == 3  # Shift-JIS 側を二重に読んでいない
    med = ksj.load("medical", prefs=["13"], data_dir=fake_ksj, auto_download=False)
    assert len(med) == 1 and med.loc[0, "medical_type"] == 1


def test_station_table_groups_and_fallback(fake_ksj):
    st = station_table(fake_ksj).set_index("station_name")
    # A線は 2024 が 0 なので 2023 の 400000 を使い、B線の 100000 と合算
    assert st.loc["東京", "passengers"] == 500000
    assert st.loc["東京", "n_lines"] == 2
    assert st.loc["神田", "passengers"] == 50000


def test_build_ksj_features_end_to_end(fake_ksj):
    lat = np.array([CENTER[0], 36.5])
    lon = np.array([CENTER[1], 140.5])
    f = build_ksj_features(lat, lon, prefs=["13"], data_dir=fake_ksj)
    assert len(f) == 2
    r = f.iloc[0]
    assert r["station_dist1"] < 100
    assert r["station_nn_passengers"] == 500000
    assert r["station_passengers_sum_2000m"] == 550000
    assert r["mesh500_pop_2020"] == 123
    assert r["landprice_nn_price_per_m2"] == 3960000
    assert r["bus_cnt_250m"] == 1
    assert r["zoning_zoning_code"] == 9
    # 遠い点は人口メッシュ・用途地域が欠損
    assert np.isnan(f.iloc[1]["mesh500_pop_2020"])
    assert np.isnan(f.iloc[1]["zoning_zoning_code"])
