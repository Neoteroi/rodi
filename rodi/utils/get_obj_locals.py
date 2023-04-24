from typing import Any, Dict, Optional


def _get_obj_locals(obj) -> Optional[Dict[str, Any]]:
    return getattr(obj, "_locals", None)
