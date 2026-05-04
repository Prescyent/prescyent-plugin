#!/usr/bin/env python3
"""
build_realistic_dumps.py — bulk up baseline-discovery-v0.5.json with realistic-size raw_subagent_dumps.

Why this exists:
  v0.8.1 sized the email-inline-embed pattern against this fixture's stub raw_subagent_dumps
  (~600 chars per subagent → ~30KB total rendered markdown). Real audits on rich Cowork
  sessions produce ~99KB markdown because every subagent's actual return JSON is 5-10KB
  with full _trace[], findings, opportunities, behavioral findings, etc. The 3.3× size
  gap pushed v0.8.1 into a synthesis-only fallback that wasn't supposed to be the default
  path.

What this does:
  Loads the existing fixture, replaces each subagent's raw_subagent_dumps slot with a
  realistic-size synthetic return (~7-10KB each), writes the fixture back. Result: the
  renderer now produces ~95-100KB markdown matching real-world audit sizes, so smoke
  tests catch size issues in CI rather than dogfood.

Run:
  python3 tests/fixtures/build_realistic_dumps.py

Idempotency:
  Detects if dumps are already realistic-sized (>5KB each) and skips. Safe to re-run.
"""

from __future__ import annotations

import json
from pathlib import Path

FIXTURE_PATH = Path(__file__).parent / "baseline-discovery-v0.5.json"
SIZE_THRESHOLD_BYTES = 5000  # if every dump >5KB, treat as already realistic


