# Per-Proposal Chat with Agnes

## Context

Today Agnes is advisory-only: the human reviews ranked proposals, inspects evidence in [agnes/frontend/app/proposals/[id]/page.tsx](agnes/frontend/app/proposals/[id]/page.tsx), and can chat with the agent — but *only* on the separate [agnes/frontend/app/chat/page.tsx](agnes/frontend/app/chat/page.tsx) page, with no awareness of which proposal the reviewer is looking at. Reviewers have to re-ground the agent every turn ("the Prinova one", "proposal 12 — which supplier was it again?"), which kills the interrogation flow that's supposed to be the whole point of the human-in-the-loop step.

Goal: attach a chat surface **inside** each proposal detail page that is pre-scoped to that proposal, so the user can drill into "why this supplier?", "what certifications are missing?", "what would change your confidence?" without re-stating context. The existing `/api/chat` endpoint and retrieval stack are reusable — we mostly need to (a) give the endpoint a proposal context, (b) bias retrieval to that proposal's evidence, and (c) render the chat alongside the evidence trail.

## Approach

### Backend

**1. Add an optional `proposal_id` to the chat request** in [agnes/backend/phase4_output/api.py:61](agnes/backend/phase4_output/api.py#L61).

```python
class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    proposal_id: int | None = None
```

Pass it through to `chat_answer(msgs, index, proposal_id=req.proposal_id)` at [api.py:149](agnes/backend/phase4_output/api.py#L149).

**2. Scope retrieval to the proposal** in [agnes/backend/phase4_output/chat_agent.py](agnes/backend/phase4_output/chat_agent.py) and [retriever.py](agnes/backend/phase4_output/retriever.py).

In `chat_agent.answer()` ([chat_agent.py:119](agnes/backend/phase4_output/chat_agent.py#L119)), when `proposal_id` is provided:

- Look up the proposal via the existing `get_sourcing_proposal(proposal_id)` ([backend/db/queries.py](agnes/backend/db/queries.py)) and the evidence trail via the existing `build_evidence_trail(proposal_id)` ([evidence_trail_builder.py](agnes/backend/phase4_output/evidence_trail_builder.py)). Reuse — don't duplicate.
- Build a **pinned context block** from that data: headline, metrics, risks, verifications, every claim + citation. This always goes into the prompt regardless of retrieval scores, so the agent can never "forget" which proposal is on screen.
- For the retrieval side, add a lightweight filter to `RetrievalIndex.retrieve()` ([retriever.py:200](agnes/backend/phase4_output/retriever.py#L200)) — e.g. `retrieve(query, proposal_id=None, ingredient_group_id=None, supplier_id=None)`. When a proposal is scoped, prefer evidence docs whose `meta.entity_id` matches the proposal's supplier or group (boost score, or hard-filter to `top_k` scoped + `top_k/2` global as a fallback when scoped pool is thin). The `Doc.meta` already carries `entity_type`, `entity_id`, `ingredient_group_id`, `supplier_id` — no schema change needed.
- Extend `SYSTEM_PROMPT` ([chat_agent.py:27](agnes/backend/phase4_output/chat_agent.py#L27)) with a conditional paragraph: "You are currently helping the user evaluate Proposal {id}. Prefer answers grounded in the PINNED PROPOSAL block; only pull from broader context when the user asks a comparative question."

**3. No new endpoint, no DB migration.** Approve/reject persistence is explicitly out of scope for this task (user asked for chat only). Keep conversation state client-side for now — matches how [`/chat`](agnes/frontend/app/chat/page.tsx) already works.

### Frontend

**1. Extract a reusable `<AgnesChat />` component** from [agnes/frontend/app/chat/page.tsx](agnes/frontend/app/chat/page.tsx) into something like `agnes/frontend/app/components/AgnesChat.tsx`. Props: `{ proposalId?: number; initialGreeting?: string; compact?: boolean }`. The existing `/chat` page renders `<AgnesChat />` with no `proposalId`; the proposal detail page renders it with one.

The component:
- Keeps local `messages` state (same shape as today).
- POSTs to `/api/chat` with `{ messages, proposal_id }`.
- Renders citations from `data.citations` as clickable chips — today they're discarded at [chat/page.tsx:49](agnes/frontend/app/chat/page.tsx#L49). Small upgrade worth doing while we're in there since the proposal chat's whole value is interrogating cited claims.

**2. Mount the chat in the proposal detail page** at [agnes/frontend/app/proposals/[id]/page.tsx](agnes/frontend/app/proposals/[id]/page.tsx), after the Evidence Trail section (~line 244). Seed with a contextual greeting like *"Ask me anything about this proposal — why this supplier, what's missing, what would change my confidence."*

**3. Layout**: keep the page single-column to stay consistent with the current design; the chat becomes a new card at the bottom. A side-by-side split is tempting but would require redoing the `max-w-4xl mx-auto` layout and adds scope.

## Files to modify

- [agnes/backend/phase4_output/api.py](agnes/backend/phase4_output/api.py) — add `proposal_id` to `ChatRequest`, pass through.
- [agnes/backend/phase4_output/chat_agent.py](agnes/backend/phase4_output/chat_agent.py) — accept `proposal_id`, build pinned context, extend system prompt.
- [agnes/backend/phase4_output/retriever.py](agnes/backend/phase4_output/retriever.py) — add scoped filtering in `retrieve()` / `search()`.
- [agnes/frontend/app/chat/page.tsx](agnes/frontend/app/chat/page.tsx) — slim down to a wrapper around the new component.
- `agnes/frontend/app/components/AgnesChat.tsx` — new, extracted component (the one new file this warrants).
- [agnes/frontend/app/proposals/[id]/page.tsx](agnes/frontend/app/proposals/[id]/page.tsx) — mount `<AgnesChat proposalId={trail.proposal_id} />`.

## Verification

1. Start the API: `uvicorn backend.phase4_output.api:app --reload --port 8000` from `agnes/`.
2. Start the frontend dev server and open a proposal (`/proposals/1`).
3. Ask a proposal-specific question ("why did you pick this supplier?") — answer should cite `[P1]` / `[E*]` tied to that proposal's group/supplier.
4. Ask a deliberately off-topic question ("what about vitamin D consolidation?") — answer should still work via the unscoped fallback retrieval tier.
5. Open the standalone `/chat` page — behavior unchanged (regression check for the extracted component).
6. `curl -X POST localhost:8000/api/chat -d '{"messages":[{"role":"user","content":"why this supplier?"}],"proposal_id":1}'` — verify pinned context appears in logs and citations come back.
