# FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
└── requirements.txt           # Python dependencies
```

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design.

---

## Running FitFindr

Run the Gradio UI:
```bash
python app.py
```

Run the CLI test (happy path + no-results path):
```bash
python agent.py
```

Run the test suite:
```bash
python -m pytest tests/test_tools.py -v
```

---

## Tool Inventory

### `search_listings(description, size, max_price)`

**Purpose:** Filters the mock listings dataset and returns items ranked by relevance to the user's query.

| Parameter | Type | Description |
|-----------|------|-------------|
| `description` | `str` | Keywords extracted from the query (e.g. `"vintage graphic tee"`) — matched against listing `title`, `description`, and `style_tags` |
| `size` | `str \| None` | Size to filter by (e.g. `"M"`, `"S/M"`, `"W30 L30"`) — case-insensitive substring match; `None` skips size filtering |
| `max_price` | `float \| None` | Upper price ceiling in dollars (inclusive); `None` skips price filtering |

**Returns:** `list[dict]` — matching listing dicts sorted by keyword relevance score, highest first. Each dict contains: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Returns an empty list if nothing matches — never raises.

---

### `suggest_outfit(new_item, wardrobe)`

**Purpose:** Calls the Groq LLM to suggest 1–2 complete outfits built around the thrifted item. If the wardrobe is empty, it generates general styling advice instead.

| Parameter | Type | Description |
|-----------|------|-------------|
| `new_item` | `dict` | A single listing dict — the item selected from `search_results` |
| `wardrobe` | `dict` | A wardrobe dict with an `items` key containing a list of wardrobe item dicts (each with `id`, `name`, `category`, `colors`, `style_tags`, `notes`). May have an empty `items` list. |

**Returns:** `str` — outfit suggestions referencing specific wardrobe pieces by name, or general styling tips if the wardrobe is empty. Never raises or returns an empty string on an empty wardrobe.

**Model:** `llama-3.3-70b-versatile` via Groq

---

### `create_fit_card(outfit, new_item)`

**Purpose:** Calls the Groq LLM to write a 2–4 sentence OOTD caption suitable for Instagram or TikTok. Uses a higher temperature (1.4) so the tone varies across calls on the same input.

| Parameter | Type | Description |
|-----------|------|-------------|
| `outfit` | `str` | The outfit suggestion string from `suggest_outfit`. May be empty — the tool guards against this internally and returns a descriptive error string instead of raising. |
| `new_item` | `dict` | The selected listing dict — used to pull `title`, `price`, and `platform` into the caption |

**Returns:** `str` — a casual OOTD caption mentioning the item name, price, and platform once each. If `outfit` is empty or whitespace-only, returns a descriptive error string instead of raising.

**Model:** `llama-3.3-70b-versatile` via Groq, `temperature=1.4`

---

## How the Planning Loop Works

The agent does not call all three tools unconditionally. Each tool call is gated by the result of the previous one. Here is the exact decision logic in `run_agent()`:

**Step 1 — Parse:** `_parse_query()` uses regex to extract `description` (str), `size` (str or None), and `max_price` (float or None) from the natural language query. Stored in `session["parsed"]`.

**Step 2 — Search:** `search_listings()` is called with the parsed parameters. Result stored in `session["search_results"]`.
- If the list is **empty**: `session["error"]` is set and the function returns immediately. `suggest_outfit` is never called.
- If **non-empty**: `session["selected_item"] = results[0]` (top-ranked match) and the loop continues.

**Step 3 — Style:** `suggest_outfit()` is called with `session["selected_item"]` and `session["wardrobe"]`. Result stored in `session["outfit_suggestion"]`.
- If the result is an **empty string** (LLM failure): `session["error"]` is set and the function returns immediately. `create_fit_card` is never called.
- If **non-empty**: the loop continues.

**Step 4 — Caption:** `create_fit_card()` is called with `session["outfit_suggestion"]` and `session["selected_item"]`. Result stored in `session["fit_card"]`. This tool handles its own empty-input guard internally — no additional branching needed in the loop.

**Step 5 — Return:** The completed session dict is returned. The Gradio UI reads from it to populate the three output panels.

---

## State Management

All state lives in a single session dict initialized by `_new_session(query, wardrobe)` at the start of each run. No tool receives state implicitly — the planning loop pulls each value from the session and passes it as an explicit argument. This means each tool can be called and tested in isolation without a live session.

| Key | Set by | Read by | Contains |
|-----|--------|---------|----------|
| `session["parsed"]` | `_parse_query()` | planning loop | `{description, size, max_price}` |
| `session["search_results"]` | `search_listings()` | planning loop (empty check) | Ranked list of matching listing dicts |
| `session["selected_item"]` | planning loop (`results[0]`) | `suggest_outfit`, `create_fit_card` | Single listing dict — top search result |
| `session["wardrobe"]` | `_new_session()` (passed in by caller) | `suggest_outfit` | User's wardrobe dict with `items` list |
| `session["outfit_suggestion"]` | `suggest_outfit()` | planning loop (empty check), `create_fit_card` | Outfit suggestion string from LLM |
| `session["fit_card"]` | `create_fit_card()` | Gradio UI | OOTD caption (or error string if outfit was empty) |
| `session["error"]` | planning loop (on early exit) | Gradio UI | Human-readable error message; `None` on success |

---

## Error Handling

### `search_listings` — no results

**Failure mode:** No listings match the description, size, and price filters.

**Agent response:** Sets `session["error"]` to `"No listings matched your search. Try a broader description, a different size, or raise your price limit."` Returns the session immediately. `suggest_outfit` is never called.

**Concrete example from testing:**
```
query = "designer ballgown size XXS under $5"
→ search_listings("designer ballgown", size="XXS", max_price=5.0) → []
→ session["error"] = "No listings matched your search..."
→ session["fit_card"] = None  (never set)
→ suggest_outfit never called (verified with mock in test suite)
```

---

### `suggest_outfit` — wardrobe is empty

**Failure mode:** `wardrobe["items"]` is an empty list — the user has no wardrobe entered yet.

**Agent response:** The tool handles this internally. It switches to a general styling prompt (what types of bottoms, shoes, and outerwear pair well with the item) instead of a wardrobe-specific one, and returns styling advice as a non-empty string. The planning loop continues normally to `create_fit_card` — no error is set, no early exit.

**Concrete example from testing:**
```python
mock_get_client.return_value = _mock_groq("Pair with wide-leg trousers and chunky sneakers.")
result = suggest_outfit(SAMPLE_ITEM, EMPTY_WARDROBE)
assert isinstance(result, str)
assert len(result) > 0  # non-empty — no crash, no error string
```

---

### `create_fit_card` — empty outfit string

**Failure mode:** `outfit` argument is empty or whitespace-only.

**Agent response:** `create_fit_card` guards against this internally and returns `"Could not generate fit card: outfit suggestion was empty."` Stored in `session["fit_card"]` and shown in the fit card panel. `session["error"]` remains `None` — the listing and outfit panels still render.

**Concrete example from testing:**
```python
result = create_fit_card("", SAMPLE_ITEM)
assert "empty" in result.lower()  # error string, not an exception
```

---

## Spec Reflection

**One way the spec helped:** Writing specific state transitions in planning.md before writing any code made `run_agent()` mechanical to implement. The State Management table named every session key, what sets it, and what reads it — there were no judgment calls left to make during coding. The error messages in the implementation are word-for-word matches to the Planning Loop spec because they were written there first.

**One way implementation diverged from the spec:** The Error Handling table in planning.md originally listed `suggest_outfit`'s failure mode as "Wardrobe is empty." Through testing, this turned out to be wrong — an empty wardrobe is handled gracefully inside the tool itself by switching to general styling advice. The real failure mode is the LLM returning an empty string. The implementation handles this correctly; the planning.md table entry was the thing that needed fixing. Writing the tests first exposed the mismatch before it could cause a silent bug in the planning loop.

---

## AI Usage

**Instance 1 — Implementing `search_listings`:**
I directed Claude to implement `search_listings()` using the Tool 1 spec from planning.md (inputs with types, the fields to match against, scoring rules, and the empty-results failure mode), and to use `load_listings()` from the existing data loader rather than re-implementing file loading. The generated code was correct on the filtering logic but I revised the size matching from an exact equality check (`listing["size"] == size`) to a case-insensitive substring match (`size.lower() in listing["size"].lower()`). The exact match would have failed for sizes like "S/M" when the user typed "M", which is a real case in the dataset.

**Instance 2 — Implementing `run_agent()`:**
I directed Claude to implement `run_agent()` using the Planning Loop section of planning.md and the Architecture diagram, and to wire the three tools together using the session dict defined in `_new_session()`. Before accepting the output I checked: does it branch on `search_results` being empty? Does it store `results[0]` in `session["selected_item"]` specifically? Does it check `outfit_suggestion` for an empty string before calling `create_fit_card`? All three passed. I also added `_parse_query()` as a helper that wasn't in the original spec — the agent.py TODO mentioned parsing but didn't define how, so I used regex to extract size and price tokens and strip filler words, then verified it against four test queries before wiring it into the loop.
