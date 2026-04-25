

https://github.com/user-attachments/assets/923b77ca-ecf0-4cfd-a97f-7acce71fdd89

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
flowchart LR
    subgraph Data_Acquisition [Data Acquisition & Orchestration]
        direction LR
        Cron[Python Scheduler / Cron] -->|Triggers Every 3 Days| Sources
        
        subgraph Sources [Specific Data Targets]
            direction TB
            S1[Regulations: EUR-Lex, VDI]
            S2[Macro: Copper Prices, Tariffs]
            S3[Certs: DVGW, WRAS]
            S4[Global Patents: Abstracts]
            S5[Competitor PR: Geberit, NIBCO]
        end
        
        Sources -->|POST Raw Data| Webhook[FastAPI Webhook]
    end

    subgraph Backend_Pipeline [Python Data Cleaning Pipeline]
        direction LR
        Webhook --> TimeFilter[Strict Time Filter:<br/>Keep Only Recent]
        TimeFilter --> ZeroShot{Vertex AI:<br/>Zero-Shot Anti-Hallucination}
        ZeroShot -->|Spam/Irrelevant| Discard[Discard]
        ZeroShot -->|Verified Signal| Pydantic[Pydantic Schema Validation]
    end

    subgraph Intelligence_Engine [Vertex AI Reasoning & Classification]
        direction LR
        Pydantic --> DualEval[Vertex AI: Dual-Pass Extraction]
        
        DualEval --> Factors[1. Calculate Routing Factors <br/> Quality, Benefit, Timing, Tech Direction]
        DualEval --> UIMetrics[2. Estimate UI Display Metrics <br/> Relevance, Impact, Urgency, Risk, Profit]
        
        Factors --> Math[Apply Coefficient Weights:<br/>1.0 to 0.3]
        Math --> Classifier{Decision Classifier}
        
        Classifier -->|Gap / Demand| D1[BUILD]
        Classifier -->|Material / Tech Shift| D2[INVEST]
        Classifier -->|Low Confidence / Hype| D4[IGNORE]
        
        %% Both final decisions and UI metrics go to DB
        D1 & D2 & D4 --> DB[(Google Cloud Firestore)]
        UIMetrics -->|Attach to Payload| DB
    end

    subgraph Frontend [React / Vue User Interface]
        direction LR
        DB --> CriticalCheck{Is Update Critical?}
        CriticalCheck -->|Yes| Alert[UI: Urgent Pop-up Alert]
        CriticalCheck -->|No| Dashboard[Dashboard: Trend List & UI Charts]
        Alert --> Dashboard
        
        Dashboard --> TrendPage[Trend Detail Page]
        TrendPage --> ChatUI[On-Page RAG Chatbot]
    end
    
    subgraph RAG_System [Interactive Evidence Agent]
        direction LR
        ChatUI -->|Ask about Decision/Evidence| RAG_API[FastAPI: RAG Chat Endpoint]
        RAG_API -->|1. Fetch Trend Context| DB
        DB -.->|2. Return Evidence Payload| RAG_API
        RAG_API -->|3. Inject Context into Prompt| RAG_LLM{Vertex AI:<br/>Gemini RAG Agent}
        RAG_LLM -->|4
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
## ⚠️ Limitations

The system is a working **prototype**. Due to time and data constraints, several components have been simplified:

* **Heuristic Confidence Scoring:** Reliability scores are currently based on fixed rules rather than being learned from historical labeled data.
* **Data Consistency:** External supplier data gathered via scraping or APIs may be **incomplete or inconsistent** depending on source availability.
* **Inference Precision:** Compliance checking utilizes a hybrid of rule-based logic and LLM assistance; as a result, precision levels may vary.
* **System Integration:** There is currently **no integration** with enterprise procurement systems (e.g., SAP or ERP platforms).
* **Ranking Model:** The system lacks a trained machine learning ranking model due to a **lack of labeled historical sourcing decisions**. 

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
