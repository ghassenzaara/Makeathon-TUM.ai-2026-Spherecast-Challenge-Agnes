0# 🏆 Agnes Hackathon — Team Task Plan (5 Members)

> **Challenge:** TUM.ai Makeathon 2026 — Spherecast Challenge
> **Product:** "Agnes" — AI-powered CPG procurement assistant
> **Team size:** 5 | **Technical level:** Not so technical

---

## 🧠 Key Insight for Non-Technical Teams

You don't need 5 engineers. You need **clear ownership** and **the right tools**. This plan splits work into 5 parallel workstreams so nobody is blocked by anyone else. Each person "owns" a lane and uses AI tools (Cursor, Antigravity, ChatGPT, Dify's no-code UI) to do the heavy lifting.

---

## 👥 Role Assignments

### Person 1 — 🗄️ **Data & Knowledge Graph Lead**
> *"I make the data smart"*

**Owns:** SQLite database → Cognee pipeline (Phase 1 of the technical pipeline)

| Task | Detail | Tools |
|------|--------|-------|
| Explore & clean `db.sqlite` | Understand the schema, identify components, suppliers, BOMs | DB Browser for SQLite, ChatGPT |
| Write the ingestion script | Extract data, format documents, run `cognee.add()` + `cognee.cognify()` | Python + Cognee (use the code from your docs as a starting template) |
| Create synthetic/demo data | If the real data is messy, create a clean demo dataset matching the "Citric Acid" scenario | ChatGPT to generate realistic data |
| Test Cognee queries | Verify that `cognee.search("citric acid suppliers")` returns meaningful results | Python REPL |

**Deliverable:** A working Cognee knowledge graph that the backend can query.

---

### Person 2 — ⚙️ **Backend / API Lead**
> *"I connect everything together"*

**Owns:** FastAPI bridge server + Dify workflow (Phase 2 & 3 of the technical pipeline)

| Task | Detail | Tools |
|------|--------|-------|
| Set up FastAPI server | Use the template from your docs — `/api/retrieve` and `/api/memory/add` endpoints | Python + FastAPI + Uvicorn |
| Build the Dify workflow | Wire up the nodes: Start → HTTP Request (Cognee) → LLM → Feedback → End | Dify (visual drag-and-drop, NO coding needed!) |
| Configure the LLM prompt | Write the system prompt that enforces evidence-based reasoning | Dify LLM node |
| Test end-to-end | Send a query through Dify → FastAPI → Cognee → LLM → Response | Postman / Dify test panel |

**Deliverable:** A working API that takes a user query and returns an AI-reasoned recommendation with evidence.

---

### Person 3 — 🎨 **Frontend / UI Lead**
> *"I build what the judges SEE"*

**Owns:** The Agnes Dashboard (the UI from your step-by-step doc)

| Task | Detail | Tools |
|------|--------|-------|
| Build the "Opportunities Inbox" | Cards with savings estimates, risk alerts, quick wins | HTML/CSS/JS or React (use Cursor/Antigravity to generate) |
| Build the "Deep Dive View" | Before/After table, substitution logic display | Same |
| Build the "Trust & Evidence Panel" | Compliance checkmarks with clickable evidence modals | Same |
| Connect to backend API | Fetch recommendations from the Dify/FastAPI endpoint | `fetch()` API calls |
| Make it look polished | Dark mode, clean typography, smooth animations — **this wins hackathons** | CSS, Google Fonts |

**Deliverable:** A beautiful, functional web dashboard that tells the story visually.

> [!TIP]
> **For a non-technical person:** Use Cursor or Antigravity to generate the entire frontend from a description. You don't need to write code from scratch. Describe each screen in detail and iterate.

---

### Person 4 — 📊 **Business Logic & Storytelling Lead**
> *"I make sure we WIN"*

**Owns:** The business narrative, demo data/scenarios, judging criteria alignment

| Task | Detail | Tools |
|------|--------|-------|
| Craft the demo scenario | Flesh out the "GlobalSnacks" story — make it compelling and realistic | Google Docs / Notion |
| Define the savings calculations | Create the exact math: 65,000 kg × price difference = $23,500 savings | Spreadsheet |
| Write compliance evidence text | Create realistic "scraped" evidence snippets for the Trust Panel | Google Docs |
| Prepare the pitch deck | 3-5 slides: Problem → Solution → Demo → Impact → Team | Google Slides / Canva |
| Coach the presenter | Help whoever presents practice the 3-minute pitch | Practice sessions |

**Deliverable:** A compelling business narrative + pitch deck that frames the technical demo perfectly.

