"""検証の分け方。

テストデータが「学習にない地域」なら空間ブロックで、「学習より後の期間」なら時系列で分ける。
どちらになるかはデータ公開後に確認して選ぶ。
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold

from .mesh import latlon_to_mesh


def spatial_block_folds(lat, lon, n_splits: int = 5, block: str | int = "10km", seed: int = 42) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """メッシュ単位のブロックでグループ分けした KFold。

    近くの地点が学習と検証にまたがって楽観的なスコアになるのを防ぐ。
    ``block`` はメッシュレベル（"80km", "10km", "1km" など）。
    """
    groups = np.asarray(latlon_to_mesh(lat, lon, block))
    # GroupKFold は決定的なので、グループ ID をシャッフルしてから渡す
    rng = np.random.default_rng(seed)
    uniq = np.unique(groups)
    perm = dict(zip(uniq, rng.permutation(len(uniq))))
    shuffled = np.vectorize(perm.get)(groups)
    yield from GroupKFold(n_splits=n_splits).split(np.zeros(len(groups)), groups=shuffled)


def group_folds(groups, n_splits: int = 5) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """市区町村コードなど任意のグループで分ける。"""
    groups = np.asarray(groups)
    yield from GroupKFold(n_splits=n_splits).split(np.zeros(len(groups)), groups=groups)


def time_split(dates, valid_start) -> tuple[np.ndarray, np.ndarray]:
    """``valid_start`` 以降を検証にする 1 分割。"""
    d = pd.to_datetime(pd.Series(dates))
    valid = (d >= pd.Timestamp(valid_start)).to_numpy()
    return np.where(~valid)[0], np.where(valid)[0]
