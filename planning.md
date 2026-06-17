# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Filters the listings dataset against the user's query and returns a ranked list of matching items sorted by relevance. It scores each listing by keyword overlap with the description and applies hard filters for size and price before sorting.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): Natural language keywords extracted from the user's query (e.g. "vintage graphic tee") — matched against listing title, description, and style_tags
- `size` (str): The size to filter by (e.g. "M", "W30 L30") — matched against listing size; if None, size filtering is skipped
- `max_price` (float): Upper price ceiling in dollars — listings with price above this are excluded; if None, no price filter is applied

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
A list of listing dicts, each containing: id, title, description, category, style_tags, size, condition, price, colors, brand, platform. Sorted by keyword relevance score, highest first. Returns an empty list if nothing matches.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
The agent sets session["error"] to a message like "No listings matched your search. Try a broader description, a different size, or raise your price limit." and returns the session early — suggest_outfit is never called.

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Takes the selected listing and the user's wardrobe and asks the Groq LLM to suggest 1–2 complete outfits built around the new item. If the wardrobe is empty, it generates general styling advice for the item instead.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): A single listing dict selected from search_results — the item the user is considering buying
- `wardrobe` (dict): A wardrobe dict with an items key containing a list of wardrobe item dicts (each with id, name, category, colors, style_tags, notes). May have an empty items list.

**What it returns:**
<!-- Describe the return value -->
A non-empty string with 1–2 outfit suggestions, each referencing specific wardrobe pieces by name (or general styling tips if the wardrobe is empty).

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
If the LLM call fails or returns an empty string, the agent sets `session["error"]` to "Couldn't generate outfit suggestions — please try again." and returns the session early without calling `create_fit_card`.

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
Takes the outfit suggestion string and the selected listing and asks the Groq LLM to write a 2–4 sentence OOTD caption suitable for Instagram or TikTok. Uses a higher LLM temperature so the tone feels fresh and varied across different inputs.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): The outfit suggestion string from `suggest_outfit`. May be empty or whitespace-only — the tool guards against this internally and returns a descriptive error string instead of raising an exception.
- `new_item` (dict): The selected listing dict, used to pull title, price, and platform into the caption naturally.

**What it returns:**
<!-- Describe the return value -->
A 2–4 sentence string written in a casual, authentic OOTD voice. Mentions the item name, price, and platform once each. 

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
If outfit is empty or whitespace-only, returns a descriptive error string (e.g. "Could not generate fit card: outfit suggestion was empty.") instead of raising an exception.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->

1. Parse the user's query to extract `description` (str), `size` (str or None), and `max_price` (float or None). Store in `session["parsed"]`.

2. Call `search_listings(description, size, max_price)`. Store the returned list in `session["search_results"]`.
   - If `session["search_results"]` is empty: set `session["error"]` to "No listings matched your search. Try a broader description, a different size, or raise your price limit." and return the session immediately. Do not proceed.
   - If non-empty: set `session["selected_item"] = session["search_results"][0]` and proceed.

3. Call `suggest_outfit(new_item=session["selected_item"], wardrobe=session["wardrobe"])`. Store the result in `session["outfit_suggestion"]`.
   - If `session["outfit_suggestion"]` is an empty string: set `session["error"]` to "Couldn't generate outfit suggestions — please try again." and return the session immediately. Do not proceed.
   - If non-empty: proceed.

4. Call `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`. Store the result in `session["fit_card"]`.
   - `create_fit_card` handles its own empty-input guard and returns an error string rather than raising — no additional branching needed here.

5. Return the session. The agent is done.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

All state lives in a single session dict initialized by `_new_session(query, wardrobe)` at the start of each run. Each tool writes its output into a named key, and the next tool reads from that key — the user never re-enters anything between steps.

| Key | Set by | Read by | Contains |
|-----|--------|---------|----------|
| `session["parsed"]` | Planning loop (query parser) | `search_listings` call | `{description, size, max_price}` extracted from user query |
| `session["search_results"]` | `search_listings` | Planning loop (empty check) | Ranked list of matching listing dicts |
| `session["selected_item"]` | Planning loop (`results[0]`) | `suggest_outfit`, `create_fit_card` | Single listing dict — the top search result |
| `session["wardrobe"]` | `_new_session` (passed in by caller) | `suggest_outfit` | User's wardrobe dict with `items` list |
| `session["outfit_suggestion"]` | `suggest_outfit` | Planning loop (empty check), `create_fit_card` | Outfit suggestion string from Groq LLM |
| `session["fit_card"]` | `create_fit_card` | Gradio UI | OOTD caption string (or error string if outfit was empty) |
| `session["error"]` | Planning loop (on early exit) | Gradio UI | Human-readable error message; None on success |

