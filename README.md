# 🧠 Agnes – AI Supply Chain Intelligence System

> A transparent, explainable AI system for **supplier consolidation, compliance reasoning, and sourcing optimization** in the CPG industry.

---

# 🚀 Overview

Agnes transforms fragmented supply chain data into **structured, explainable sourcing decisions**.

It answers:

- Which ingredients are functionally identical across companies?
- Which suppliers can be consolidated safely?
- What compliance risks exist in substitutions?
- How confident is each recommendation — and why?

> Unlike typical ML systems, Agnes is built as a **full decision pipeline with traceable reasoning, evidence, and scoring.**

---

```mermaid
flowchart TD

%% ─────────────────────────────
%% Phase 1: Data Ingestion & Structuring
%% ─────────────────────────────
A[(SQLite Database)] --> B[Data Extraction Layer]
B --> C[Ingredient Normalization & Semantic Matching]
C --> D[Cross-Company Substitution Groups]

%% ─────────────────────────────
%% Phase 2: External Intelligence & Enrichment
%% ─────────────────────────────
D --> E[External Intelligence Layer]

E --> F[iHerb / Supplier Scraping APIs]
E --> G[Supplier Websites: Certifications, Specs, Geography]
E --> H[LLM-assisted Compliance Inference]

F & G & H --> I[(Enriched Knowledge Base)]

%% ─────────────────────────────
%% Phase 3: Retrieval & Grounding (RAG Layer)
%% ─────────────────────────────
I --> R[Embedding Index + RAG Retrieval System]
R --> Q[Contextual Grounding over Proposals & Evidence]

%% ─────────────────────────────
%% Phase 4: Reasoning & Optimization Engine
%% ─────────────────────────────
Q --> J[Substitution Validator]
J --> K[Compliance & Risk Checker]

K --> L[Multi-Objective Sourcing Optimizer]

L --> M1[Cost Savings Objective]
L --> M2[Compliance Probability Objective]
L --> M3[Supplier Concentration Risk Objective]
L --> M4[Data Quality / Uncertainty Objective]

M1 & M2 & M3 & M4 --> N[Pareto Frontier Selection Engine]

%% ─────────────────────────────
%% Phase 5: Trust, Explainability & Uncertainty
%% ─────────────────────────────
N --> O[Confidence Scoring Module]
O --> P[Verification & Hallucination Guardrails]
P --> U[Uncertainty & Evidence Attribution Layer]

%% ─────────────────────────────
%% Phase 6: Output Layer
%% ─────────────────────────────
U --> V[Evidence Trail Builder]
V --> W[Agnes Dashboard & Chat UI (RAG-powered)]

%% ─────────────────────────────
%% Feedback Loop
%% ─────────────────────────────
W -.-> |Human-in-the-Loop Feedback| C

%% ─────────────────────────────
%% Styling
%% ─────────────────────────────
style C fill:#ff6b6b,color:white
style E fill:#ff6b6b,color:white
style R fill:#9c27b0,color:white
style L fill:#ff9800,color:white
style N fill:#4caf50,color:white
style O fill:#4caf50,color:white
style W fill:#2196f3,color:white
```

# 🧩 Core Idea (Why this is powerful)

Agnes is not just prediction — it is:

### ✔ Multi-objective decision system

It balances:

- 💰 Cost savings (consolidation efficiency)
- ⚖ Compliance safety (certifications, regulatory risk)
- 📊 Data quality (scraped vs missing vs inferred)
- 🏭 Supplier coverage (market fragmentation reduction)

### ✔ Pareto-aware reasoning (implicit)

Recommendations are not single-optimum:

- Some suppliers maximize savings
- Others maximize compliance safety
- Others maximize data certainty

Agnes surfaces **trade-offs instead of hiding them**

---

# 🏗 System Architecture

## 🔹 Phase 1 – Data Extraction

- Extracts raw materials (SKUs)
- Maps companies → ingredients → suppliers
- Builds structured relational dataset

---

## 🔹 Phase 2 – External Enrichment (Scraping Layer)

- Scrapes supplier websites + product pages
- Extracts certifications (organic, halal, GMP, etc.)
- Builds compliance evidence database
- Assigns confidence scores to scraped data

> This is the **external intelligence layer**

---

## 🔹 Phase 3 – Reasoning Engine (Core Intelligence)

### What happens here

