"use client";

import { useEffect, useMemo, useState } from "react";
import { RefreshCw, ShieldAlert, Waypoints } from "lucide-react";
import { ApiError } from "@/lib/api";
import {
  useAdminAnnouncementDepartmentBootstrapMutation,
  useAdminAnnouncementRebuildMutation,
  useAdminAnnouncementSchoolBootstrapMutation,
  useAdminContentExplainQuery,
  useAdminContentReclassifyMutation,
  useAdminWorkflowDetailQuery,
  useAdminWorkflowsQuery,
} from "@/hooks/useAdmin";

type Filters = {
  family: string;
  scopeType: string;
  status: string;
  workflowType: string;
  scopeKey: string;
  hostKey: string;
};

const INPUT_CLASS =
  "w-full rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm text-white outline-none transition focus:border-cyan-400/40";

function parseSeedUrls(value: string) {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatTime(value?: string | null) {
  if (!value) return "--";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "请求失败，请稍后重试";
}

function statusClass(status: string) {
  if (status === "done") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-200";
  if (status === "running") return "border-cyan-500/30 bg-cyan-500/10 text-cyan-100";
  if (status === "failed") return "border-rose-500/30 bg-rose-500/10 text-rose-200";
  return "border-amber-500/30 bg-amber-500/10 text-amber-100";
}

export default function AnnouncementGovernanceWorkspace({ enabled }: { enabled: boolean }) {
  const [message, setMessage] = useState("");
  const [filters, setFilters] = useState<Filters>({
    family: "",
    scopeType: "",
    status: "",
    workflowType: "",
    scopeKey: "",
    hostKey: "",
  });
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
  const [schoolName, setSchoolName] = useState("");
  const [schoolHomepage, setSchoolHomepage] = useState("");
  const [schoolSeeds, setSchoolSeeds] = useState("");
  const [departmentSchoolName, setDepartmentSchoolName] = useState("");
  const [departmentName, setDepartmentName] = useState("");
  const [departmentHomepage, setDepartmentHomepage] = useState("");
  const [departmentSeeds, setDepartmentSeeds] = useState("");
  const [rebuildScopeType, setRebuildScopeType] = useState<"school" | "department">("school");
  const [rebuildSchoolName, setRebuildSchoolName] = useState("");
  const [rebuildDepartmentName, setRebuildDepartmentName] = useState("");
  const [rebuildHomepage, setRebuildHomepage] = useState("");
  const [rebuildSeeds, setRebuildSeeds] = useState("");
  const [contentIdInput, setContentIdInput] = useState("");
  const [explainContentId, setExplainContentId] = useState<string | null>(null);

  const workflowsQuery = useAdminWorkflowsQuery(enabled, {
    family: filters.family || undefined,
    scope_type: filters.scopeType || undefined,
    status: filters.status || undefined,
    workflow_type: filters.workflowType || undefined,
    scope_key: filters.scopeKey.trim() || undefined,
    host_key: filters.hostKey.trim() || undefined,
    page: 1,
    page_size: 20,
  });
  const detailQuery = useAdminWorkflowDetailQuery(enabled, selectedWorkflowId);
  const explainQuery = useAdminContentExplainQuery(enabled, explainContentId);
  const schoolBootstrapMutation = useAdminAnnouncementSchoolBootstrapMutation();
  const departmentBootstrapMutation = useAdminAnnouncementDepartmentBootstrapMutation();
  const rebuildMutation = useAdminAnnouncementRebuildMutation();
  const reclassifyMutation = useAdminContentReclassifyMutation();

  const items = useMemo(() => workflowsQuery.data?.items || [], [workflowsQuery.data?.items]);
  useEffect(() => {
    if (!items.length) {
      setSelectedWorkflowId(null);
      return;
    }
    if (selectedWorkflowId && items.some((item) => item.workflow_run_id === selectedWorkflowId)) return;
    setSelectedWorkflowId(items[0].workflow_run_id);
  }, [items, selectedWorkflowId]);

  const stats = useMemo(() => {
    return items.reduce(
      (acc, item) => {
        acc.total += 1;
        acc[item.status === "done" || item.status === "running" || item.status === "failed" ? item.status : "pending"] += 1;
        return acc;
      },
      { total: 0, pending: 0, running: 0, done: 0, failed: 0 },
    );
  }, [items]);

  async function submitSchoolBootstrap(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const response = await schoolBootstrapMutation.mutateAsync({
        schoolName: schoolName.trim(),
        homepageUrl: schoolHomepage.trim(),
        seedUrls: parseSeedUrls(schoolSeeds),
        maxSections: 12,
      });
      setSelectedWorkflowId(response.workflow_run_id);
      setMessage(`学校公告 bootstrap 已入队：${response.workflow_run_id}`);
    } catch (error) {
      setMessage(`学校公告 bootstrap 失败：${errorMessage(error)}`);
    }
  }

  async function submitDepartmentBootstrap(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const response = await departmentBootstrapMutation.mutateAsync({
        schoolName: departmentSchoolName.trim(),
        departmentName: departmentName.trim(),
        departmentType: "college",
        homepageUrl: departmentHomepage.trim(),
        seedUrls: parseSeedUrls(departmentSeeds),
        maxSections: 12,
      });
      setSelectedWorkflowId(response.workflow_run_id);
      setMessage(`院系公告 bootstrap 已入队：${response.workflow_run_id}`);
    } catch (error) {
      setMessage(`院系公告 bootstrap 失败：${errorMessage(error)}`);
    }
  }

  async function submitRebuild(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const response = await rebuildMutation.mutateAsync({
        scopeType: rebuildScopeType,
        schoolName: rebuildSchoolName.trim(),
        departmentName: rebuildScopeType === "department" ? rebuildDepartmentName.trim() || null : null,
        homepageUrl: rebuildHomepage.trim() || null,
        seedUrls: parseSeedUrls(rebuildSeeds),
        maxSections: 12,
      });
      setSelectedWorkflowId(response.workflow_run_id);
      setMessage(`公告 rebuild 已入队：${response.workflow_run_id}`);
    } catch (error) {
      setMessage(`公告 rebuild 失败：${errorMessage(error)}。这通常表示 seed governance 仍有缺口。`);
    }
  }

  async function submitReclassify() {
    const contentId = contentIdInput.trim();
    if (!contentId) {
      setMessage("请先输入 content ID");
      return;
    }
    try {
      const response = await reclassifyMutation.mutateAsync(contentId);
      setSelectedWorkflowId(response.workflow_run_id);
      setExplainContentId(contentId);
      setMessage(`内容重分类已入队：${response.workflow_run_id}`);
    } catch (error) {
      setMessage(`内容重分类失败：${errorMessage(error)}`);
    }
  }

  if (!enabled) return null;

  return (
    <section id="announcement-governance" className="rounded-3xl border border-white/10 bg-black/40 p-6 shadow-2xl md:col-span-4">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h3 className="flex items-center gap-2 text-lg font-semibold text-white">
            <ShieldAlert size={18} className="text-cyan-300" />
            公告治理工作区
          </h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-400">
            这里只处理公告家族 `notice + admissions`。`not_ready`、`no_candidate` 和缺 seed 都按治理缺口展示，不再带自动补抓语义。
          </p>
        </div>
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-xs leading-6 text-amber-50/85">
          学校 rebuild 可留空 seed 走 canonical registry。院系 rebuild 缺显式 seed 时，后端会直接返回治理缺口。
        </div>
      </div>
      {message ? <div className="mt-4 rounded-2xl border border-cyan-500/20 bg-cyan-500/10 px-4 py-3 text-sm text-cyan-50">{message}</div> : null}
      <div className="mt-6 grid gap-3 md:grid-cols-5">
        <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-white">总数 {stats.total}</div>
        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4 text-white">Pending {stats.pending}</div>
        <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/10 p-4 text-white">Running {stats.running}</div>
        <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4 text-white">Done {stats.done}</div>
        <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 p-4 text-white">Failed {stats.failed}</div>
      </div>
      <div className="mt-6 grid gap-3 xl:grid-cols-6">
        <select className={INPUT_CLASS} value={filters.family} onChange={(event) => setFilters((current) => ({ ...current, family: event.target.value }))}>
          <option value="">全部 family</option>
          <option value="notice">notice</option>
          <option value="admissions">admissions</option>
        </select>
        <select className={INPUT_CLASS} value={filters.scopeType} onChange={(event) => setFilters((current) => ({ ...current, scopeType: event.target.value }))}>
          <option value="">全部 scope</option>
          <option value="school">school</option>
          <option value="department">department</option>
        </select>
        <select className={INPUT_CLASS} value={filters.status} onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))}>
          <option value="">全部 status</option>
          <option value="pending">pending</option>
          <option value="running">running</option>
          <option value="done">done</option>
          <option value="failed">failed</option>
        </select>
        <select className={INPUT_CLASS} value={filters.workflowType} onChange={(event) => setFilters((current) => ({ ...current, workflowType: event.target.value }))}>
          <option value="">全部 workflow</option>
          <option value="scope_rebuild">scope_rebuild</option>
          <option value="school_portal_discovery">school_portal_discovery</option>
          <option value="department_portal_discovery">department_portal_discovery</option>
          <option value="detail_fetch">detail_fetch</option>
          <option value="file_parse">file_parse</option>
          <option value="content_reclassify">content_reclassify</option>
        </select>
        <input className={INPUT_CLASS} value={filters.scopeKey} onChange={(event) => setFilters((current) => ({ ...current, scopeKey: event.target.value }))} placeholder="scope_key" />
        <input className={INPUT_CLASS} value={filters.hostKey} onChange={(event) => setFilters((current) => ({ ...current, hostKey: event.target.value }))} placeholder="host_key" />
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
        <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-4">
          <div className="mb-3 flex items-center justify-between text-sm font-semibold text-white">
            <span>Workflow 列表</span>
            <button type="button" onClick={() => workflowsQuery.refetch()} className="rounded-xl border border-white/10 bg-black/20 p-2 text-slate-300 transition hover:border-white/20 hover:text-white">
              <RefreshCw size={15} />
            </button>
          </div>
          <div className="space-y-3">
            {items.map((item) => (
              <button key={item.workflow_run_id} type="button" onClick={() => setSelectedWorkflowId(item.workflow_run_id)} className={`w-full rounded-2xl border p-4 text-left ${item.workflow_run_id === selectedWorkflowId ? "border-cyan-400/30 bg-cyan-500/10" : "border-white/10 bg-black/20"}`}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-white">{item.scope_label || item.scope_key}</div>
                    <div className="mt-1 text-[11px] uppercase tracking-[0.2em] text-slate-500">{item.workflow_type}</div>
                  </div>
                  <span className={`rounded-xl border px-2 py-1 text-[11px] ${statusClass(item.status)}`}>{item.status}</span>
                </div>
                <div className="mt-2 text-xs leading-6 text-slate-400">
                  seed={item.seed_source || "--"} · host={item.host_keys[0] || "--"} · reason={item.terminal_reason || item.latest_step_error || "--"}
                </div>
              </button>
            ))}
            {workflowsQuery.isLoading ? <div className="text-sm text-slate-400">正在加载 workflow 列表...</div> : null}
            {workflowsQuery.isError ? <div className="text-sm text-rose-300">列表加载失败：{errorMessage(workflowsQuery.error)}</div> : null}
          </div>
        </div>
        <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
          <div className="mb-4 flex items-center gap-2 text-sm font-semibold text-white">
            <Waypoints size={16} className="text-cyan-300" />
            Workflow 详情
          </div>
          {!selectedWorkflowId ? <div className="text-sm text-slate-400">从左侧选择 workflow 查看详情。</div> : detailQuery.isLoading ? <div className="text-sm text-slate-400">正在加载 workflow 详情...</div> : detailQuery.isError ? <div className="text-sm text-rose-300">详情加载失败：{errorMessage(detailQuery.error)}</div> : detailQuery.data ? (
            <div className="space-y-4 text-sm text-slate-200">
              <div className="grid gap-3 md:grid-cols-4">
                <div className={`rounded-2xl border p-4 ${statusClass(detailQuery.data.status)}`}>status: {detailQuery.data.status}</div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">seed_source: {detailQuery.data.seed_source || "--"}</div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">terminal_reason: {detailQuery.data.terminal_reason || "--"}</div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">classifications: {detailQuery.data.content_classifications.length}</div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <div>homepage: {String(detailQuery.data.request_payload.homepage_url || "--")}</div>
                <div className="mt-2 text-xs leading-6 text-slate-400">seed_urls: {Array.isArray(detailQuery.data.request_payload.seed_urls) ? (detailQuery.data.request_payload.seed_urls as string[]).join(", ") : "--"}</div>
              </div>
              <div className="space-y-3">
                {detailQuery.data.steps.map((step) => (
                  <div key={step.id} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-semibold text-white">{step.step_type}</div>
                      <span className={`rounded-xl border px-2 py-1 text-[11px] ${statusClass(step.status)}`}>{step.status}</span>
                    </div>
                    <div className="mt-2 grid gap-2 text-xs text-slate-400 md:grid-cols-3">
                      <div>attempt {step.attempt_count}/{step.max_attempts}</div>
                      <div>timeout {step.timeout_seconds}s</div>
                      <div>host {step.host_key || "--"}</div>
                      <div>lease_owner {step.lease_owner || "--"}</div>
                      <div>leased_at {formatTime(step.leased_at)}</div>
                      <div>available_at {formatTime(step.available_at)}</div>
                    </div>
                    {step.error_message ? <div className="mt-2 text-xs text-rose-300">{step.error_message}</div> : null}
                  </div>
                ))}
              </div>
              <div className="grid gap-4 xl:grid-cols-2">
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <div className="text-sm font-semibold text-white">Persisted Classification</div>
                  <div className="mt-3 space-y-3">
                    {detailQuery.data.content_classifications.map((item) => (
                      <div key={item.content_id} className="rounded-2xl border border-white/10 bg-black/30 p-3 text-xs text-slate-300">
                        <div className="font-semibold text-white">{item.content_id}</div>
                        <div className="mt-1">{item.classification_state} · {item.visibility}</div>
                        <div className="mt-1">{item.scope_type} / {item.scope_key}</div>
                      </div>
                    ))}
                    {!detailQuery.data.content_classifications.length ? <div className="text-xs text-slate-400">当前 workflow 还没有持久化 classification。</div> : null}
                  </div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4 text-xs text-slate-300">
                  <div>raw_artifacts: {detailQuery.data.raw_artifacts.length}</div>
                  <div className="mt-2">parse_artifacts: {detailQuery.data.parse_artifacts.length}</div>
                  <div className="mt-2">governance_actions: {detailQuery.data.governance_actions.length}</div>
                </div>
              </div>
            </div>
          ) : null}
        </div>
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <form onSubmit={submitSchoolBootstrap} className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
          <div className="mb-3 text-sm font-semibold text-white">School Bootstrap</div>
          <div className="space-y-3">
            <input className={INPUT_CLASS} value={schoolName} onChange={(event) => setSchoolName(event.target.value)} placeholder="school_name" required />
            <input className={INPUT_CLASS} value={schoolHomepage} onChange={(event) => setSchoolHomepage(event.target.value)} placeholder="homepage_url" required />
            <textarea className={INPUT_CLASS} value={schoolSeeds} onChange={(event) => setSchoolSeeds(event.target.value)} placeholder="seed_urls: 一行一个或逗号分隔" />
            <button type="submit" disabled={schoolBootstrapMutation.isPending} className="w-full rounded-2xl border border-cyan-500/30 bg-cyan-500/15 px-4 py-3 text-sm font-semibold text-cyan-50 disabled:opacity-70">{schoolBootstrapMutation.isPending ? "提交中..." : "创建学校公告 bootstrap"}</button>
          </div>
        </form>
        <form onSubmit={submitDepartmentBootstrap} className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
          <div className="mb-3 text-sm font-semibold text-white">Department Bootstrap</div>
          <div className="space-y-3">
            <input className={INPUT_CLASS} value={departmentSchoolName} onChange={(event) => setDepartmentSchoolName(event.target.value)} placeholder="school_name" required />
            <input className={INPUT_CLASS} value={departmentName} onChange={(event) => setDepartmentName(event.target.value)} placeholder="department_name" required />
            <input className={INPUT_CLASS} value={departmentHomepage} onChange={(event) => setDepartmentHomepage(event.target.value)} placeholder="homepage_url" required />
            <textarea className={INPUT_CLASS} value={departmentSeeds} onChange={(event) => setDepartmentSeeds(event.target.value)} placeholder="seed_urls" />
            <button type="submit" disabled={departmentBootstrapMutation.isPending} className="w-full rounded-2xl border border-emerald-500/30 bg-emerald-500/15 px-4 py-3 text-sm font-semibold text-emerald-50 disabled:opacity-70">{departmentBootstrapMutation.isPending ? "提交中..." : "创建院系公告 bootstrap"}</button>
          </div>
        </form>
        <form onSubmit={submitRebuild} className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
          <div className="mb-3 text-sm font-semibold text-white">Announcement Rebuild</div>
          <div className="space-y-3">
            <select className={INPUT_CLASS} value={rebuildScopeType} onChange={(event) => setRebuildScopeType(event.target.value as "school" | "department")}>
              <option value="school">school</option>
              <option value="department">department</option>
            </select>
            <input className={INPUT_CLASS} value={rebuildSchoolName} onChange={(event) => setRebuildSchoolName(event.target.value)} placeholder="school_name" required />
            {rebuildScopeType === "department" ? <input className={INPUT_CLASS} value={rebuildDepartmentName} onChange={(event) => setRebuildDepartmentName(event.target.value)} placeholder="department_name" required /> : null}
            <input className={INPUT_CLASS} value={rebuildHomepage} onChange={(event) => setRebuildHomepage(event.target.value)} placeholder="homepage_url（学校可留空）" />
            <textarea className={INPUT_CLASS} value={rebuildSeeds} onChange={(event) => setRebuildSeeds(event.target.value)} placeholder="seed_urls" />
            <button type="submit" disabled={rebuildMutation.isPending} className="w-full rounded-2xl border border-amber-500/30 bg-amber-500/15 px-4 py-3 text-sm font-semibold text-amber-50 disabled:opacity-70">{rebuildMutation.isPending ? "提交中..." : "提交 rebuild"}</button>
          </div>
        </form>
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-[1.15fr,0.85fr]">
        <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-5">
          <div className="mb-3 text-sm font-semibold text-white">Content Explain / Reclassify</div>
          <div className="grid gap-3 xl:grid-cols-[1fr,auto,auto]">
            <input className={INPUT_CLASS} value={contentIdInput} onChange={(event) => setContentIdInput(event.target.value)} placeholder="content ID" />
            <button type="button" onClick={() => setExplainContentId(contentIdInput.trim() || null)} className="rounded-2xl border border-white/10 bg-black/30 px-4 py-3 text-sm font-semibold text-white">查看 explain</button>
            <button type="button" onClick={submitReclassify} disabled={reclassifyMutation.isPending} className="rounded-2xl border border-cyan-500/30 bg-cyan-500/15 px-4 py-3 text-sm font-semibold text-cyan-50 disabled:opacity-70">{reclassifyMutation.isPending ? "提交中..." : "触发 reclassify"}</button>
          </div>
          <div className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-slate-200">
            {explainQuery.isLoading ? <div className="text-slate-400">正在加载 explain...</div> : explainQuery.isError ? <div className="text-rose-300">explain 加载失败：{errorMessage(explainQuery.error)}</div> : explainQuery.data ? (
              <div className="space-y-2">
                <div>scope: {explainQuery.data.scope_type} / {explainQuery.data.scope_key}</div>
                <div>classification_state: {explainQuery.data.classification_state}</div>
                <div>visibility: {explainQuery.data.visibility}</div>
                <pre className="overflow-auto rounded-2xl border border-white/10 bg-black/30 p-3 text-xs text-slate-300">{JSON.stringify(explainQuery.data.explain_payload, null, 2)}</pre>
              </div>
            ) : <div className="text-slate-400">输入 content ID 后可以查看 explain，也可以直接触发重分类。</div>}
          </div>
        </div>
        <div className="rounded-3xl border border-white/10 bg-white/[0.03] p-5 text-sm text-slate-300">
          <div className="mb-3 font-semibold text-white">治理提示</div>
          <div className="space-y-3">
            <div className="rounded-2xl border border-rose-500/20 bg-rose-500/10 p-4">`not_ready + required_action=admin.bootstrap.school` 表示学校公告资产不存在，不会自动补抓。</div>
            <div className="rounded-2xl border border-amber-500/20 bg-amber-500/10 p-4">`no_candidate` 和缺 seed 都按治理缺口展示；尤其院系 rebuild 缺显式 seed 时会直接失败。</div>
            <div className="rounded-2xl border border-cyan-500/20 bg-cyan-500/10 p-4">公告可见性只认 persisted `content_classifications`，不能再直接解释 `contents.extra`。</div>
          </div>
        </div>
      </div>
    </section>
  );
}
