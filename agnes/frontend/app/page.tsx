"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { 
  ArrowRight, 
  CheckCircle2, 
  AlertTriangle, 
  TrendingUp, 
  FileCheck,
  ShieldAlert,
  Loader2,
  Box
} from "lucide-react";

interface Stats {
  proposal_count: number;
  verified_count: number;
  avg_confidence: number;
  avg_savings_pct: number;
  by_priority: Record<string, number>;
  by_compliance: Record<string, number>;
}

interface Proposal {
  id: number;
  ingredient_group_id: number;
  recommended_supplier_id: number;
  recommended_supplier_name: string;
  companies_consolidated: string[];
  members_served: number;
  total_companies_in_group: number;
  estimated_savings_pct: number;
  compliance_status: string;
  confidence_score: number;
  priority: string;
  verification_passed: boolean;
  canonical_name: string;
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [statsRes, propsRes] = await Promise.all([
          fetch("http://127.0.0.1:8000/api/stats"),
          fetch("http://127.0.0.1:8000/api/proposals")
        ]);
        
        if (statsRes.ok) setStats(await statsRes.json());
        if (propsRes.ok) setProposals(await propsRes.json());
      } catch (err) {
        console.error("Failed to fetch data", err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-slate-400" />
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-in fade-in duration-500">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-slate-900">Dashboard</h1>
          <p className="text-slate-500 mt-2">Overview of AI-generated sourcing proposals.</p>
        </div>
      </div>

      {stats && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard 
            title="Total Proposals" 
            value={stats.proposal_count.toString()} 
            icon={<Box className="h-5 w-5 text-blue-500" />} 
          />
          <StatCard 
            title="Avg Est. Savings" 
            value={`${stats.avg_savings_pct}%`} 
            icon={<TrendingUp className="h-5 w-5 text-emerald-500" />} 
          />
          <StatCard 
            title="Verified by Agent" 
            value={stats.verified_count.toString()} 
            icon={<CheckCircle2 className="h-5 w-5 text-violet-500" />} 
          />
          <StatCard 
            title="High Priority" 
            value={(stats.by_priority["HIGH"] || 0).toString()} 
            icon={<AlertTriangle className="h-5 w-5 text-amber-500" />} 
          />
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="border-b border-slate-200 px-6 py-4">
          <h2 className="text-lg font-semibold text-slate-800">Sourcing Consolidation Proposals</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-500">
              <tr>
                <th className="px-6 py-3 font-medium">Ingredient</th>
                <th className="px-6 py-3 font-medium">Recommended Supplier</th>
                <th className="px-6 py-3 font-medium">Est. Savings</th>
                <th className="px-6 py-3 font-medium">Confidence</th>
                <th className="px-6 py-3 font-medium">Compliance</th>
                <th className="px-6 py-3 font-medium">Priority</th>
                <th className="px-6 py-3 font-medium text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {proposals.map((p) => (
                <tr key={p.id} className="hover:bg-slate-50 transition-colors group">
                  <td className="px-6 py-4">
                    <div className="font-medium text-slate-900">{p.canonical_name}</div>
                    <div className="text-xs text-slate-500 mt-1">{p.members_served} of {p.total_companies_in_group} companies</div>
                  </td>
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center gap-1.5 font-medium text-slate-700">
                      {p.recommended_supplier_name}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <span className="text-emerald-600 font-semibold">+{p.estimated_savings_pct}%</span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-16 bg-slate-100 rounded-full overflow-hidden">
                        <div 
                          className={`h-full rounded-full ${p.confidence_score > 80 ? 'bg-emerald-500' : p.confidence_score > 60 ? 'bg-amber-500' : 'bg-red-500'}`}
                          style={{ width: `${p.confidence_score}%` }}
                        />
                      </div>
                      <span className="text-xs text-slate-600">{p.confidence_score}%</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    {p.compliance_status === 'PASSED' ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-600/20">
                        <FileCheck className="h-3 w-3" /> Passed
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-red-50 px-2 py-1 text-xs font-medium text-red-700 ring-1 ring-inset ring-red-600/10">
                        <ShieldAlert className="h-3 w-3" /> Failed
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4">
                    <span className={`inline-flex items-center rounded-md px-2 py-1 text-xs font-medium ring-1 ring-inset ${
                      p.priority === 'HIGH' ? 'bg-red-50 text-red-700 ring-red-600/10' : 
                      p.priority === 'MEDIUM' ? 'bg-amber-50 text-amber-800 ring-amber-600/20' : 
                      'bg-slate-50 text-slate-600 ring-slate-500/10'
                    }`}>
                      {p.priority}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <Link 
                      href={`/proposals/${p.id}`}
                      className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-slate-950 disabled:pointer-events-none disabled:opacity-50 hover:bg-slate-100 h-8 w-8 text-slate-500 group-hover:text-slate-900 group-hover:bg-slate-200"
                    >
                      <ArrowRight className="h-4 w-4" />
                    </Link>
                  </td>
                </tr>
              ))}
              {proposals.length === 0 && !loading && (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center text-slate-500">
                    No sourcing proposals found. Run Phase 1-3 first.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function StatCard({ title, value, icon }: { title: string; value: string; icon: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-center gap-4">
        <div className="rounded-lg bg-slate-50 p-3 ring-1 ring-inset ring-slate-200/50">
          {icon}
        </div>
        <div>
          <p className="text-sm font-medium text-slate-500">{title}</p>
          <p className="text-2xl font-semibold tracking-tight text-slate-900">{value}</p>
        </div>
      </div>
    </div>
  );
}
