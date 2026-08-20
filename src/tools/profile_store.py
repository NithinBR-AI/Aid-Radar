# Moved to src.db.profile_store — kept here for backwards compatibility only.
from src.db.profile_store import (  # noqa: F401
    save_profile,
    get_profile,
    update_snapshot,
    ensure_table_exists,
)
