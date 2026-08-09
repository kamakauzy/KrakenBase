"""Fleet registry tests."""

from krakenbase.fleet.registry import FleetRegistry
from krakenbase.models import SecondaryNodeStatus


def test_heartbeat_and_list():
    fleet = FleetRegistry(offline_after_s=60)
    n = fleet.heartbeat("sec-1", status="online", site="patrol-base-01")
    assert n.node_id == "sec-1"
    assert n.status == SecondaryNodeStatus.ONLINE
    nodes = fleet.list_nodes()
    assert len(nodes) == 1


def test_pick_idle_skips_busy():
    fleet = FleetRegistry()
    fleet.heartbeat("a", status="busy", current_freq_hz=100)
    fleet.heartbeat("b", status="online")
    picked = fleet.pick_idle()
    assert picked is not None
    assert picked.node_id == "b"


def test_mark_busy():
    fleet = FleetRegistry()
    fleet.heartbeat("x", status="online")
    n = fleet.mark_busy("x", 462_712_500, task_id="t1")
    assert n is not None
    assert n.status == SecondaryNodeStatus.BUSY
    assert n.current_freq_hz == 462_712_500
