import { Stats, Proposal } from "./types";

export const MOCK_STATS: Stats = {
  proposal_count: 12,
  verified_count: 9,
  avg_confidence: 82,
  avg_savings_pct: 14.8,
  by_priority: { HIGH: 3, MEDIUM: 5, LOW: 4 },
  by_compliance: { ALL_PASS: 8, PARTIAL: 3, REVIEW_NEEDED: 1 },
};

export const MOCK_PROPOSALS: Proposal[] = [
  {
    id: 1,
    ingredient_group_id: 101,
    recommended_supplier_id: 501,
    canonical_name: "Premium Steel Tubing (1.5mm)",
    priority: "HIGH",
    compliance_status: "ALL_PASS",
    confidence_score: 92,
    recommended_supplier_name: "Industrial Metals Corp",
    estimated_savings_pct: 18.5,
    members_served: 4,
    total_companies_in_group: 5,
    companies_consolidated: ["AutoCenter", "GearWorks", "MetalFab", "BuildIt"],
    verification_passed: true,
  },
  {
    id: 2,
    ingredient_group_id: 102,
    recommended_supplier_id: 502,
    canonical_name: "Bio-Degradable Packaging Foam",
    priority: "MEDIUM",
    compliance_status: "PARTIAL",
    confidence_score: 74,
    recommended_supplier_name: "EcoPack Solutions",
    estimated_savings_pct: 12.2,
    members_served: 8,
    total_companies_in_group: 12,
    companies_consolidated: ["FreshFoods", "GreenMart", "LogiWrap"],
    verification_passed: true,
  },
  {
    id: 3,
    ingredient_group_id: 103,
    recommended_supplier_id: 503,
    canonical_name: "Industrial Grade Lubricant X-9",
    priority: "HIGH",
    compliance_status: "REVIEW_NEEDED",
    confidence_score: 58,
    recommended_supplier_name: "ChemFlow Systems",
    estimated_savings_pct: 21.4,
    members_served: 2,
    total_companies_in_group: 6,
    companies_consolidated: ["HeavyMachinery", "LineOps"],
    verification_passed: false,
  }
];
