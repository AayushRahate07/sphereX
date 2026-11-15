"""Services package initialization."""

from .retrieval import (
    RetrievalError,
    batch_retrieve_cutouts,
    fetch_or_cache_fits_cutout,
    fetch_or_cache_full_fits,
    resolve_cutout_url_from_datalink,
    resolve_science_product_url,
)
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
    "fetch_or_cache_full_fits",
    "get_target_name_if_preset",
    "resolve_cutout_url_from_datalink",
    "resolve_science_product_url",
    "select_observations_for_target",
]
