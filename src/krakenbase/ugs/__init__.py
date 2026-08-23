"""Remote UGS contracts (U0). Capture daemon is U1+."""

from krakenbase.models import HandOffTask


def accepts_handoff(node_id: str, task: HandOffTask) -> bool:
    """True if this pole should consume the task. None target = any node."""
    if not task.target_node_id:
        return True
    return task.target_node_id == node_id
