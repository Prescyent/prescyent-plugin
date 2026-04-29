# Widget Form Spec — `/discover` Phase 2

> Canonical definition of the single elicitation form `/discover` renders at Phase 2. Five fields. One submit. All answers return via `mcp__cowork__read_widget_context`.

## Form metadata

| Field | Value |
|---|---|
| `title` | "Tell me about your company" |
| `subtitle` | "I'll use this to scope discovery against your data." |
| `submit_label` | "Run discovery" |
| `skip_label` | "Skip — use defaults" |

## Fields (in render order)

| # | Key | Type | Required | Label / placeholder |
|---|---|---|---|---|
| 1 | `company_name` | text | yes | "What's your company called?" |
| 2 | `user_role` | single-select | yes | "Which describes you best?" |
| 3 | `buyer_intent` | single-select | yes | "What brought you here?" |
| 4 | `verbatim_pain` | text (multiline) | no | "Anything specific been frustrating? (Optional)" |
| 5 | `depth` | single-select | yes | "How deep should the search go?" |

### Field 2 — `user_role` options

| Value | Label |
|---|---|
| `founder` | Founder / CEO |
| `cfo` | CFO / Finance lead |
| `ops` | Head of Ops |
| `sales` | Sales / GTM lead |
| `marketing` | Marketing lead |
| `product` | Product / Engineering lead |
| `other` | Other |

### Field 3 — `buyer_intent` options

| Value | Label |
|---|---|
| `ai-readiness` | I want to understand my current AI readiness |
| `capture-senior-knowledge` | I want to capture senior knowledge before someone leaves |
| `claude-actually-useful` | I want to make Claude actually useful for my team |
| `other` | Something else |

### Field 5 — `depth` options

| Value | Label | Default |
|---|---|---|
| `standard` | Standard — top 10–15 sources | yes |
| `deep` | Deep — broader sweep, more sources | — |

## Defaults applied when the user clicks Skip

```json
{
  "company_name": null,
  "user_role": "other",
  "buyer_intent": "ai-readiness",
  "verbatim_pain": null,
  "depth": "standard"
}
```

`company_name` is required — no useful default exists. If Skip is clicked with `company_name` empty, emit:

> I need a company name to label the report. Re-run `/discover` and fill in that one field.

Then exit cleanly. No subagent dispatch.

## `mcp__visualize__show_widget` invocation

When the widget MCP is available (Cowork host), dispatch the form like this. The exact JSON schema is documented at `mcp__visualize__read_me` — fetch it on first run if uncertain.

```jsonc
mcp__visualize__show_widget({
  "title": "Tell me about your company",
  "subtitle": "I'll use this to scope discovery against your data.",
  "fields": [
    {
      "key": "company_name",
      "type": "text",
      "label": "What's your company called?",
      "required": true
    },
    {
      "key": "user_role",
      "type": "select",
      "label": "Which describes you best?",
      "required": true,
      "options": [
        {"value": "founder",   "label": "Founder / CEO"},
        {"value": "cfo",       "label": "CFO / Finance lead"},
        {"value": "ops",       "label": "Head of Ops"},
        {"value": "sales",     "label": "Sales / GTM lead"},
        {"value": "marketing", "label": "Marketing lead"},
        {"value": "product",   "label": "Product / Engineering lead"},
        {"value": "other",     "label": "Other"}
      ]
    },
    {
      "key": "buyer_intent",
      "type": "select",
      "label": "What brought you here?",
      "required": true,
      "options": [
        {"value": "ai-readiness",              "label": "I want to understand my current AI readiness"},
        {"value": "capture-senior-knowledge",  "label": "I want to capture senior knowledge before someone leaves"},
        {"value": "claude-actually-useful",    "label": "I want to make Claude actually useful for my team"},
        {"value": "other",                     "label": "Something else"}
      ]
    },
    {
      "key": "verbatim_pain",
      "type": "textarea",
      "label": "Anything specific been frustrating? (Optional)",
      "required": false
    },
    {
      "key": "depth",
      "type": "select",
      "label": "How deep should the search go?",
      "required": true,
      "default": "standard",
      "options": [
        {"value": "standard", "label": "Standard — top 10–15 sources"},
        {"value": "deep",     "label": "Deep — broader sweep, more sources"}
      ]
    }
  ],
  "submit_label": "Run discovery",
  "skip_label": "Skip — use defaults"
})
```

Read the submission via:

```jsonc
mcp__cowork__read_widget_context()
// → {"submitted": true, "values": {"company_name": "Acme", "user_role": "founder", ...}}
```

## Fallback — sequential `AskUserQuestion`

In Claude Code or any environment without `mcp__visualize__show_widget`, dispatch five sequential `AskUserQuestion` calls in field order.

- **Q1 (`company_name`)** — single free-text. Empty = abort.
- **Q2 (`user_role`)** — single-select with the seven options above. Empty = abort.
- **Q3 (`buyer_intent`)** — single-select with the four options above. Empty = abort.
- **Q4 (`verbatim_pain`)** — single free-text. **Empty = skip = `null`** (the only field where empty isn't an abort).
- **Q5 (`depth`)** — single-select with the two options above. Empty = abort.

Order matters: company_name first (it labels everything downstream), depth last (lowest-stakes default).

## Argument pre-seed

If the calling command passed `$ARGUMENTS` with `role:<value>` or `depth:<value>`, pre-seed those fields and skip the corresponding form question (or AskUserQuestion call). Pre-seeded fields skip the empty-response contract.

## Voice rules

The widget's title, subtitle, and labels are all user-facing strings. Each one passes the gauntlet at `../../kb-builder/references/voice-rules.md`:

- No banned words.
- Sub-30 words on each line where possible.
- About them, not us.
- No process narration ("now I'll ask you...") anywhere.

The form is a one-shot scope capture. Treat its surface as marketing copy.

## Returned object — `discovery_scope`

After the form returns (or AskUserQuestion fallback completes), the orchestrator builds:

```jsonc
{
  "company_name": "Acme",
  "company_slug": "acme",
  "user_role": "founder",
  "buyer_intent": "ai-readiness",
  "verbatim_pain": "Sales reps don't update HubSpot, leadership flies blind.",
  "depth": "standard",
  "today_date": "2026-04-29",
  "connectors_detected": [...]   // from Phase 1
}
```

`company_slug` derives from `company_name`: lowercase, replace `[^a-z0-9-]+` with `-`, strip leading/trailing hyphens, collapse runs of `-`.
