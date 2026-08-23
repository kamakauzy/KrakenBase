"""R1 SigMF capture + U1 bench node."""

from pathlib import Path
from uuid import uuid4

from krakenbase.models import HandOffTask, UgsTrigger
from krakenbase.rff.capture import capture_burst
from krakenbase.rff.recipe import get_recipe
from krakenbase.rff.sigmf_io import read_sigmf, validate_pair
from krakenbase.ugs.node import UgsNode


def test_synthetic_sigmf(tmp_path: Path):
    rec = get_recipe("synthetic:48k:0")
    burst = capture_burst(
        462_712_500,
        rec,
        tmp_path,
        sensor_id="t0",
        backend="synthetic",
    )
    assert burst.backend == "synthetic"
    assert burst.meta_path.exists()
    assert burst.data_path.exists()
    validate_pair(burst.meta_path)
    meta, blob = read_sigmf(burst.meta_path)
    assert meta["global"]["core:datatype"] == "cf32_le"
    assert meta["captures"][0]["core:frequency"] == 462_712_500
    assert meta["global"]["krakenbase:recipe_id"] == rec.recipe_id
    assert len(blob) == rec.sample_count * 8


def test_ugs_synthetic_and_handoff(tmp_path: Path):
    node = UgsNode(
        node_id="ugs-west-gate",
        out_dir=tmp_path / "ugs",
        recipe=get_recipe("synthetic:48k:0"),
        sensor_id="rtl-sim",
        backend="synthetic",
    )
    ev = node.synthetic_trigger(146_520_000)
    assert ev.trigger == UgsTrigger.ENERGY
    assert ev.freq_hz == 146_520_000
    assert Path(ev.burst_path).exists()

    mine = HandOffTask(freq_hz=462_562_500, source_event_id=uuid4(), target_node_id="ugs-west-gate")
    other = HandOffTask(freq_hz=462_562_500, source_event_id=uuid4(), target_node_id="ugs-east")
    got = node.handle_task(mine)
    assert got is not None and got.trigger == UgsTrigger.HANDOFF
    assert node.handle_task(other) is None
    assert node.handle_task(mine) is None

    watch = tmp_path / "handoff"
    watch.mkdir()
    open_task = HandOffTask(freq_hz=433_000_000, source_event_id=uuid4())
    (watch / f"{open_task.task_id}.json").write_text(open_task.model_dump_json())
    found = node.scan_watch_dir(watch)
    assert len(found) == 1
    assert found[0].freq_hz == 433_000_000