def synthetic_trace(subagent_slug: str, n_calls: int = 18) -> list[dict]:
    """Generate a realistic-looking _trace[] array of n MCP tool calls."""
    base_tools = {
        "audit-systems": [
            ("ToolSearch", "hubspot crm deals contacts pipeline keywords"),
            ("get_user_details", "include OWNER + USER + ORG"),
            ("get_organization_details", "include TEAMS + SEATS"),
            ("search_owners", "limit:50"),
            ("search_crm_objects", "deals limit:1 props:7 (probe)"),
            ("search_crm_objects", "deals last 12mo, sorted DESC, limit:100"),
            ("search_crm_objects", "pipeline=52441416 AND open=true (Esker pipeline scan)"),
            ("search_crm_objects", "pipeline=52441416 AND open=true AND closedate NOT_HAS_PROPERTY"),
            ("search_crm_objects", "pipeline=52441416 AND open=true AND notes_last_updated < 30d"),
            ("search_crm_objects", "pipeline=10112334 (DO NOT USE bot signup-intake)"),
            ("search_crm_objects", "pipeline=2123176 (Adyen invite-tracker zombie)"),
            ("search_crm_objects", "pipeline=753622169 (Direct Merchant)"),
            ("search_crm_objects", "pipeline=753622169 AND open AND notes_last_updated<30d"),
            ("search_crm_objects", "contacts limit:1 (probe count)"),
            ("search_crm_objects", "companies limit:1 (probe count)"),
            ("search_crm_objects", "tickets limit:1 (probe count)"),
            ("search_crm_objects", "deals closed-won AND created>=12mo"),
            ("search_crm_objects", "deals closed-lost AND created>=12mo"),
            ("search_crm_objects", "deals hubspot_owner_id NOT_HAS_PROPERTY"),
            ("search_crm_objects", "deals num_associated_contacts=0 AND open"),
            ("search_crm_objects", "tickets created>=90d AND stage NEQ 4"),
            ("search_crm_objects", "deals pipeline=52441416 AND open AND amount NOT_HAS_PROPERTY"),
            ("search_crm_objects", "deals pipeline=52441416 AND open AND dealstage='qualified'"),
            ("search_crm_objects", "tickets hubspot_owner_id NOT_HAS_PROPERTY"),
        ],
        "audit-knowledge": [
            ("ToolSearch", "notion confluence wiki search fetch pages"),
            ("notion-search", "query=company name, page_size=25"),
            ("notion-get-users", "list all users"),
            ("notion-search", "query=sales playbook OR doctrine OR SOP, last 12mo"),
            ("notion-search", "query=archived OR deprecated OR DO NOT EDIT"),
            ("notion-search", "query=customer success OR support docs"),
            ("notion-fetch", "page_id=<sales-wiki-landing>"),
            ("notion-fetch", "page_id=<onboarding-checklist>"),
            ("notion-search", "query=product spec OR roadmap OR engineering"),
            ("notion-search", "query=deal review OR forecast OR pipeline hygiene"),
            ("notion-search", "query=competitor OR battlecard"),
            ("notion-fetch", "page_id=<competitive-intel-page>"),
            ("notion-search", "query=meeting notes OR EOW OR weekly review"),
            ("notion-fetch", "page_id=<weekly-review-template>"),
        ],
        "audit-drive": [
            ("ToolSearch", "drive onedrive sharepoint dropbox box files folders"),
            ("list_recent_files", "orderBy=lastModified, pageSize=50"),
            ("search_files", "owner=me AND modifiedTime>365d, pageSize=50"),
            ("search_files", "title contains playbook|SOP|doctrine|wiki|CLAUDE.md"),
            ("search_files", "title contains draft|recap|memo|plan"),
            ("search_files", "title contains pricing OR quote OR proposal"),
            ("search_files", "modifiedTime<730d AND owner=me (legacy detection)"),
            ("read_file_content", "fileId=<duplicate-claude-md-1>"),
            ("read_file_content", "fileId=<duplicate-claude-md-2>"),
            ("read_file_content", "fileId=<duplicate-claude-md-3>"),
            ("read_file_content", "fileId=<sales-playbook>"),
            ("read_file_content", "fileId=<customer-success-handbook>"),
            ("get_file_metadata", "fileId=<onboarding-folder>"),
            ("search_files", "mimeType=application/pdf, pageSize=20"),
        ],
        "audit-email": [
            ("ToolSearch", "gmail outlook email threads draft labels search"),
            ("search_threads", "newer_than:30d pageSize:50"),
            ("search_threads", "from:me newer_than:30d pageSize:30"),
            ("search_threads", "from:@key-partner.com newer_than:365d"),
            ("search_threads", "from:me to:@key-partner.com newer_than:365d"),
            ("search_threads", "from:donotreply OR no-reply newer_than:90d"),
            ("get_thread", "id=<key-partner-thread-1>"),
            ("get_thread", "id=<key-partner-thread-2>"),
            ("search_threads", "from:me has:attachment newer_than:90d"),
            ("search_threads", "subject:re subject:fwd newer_than:30d (correction loops)"),
            ("list_labels", "all labels"),
            ("search_threads", "label:important newer_than:90d"),
            ("get_thread", "id=<correction-loop-example>"),
        ],
        "audit-comms": [
            ("ToolSearch", "calendar+chat google_chat list_events list_spaces messages"),
            ("ToolSearch", "select 5 specific calendar+chat tools by name"),
            ("list_calendars", "discover calendars"),
            ("list_spaces", "page_size 50"),
            ("list_events", "Q1 sample 90d, pageSize 25"),
            ("list_events", "Q2 sample 90d, pageSize 25"),
            ("list_events", "Q3 sample 90d, pageSize 25"),
            ("list_events", "Q4 sample 90d, pageSize 25"),
            ("list_messages", "spaces/<sales-room>, post-90d, page 30 desc"),
            ("list_messages", "spaces/<eng-room>, post-90d, page 30 desc"),
            ("list_messages", "spaces/<exec-channel>, post-90d, page 30 desc"),
            ("list_messages", "spaces/<dev-channel>, post-90d, page 30 desc"),
            ("list_messages", "spaces/<bigbosses>, post-90d, page 30 desc"),
        ],
        "audit-meeting-transcripts": [
            ("ToolSearch", "fathom granola meeting transcript summary recordings"),
            ("fathom.list_meetings", "created_after 365d, include_summary=true, max_pages=5"),
            ("granola.list_meetings", "custom 365d, include_summary"),
            ("fathom.list_meetings", "page 2 cursor, summaries"),
            ("fathom.list_meetings", "page 3 cursor, no summary (metadata only)"),
            ("fathom.list_meetings", "page 4 cursor, no summary"),
            ("fathom.get_meeting_transcript", "id=<deep-1: weekly review>"),
            ("fathom.get_meeting_transcript", "id=<deep-2: partner debrief>"),
            ("fathom.get_meeting_transcript", "id=<deep-3: kickoff>"),
            ("fathom.get_meeting_transcript", "id=<deep-4: board prep>"),
            ("fathom.get_meeting_transcript", "id=<deep-5: 1on1 leadership>"),
            ("fathom.get_meeting_transcript", "id=<deep-6: customer escalation>"),
        ],
        "audit-stack": [
            ("ToolSearch", "list_connectors registry mcp suggest"),
            ("static_inventory", "pre-detected connectors + plugins from prompt"),
        ],
        "audit-sessions": [
            ("ToolSearch", "session_info list_sessions read_transcript"),
            ("mcp__session_info__list_sessions", "limit:100"),
            ("mcp__session_info__read_transcript", "session=<deal-prep-1>, limit:30"),
            ("mcp__session_info__read_transcript", "session=<call-summary-1>, limit:30"),
            ("mcp__session_info__read_transcript", "session=<dossier-build-1>, limit:30"),
            ("mcp__session_info__read_transcript", "session=<dossier-build-2>, limit:30"),
            ("mcp__session_info__read_transcript", "session=<dossier-build-3>, limit:30"),
            ("mcp__session_info__read_transcript", "session=<weekly-prep>, limit:30"),
            ("mcp__session_info__read_transcript", "session=<email-triage>, limit:30"),
            ("mcp__session_info__read_transcript", "session=<notion-restructure>, limit:30"),
            ("mcp__session_info__read_transcript", "session=<pipeline-review>, limit:30"),
            ("mcp__session_info__read_transcript", "session=<deal-restage>, limit:30"),
            ("mcp__session_info__read_transcript", "session=<board-prep>, limit:30"),
            ("mcp__session_info__read_transcript", "session=<partner-update>, limit:30"),
            ("mcp__session_info__read_transcript", "session=<comp-intel>, limit:30"),
            ("mcp__session_info__read_transcript", "session=<onboarding-doc>, limit:30"),
            ("mcp__session_info__read_transcript", "session=<press-release-draft>, limit:30"),
        ],
        "audit-web-search": [
            ("ToolSearch", "WebSearch ZoomInfo enrich account_research"),
            ("WebSearch", "company name + 'crunchbase' OR 'pitchbook'"),
            ("WebSearch", "company name + 'press release' OR 'news' last 365d"),
            ("WebSearch", "company name + 'leadership' OR 'team'"),
            ("WebSearch", "company name + 'pricing' OR 'how it works'"),
            ("WebSearch", "company name + 'reviews' G2 OR Capterra OR TrustRadius"),
            ("WebSearch", "company name + 'careers' OR 'hiring'"),
            ("WebSearch", "company name + 'integrations' OR 'partners'"),
            ("WebSearch", "company name + 'case study' OR 'customer story'"),
            ("WebSearch", "company name + competitor 1"),
            ("WebSearch", "company name + competitor 2"),
            ("WebSearch", "company name + competitor 3"),
            ("WebSearch", "company name + 'acquisition' OR 'M&A'"),
            ("WebSearch", "company name + 'funding' OR 'series'"),
            ("ZoomInfo.account_research", "company=primary entity"),
            ("ZoomInfo.contact_research", "company=primary entity, role=CEO"),
            ("ZoomInfo.contact_research", "company=primary entity, role=CFO"),
            ("ZoomInfo.contact_research", "company=primary entity, role=COO"),
            ("ZoomInfo.enrich_companies", "domain=primary"),
            ("ZoomInfo.enrich_news", "company=primary, last 90d"),
            ("WebFetch", "url=primary owned site /about"),
        ],
    }
    tools = base_tools.get(subagent_slug, [("ToolSearch", "generic"), ("placeholder", "n/a")])
    out = []
    for tool_name, args in tools[:n_calls]:
        out.append({
            "tool": tool_name,
            "args_summary": args,
            "result_summary": f"Returned data for {args[:60]}",
            "ms": 800 if tool_name == "ToolSearch" else 600,
            "tokens_est": 4000 if tool_name == "ToolSearch" else 1500,
        })
    return out


