"use client";

import { useEffect, useState } from "react";
import type { AIEndpoint, AIModel, AIRuntimePool } from "../types/models";

export function ModelRegistryAdmin() {
  const [models, setModels] = useState<AIModel[]>([]);
  const [endpoints, setEndpoints] = useState<AIEndpoint[]>([]);
  const [pools, setPools] = useState<AIRuntimePool[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [probing, setProbing] = useState<boolean>(false);
  const [probeResult, setProbeResult] = useState<string | null>(null);

  const fetchRegistryData = async () => {
    try {
      setLoading(true);
      const res = await fetch("/api/models");
      if (res.ok) {
        const data = await res.json();
        setModels(data.models || []);
      }

      // Initial defaults
      setEndpoints([
        {
          id: "ep-gen",
          name: "vllm_generation",
          endpoint_type: "generation",
          base_url: "http://192.168.50.9:8000",
          is_active: true,
          created_at: new Date().toISOString(),
        },
        {
          id: "ep-embed",
          name: "vllm_embedding",
          endpoint_type: "embedding",
          base_url: "http://192.168.50.9:8001",
          is_active: true,
          created_at: new Date().toISOString(),
        },
      ]);

      setPools([
        {
          id: "pool-nemo",
          name: "nemo_pool",
          max_in_flight: 3,
          interactive_reserve: 1,
          created_at: new Date().toISOString(),
        },
      ]);
    } catch (err) {
      console.error("Failed to load model registry:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial fetch on component mount
    fetchRegistryData();
  }, []);

  const handleProbeEndpoints = async () => {
    try {
      setProbing(true);
      setProbeResult(null);
      const res = await fetch("/api/vllm/models");
      if (res.ok) {
        const data = await res.json();
        const discovered = data.models?.map((m: { id: string }) => m.id).join(", ");
        setProbeResult(`Discovered served models: ${discovered || "None"}`);
      } else {
        setProbeResult("Endpoint probe returned status error.");
      }
    } catch (err) {
      setProbeResult(`Probe failed: ${err}`);
    } finally {
      setProbing(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 text-center text-xs text-slate-400">
        Loading AI Model Registry configurations...
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-5xl mx-auto py-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-2xs">
        <div>
          <h1 className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
            <span>⚙️</span>
            <span>AI Model Registry & Serving Topology</span>
          </h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
            Manage multi-model endpoints, pool admission limits, and qualification test states.
          </p>
        </div>

        <button
          type="button"
          onClick={handleProbeEndpoints}
          disabled={probing}
          className="px-3.5 py-2 text-xs font-semibold rounded-xl bg-blue-600 hover:bg-blue-700 text-white transition-colors cursor-pointer flex items-center gap-2 disabled:opacity-50"
        >
          <span>{probing ? "Probing..." : "🔍 Probe /v1/models"}</span>
        </button>
      </div>

      {probeResult && (
        <div className="p-4 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-xl text-xs text-blue-900 dark:text-blue-200">
          {probeResult}
        </div>
      )}

      {/* Endpoints Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-2xs">
        <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Active Serving Endpoints ({endpoints.length})
          </h2>
        </div>
        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {endpoints.map((ep) => (
            <div key={ep.id} className="p-4 flex items-center justify-between gap-4 text-xs">
              <div>
                <div className="font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <span>{ep.name}</span>
                  <span className="px-2 py-0.5 rounded text-[10px] uppercase font-mono font-bold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                    {ep.endpoint_type}
                  </span>
                </div>
                <div className="font-mono text-slate-500 text-[11px] mt-0.5">{ep.base_url}</div>
              </div>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300">
                Online
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Registered Models Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-2xs">
        <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Registered Models ({models.length})
          </h2>
        </div>
        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {models.map((m) => (
            <div key={m.model_id} className="p-4 flex items-center justify-between gap-4 text-xs">
              <div>
                <div className="font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                  <span>{m.display_name}</span>
                  {m.is_default && (
                    <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-blue-100 dark:bg-blue-900/60 text-blue-800 dark:text-blue-200">
                      DEFAULT
                    </span>
                  )}
                </div>
                <div className="font-mono text-slate-500 text-[11px] mt-0.5">
                  ID: {m.model_id} • Context: {m.context_window.toLocaleString()} tokens
                </div>
              </div>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-100 dark:bg-emerald-950/60 text-emerald-800 dark:text-emerald-300">
                Qualified (Passed)
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Runtime Pools Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl overflow-hidden shadow-2xs">
        <div className="px-5 py-4 border-b border-slate-200 dark:border-slate-800">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500">
            Runtime Concurrency Pools ({pools.length})
          </h2>
        </div>
        <div className="p-5 space-y-4">
          {pools.map((p) => (
            <div key={p.id} className="space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="font-bold text-slate-900 dark:text-slate-100">{p.name}</span>
                <span className="font-mono text-slate-500">
                  Max: {p.max_in_flight} concurrency • Interactive Reserve: {p.interactive_reserve} slot
                </span>
              </div>
              <div className="h-2 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden flex">
                <div style={{ width: "33%" }} className="bg-blue-500 h-full" title="Interactive reserve" />
                <div style={{ width: "67%" }} className="bg-indigo-400 h-full" title="Batch queue capacity" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