> [!IMPORTANT]
> **This role is CRITICAL.** Hackathons are won by storytelling, not just code. The judges need to understand the $23,500 savings, the compliance risk, and why this matters in 3 minutes.

---

### Person 5 — 🔍 **Research & Web Scraping / Demo Support**
> *"I gather evidence and make everything work smoothly"*

**Owns:** External data enrichment + demo preparation + integration testing

| Task | Detail | Tools |
|------|--------|-------|
| Research real supplier data | Find real-world examples of ingredient specs, certifications, pricing | Web search |
| Build mock "scraped" evidence | Create realistic supplier spec sheets, FDA entries, organic certificates | Google Docs / PDF |
| Help Person 2 with Dify | Configure the web scraping nodes or mock the external data | Dify |
| Integration testing | Be the first "user" — go through the full flow and find bugs | The Agnes dashboard |
| Record a backup demo video | Screen-record a perfect run in case of live demo failure | OBS / Loom |

**Deliverable:** Realistic external evidence data + a polished, tested demo flow.

---

## ⏰ Time-Phased Schedule

Assuming a **24-48 hour** hackathon:

### Hours 0–2: 🚀 Kickoff & Setup
| Everyone | Action |
|----------|--------|
| All | Read all docs together, align on the vision |
| All | Set up communication (Discord/WhatsApp group) |
| All | Each person sets up their tools and environment |
| Person 4 | Start drafting the demo scenario immediately |

### Hours 2–8: 🔨 Build Phase 1 (Independent Work)
| Person | Focus |
|--------|-------|
| P1 | Get Cognee running with demo data |
| P2 | Get FastAPI server running, start Dify workflow |
| P3 | Build the UI mockup / first screens |
| P4 | Finalize the demo narrative + start pitch deck |
| P5 | Gather evidence data, create mock certificates |

> [!WARNING]
> **Sync checkpoint at Hour 8!** Everyone shares a 2-minute status update. Identify blockers early.

### Hours 8–16: 🔗 Build Phase 2 (Integration)
| Person | Focus |
|--------|-------|
| P1 + P2 | Connect Cognee ↔ FastAPI — make sure queries return real results |
| P3 + P5 | Integrate frontend with backend API |
| P4 | Refine pitch, help P3 with UI copy/text |

### Hours 16–22: ✨ Polish Phase
| Person | Focus |
|--------|-------|
| P3 | UI polish — animations, dark mode, typography |
| P1 + P2 | Edge cases, error handling, speed optimization |
| P4 + P5 | Full demo rehearsal, fix the story flow |
| P5 | Record backup demo video |

### Hours 22–24: 🎯 Final Prep
| Everyone | Action |
|----------|--------|
| All | Final demo rehearsal (3 full run-throughs) |
| P4 | Final pitch deck review |
| All | Freeze code — NO MORE CHANGES |

---

## 📞 Communication Rules

1. **Use one channel** (Discord or WhatsApp group) for all updates
2. **Hourly check-ins** during build phases — just a one-line status: "Working on X, blocked by Y"
3. **Sync meetings** at Hours 8 and 16 — 15 minutes max
4. **Use a shared task board** — even a simple Notion/Trello board with 3 columns: `To Do | In Progress | Done`

---

## 🤖 AI Tools Cheat Sheet (for Non-Technical Members)

| Need | Tool | How |
|------|------|-----|
| Generate frontend code | **Cursor / Antigravity** | Describe the UI screen in detail, iterate |
| Build backend logic | **Cursor / Antigravity** | Use the code templates from your docs as starting points |
| Build AI workflow (no code) | **Dify** | Drag-and-drop nodes, no coding required |
| Generate demo data | **ChatGPT** | "Generate 20 rows of supplier data for citric acid with varying certifications" |
| Design pitch deck | **Canva** | Use a startup pitch template |
| Create diagrams | **Excalidraw / Mermaid** | Visualize the pipeline architecture |

---

## ⚡ Top 5 Tips for Winning

1. **Demo > Code quality.** Judges see the demo, not your Git history. Make it look amazing.
2. **Evidence panel is your killer feature.** The clickable compliance evidence is what differentiates you. Nail this.
3. **Have a backup plan.** If Cognee fails, hardcode the demo data. The story matters more than the live pipeline.
4. **Practice the pitch 5+ times.** Smooth delivery beats impressive tech every time.
5. **Assign one person to NOT code.** Person 4 (Business Lead) should focus 100% on story + pitch. This is the highest ROI role.

> [!CAUTION]
> **Common hackathon mistake:** Spending 90% of time coding and 10% on the pitch. Flip it to at least 70/30. A mediocre app with a great story beats a great app with no story.
