# Chatbot Integration Guide

This package provides guidance resources for an existing agent or chatbot platform; it does not include a standalone web service.

## Minimum integration

1. Make this Skill's `SKILL.md` and its `references` and `assets` files available to the host on demand. Do not mechanically insert every document into every prompt.
2. Provide web search and page-reading capability, or allow a teacher to provide readable official policy. The host must report read failures instead of pretending it performed a live search.
3. Pass the current date, user role, target competition year, division, and relevant team context to the assistant. Keep unknown fields unknown.
4. Render clickable citations, the Chinese answer, English summary, and site section. Let users see the source year and verification time.
5. For cross-session use, save project state in an access-controlled team space. Before retrieval, verify the user's access to `team_id`/`project_id`; do not trust a self-reported ID alone.

The local knowledge-base tool filters project data but does not provide internet-service authentication. A public deployment needs the host to handle login, access control, rate limits, logs, and model keys. Do not expose a command-line tool directly as a public API.

## Single-turn flow

The host receives user input and only the team state the user may access; the assistant identifies the topic; reads the relevant workflow; retrieves official pages with the search tool; checks year and applicability; produces a cited bilingual answer; and reports that state was saved only after a successful write.

## Acceptance checks

Test a current-rule question, a page that cannot be read, and a past-year example. Verify citations and handling of unknowns. Then correct the year in a second turn and check that context updates. Also test that one team cannot read another team's records. Fluent wording does not establish that fees, deadlines, or safety approvals are correct.

## Known limitations

Dynamic official pages, login gates, and rule updates may prevent access. The package's navigation is not a complete crawler. This release has no paid cloud adapter, automatic annual synchronization, or user-management console. Implement these services according to the chosen host; do not advertise features that are not connected.
