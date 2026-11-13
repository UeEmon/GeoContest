"""人流予測に効きそうな国土数値情報（KSJ）データセットの定義。

ダウンロード URL は ``https://nlftp.mlit.go.jp/ksj/gml/data/{dir}/{file}`` の形式。
2026-11 時点で各データの配布ページ（KsjTmplt-*.html）から確認したファイル名を使っている。
zip の中身（GeoJSON/shp の有無、属性名）も 2026-11 に実ファイルで確認済み。
新しい年度が出たら ``version`` / ``file`` を書き換えればよい。

``file`` の ``{pref}`` は 2 桁の都道府県コード（"13" = 東京都）に置換される。
``national`` が True のデータは ``pref=None`` で全国版ファイルを取得できる。
"""

from __future__ import annotations

from dataclasses import dataclass, field

KSJ_BASE_URL = "https://nlftp.mlit.go.jp/ksj/gml/data"


@dataclass(frozen=True)
class KsjDataset:
    key: str
    name: str
    page: str
    dir: str
    file_pref: str | None
    file_national: str | None
    geometry: str  # "point" | "line" | "polygon"
    # shp 属性名 -> 分かりやすい列名
    columns: dict[str, str] = field(default_factory=dict)
    note: str = ""

    def url(self, pref: str | int | None = None) -> str:
        if pref is None:
            if self.file_national is None:
                raise ValueError(f"{self.key} には全国版ファイルがありません。pref を指定してください")
            fname = self.file_national
        else:
            if self.file_pref is None:
                raise ValueError(f"{self.key} は全国版のみです。pref=None で取得してください")
            fname = self.file_pref.format(pref=f"{int(pref):02d}")
        return f"{KSJ_BASE_URL}/{self.dir}/{fname}"


DATASETS: dict[str, KsjDataset] = {
    d.key: d
    for d in [
        KsjDataset(
            key="station_passengers",
            name="駅別乗降客数（2024年度版）",
            page="https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-S12-2024.html",
            dir="S12/S12-25",
            file_pref=None,
            file_national="S12-25_GML.zip",
            geometry="line",
            columns={
                "S12_001": "station_name",
                "S12_001g": "station_group_code",
                "S12_002": "operator",
                "S12_003": "line_name",
                "S12_049": "passengers_2021",
                "S12_053": "passengers_2022",
                "S12_057": "passengers_2023",
                "S12_061": "passengers_2024",
            },
            note="乗降客数は人/日。0 はデータなし・非公表を含むので注意（S12_0xx のデータ有無コードを参照）。",
        ),
        KsjDataset(
            key="railway",
            name="鉄道（駅・路線）2024年",
            page="https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N02-2024.html",
            dir="N02/N02-24",
            file_pref=None,
            file_national="N02-24_GML.zip",
            geometry="line",
            columns={"N02_001": "railway_type", "N02_002": "operator_type", "N02_003": "line_name", "N02_004": "operator", "N02_005": "station_name", "N02_005g": "station_group_code"},
            note="zip 内に RailroadSection（路線）と Station（駅）の 2 レイヤーがある。load(..., layer_filter=\"Station\") で駅だけ読む。",
        ),
        KsjDataset(
            key="pop_mesh500",
            name="500mメッシュ別将来推計人口（R6国政局推計）",
            page="https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-mesh500r6.html",
            dir="m500r6/m500r6-24",
            file_pref="500m_mesh_2024_{pref}_GEOJSON.zip",
            file_national="500m_mesh_2024_GEOJSON.zip",
            geometry="polygon",
            columns={"MESH_ID": "mesh_code", "SHICODE": "city_code", "PTN_2020": "pop_2020", "PTN_2025": "pop_2025"},
            note="MESH_ID は 2分の1地域メッシュ（9桁）。年齢階級別の列も多数ある。",
        ),
        KsjDataset(
            key="land_price",
            name="地価公示（2025年）",
            page="https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-L01-2025.html",
            dir="L01/L01-25",
            file_pref="L01-25_{pref}_GML.zip",
            file_national="L01-25_GML.zip",
            geometry="point",
            columns={"L01_001": "city_code", "L01_002": "use_category", "L01_008": "price_per_m2", "L01_009": "price_change_rate", "L01_057": "coverage_ratio", "L01_058": "floor_area_ratio"},
        ),
        KsjDataset(
            key="bus_stop",
            name="バス停留所（2022年度）",
            page="https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P11-2022.html",
            dir="P11/P11-22",
            file_pref="P11-22_{pref}_SHP.zip",
            file_national="P11-22_SHP.zip",
            geometry="point",
            columns={"P11_001": "stop_name", "P11_002": "operator", "P11_003_01": "route_1"},
        ),
        KsjDataset(
            key="medical",
            name="医療機関（2020年度）",
            page="https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P04-2020.html",
            dir="P04/P04-20",
            file_pref="P04-20_{pref}_GML.zip",
            file_national="P04-20_GML.zip",
            geometry="point",
            columns={"P04_001": "medical_type", "P04_002": "name", "P04_003": "address", "P04_004": "departments"},
        ),
        KsjDataset(
            key="school",
            name="学校（2023年度）",
            page="https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P29-2023.html",
            dir="P29/P29-23",
            file_pref="P29-23_{pref}_GML.zip",
            file_national="P29-23_GML.zip",
            geometry="point",
            columns={"P29_001": "city_code", "P29_003": "school_type", "P29_004": "name"},
        ),
        KsjDataset(
            key="attraction_facility",
            name="集客施設（2014年度）",
            page="https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-P33.html",
            dir="P33/P33-14",
            file_pref="P33-14_{pref}_GML.zip",
            file_national=None,
            geometry="point",
            note="2014 年度と古く、zip 内は shp のみ。使うなら年代のずれに注意。",
        ),
        KsjDataset(
            key="zoning",
            name="用途地域（2019年度）",
            page="https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A29-2019.html",
            dir="A29/A29-19",
            file_pref="A29-19_{pref}_GML.zip",
            file_national=None,
            geometry="polygon",
            columns={"A29_004": "zoning_code", "A29_005": "zoning_name", "A29_006": "coverage_ratio", "A29_007": "floor_area_ratio"},
        ),
    ]
}

PREF_CODES = [f"{i:02d}" for i in range(1, 48)]
