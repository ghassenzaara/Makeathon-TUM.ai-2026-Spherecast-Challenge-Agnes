"""
Standalone mock API server — no database required.
Run from agnes/:
    uvicorn mock_api:app --reload --port 8000
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Agnes Mock API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mock proposals list ────────────────────────────────────────────────────────

PROPOSALS = [
    {
        "id": 1,
        "ingredient_group_id": 101,
        "recommended_supplier_id": 11,
        "recommended_supplier_name": "Cargill Specialty Ingredients",
        "companies_consolidated": ["NutriCo", "VitaPlus", "HealthEdge", "PureLife"],
        "members_served": 4,
        "total_companies_in_group": 5,
        "estimated_savings_pct": 22.5,
        "compliance_status": "ALL_PASS",
        "confidence_score": 88,
        "priority": "HIGH",
        "verification_passed": True,
        "canonical_name": "Citric Acid Anhydrous",
    },
    {
        "id": 2,
        "ingredient_group_id": 102,
        "recommended_supplier_id": 12,
        "recommended_supplier_name": "BASF Human Nutrition",
        "companies_consolidated": ["VitaPlus", "SunSource", "NovaNutrition"],
        "members_served": 3,
        "total_companies_in_group": 4,
        "estimated_savings_pct": 28.0,
        "compliance_status": "ALL_PASS",
        "confidence_score": 91,
        "priority": "HIGH",
        "verification_passed": True,
        "canonical_name": "Cholecalciferol (Vitamin D3)",
    },
    {
        "id": 3,
        "ingredient_group_id": 103,
        "recommended_supplier_id": 13,
        "recommended_supplier_name": "Univar Solutions",
        "companies_consolidated": ["HealthEdge", "PureLife"],
        "members_served": 2,
        "total_companies_in_group": 5,
        "estimated_savings_pct": 18.0,
        "compliance_status": "REVIEW_NEEDED",
        "confidence_score": 47,
        "priority": "HIGH",
        "verification_passed": False,
        "canonical_name": "Magnesium Stearate",
    },
    {
        "id": 4,
        "ingredient_group_id": 104,
        "recommended_supplier_id": 14,
        "recommended_supplier_name": "Ingredion Inc.",
        "companies_consolidated": ["NutriCo", "BioSource", "VitaPlus"],
        "members_served": 3,
        "total_companies_in_group": 4,
        "estimated_savings_pct": 15.5,
        "compliance_status": "ALL_PASS",
        "confidence_score": 79,
        "priority": "MEDIUM",
        "verification_passed": True,
        "canonical_name": "Zinc Gluconate",
    },
    {
        "id": 5,
        "ingredient_group_id": 105,
        "recommended_supplier_id": 15,
        "recommended_supplier_name": "ADM Nutrition",
        "companies_consolidated": ["SunSource", "HealthEdge"],
        "members_served": 2,
        "total_companies_in_group": 3,
        "estimated_savings_pct": 12.0,
        "compliance_status": "PARTIAL",
        "confidence_score": 55,
        "priority": "MEDIUM",
        "verification_passed": False,
        "canonical_name": "Ascorbic Acid (Vitamin C)",
    },
    {
        "id": 6,
        "ingredient_group_id": 106,
        "recommended_supplier_id": 16,
        "recommended_supplier_name": "Roquette Frères",
        "companies_consolidated": ["NovaNutrition", "PureLife", "NutriCo"],
        "members_served": 3,
        "total_companies_in_group": 3,
        "estimated_savings_pct": 19.0,
        "compliance_status": "ALL_PASS",
        "confidence_score": 72,
        "priority": "MEDIUM",
        "verification_passed": True,
        "canonical_name": "Sunflower Lecithin",
    },
    {
        "id": 7,
        "ingredient_group_id": 107,
        "recommended_supplier_id": 17,
        "recommended_supplier_name": "Omega Protein Corp.",
        "companies_consolidated": ["BioSource", "VitaPlus"],
        "members_served": 2,
        "total_companies_in_group": 4,
        "estimated_savings_pct": 20.0,
        "compliance_status": "PARTIAL",
        "confidence_score": 48,
        "priority": "HIGH",
        "verification_passed": False,
        "canonical_name": "Iron Bisglycinate Chelate",
    },
    {
        "id": 8,
        "ingredient_group_id": 108,
        "recommended_supplier_id": 18,
        "recommended_supplier_name": "Minerals Technologies Inc.",
        "companies_consolidated": ["HealthEdge", "NutriCo"],
        "members_served": 2,
        "total_companies_in_group": 3,
        "estimated_savings_pct": 16.0,
        "compliance_status": "ALL_PASS",
        "confidence_score": 82,
        "priority": "MEDIUM",
        "verification_passed": True,
        "canonical_name": "Calcium Carbonate",
    },
    {
        "id": 9,
        "ingredient_group_id": 109,
        "recommended_supplier_id": 19,
        "recommended_supplier_name": "Lonza Group",
        "companies_consolidated": ["SunSource", "NovaNutrition"],
        "members_served": 2,
        "total_companies_in_group": 2,
        "estimated_savings_pct": 11.0,
        "compliance_status": "ALL_PASS",
        "confidence_score": 68,
        "priority": "LOW",
        "verification_passed": True,
        "canonical_name": "Niacinamide (Vitamin B3)",
    },
    {
        "id": 10,
        "ingredient_group_id": 110,
        "recommended_supplier_id": 20,
        "recommended_supplier_name": "Arjuna Natural Ltd.",
        "companies_consolidated": ["PureLife"],
        "members_served": 1,
        "total_companies_in_group": 2,
        "estimated_savings_pct": 8.0,
        "compliance_status": "REVIEW_NEEDED",
        "confidence_score": 34,
        "priority": "LOW",
        "verification_passed": False,
        "canonical_name": "Organic Flaxseed Oil",
    },
]

# ── Evidence trails per proposal ──────────────────────────────────────────────

EVIDENCE_TRAILS = {
    1: {
        "proposal_id": 1,
        "canonical_name": "Citric Acid Anhydrous",
        "recommended_supplier": {"id": 11, "name": "Cargill Specialty Ingredients"},
        "headline": (
            "Consolidating Citric Acid Anhydrous purchasing from 4 companies to Cargill Specialty Ingredients "
            "is estimated to save 22.5% annually. All compliance requirements — including Non-GMO and Kosher — "
            "are verified against Cargill's current certification portfolio."
        ),
        "metrics": {
            "companies_consolidated": 4,
            "total_companies_in_group": 5,
            "members_served": 12,
            "estimated_savings_pct": 22.5,
            "confidence_score": 88,
            "priority": "HIGH",
            "compliance_status": "ALL_PASS",
        },
        "claims": [
            {
                "claim": "Cargill Specialty Ingredients holds a current Non-GMO Project Verified certificate for Citric Acid.",
                "status": "VERIFIED",
                "citations": [
                    {
                        "label": "Cargill Non-GMO Technical Data Sheet",
                        "url": "https://www.cargill.com/food-beverage/na/citric-acid",
                        "scraped_at": "2026-04-15T09:22:00Z",
                        "confidence": 0.91,
                        "snippet": "Cargill Citric Acid Anhydrous is manufactured via microbial fermentation of non-GMO dextrose. Non-GMO Project Verified certificate #NGP-2024-CA-7712 valid through December 2026.",
                    }
                ],
            },
            {
                "claim": "Cargill Citric Acid meets Kosher certification requirements for NutriCo and VitaPlus finished goods.",
                "status": "VERIFIED",
                "citations": [
                    {
                        "label": "Orthodox Union Kosher Registry",
                        "url": "https://oukosher.org/",
                        "scraped_at": "2026-04-15T09:25:00Z",
                        "confidence": 0.87,
                        "snippet": "Cargill Incorporated — Citric Acid (Anhydrous). Certified Kosher Pareve. Certificate OU-2025-112847. Valid January 2025 – December 2026.",
                    }
                ],
            },
            {
                "claim": "Consolidating to Cargill reduces supplier count from 5 to 1 for this ingredient category.",
                "status": "VERIFIED",
                "citations": [
                    {
                        "label": "Agnes Phase 3 Optimizer",
                        "url": "",
                        "scraped_at": "2026-04-16T14:00:00Z",
                        "confidence": 0.95,
                        "snippet": "Group 101 contains 5 distinct company-supplier pairings for Citric Acid Anhydrous. Cargill covers 4 of the 5 companies. Current annual volume estimate: 65,000 kg combined.",
                    }
                ],
            },
            {
                "claim": "HealthEdge's 'Organic Lemonade' product requires USDA Organic-certified Citric Acid.",
                "status": "UNVERIFIED",
                "citations": [],
            },
        ],
        "risks": [
            "Single-supplier concentration: moving 100% of volume to Cargill eliminates price competition.",
            "HealthEdge organic certification path for Cargill Citric Acid is unconfirmed — verify before contract.",
        ],
        "verification_summary": {
            "counts": {"VERIFIED": 3, "UNVERIFIED": 1, "CONTRADICTED": 0},
            "passed": True,
            "all_verified": False,
        },
    },
    2: {
        "proposal_id": 2,
        "canonical_name": "Cholecalciferol (Vitamin D3)",
        "recommended_supplier": {"id": 12, "name": "BASF Human Nutrition"},
        "headline": (
            "BASF Human Nutrition is the highest-reach supplier for Vitamin D3 / Cholecalciferol across 3 companies "
            "and can deliver a projected 28% cost reduction through consolidated volume pricing. All vegan and "
            "Non-GMO constraints are confirmed via BASF's published qualification documents."
        ),
        "metrics": {
            "companies_consolidated": 3,
            "total_companies_in_group": 4,
            "members_served": 9,
            "estimated_savings_pct": 28.0,
            "confidence_score": 91,
            "priority": "HIGH",
            "compliance_status": "ALL_PASS",
        },
        "claims": [
            {
                "claim": "BASF Cholecalciferol (Quali-D®) is sourced from lanolin-free, vegan-certified lichen.",
                "status": "VERIFIED",
                "citations": [
                    {
                        "label": "BASF Quali-D Vegan Product Sheet",
                        "url": "https://www.basf.com/global/en/who-we-are/organization/group-companies/BASF_Nutrition-Health.html",
                        "scraped_at": "2026-04-14T11:10:00Z",
                        "confidence": 0.93,
                        "snippet": "BASF Quali-D® Vegan is produced via UV-irradiation of lichen-derived ergosterol. Certified Vegan by the Vegan Society (UK). Certificate VS-2025-00341.",
                    }
                ],
            },
            {
                "claim": "BASF Vitamin D3 carries NSF GMP certification relevant to SunSource's sports nutrition line.",
                "status": "VERIFIED",
                "citations": [
                    {
                        "label": "NSF International GMP Registry",
                        "url": "https://info.nsf.org/certified/gmp/",
                        "scraped_at": "2026-04-14T11:15:00Z",
                        "confidence": 0.89,
                        "snippet": "BASF SE — Ludwigshafen Nutrition & Health facility. NSF GMP certified for vitamins and dietary ingredients. Certificate GMP-2024-EUR-0041. Expires March 2027.",
                    }
                ],
            },
            {
                "claim": "'Cholecalciferol' and 'Vitamin D3' are chemically identical (IUPAC: (3β,5Z,7E)-9,10-secocholesta-5,7,10-trien-3-ol).",
                "status": "VERIFIED",
                "citations": [
                    {
                        "label": "Agnes Phase 1 Semantic Clustering",
                        "url": "",
                        "scraped_at": "2026-04-16T14:00:00Z",
                        "confidence": 1.0,
                        "snippet": "Cluster 102: canonical='cholecalciferol-vitamin-d3'. Members: ['Vitamin D3', 'Cholecalciferol', 'Vit-D3 1000 IU', 'Cholecalciferol USP']. Avg cosine similarity: 0.97.",
                    }
                ],
            },
        ],
        "risks": [
            "NovaNutrition's 4th company slot not yet covered — one supplier relationship must be maintained.",
        ],
        "verification_summary": {
            "counts": {"VERIFIED": 3, "UNVERIFIED": 0, "CONTRADICTED": 0},
            "passed": True,
            "all_verified": True,
        },
    },
    3: {
        "proposal_id": 3,
        "canonical_name": "Magnesium Stearate",
        "recommended_supplier": {"id": 13, "name": "Univar Solutions"},
        "headline": (
            "Univar Solutions can consolidate Magnesium Stearate for 2 of 5 companies. However, a compliance gap "
            "was detected: one finished good requires plant-derived Magnesium Stearate, and Univar's current spec "
            "sheet does not confirm plant vs. animal source. Manual verification is required before proceeding."
        ),
        "metrics": {
            "companies_consolidated": 2,
            "total_companies_in_group": 5,
            "members_served": 6,
            "estimated_savings_pct": 18.0,
            "confidence_score": 47,
            "priority": "HIGH",
            "compliance_status": "REVIEW_NEEDED",
        },
        "claims": [
            {
                "claim": "Univar Solutions Magnesium Stearate is plant-derived (vegetable source), suitable for vegan capsules.",
                "status": "CONTRADICTED",
                "citations": [
                    {
                        "label": "Univar Product Specification Sheet (scraped)",
                        "url": "https://www.univarsolutions.com/",
                        "scraped_at": "2026-04-15T10:00:00Z",
                        "confidence": 0.62,
                        "snippet": "Magnesium Stearate NF/BP — Source: Bovine tallow-derived fatty acid. Not suitable for vegan or vegetarian formulations. Halal status: Not certified.",
                    }
                ],
            },
            {
                "claim": "PureLife's 'Vegan Capsule Complex' finished good requires plant-derived lubricants only.",
                "status": "VERIFIED",
                "citations": [
                    {
                        "label": "iHerb Product Page — PureLife Vegan Capsule Complex",
                        "url": "https://www.iherb.com/",
                        "scraped_at": "2026-04-15T09:50:00Z",
                        "confidence": 0.85,
                        "snippet": "PureLife Vegan Capsule Complex. Label claims: 100% Plant-Based, Certified Vegan, No Animal Derivatives. All excipients including flow agents must be plant-sourced per brand standard.",
                    }
                ],
            },
            {
                "claim": "Consolidating to Univar covers HealthEdge's non-vegan tablet lines without compliance issues.",
                "status": "UNVERIFIED",
                "citations": [],
            },
        ],
        "risks": [
            "CONTRADICTED: Univar Magnesium Stearate is bovine-derived — incompatible with PureLife's vegan label claim.",
            "Low confidence score (47%) due to animal-source conflict detected in scrape.",
            "Recommend sourcing plant-derived alternative (e.g., Florasun® from IOI Oleochemicals) before consolidation.",
        ],
        "verification_summary": {
            "counts": {"VERIFIED": 1, "UNVERIFIED": 1, "CONTRADICTED": 1},
            "passed": False,
            "all_verified": False,
        },
    },
    4: {
        "proposal_id": 4,
        "canonical_name": "Zinc Gluconate",
        "recommended_supplier": {"id": 14, "name": "Ingredion Inc."},
        "headline": (
            "Ingredion can supply Zinc Gluconate to 3 companies, representing 75% of the group. "
            "Compliance checks passed for all Non-GMO and USP requirements. Estimated savings of 15.5% "
            "from volume discount negotiation."
        ),
        "metrics": {
            "companies_consolidated": 3,
            "total_companies_in_group": 4,
            "members_served": 8,
            "estimated_savings_pct": 15.5,
            "confidence_score": 79,
            "priority": "MEDIUM",
            "compliance_status": "ALL_PASS",
        },
        "claims": [
            {
                "claim": "Ingredion Zinc Gluconate meets USP monograph specifications required by NutriCo.",
                "status": "VERIFIED",
                "citations": [
                    {
                        "label": "Ingredion Certificate of Analysis",
                        "url": "https://www.ingredion.com/",
                        "scraped_at": "2026-04-13T08:30:00Z",
                        "confidence": 0.88,
                        "snippet": "Zinc Gluconate USP/FCC Grade. Assay: 98.0–102.0% (USP method). Heavy metals: <20 ppm. Certificate of Analysis batch ZG-2025-4471.",
                    }
                ],
            },
        ],
        "risks": ["BioSource (4th company) not covered by this proposal — requires a secondary supplier."],
        "verification_summary": {
            "counts": {"VERIFIED": 1, "UNVERIFIED": 0, "CONTRADICTED": 0},
            "passed": True,
            "all_verified": True,
        },
    },
    5: {
        "proposal_id": 5,
        "canonical_name": "Ascorbic Acid (Vitamin C)",
        "recommended_supplier": {"id": 15, "name": "ADM Nutrition"},
        "headline": (
            "ADM Nutrition can consolidate Ascorbic Acid purchasing for 2 companies. "
            "Compliance is partially confirmed — Non-GMO is verified, but SunSource's Organic requirement "
            "for one SKU could not be confirmed from available data."
        ),
        "metrics": {
            "companies_consolidated": 2,
            "total_companies_in_group": 3,
            "members_served": 5,
            "estimated_savings_pct": 12.0,
            "confidence_score": 55,
            "priority": "MEDIUM",
            "compliance_status": "PARTIAL",
        },
        "claims": [
            {
                "claim": "ADM Ascorbic Acid is Non-GMO Project Verified.",
                "status": "VERIFIED",
                "citations": [
                    {
                        "label": "ADM Non-GMO Compliance Letter",
                        "url": "https://www.adm.com/en-us/products-services/health-wellness/vitamins/",
                        "scraped_at": "2026-04-12T15:00:00Z",
                        "confidence": 0.84,
                        "snippet": "ADM Ascorbic Acid Fine Granular is produced from non-GMO corn via two-step fermentation. Non-GMO Project Verified, certificate NGPV-ADM-2025-VC.",
                    }
                ],
            },
            {
                "claim": "ADM Ascorbic Acid holds USDA Organic certification for SunSource's Organic Vitamin C SKU.",
                "status": "UNVERIFIED",
                "citations": [],
            },
        ],
        "risks": [
            "SunSource organic SKU compliance unconfirmed — do not consolidate this SKU until USDA Organic cert is obtained.",
            "Partial compliance score reduces overall confidence to 55%.",
        ],
        "verification_summary": {
            "counts": {"VERIFIED": 1, "UNVERIFIED": 1, "CONTRADICTED": 0},
            "passed": True,
            "all_verified": False,
        },
    },
}

# Fill remaining proposals with minimal evidence trails
for _p in PROPOSALS:
    if _p["id"] not in EVIDENCE_TRAILS:
        EVIDENCE_TRAILS[_p["id"]] = {
            "proposal_id": _p["id"],
            "canonical_name": _p["canonical_name"],
            "recommended_supplier": {
                "id": _p["recommended_supplier_id"],
                "name": _p["recommended_supplier_name"],
            },
            "headline": (
                f"Consolidating {_p['canonical_name']} purchasing to {_p['recommended_supplier_name']} "
                f"covers {_p['members_served']} of {_p['total_companies_in_group']} companies with an "
                f"estimated {_p['estimated_savings_pct']}% savings."
            ),
            "metrics": {
                "companies_consolidated": _p["members_served"],
                "total_companies_in_group": _p["total_companies_in_group"],
                "members_served": _p["members_served"],
                "estimated_savings_pct": _p["estimated_savings_pct"],
                "confidence_score": _p["confidence_score"],
                "priority": _p["priority"],
                "compliance_status": _p["compliance_status"],
            },
            "claims": [
                {
                    "claim": f"{_p['recommended_supplier_name']} can supply {_p['canonical_name']} to all consolidated companies.",
                    "status": "UNVERIFIED",
                    "citations": [],
                }
            ],
            "risks": ["External enrichment data not yet available — run Phase 2 for full evidence."],
            "verification_summary": {
                "counts": {"VERIFIED": 0, "UNVERIFIED": 1, "CONTRADICTED": 0},
                "passed": True,
                "all_verified": False,
            },
        }

# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "docs_indexed": 42, "mode": "mock"}


@app.get("/api/stats")
def stats():
    by_priority: dict[str, int] = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    by_compliance: dict[str, int] = {}
    verified = 0
    for p in PROPOSALS:
        by_priority[p["priority"]] = by_priority.get(p["priority"], 0) + 1
        by_compliance[p["compliance_status"]] = by_compliance.get(p["compliance_status"], 0) + 1
        if p["verification_passed"]:
            verified += 1
    avg_conf = round(sum(p["confidence_score"] for p in PROPOSALS) / len(PROPOSALS), 1)
    avg_savings = round(sum(p["estimated_savings_pct"] for p in PROPOSALS) / len(PROPOSALS), 1)
    return {
        "proposal_count": len(PROPOSALS),
        "verified_count": verified,
        "avg_confidence": avg_conf,
        "avg_savings_pct": avg_savings,
        "by_priority": by_priority,
        "by_compliance": by_compliance,
    }


@app.get("/api/proposals")
def list_proposals():
    return PROPOSALS


@app.get("/api/proposals/{proposal_id}")
def get_proposal(proposal_id: int):
    trail = EVIDENCE_TRAILS.get(proposal_id)
    if not trail:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return trail


class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: list[ChatMessage]

@app.post("/api/chat")
def chat(req: ChatRequest):
    last = req.messages[-1].content.lower() if req.messages else ""

    if any(w in last for w in ["citric", "e330"]):
        answer = (
            "Citric Acid Anhydrous is the top consolidation opportunity [P1]. "
            "Cargill Specialty Ingredients covers 4 of 5 companies with Non-GMO and Kosher certifications verified [E1]. "
            "Estimated savings: 22.5%. One risk: HealthEdge's organic requirement for one SKU is still unconfirmed [P1]."
        )
    elif any(w in last for w in ["vitamin d", "cholecalciferol", "d3"]):
        answer = (
            "Cholecalciferol and Vitamin D3 are chemically identical — Agnes clustered them with 97% cosine similarity [P2]. "
            "BASF Human Nutrition (Quali-D® Vegan) is fully verified: Vegan Society certified and NSF GMP certified [E2]. "
            "This is the highest-confidence proposal in the system at 91%."
        )
    elif any(w in last for w in ["magnesium stearate", "magnesium"]):
        answer = (
            "Magnesium Stearate is flagged as HIGH priority but has a CONTRADICTED claim [P3]. "
            "Univar Solutions' spec sheet confirms bovine-derived source, which directly conflicts with PureLife's vegan label requirement [E3]. "
            "Do not consolidate this ingredient until a plant-derived alternative (e.g., Florasun®) is sourced."
        )
    elif any(w in last for w in ["high priority", "urgent", "critical", "alert"]):
        answer = (
            "There are 4 HIGH priority proposals: "
            "Citric Acid (P1, 88% confidence, all pass), "
            "Vitamin D3 (P2, 91% confidence, all pass), "
            "Magnesium Stearate (P3, 47% confidence, review needed — contradicted claim), and "
            "Iron Bisglycinate (P7, 48% confidence, partial). "
            "I recommend acting on P1 and P2 immediately, and resolving the vegan source conflict in P3 before proceeding."
        )
    elif any(w in last for w in ["saving", "savings", "cost", "cheap"]):
        answer = (
            "Across 10 proposals, average estimated savings is 17.8%. "
            "The highest individual saving is Vitamin D3 at 28% [P2], followed by Citric Acid at 22.5% [P1]. "
            "The lowest is Organic Flaxseed Oil at 8% [P10], which also has the lowest confidence score (34%)."
        )
    elif any(w in last for w in ["hello", "hi", "hey", "who are you"]):
        answer = (
            "Hello! I'm Agnes, your AI Supply Chain Manager. "
            "I can answer questions about sourcing proposals, ingredient compliance, supplier certifications, and consolidation opportunities. "
            "Try asking: 'What are the high priority alerts?' or 'Tell me about Citric Acid.'"
        )
    else:
        answer = (
            "I found relevant context in the knowledge base. "
            "Currently there are 10 sourcing proposals — 4 HIGH priority, 4 MEDIUM, and 2 LOW. "
            "The system has verified 6 proposals fully. "
            "Ask me about a specific ingredient (e.g. 'citric acid', 'vitamin D3', 'magnesium stearate') for detailed evidence trails."
        )

    return {"answer": answer, "sources": []}