No state is passed between tools directly — every tool receives its inputs as explicit arguments pulled from the session by the planning loop. This means each tool can be called and tested in isolation without needing a live session.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | Sets `session["error"]` to "No listings matched your search. Try a broader description, a different size, or raise your price limit." Displays in the error panel. Interaction stops — `suggest_outfit` is never called. |
| suggest_outfit | Wardrobe is empty | The tool handles this internally — it calls the LLM with a general styling prompt instead of a wardrobe-specific one, and returns styling advice rather than raising or returning an empty string. The planning loop continues normally to `create_fit_card`. |
| create_fit_card | Outfit input is missing or incomplete | Returns a descriptive error string (e.g. "Could not generate fit card: outfit suggestion was empty.") stored in `session["fit_card"]`. Displayed in the fit card panel as a degraded output — `session["error"]` remains None, the listing and outfit panels still show. |

---

## Architecture

```
User query (natural language)
    │
    ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Planning Loop                            │
│                                                                 │
│  Parse query → session["parsed"]                                │
│    description (str), size (str|None), max_price (float|None)   │
│                         │                                       │
│                         ▼                                       │
│  search_listings(description, size, max_price)                  │
│    filters: title, description, style_tags, category, price     │
│                         │                                       │
│           ┌─────────────┴──────────────┐                        │
│     results=[]                   results=[item,...]             │
│           │                            │                        │
│           ▼                            ▼                        │
│  session["error"] =          session["search_results"] = [...]  │
│  "No listings matched..."    session["selected_item"] = [0]     │
│  return session ◄────────────────────  │                        │
│  (early exit)                          ▼                        │
│                         suggest_outfit(selected_item, wardrobe) │
│                           sends item + wardrobe to Groq LLM     │
│                                        │                        │
│                        ┌───────────────┴──────────────┐         │
│                  outfit=""                    outfit="..."       │
│                        │                              │          │
│                        ▼                              ▼          │
│             session["error"] =          session["outfit_        │
│             "Couldn't generate..."      suggestion"] = "..."     │
│             return session ◄────────────────────  │              │
│             (early exit)                          ▼              │
│                         create_fit_card(outfit_suggestion,      │
│                                         selected_item)          │
│                           sends outfit + item to Groq LLM       │
│                                        │                        │
│                        ┌───────────────┴──────────────┐         │
│                 outfit="" (guard)             caption="..."      │
│                        │                              │          │
│                        ▼                              ▼          │
│             session["fit_card"] =       session["fit_card"] =   │
│             "Could not generate        caption string           │
│              fit card: ..."                           │          │
│             (degraded, no hard stop)                  │          │
│                        │                              │          │
│                        └───────────────┬──────────────┘         │
│                                        ▼                        │
│                                 return session                   │
└─────────────────────────────────────────────────────────────────┘
    │
    ▼
Gradio UI displays:
  • session["search_results"][0]  → listing panel
  • session["outfit_suggestion"]  → outfit panel
  • session["fit_card"]           → fit card panel
  • session["error"]              → error panel (replaces all above if set)
```

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**

**Tool 1 — search_listings:** I'll give Claude the Tool 1 block from planning.md (what it does, all three input parameters with types, the return value fields, and the failure mode). I'll also include the listings.json schema so it knows the exact field names to filter against. I'll ask it to implement `search_listings()` using `load_listings()` from the data loader. Before running it, I'll check that the generated code filters by `size` and `max_price` as hard filters, scores by keyword overlap against `title`, `description`, and `style_tags`, drops zero-score results, and sorts highest-first. Then I'll test it with three queries: one that matches multiple listings, one that matches nothing (to verify an empty list is returned), and one with no size or price to verify those filters are skipped.

