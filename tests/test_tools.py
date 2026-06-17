from unittest.mock import MagicMock, patch

from tools import create_fit_card, search_listings, suggest_outfit

# ── search_listings ───────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)

def test_search_size_filter():
    results = search_listings("jeans", size="XL", max_price=None)
    assert all("xl" in item["size"].lower() for item in results)

def test_search_sorted_by_relevance():
    results = search_listings("vintage graphic tee", size=None, max_price=None)
    assert len(results) >= 2
    # every result must mention at least one keyword — zero-score items are dropped
    for item in results:
        fields = item["title"] + " " + item["description"] + " " + " ".join(item["style_tags"])
        assert any(kw in fields.lower() for kw in ["vintage", "graphic", "tee"])

def test_search_no_size_filter_when_none():
    results_with = search_listings("top", size=None, max_price=None)
    results_without = search_listings("top", size=None, max_price=None)
    assert results_with == results_without  # both skip size filtering


# ── suggest_outfit ────────────────────────────────────────────────────────────

SAMPLE_ITEM = {
    "title": "Y2K Baby Tee — Butterfly Print",
    "price": 18.0,
    "condition": "excellent",
    "platform": "depop",
    "style_tags": ["y2k", "vintage", "graphic tee"],
}

SAMPLE_WARDROBE = {
    "items": [
        {
            "id": "w_001",
            "name": "Baggy straight-leg jeans",
            "category": "bottoms",
            "colors": ["dark blue"],
            "style_tags": ["denim", "streetwear", "baggy"],
            "notes": None,
        }
    ]
}

EMPTY_WARDROBE = {"items": []}


def _mock_groq(content: str):
    """Return a mock Groq client whose completions.create returns `content`."""
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value.choices[0].message.content = content
    return mock_client


@patch("tools._get_groq_client")
def test_suggest_outfit_with_wardrobe(mock_get_client):
    mock_get_client.return_value = _mock_groq("Wear the tee with your baggy jeans.")
    result = suggest_outfit(SAMPLE_ITEM, SAMPLE_WARDROBE)
    assert isinstance(result, str)
    assert len(result) > 0


@patch("tools._get_groq_client")
def test_suggest_outfit_empty_wardrobe_no_crash(mock_get_client):
    # Empty wardrobe must not crash — LLM is called with general styling prompt
    mock_get_client.return_value = _mock_groq("Pair with wide-leg trousers and chunky sneakers.")
    result = suggest_outfit(SAMPLE_ITEM, EMPTY_WARDROBE)
    assert isinstance(result, str)
    assert len(result) > 0


@patch("tools._get_groq_client")
def test_suggest_outfit_llm_returns_empty_string(mock_get_client):
    # Failure mode: LLM returns empty — tool returns "" and planning loop handles it
    mock_get_client.return_value = _mock_groq("")
    result = suggest_outfit(SAMPLE_ITEM, SAMPLE_WARDROBE)
    assert result == ""


# ── create_fit_card ───────────────────────────────────────────────────────────

@patch("tools._get_groq_client")
def test_create_fit_card_returns_caption(mock_get_client):
    mock_get_client.return_value = _mock_groq("thrifted this y2k tee for $18 off depop and honestly obsessed.")
    result = create_fit_card("Wear with baggy jeans and chunky sneakers.", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert len(result) > 0


def test_create_fit_card_empty_outfit_returns_error_string():
    # Failure mode: empty outfit — must return error string, not raise
    result = create_fit_card("", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert "empty" in result.lower() or "could not" in result.lower()


def test_create_fit_card_whitespace_outfit_returns_error_string():
    result = create_fit_card("   ", SAMPLE_ITEM)
    assert isinstance(result, str)
    assert "empty" in result.lower() or "could not" in result.lower()
