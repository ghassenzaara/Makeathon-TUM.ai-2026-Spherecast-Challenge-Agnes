import { Stats, Proposal } from "./types";

export const MOCK_STATS: Stats = {
  proposal_count: 12,
  verified_count: 9,
  avg_savings_pct: 14.8,
  by_priority: { HIGH: 3, MEDIUM: 5, LOW: 4 },
  by_compliance: { ALL_PASS: 8, PARTIAL: 3, REVIEW_NEEDED: 1 },
};

export const MOCK_PROPOSALS: Proposal[] = [
  {
    id: 1,
    canonical_name: "Premium Steel Tubing (1.5mm)",
    priority: "HIGH",
    compliance_status: "ALL_PASS",
    confidence_score: 92,
    recommended_supplier_name: "Industrial Metals Corp",
    estimated_savings_pct: 18.5,
    members_served: 4,
    total_companies_in_group: 5,
    companies_consolidated: ["AutoCenter", "GearWorks", "MetalFab", "BuildIt"],
  },
  {
    id: 2,
    canonical_name: "Bio-Degradable Packaging Foam",
    priority: "MEDIUM",
    compliance_status: "PARTIAL",
    confidence_score: 74,
    recommended_supplier_name: "EcoPack Solutions",
    estimated_savings_pct: 12.2,
    members_served: 8,
    total_companies_in_group: 12,
    companies_consolidated: ["FreshFoods", "GreenMart", "LogiWrap"],
  },
  {
    id: 3,
    canonical_name: "Industrial Grade Lubricant X-9",
    priority: "HIGH",
    compliance_status: "REVIEW_NEEDED",
    confidence_score: 58,
    recommended_supplier_name: "ChemFlow Systems",
    estimated_savings_pct: 21.4,
    members_served: 2,
    total_companies_in_group: 6,
    companies_consolidated: ["HeavyMachinery", "LineOps"],
  }
];