- Groups functionally identical ingredients
- Detects substitution opportunities
- Evaluates supplier consolidation potential
- Runs compliance validation (PASS / FAIL / UNKNOWN)
- Computes:
  - 💰 estimated savings
  - ⚠ risk factors
  - 📦 coverage across companies

### Outputs

- Sourcing proposals
- Verification results
- Risk analysis
- Structured reasoning artifacts

---

## 🔹 Phase 4 – Output & Intelligence Layer

- FastAPI backend
- Retrieval system over:
  - proposals
  - evidence (scraped + enriched data)
- Evidence Trail Builder (explainability engine)
- Chat agent (RAG-based optional LLM interface)

> This phase turns raw reasoning into a **queryable intelligence system**

---

# 🧠 Key System Strengths

## 1. 🔍 Full Explainability (not a black box)

Every decision includes:

- Supplier identity proof
- Compliance verification status
- Risk factors
- Evidence citations (scraped sources)
- Confidence score breakdown

---

## 2. 📊 Structured Optimization Logic

Each recommendation is computed using explicit signals:

- Functional equivalence (ingredient matching)
- Compliance coverage
- Supplier reach across companies
- Data completeness (real vs missing vs inferred)

## 4. 🌐 Evidence-Based AI (Scraping + Grounding)

The system explicitly tracks:

- scraped supplier pages
- certifications
- compliance requirements
- product-level evidence

> Every recommendation is traceable to real sources

---

## 5. 🧠 Hybrid AI Design

Agnes combines:

- deterministic rule-based reasoning (core engine)
- retrieval system (vector + fallback hashing)
- optional LLM layer (chat interface)

✔ Fully functional even WITHOUT API keys

---

## 6. ⚠ Uncertainty Handling

Instead of guessing, Agnes explicitly outputs:

- UNKNOWN when data is missing
- REVIEW_NEEDED when partial compliance exists
- confidence penalties for low-quality data

> No hallucinated certifications allowed

---

# 🚀 Setup & Running the Demo

## 1. Prerequisites

- **Python 3.10+**
- **Node.js & npm** (for the Next.js frontend)
- **OpenAI API Key** (required for semantic matching, enrichment, and the RAG chat)
- **SQLite** (pre-installed with Python)

---

## 2. Clone the Repository

```bash
git clone https://github.com/<your-github-username>/Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes.git
cd Makeathon-TUM.ai-2026-Spherecast-Challenge-Agnes/agnes
```

---

## 3. Environment Setup

### Backend (Python)

```bash
python -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the `agnes/` directory (or set environment variables):

```env
OPENAI_API_KEY=your_api_key_here
OPENAI_CHAT_MODEL=gpt-4o
```

---

## 4. Running the Intelligence Pipeline

Agnes processes data in phases. You must run these to populate the enrichment data and build the search index.

### Phase 1: Semantic Matching

Groups raw materials across 61 companies into substitution groups.

```bash
python -m backend.run_phase1
```

### Phase 4: Build RAG Index & Evidence Trails

This generates the sourcing proposals and builds the embedding index for the Chat AI.

```bash
python -m backend.run_phase4 --rebuild-index
```

---

## 5. Run the Servers

### Backend API (FastAPI)

```bash
uvicorn backend.main:app --reload --port 8000
```

The API will be live at `http://localhost:8000`. You can view the automated docs at `http://localhost:8000/docs`.

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

The Dashboard will be live at `http://localhost:3000`.

---

## 6. Testing the System

### Verify RAG Chat via CLI

```bash
curl -X POST http://localhost:8000/api/chat \
-H "Content-Type: application/json" \
-d '{
  "messages": [
    {"role": "user", "content": "Which supplier should we consolidate Vitamin D3 for?"}
  ]
}'
```

---

## 7. System Architecture Flow

- **Phase 1 (Extraction):** Parses SKUs and clusters 876 raw materials using OpenAI embeddings.
- **Phase 2 (Enrichment):** Scrapes iHerb and uses LLM agents to infer compliance requirements for finished goods.
- **Phase 3 (Reasoning):** Validates substitutions against compliance constraints and calculates savings.
- **Phase 4 (Output):** Builds the evidence-backed proposals and the retrieval index.

---

## 🎯 Result

You now have a working supply chain intelligence engine capable of finding millions in potential savings with full compliance verification and a RAG-powered chat interface.