def synthetic_findings(subagent_slug: str, n: int = 6) -> list[dict]:
    """Generate n realistic-looking findings."""
    prefix_map = {
        "audit-systems": "SYS",
        "audit-knowledge": "KD",
        "audit-drive": "DRV",
        "audit-email": "EM",
        "audit-comms": "COM",
        "audit-meeting-transcripts": "MTG",
        "audit-stack": "STK",
        "audit-sessions": "SES",
        "audit-web-search": "WEB",
    }
    prefix = prefix_map.get(subagent_slug, "GEN")
    sample_titles = [
        "Pipeline contamination concentrated in two zombie pipelines",
        "Owner assignment incomplete on 18% of open deals",
        "Stage-time velocity exceeds reasonable bounds in tier-2 pipeline",
        "Note hygiene degraded — 65% of open deals untouched in 30 days",
        "Forecast credibility is fictitious due to rep abandonment pattern",
        "Custom property explosion — 247 props but 12 actually queried",
        "Workflow automation count high (89) but 23 are paused indefinitely",
        "Cross-object association rate is 34% (industry baseline 78%)",
        "Activity logging gap on partner-deal subset (no calls/emails)",
        "Required-field policies bypassed via admin override on 12% of records",
    ]
    out = []
    for i in range(n):
        title = sample_titles[i % len(sample_titles)]
        out.append({
            "id": f"{prefix}-{i+1:02d}",
            "headline": title,
            "detail": (
                f"Evidence for {prefix}-{i+1:02d}: cross-referenced queries against metadata, "
                f"owner records, and 12-month activity windows. Pattern repeated across ~38% of "
                f"audited records. Operator overhead bands 2-6 hrs/week. Fix is operationally "
                f"simple but requires owner sign-off."
            ),
            "severity": "High" if i < 3 else "Medium" if i < 7 else "Low",
            "confidence": "High" if i < 5 else "Medium",
            "surprise_factor": "High" if i < 3 else "Medium" if i < 6 else "Low",
            "data_source": (
                f"HubSpot {prefix.lower()} queries pulled current date; "
                f"cross-checked against 12-month activity window."
            ),
            "recommendation": (
                f"Schedule a 1-hr admin pass to address root pattern. Document in team CHANGELOG."
            ),
            "effort": "Low" if i < 4 else "Medium",
            "impact": "High" if i < 4 else "Medium",
            "classification": "internal",
            "framework_indexes": {"pcf": "8.6", "bian": None, "togaf": None, "zachman": None},
        })
    return out


