"""国土数値情報のダウンロードと読み込み。"""

from __future__ import annotations

import tempfile
import time
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests

from .ksj_catalog import DATASETS, KsjDataset

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "external" / "ksj"
WGS84 = "EPSG:4326"

# 国土数値情報は日本測地系2011（JGD2011, EPSG:6668）か旧 JGD2000（EPSG:4612）で配布される。
# 緯度経度の差は実用上無視できるので、すべて WGS84 として扱う。


def get_dataset(key: str) -> KsjDataset:
    try:
        return DATASETS[key]
    except KeyError:
        raise KeyError(f"未登録のデータセット: {key}。候補: {sorted(DATASETS)}") from None


def zip_path(key: str, pref: str | int | None = None, data_dir: Path | str = DEFAULT_DATA_DIR) -> Path:
    ds = get_dataset(key)
    return Path(data_dir) / ds.key / Path(ds.url(pref)).name


def download(
    key: str,
    pref: str | int | None = None,
    data_dir: Path | str = DEFAULT_DATA_DIR,
    overwrite: bool = False,
    retries: int = 3,
    timeout: int = 120,
) -> Path:
    """データセットの zip を ``data_dir/<key>/`` に保存して、そのパスを返す。"""
    ds = get_dataset(key)
    url = ds.url(pref)
    out = zip_path(key, pref, data_dir)
    if out.exists() and not overwrite:
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part")
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with requests.get(url, stream=True, timeout=timeout) as r:
                r.raise_for_status()
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        f.write(chunk)
            if not zipfile.is_zipfile(tmp):
                raise ValueError(f"zip ではないファイルが返されました: {url}")
            tmp.replace(out)
            return out
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(2**attempt)
    tmp.unlink(missing_ok=True)
    raise RuntimeError(f"ダウンロード失敗: {url}") from last_err


def _vector_members(zf: zipfile.ZipFile) -> list[str]:
    """読み込むべきメンバー名を返す。

    - GeoJSON があればそれを、無ければ shp を使う。
    - 最近の配布 zip は ``Shift-JIS/`` と ``UTF-8/`` に同じデータが入っているので UTF-8 側だけ使う。
    - zip 内パスの区切りが ``\\`` のもの（P04 など）があるので、判定は正規化して行う。
    """
    names = [n for n in zf.namelist() if not n.startswith("__MACOSX")]

    def norm(n: str) -> str:
        return n.replace("\\", "/")

    def pick(ext: str) -> list[str]:
        c = [n for n in names if norm(n).lower().endswith(ext)]
        utf8 = [n for n in c if "/utf-8/" in f"/{norm(n).lower()}"]
        if utf8:
            return utf8
        return [n for n in c if "/shift-jis/" not in f"/{norm(n).lower()}"]

    return pick(".geojson") or pick(".shp")


def list_layers(path: Path | str) -> list[str]:
    """zip 内の読み込み対象ファイル名を返す。"""
    with zipfile.ZipFile(path) as zf:
        return _vector_members(zf)


def _basename(member: str) -> str:
    return member.replace("\\", "/").rsplit("/", 1)[-1]


def read_zip(path: Path | str, member: str | None = None, layer_filter: str | None = None) -> gpd.GeoDataFrame:
    """zip 内のベクタファイルを読み込み、WGS84 の GeoDataFrame を返す。

    - ``member`` を指定するとそのファイルだけ読む。
    - ``layer_filter`` を指定するとファイル名にその文字列を含むものだけ読む
      （例: 鉄道データの "Station" / "RailroadSection"）。
    - 該当ファイルが複数ある場合は縦に連結し、``_source`` 列にファイル名を残す。
    - shp は .cpg が無ければ cp932 (Shift_JIS) として読む。
    """
    path = Path(path)
    frames = []
    with zipfile.ZipFile(path) as zf, tempfile.TemporaryDirectory() as tmp:
        names = zf.namelist()
        members = [member] if member else _vector_members(zf)
        if layer_filter:
            members = [m for m in members if layer_filter in _basename(m)]
        if not members:
            raise FileNotFoundError(f"{path} に読み込めるファイルがありません（filter={layer_filter}）")
        for i, m in enumerate(members):
            # zip 内パスの区切り文字の違いを避けるため、一度展開してから読む
            stem = m[: m.rfind(".")]
            sidecars = [n for n in names if n[: n.rfind(".")] == stem] if m.lower().endswith(".shp") else [m]
            outdir = Path(tmp) / str(i)
            outdir.mkdir()
            for n in sidecars:
                (outdir / _basename(n)).write_bytes(zf.read(n))
            local = outdir / _basename(m)
            kwargs = {}
            if local.suffix.lower() == ".shp" and not local.with_suffix(".cpg").exists():
                kwargs["encoding"] = "cp932"
            gdf = gpd.read_file(local, **kwargs)
            gdf = gdf.set_crs(WGS84) if gdf.crs is None else gdf.to_crs(WGS84)
            gdf["_source"] = _basename(m)
            frames.append(gdf)
    return gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=WGS84)


def load(
    key: str,
    prefs: list[str | int] | None = None,
    data_dir: Path | str = DEFAULT_DATA_DIR,
    layer_filter: str | None = None,
    rename: bool = True,
    auto_download: bool = True,
) -> gpd.GeoDataFrame:
    """データセットを読み込む。``prefs=None`` なら全国版。

    ``rename=True`` ならカタログの ``columns`` に従って列名を分かりやすい名前に変える。
    """
    ds = get_dataset(key)
    targets: list[str | int | None] = [None] if prefs is None else list(prefs)
    frames = []
    for pref in targets:
        p = zip_path(key, pref, data_dir)
        if not p.exists():
            if not auto_download:
                raise FileNotFoundError(p)
            download(key, pref, data_dir)
        frames.append(read_zip(p, layer_filter=layer_filter))
    gdf = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=WGS84)
    if rename and ds.columns:
        gdf = gdf.rename(columns={k: v for k, v in ds.columns.items() if k in gdf.columns})
    return gdf
