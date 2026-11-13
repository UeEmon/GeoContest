# GeoContest

[第3回 国土交通省 地理空間情報データチャレンジ](https://user.competition.signate.jp/ja/competition/detail/?competition=d97fc46b1b4841a090ce0d042c860e1d)（SIGNATE）用のリポジトリです。テーマは「人流予測」で、コンペは 2026-11-16 13:00 に開始します。

コンペのデータが公開される前の準備として、国土数値情報をダウンロードし、緯度経度やメッシュに結び付けて特徴量にするコードを用意しています。

## セットアップ

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## 国土数値情報の取得

```bash
python scripts/fetch_ksj.py --list                  # 登録済みデータセットの一覧
python scripts/fetch_ksj.py --prefs 13 14 --dry-run # URL の確認だけ
python scripts/fetch_ksj.py --prefs 13 14           # 東京・神奈川を取得
python scripts/fetch_ksj.py --all-japan             # 全国を取得
```

保存先は `data/external/ksj/<データセット>/` です。`data/` 以下は git の管理対象外です。

| キー | データ | 年度 | 形 |
|---|---|---|---|
| `station_passengers` | 駅別乗降客数（S12） | 2024 | 線（駅） |
| `railway` | 鉄道（N02） | 2024 | 線（路線・駅） |
| `pop_mesh500` | 500m メッシュ別将来推計人口（R6） | 2020 実績・2025〜推計 | 面 |
| `land_price` | 地価公示（L01） | 2025 | 点 |
| `bus_stop` | バス停留所（P11） | 2022 | 点 |
| `medical` | 医療機関（P04） | 2020 | 点 |
| `school` | 学校（P29） | 2023 | 点 |
| `attraction_facility` | 集客施設（P33） | 2014 | 点 |
| `zoning` | 用途地域（A29） | 2019 | 面 |

URL・zip の中身・属性名は 2026-11 時点の配布ファイルで確認しています。データの追加や年度の更新は `src/geocontest/ksj_catalog.py` を編集してください。

## 特徴量の作成

```python
from geocontest.features import build_ksj_features
feats = build_ksj_features(df["lat"], df["lon"], prefs=["13", "14"])
```

緯度経度を含む CSV から直接作ることもできます。

```bash
python scripts/build_features.py data/raw/train.csv data/processed/train_ksj.parquet \
    --lat-col lat --lon-col lon --prefs 13 14
```

作られる主な特徴量:

- **駅**: 最寄り 3 駅までの距離、最寄り駅の乗降客数と路線数、半径 500m〜5km の駅数と乗降客数合計、距離減衰つきの乗降客数（アクセシビリティ）。乗換駅はグループコードで 1 駅にまとめています。
- **人口**: 地点が入る 500m メッシュの人口（2020, 2025）と、半径 1〜5km の人口合計。
- **地価**: 最寄りの地価公示地点 3 件までの距離と、最寄り地点の価格。
- **バス停・医療機関・学校**: 最寄りまでの距離と、半径ごとの件数。
- **用途地域**: 地点が入る用途地域のコード、建蔽率、容積率。

## ライブラリの構成

```
src/geocontest/
  ksj_catalog.py  データセットの定義（URL、属性名の対応）
  ksj.py          ダウンロードと読み込み（zip 内の UTF-8 版を優先、WGS84 に統一）
  mesh.py         地域メッシュコードの変換（1次〜8分の1、ベクトル化）
  spatial.py      最近傍・半径内集計・ポリゴン属性・メッシュ結合
  features.py     上記をまとめて地点ごとの特徴量にする
  validation.py   空間ブロック CV、グループ CV、時系列分割
scripts/          fetch_ksj.py, build_features.py
notebooks/        EDA 用
data/             raw（コンペ配布データ）, external（国土数値情報）, interim, processed
submissions/      提出ファイル
```

## データ公開後にやること

1. 目的変数の単位（地点・メッシュ・駅など）と、テストの分け方（地域か期間か）を確認する。
2. `validation.py` からテストの分け方に合う検証方法を選ぶ。
3. 配布データの緯度経度で `build_ksj_features` を回し、LightGBM でベースラインを作って最初の提出をする。

注意: コンペの規約で外部データの扱いが決まるので、国土数値情報以外のデータを使う前に規約を確認してください。