def synthetic_dump(subagent_slug: str, company_name: str) -> dict:
    """Build a realistic-size return for one subagent."""
    return {
        "_trace": synthetic_trace(subagent_slug),
        "contract_version": "3.0",
        "subagent": subagent_slug,
        "company_name": company_name,
        "connectors_used": ["HubSpot"] if "systems" in subagent_slug else
                            ["Notion"] if "knowledge" in subagent_slug else
                            ["Google Drive"] if "drive" in subagent_slug else
                            ["Gmail"] if "email" in subagent_slug else
                            ["Google Calendar", "Google Chat"] if "comms" in subagent_slug else
                            ["Fathom", "Granola"] if "meeting" in subagent_slug else
                            ["mcp-registry"] if "stack" in subagent_slug else
                            ["session_info"] if "sessions" in subagent_slug else
                            ["WebSearch", "ZoomInfo"] if "web-search" in subagent_slug else
                            ["unknown"],
        "records_analyzed": {
            "total_records": 2113,
            "total_documents": 235,
            "date_range": "365 days",
        },
        "dimension_scores": {
            "data_accessibility": {"score": 6, "confidence": "High",
                                   "rationale": "Connector returned full result sets within budget."},
            "process_discipline": {"score": 4, "confidence": "High",
                                   "rationale": "Patterns of bypass observed across multiple workflows."},
            "confidentiality_posture": {"score": None, "confidence": None, "rationale": "v0.2-beta — not scored"},
        },
        "findings": synthetic_findings(subagent_slug),
        "behavioral_trace_findings": [
            {"pattern": f"Observed: {subagent_slug} pattern A — weekly, 4-week window",
             "confidence": "High", "evidence": "Calendar + activity logs."},
            {"pattern": f"Observed: {subagent_slug} pattern B — owner-specific cluster",
             "confidence": "Medium", "evidence": "3 owners exhibit same anti-pattern."},
        ],
        "opportunities": [
            {"id": "OPP-01",
             "headline": f"{subagent_slug} workflow standardization candidate",
             "why_now": "AI automation mature; 40-60% efficiency gain plausible.",
             "effort": "Medium", "impact": "High", "confidence": "High", "surprise_factor": "Medium"},
        ],
        "coverage_gaps": [
            {"gap": f"{subagent_slug}: connector scope requires reauth",
             "impact": "Medium",
             "fix": "Reauth in Cowork settings."},
        ],
        "open_questions": [
            {"question": f"{subagent_slug}: Auto-apply or human-approve category-X classification?",
             "recommended_answer": "Auto-apply with 30-day digest review."},
        ],
    }


def main() -> int:
    import sys
    force = "--force" in sys.argv

    if not FIXTURE_PATH.exists():
        print(f"ERROR: fixture not found at {FIXTURE_PATH}")
        return 1
    with FIXTURE_PATH.open() as f:
        fixture = json.load(f)

    company_name = fixture.get("company_name", "Test Company")
    dumps = fixture.get("raw_subagent_dumps", {})

    # Idempotency check — if every dump is already realistic-sized, skip (unless --force)
    if not force and dumps and all(
        len(json.dumps(v)) > SIZE_THRESHOLD_BYTES
        for v in dumps.values()
    ):
        print(f"All {len(dumps)} dumps already >{SIZE_THRESHOLD_BYTES} chars. Pass --force to regenerate.")
        return 0

    # Build realistic dumps for every subagent in the existing keys
    new_dumps = {}
    for slug in dumps.keys():
        new_dumps[slug] = synthetic_dump(slug, company_name)

    fixture["raw_subagent_dumps"] = new_dumps

    # Bump fixture's plugin_version stamp to match v0.8.2
    fixture["plugin_version"] = "0.8.2"

    with FIXTURE_PATH.open("w") as f:
        json.dump(fixture, f, indent=2)

    # Report
    new_size = sum(len(json.dumps(v)) for v in new_dumps.values())
    print(f"Bulked up raw_subagent_dumps for {len(new_dumps)} subagents.")
    print(f"Total dump content: {new_size:,} chars (~{new_size//1024}KB)")
    print(f"Wrote fixture to {FIXTURE_PATH}")
    print(f"Next: re-render and verify markdown is ~95-100KB.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
