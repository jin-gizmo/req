"""Pytest conf."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest


# ------------------------------------------------------------------------------
class DotDict:
    """
    Access dict values with dot notation or conventional dict notation or mix and match.

    ..warning:: This does not handle all dict syntax, just what is needed here.

    """

    def __init__(self, *data: Mapping[str, Any]):
        """Create dotable dict from dict(s)."""
        self._data = {}

        for d in data:
            self._data.update(d)

    def __getattr__(self, item: str) -> Any:
        """Access config elements with dot notation support for keys."""

        if not item or not isinstance(item, str):
            raise ValueError(f'Bad config item name: {item}')

        try:
            value = self._data[item]
        except KeyError:
            raise AttributeError(item)
        return self.__class__(value) if isinstance(value, dict) else value

    def __getitem__(self, item):
        value = self._data[item]
        return self.__class__(value) if isinstance(value, dict) else value

    def __str__(self):
        return str(self._data)

    def __repr__(self):
        return repr(self._data)

    @property
    def dict(self) -> dict[str, Any]:
        """Return the underlying data as a dict."""
        return self._data


# ------------------------------------------------------------------------------
@pytest.fixture(scope='session')
def td() -> Path:
    """Path for test data."""
    return Path(__file__).parent.parent / 'data'


# ------------------------------------------------------------------------------
@pytest.fixture(scope='session')
def dirs(td) -> DotDict:
    """Package to access useful directories in the source tree."""

    return DotDict(
        {
            'cwd': Path('.').resolve(),
            'base': Path(__file__).parent.parent.parent,
            'src': Path(__file__).parent.parent.parent / 'req',
            'test': Path(__file__).parent.parent,
            'data': td,
        }
    )
