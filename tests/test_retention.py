"""Event store retention tests."""

import pytest

from krakenbase.models import AnomalyEvent
from krakenbase.store.events import EventStore


@pytest.mark.asyncio
async def test_purge_older_than(tmp_path):
    db = tmp_path / "events.db"
    store = EventStore(db)
    await store.open()

    await store.log_anomaly(
        AnomalyEvent(
            freq_hz=100000000,
            power_db=-30,
            baseline_db=-90,
            margin_db=60,
            duration_s=2.0,
        )
    )
    deleted = await store.purge_older_than(30)
    assert deleted == 0
    rows = await store.recent(10)
    assert len(rows) == 1

    assert store._db is not None
    await store._db.execute(
        "UPDATE events SET timestamp = ?",
        ("2020-01-01T00:00:00+00:00",),
    )
    await store._db.commit()
    deleted = await store.purge_older_than(30)
    assert deleted >= 1
    rows = await store.recent(10)
    assert len(rows) == 0
    await store.close()
