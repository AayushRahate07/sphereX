"""Services package initialization."""

from .retrieval import RetrievalError, batch_retrieve_cutouts, fetch_or_cache_fits_cutout
from .selector import (
    SelectedObservation,
    SelectionError,
    TargetNotFoundError,
    get_target_name_if_preset,
    select_observations_for_target,
)

__all__ = [
    "RetrievalError",
    "SelectedObservation",
    "SelectionError",
    "TargetNotFoundError",
    "batch_retrieve_cutouts",
    "fetch_or_cache_fits_cutout",
    "get_target_name_if_preset",
    "select_observations_for_target",
]