**Tool 2 — suggest_outfit:** I'll give Claude the Tool 2 block from planning.md (inputs, return type, empty-wardrobe edge case) plus the wardrobe schema from `wardrobe_schema.json`. I'll ask it to implement `suggest_outfit()` using the Groq client, building a prompt that includes the item's `title`, `style_tags`, and `condition`, and the wardrobe's item names and `style_tags`. Before running it, I'll check that the generated code handles an empty `items` list without crashing and that the prompt instructs the LLM to suggest 1–2 complete outfits. I'll test it once with the example wardrobe and once with an empty wardrobe to verify both paths return a non-empty string.

**Tool 3 — create_fit_card:** I'll give Claude the Tool 3 block from planning.md (inputs, return value, caption style guidelines, and the empty-outfit guard). I'll ask it to implement `create_fit_card()` using the Groq client with a higher temperature. Before running it, I'll check that the code guards against an empty or whitespace-only `outfit` string and returns an error string rather than raising, and that the prompt asks for a 2–4 sentence casual caption mentioning `title`, `price`, and `platform`. I'll test it with a real outfit string and once with an empty string to confirm the error path returns a string, not an exception.

**Milestone 4 — Planning loop and state management:**

I'll give Claude the Planning Loop section, the State Management table, and the Architecture diagram from planning.md. I'll ask it to implement `run_agent()` in `agent.py`, wiring the three tools together using the session dict defined in `_new_session()`. Before running it, I'll check that the generated code sets `session["selected_item"] = session["search_results"][0]` (not a different index), checks for an empty `outfit_suggestion` before calling `create_fit_card`, and returns the session early (not raises) on each error branch. I'll verify by running the two test cases already in `agent.py`'s `__main__` block: the happy path query `("vintage graphic tee under $30")`should print a found item, outfit, and fit card; the no-results query ("designer ballgown size XXS under $5") should print only an error message.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->
The planning loop parses the query and extracts `description="vintage graphic tee"`, `size=None`, `max_price=30.0`. It calls `search_listings("vintage graphic tee", size=None, max_price=30.0)`, which filters listings.json against `title`, `description`, `style_tags`, and `price`. It scores by keyword overlap with "vintage graphic tee", drops anything over $30, and returns a ranked list. The top result is `lst_002`: `{"title": "Y2K Baby Tee — Butterfly Print", "price": 18.0, "condition": "excellent", "platform": "depop", "style_tags": ["y2k", "vintage", "graphic tee", "cottagecore"], ...}`. The planning loop sets `session["selected_item"] = results[0]` and proceeds. If the list is empty, the planning loop sets `session["error"]` to "No listings matched your search. Try a broader description, a different size, or raise your price limit." and returns the session immediately without calling `suggest_outfit`.

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->
The planning loop calls `suggest_outfit(new_item=session["selected_item"], wardrobe=session["wardrobe"])`. The wardrobe contains baggy straight-leg jeans, chunky white sneakers, and a vintage black denim jacket (among others). The Groq LLM returns: `"Pair the Y2K baby tee with your baggy straight-leg jeans and chunky white sneakers for an easy streetwear look. Throw your vintage black denim jacket over it and leave it open for a layered 90s vibe."` The planning loop stores this in `session["outfit_suggestion"]` and proceeds. If the LLM returns an empty string, the planning loop sets `session["error"]` to "Couldn't generate outfit suggestions — please try again." and returns early without calling `create_fit_card`.

**Step 3:**
<!-- Continue until the full interaction is complete -->
The planning loop calls `create_fit_card(outfit=session["outfit_suggestion"], new_item=session["selected_item"])`. The Groq LLM returns: `"thrifted this y2k butterfly tee off depop for $18 and it was made for my baggy jeans 🦋 vintage denim jacket on top and we're done. full look in my stories"`. The planning loop stores this in `session["fit_card"]` and returns the session. If `outfit` is empty or whitespace-only, `create_fit_card` returns a descriptive error string (e.g. "Could not generate fit card: outfit suggestion was empty.") which is stored in `session["fit_card"]` — this is a degraded output, not a hard stop.

**Final output to user:**
<!-- What does the user actually see at the end? -->
The Gradio UI displays three panels:
- **Listing:** "Y2K Baby Tee — Butterfly Print — $18.00, depop, excellent condition"
- **Outfit suggestion:** "Pair the Y2K baby tee with your baggy straight-leg jeans and chunky white sneakers..."
- **Fit card:** "thrifted this y2k butterfly tee off depop for $18 and it was made for my baggy jeans 🦋..."

On the error path, only the error panel appears: "No listings matched your search. Try a broader description, a different size, or raise your price limit."