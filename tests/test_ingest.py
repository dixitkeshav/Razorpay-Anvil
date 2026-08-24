"""Phase 2 gate: a query returns SR/P95/timeout-rate for any slice x minute,
matching a hand-computed fixture. See docs/PHASES.md.
"""

import polars as pl
import pytest

from src.ingest.db import connect, register_events
from src.ingest.rollup import rollup, slice_stats

MINUTE = 1000
BASE_TS = MINUTE * 60

FIXTURE_ROWS = [
    # Slice X: upi / PSP-A / HDFC, minute 1000 — 5 rows.
    # SR = 4/5 = 0.8. Latencies sorted [100,200,300,400,500]:
    #   P50 (idx 2.0)  = 300
    #   P95 (idx 3.8)  = 400 + 0.8*(500-400) = 480
    #   P99 (idx 3.96) = 400 + 0.96*(500-400) = 496
    # timeout_rate = 1/5 = 0.2 (only the failed row is a timeout)
    # retry_rate   = 1/5 = 0.2 (only the failed row has attempt_number 2)
    dict(created_at=BASE_TS + 0, status="captured", x_latency_ms=100,
         error_reason=None, x_attempt_number=1,
         method="upi", x_psp="PSP-A", x_issuer="HDFC"),
    dict(created_at=BASE_TS + 1, status="captured", x_latency_ms=200,
         error_reason=None, x_attempt_number=1,
         method="upi", x_psp="PSP-A", x_issuer="HDFC"),
    dict(created_at=BASE_TS + 2, status="captured", x_latency_ms=300,
         error_reason=None, x_attempt_number=1,
         method="upi", x_psp="PSP-A", x_issuer="HDFC"),
    dict(created_at=BASE_TS + 3, status="captured", x_latency_ms=400,
         error_reason=None, x_attempt_number=1,
         method="upi", x_psp="PSP-A", x_issuer="HDFC"),
    dict(created_at=BASE_TS + 4, status="failed", x_latency_ms=500,
         error_reason="bank server timeout", x_attempt_number=2,
         method="upi", x_psp="PSP-A", x_issuer="HDFC"),
    # Slice Y: card / PSP-B / ICICI, same minute — 3 rows.
    # SR = 2/3 = 0.6667. Latencies sorted [1000,1200,1400]:
    #   P50 (idx 1.0)  = 1200
    #   P95 (idx 1.9)  = 1200 + 0.9*(1400-1200) = 1380
    #   P99 (idx 1.98) = 1200 + 0.98*(1400-1200) = 1396
    # timeout_rate = 0, retry_rate = 0
    dict(created_at=BASE_TS + 5, status="captured", x_latency_ms=1000,
         error_reason=None, x_attempt_number=1,
         method="card", x_psp="PSP-B", x_issuer="ICICI"),
    dict(created_at=BASE_TS + 6, status="captured", x_latency_ms=1200,
         error_reason=None, x_attempt_number=1,
         method="card", x_psp="PSP-B", x_issuer="ICICI"),
    dict(created_at=BASE_TS + 7, status="failed", x_latency_ms=1400,
         error_reason="insufficient funds in the account", x_attempt_number=1,
         method="card", x_psp="PSP-B", x_issuer="ICICI"),
    # Slice X again, but the *next* minute bucket — must not leak into MINUTE.
    dict(created_at=BASE_TS + 61, status="captured", x_latency_ms=999,
         error_reason=None, x_attempt_number=1,
         method="upi", x_psp="PSP-A", x_issuer="HDFC"),
]


@pytest.fixture
def con():
    df = pl.DataFrame(FIXTURE_ROWS)
    c = connect()
    register_events(c, df)
    return c


def test_slice_stats_matches_hand_computed_slice_x(con):
    stats = slice_stats(con, MINUTE, {"method": "upi", "x_psp": "PSP-A", "x_issuer": "HDFC"})
    assert stats["attempts"] == 5
    assert stats["successes"] == 4
    assert stats["success_rate"] == pytest.approx(0.8)
    assert stats["p50_latency_ms"] == pytest.approx(300)
    assert stats["p95_latency_ms"] == pytest.approx(480)
    assert stats["p99_latency_ms"] == pytest.approx(496)
    assert stats["timeout_rate"] == pytest.approx(0.2)
    assert stats["retry_rate"] == pytest.approx(0.2)


def test_slice_stats_matches_hand_computed_slice_y(con):
    stats = slice_stats(con, MINUTE, {"method": "card", "x_psp": "PSP-B", "x_issuer": "ICICI"})
    assert stats["attempts"] == 3
    assert stats["successes"] == 2
    assert stats["success_rate"] == pytest.approx(2 / 3)
    assert stats["p50_latency_ms"] == pytest.approx(1200)
    assert stats["p95_latency_ms"] == pytest.approx(1380)
    assert stats["p99_latency_ms"] == pytest.approx(1396)
    assert stats["timeout_rate"] == pytest.approx(0.0)
    assert stats["retry_rate"] == pytest.approx(0.0)


def test_slice_stats_does_not_leak_across_minute_buckets(con):
    stats = slice_stats(con, MINUTE, {"method": "upi", "x_psp": "PSP-A", "x_issuer": "HDFC"})
    assert stats["attempts"] == 5  # not 6 — the +61s row belongs to minute 1001

    next_minute = slice_stats(
        con, MINUTE + 1, {"method": "upi", "x_psp": "PSP-A", "x_issuer": "HDFC"}
    )
    assert next_minute["attempts"] == 1


def test_slice_stats_empty_slice_returns_zero_attempts(con):
    stats = slice_stats(con, MINUTE, {"method": "netbanking", "x_psp": "PSP-A", "x_issuer": "HDFC"})
    assert stats["attempts"] == 0
    assert stats["success_rate"] is None


def test_rollup_groups_by_minute_and_dims(con):
    df = rollup(con, ["method"])
    upi_row = df.filter((pl.col("minute_bucket") == MINUTE) & (pl.col("method") == "upi"))
    assert upi_row.height == 1
    assert upi_row["attempts"][0] == 5
    assert upi_row["success_rate"][0] == pytest.approx(0.8)

    card_row = df.filter((pl.col("minute_bucket") == MINUTE) & (pl.col("method") == "card"))
    assert card_row["attempts"][0] == 3


def test_rollup_overall_has_no_dim_columns(con):
    df = rollup(con, [])
    assert set(df.columns) == {
        "minute_bucket", "attempts", "successes", "success_rate",
        "p50_latency_ms", "p95_latency_ms", "p99_latency_ms",
        "timeout_rate", "retry_rate",
    }
    total = df.filter(pl.col("minute_bucket") == MINUTE)["attempts"][0]
    assert total == 8  # 5 + 3 in minute 1000


def test_unknown_dimension_rejected(con):
    with pytest.raises(ValueError):
        slice_stats(con, MINUTE, {"x_episode_id": "ep-A"})
