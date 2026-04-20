import os

import pytest
from src.observability.cost_tracker import (
    calculate_query_cost,
    calculate_ingestion_cost,
    DailyBudgetTracker,
    OPENAI_INPUT_COST_PER_TOKEN,
    OPENAI_OUTPUT_COST_PER_TOKEN,
    COHERE_RERANK_COST_PER_SEARCH_UNIT,
)


def test_query_cost_calculation_is_correct():
    cost = calculate_query_cost(
        input_tokens=1000,
        output_tokens=100,
        docs_reranked=10,
        pinecone_read_units=0,
        embed_tokens=0,
    )

    expected_input  = 1000 * OPENAI_INPUT_COST_PER_TOKEN
    expected_output = 100  * OPENAI_OUTPUT_COST_PER_TOKEN
    expected_cohere = 10   * COHERE_RERANK_COST_PER_SEARCH_UNIT

    assert abs(cost.openai_input_usd  - expected_input)  < 1e-9
    assert abs(cost.openai_output_usd - expected_output) < 1e-9
    assert abs(cost.cohere_usd        - expected_cohere) < 1e-9
    assert abs(cost.total_usd - (expected_input + expected_output + expected_cohere)) < 1e-9


def test_zero_tokens_zero_cost():
    cost = calculate_query_cost(
        input_tokens=0, output_tokens=0,
        docs_reranked=0, pinecone_read_units=0, embed_tokens=0
    )
    assert cost.total_usd == 0.0
    assert cost.openai_input_usd  >= 0
    assert cost.openai_output_usd >= 0
    assert cost.cohere_usd        >= 0



#@pytest.mark.skipif(
#    os.getenv("CI") == "true",
#    reason="Skipping failing test in CI"
#)
def test_budget_alert_fires_at_threshold():
    from unittest.mock import MagicMock

    tracker = DailyBudgetTracker(daily_budget_usd=0.01)

    # ✅ Inject mock logger directly
    tracker.log = MagicMock()

    # Make cost high enough
    cheap_cost = calculate_query_cost(input_tokens=5000, output_tokens=500)

    tracker.record(cheap_cost)
    for _ in range(50):
        tracker.record(cheap_cost)

    # ✅ Assert warning was called
    assert tracker.log.warning.called, "Budget exceeded but no warning was logged"

    # Optional: stronger assertion
    calls = [call.args[0] for call in tracker.log.warning.call_args_list]
    assert any("budget" in str(c).lower() for c in calls)



def test_ingestion_cost_includes_ocr_when_pages_present():
    cost_with_ocr    = calculate_ingestion_cost(total_chunks=10, ocr_pages=3)
    cost_without_ocr = calculate_ingestion_cost(total_chunks=10, ocr_pages=0)
    assert cost_with_ocr.total_usd > cost_without_ocr.total_usd


def test_cost_to_dict_rounds_to_six_decimals():
    cost = calculate_query_cost(input_tokens=412, output_tokens=87)
    d = cost.to_dict()
    for key, val in d.items():
        assert isinstance(val, float)
        assert round(val, 6) == val, f"{key}={val} is not rounded to 6 decimals"