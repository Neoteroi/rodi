from typing import Optional, Dict, Any


def _get_obj_locals(obj) -> Optional[Dict[str, Any]]:
    return getattr(obj, "_locals", None)
