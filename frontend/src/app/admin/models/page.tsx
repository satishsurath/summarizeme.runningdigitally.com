import { ModelRegistryAdmin } from "../../../components/ModelRegistryAdmin";

export const metadata = {
  title: "AI Model Registry | SummarizeMe",
  description: "Manage serving endpoints, model qualifications, and runtime concurrency pools.",
};

export default function AdminModelsPage() {
  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950 px-4 py-8">
      <ModelRegistryAdmin />
    </div>
  );
}
