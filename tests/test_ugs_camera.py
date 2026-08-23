"""U2 camera file trigger, rate-limit, degraded heartbeat."""

from pathlib import Path

from krakenbase.models import UgsTrigger
from krakenbase.rff.recipe import get_recipe
from krakenbase.ugs.camera import CameraTrigger
from krakenbase.ugs.node import UgsNode


def _node(tmp: Path, **kw) -> UgsNode:
    return UgsNode(
        node_id="ugs-west-gate",
        out_dir=tmp / "ugs",
        recipe=get_recipe("synthetic:48k:0"),
        sensor_id="s0",
        backend="synthetic",
        **kw,
    )


def test_motion_file_edge(tmp_path: Path):
    motion = tmp_path / "motion"
    cam = CameraTrigger(motion_file=motion, camera_id="amcrest-01")
    node = _node(tmp_path, camera=cam, rate_limit_s=0.0)
    assert node.camera_poll(462_712_500) is None
    motion.write_text("1")
    ev = node.camera_poll(462_712_500)
    assert ev is not None
    assert ev.trigger == UgsTrigger.CAMERA
    assert ev.camera_id == "amcrest-01"
    assert node.camera_poll(462_712_500) is None


def test_rate_limit_collapses(tmp_path: Path):
    node = _node(tmp_path, rate_limit_s=60.0)
    assert node.synthetic_trigger(100) is not None
    assert node.synthetic_trigger(100) is None


def test_uplink_copy(tmp_path: Path):
    shop = tmp_path / "shop"
    node = _node(tmp_path, uplink_dir=shop, rate_limit_s=0.0)
    ev = node.synthetic_trigger(146_520_000)
    assert ev is not None
    assert (shop / f"{ev.event_id}.ugs.json").exists()


def test_rtl_missing_is_degraded(tmp_path: Path):
    node = _node(tmp_path)
    node.backend = "rtl"
    assert node.heartbeat_status() == "degraded"
    node.backend = "synthetic"
    assert node.heartbeat_status() == "online"
