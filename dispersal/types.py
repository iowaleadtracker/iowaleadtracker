"""Type aliases used across the model (annotations only)."""

from __future__ import annotations

from typing import Any, TypeAlias

import numpy as np
import numpy.typing as npt

FloatArray: TypeAlias = npt.NDArray[np.float64]
IntArray: TypeAlias = npt.NDArray[np.int_]
BoolArray: TypeAlias = npt.NDArray[np.bool_]
ArrayOrFloat: TypeAlias = FloatArray | float
#: Weather fields: float arrays, except the integer stability class.
MetArray: TypeAlias = npt.NDArray[Any]
#: One particle-size bin: (particle mass kg, mass fraction, settling velocity m/s).
Bin: TypeAlias = tuple[float, float, float]
#: A size distribution: [(particle mass kg or diameter m, mass fraction)].
SizeDist: TypeAlias = list[tuple[float, float]]
#: One model time step for the gridder: (hour index, x, y, sigma_y, concentration weight,
#: deposited mass, 1/particle mass, last step of the hour). Arrays are per active puff.
Record: TypeAlias = tuple[
    int, FloatArray, FloatArray, FloatArray, FloatArray, FloatArray, FloatArray, bool
]
#: Open-Meteo responses, payload pieces and other JSON-shaped data.
Json: TypeAlias = dict[str, Any]
