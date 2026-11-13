"""国土数値情報をまとめてダウンロードする。

例:
    # 登録済みデータセットの一覧
    python scripts/fetch_ksj.py --list
    # 東京・神奈川の全データセット（全国版しかないものは全国版）
    python scripts/fetch_ksj.py --prefs 13 14
    # 全国版（全国版がないデータセットは 47 都道府県すべて）
    python scripts/fetch_ksj.py --all-japan
    # URL の確認だけ（ダウンロードしない）
    python scripts/fetch_ksj.py --prefs 13 --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from geocontest import ksj  # noqa: E402
from geocontest.ksj_catalog import DATASETS, PREF_CODES  # noqa: E402


def targets(key: str, prefs: list[str] | None, all_japan: bool) -> list[str | None]:
    ds = DATASETS[key]
    if all_japan:
        return [None] if ds.file_national else list(PREF_CODES)
    if ds.file_pref is None:
        return [None]
    return list(prefs or [])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--datasets", nargs="*", default=list(DATASETS), help="データセットのキー（省略時は全部）")
    ap.add_argument("--prefs", nargs="*", help="都道府県コード（例: 13 14）")
    ap.add_argument("--all-japan", action="store_true", help="全国分を取得")
    ap.add_argument("--data-dir", default=str(ksj.DEFAULT_DATA_DIR))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        for k, d in DATASETS.items():
            print(f"{k:22s} {d.name}  {d.page}")
        return
    if not args.prefs and not args.all_japan:
        ap.error("--prefs か --all-japan を指定してください")

    failed = []
    for key in args.datasets:
        for pref in targets(key, args.prefs, args.all_japan):
            url = DATASETS[key].url(pref)
            if args.dry_run:
                print(url)
                continue
            try:
                p = ksj.download(key, pref, args.data_dir, overwrite=args.overwrite)
                print(f"ok   {key} pref={pref} -> {p}")
            except Exception as e:  # noqa: BLE001
                print(f"FAIL {key} pref={pref} {url}: {e}")
                failed.append(url)
    if failed:
        sys.exit(f"{len(failed)} 件失敗しました")


if __name__ == "__main__":
    main()
