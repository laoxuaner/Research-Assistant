import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Check,
  ChevronDown,
  Database,
  Download,
  FileText,
  FlaskConical,
  FolderOpen,
  GitCompareArrows,
  LayoutDashboard,
  LoaderCircle,
  MessageSquare,
  Plus,
  Search,
  Settings as SettingsIcon,
  Sparkles,
  Trash2,
  Upload,
  X,
  PanelRightClose,
  Menu,
  Archive,
  Pencil,
  RefreshCw,
  Layers,
} from "lucide-react";
import {
  api,
  json,
  date,
  fmt,
  type Project,
  type Paper,
  type Citation,
  type Settings,
  type Job,
  type Report,
  type Message,
  type Conversation,
  type ReadingField,
} from "./api";
import {
  Alert,
  Badge,
  Citations,
  Empty,
  Evidence,
  Field,
  Modal,
  Reader,
  Spinner,
  statusLabel,
  ReadOnlyDemoContext,
  useReadOnlyDemo,
  demoReadOnlyHint,
} from "./components";
import Experiments from "./Experiments";
type Page =
  | "overview"
  | "papers"
  | "chat"
  | "compare"
  | "experiments"
  | "reports"
  | "settings";
const nav: { id: Page; name: string; icon: typeof BookOpen }[] = [
  { id: "overview", name: "项目概览", icon: LayoutDashboard },
  { id: "papers", name: "论文知识库", icon: BookOpen },
  { id: "chat", name: "科研问答", icon: MessageSquare },
  { id: "compare", name: "文献对比", icon: GitCompareArrows },
  { id: "experiments", name: "实验分析", icon: FlaskConical },
  { id: "reports", name: "研究报告", icon: FileText },
];
const subtitles: Record<Page, string> = {
  overview: "从文献证据到实验发现，让每一步研究都有据可循。",
  papers: "保存原始论文，逐页阅读，让知识成为可以追溯的证据。",
  chat: "围绕研究问题提问，回到原始论文验证每一个结论。",
  compare: "并排梳理研究方法与边界，找到下一步值得验证的问题。",
  experiments: "明确实验设计，再用可复现的计算检验研究假设。",
  reports: "把文献证据、实验结果与分析过程整理为可复现的报告。",
  settings: "管理模型连接与隐私选项，离线功能始终可用。",
};
export default function App() {
  const [projects, setProjects] = useState<Project[]>([]),
    [pid, setPid] = useState(""),
    [page, setPage] = useState<Page>("overview"),
    [papers, setPapers] = useState<Paper[]>([]),
    [settings, setSettings] = useState<Settings | null>(null),
    [loading, setLoading] = useState(true),
    [loadError, setLoadError] = useState(""),
    [revision, setRevision] = useState(0),
    [projectModal, setProjectModal] = useState(false),
    [edit, setEdit] = useState<Project | null>(null),
    [citation, setCitation] = useState<Citation | null>(null),
    [reader, setReader] = useState<{ paperId: string; page: number } | null>(
      null,
    ),
    [toast, setToast] = useState<{ text: string; error: boolean } | null>(null),
    [mobile, setMobile] = useState(false),
    [demoBusy, setDemoBusy] = useState(false);
  const notify = useCallback((text: string, error = false) => {
    setToast({ text, error });
  }, []);
  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 6500);
    return () => clearTimeout(t);
  }, [toast]);
  const refresh = useCallback(() => setRevision((v) => v + 1), []);
  const loadProjects = useCallback(async () => {
    const list = await api<Project[]>("/projects");
    setProjects(list);
    setPid((current) =>
      list.some((p) => p.id === current)
        ? current
        : list.find((p) => p.id === localStorage.getItem("research-project"))
            ?.id ||
          list.find((p) => !p.archived)?.id ||
          list[0]?.id ||
          "",
    );
    return list;
  }, []);
  useEffect(() => {
    setLoadError("");
    Promise.all([loadProjects(), api<Settings>("/settings").then(setSettings)])
      .catch((e) => setLoadError(e.message))
      .finally(() => setLoading(false));
  }, [loadProjects, revision]);
  useEffect(() => {
    setCitation(null);
    setReader(null);
    if (pid) {
      localStorage.setItem("research-project", pid);
      api<Paper[]>("/projects/" + pid + "/papers")
        .then(setPapers)
        .catch((e) => notify(e.message, true));
    } else setPapers([]);
  }, [pid, revision, notify]);
  useEffect(() => {
    if (!pid || !papers.some((p) => ["running", "queued"].includes(p.status)))
      return;
    const t = setInterval(() => {
      api<Paper[]>("/projects/" + pid + "/papers")
        .then(setPapers)
        .catch(() => {});
    }, 2500);
    return () => clearInterval(t);
  }, [pid, papers]);
  const project = projects.find((p) => p.id === pid);
  const readOnly = settings?.read_only === true;
  const importDemo = async () => {
    if (readOnly) return;
    setDemoBusy(true);
    try {
      const r = await api<{ project_id: string }>("/demo", json({}));
      await loadProjects();
      setPid(r.project_id);
      refresh();
      notify("已导入明确标记的测试材料与实验数据");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setDemoBusy(false);
    }
  };
  const navigate = (p: Page) => {
    setPage(p);
    setMobile(false);
  };
  const openCitation = (c: Citation) => setCitation(c);
  const onProjectSaved = async (id: string) => {
    await loadProjects();
    setPid(id);
    refresh();
    setProjectModal(false);
    setEdit(null);
  };
  return (
    <ReadOnlyDemoContext.Provider value={readOnly}>
      <div className="app">
        <aside className={"sidebar " + (mobile ? "mobile-open" : "")}>
          <a
            className="brand"
            href="#"
            onClick={(e) => {
              e.preventDefault();
              navigate("overview");
            }}
          >
            <div className="brand-mark">
              <Layers size={24} />
            </div>
            <div>
              <strong>
                研知<span>LAB</span>
              </strong>
              <small>RESEARCH WORKSPACE</small>
            </div>
          </a>
          <div className="workspace-label">
            {readOnly ? "公开科研演示" : "个人科研工作台"}{" "}
            <Badge>{readOnly ? "DEMO" : "LOCAL"}</Badge>
          </div>
          <nav>
            {nav.map((n) => (
              <button
                className={page === n.id ? "nav-item active" : "nav-item"}
                key={n.id}
                onClick={() => navigate(n.id)}
              >
                <n.icon size={18} />
                {n.name}
                {n.id === "papers" && papers.length > 0 && (
                  <span className="nav-count">{papers.length}</span>
                )}
              </button>
            ))}
          </nav>
          <div className="sidebar-bottom">
            <div className="local-card">
              <div className="row">
                <span className="status-dot" />
                <strong>{readOnly ? "公开只读演示" : "本地工作空间"}</strong>
              </div>
              <p>
                {readOnly ? "仅展示合成测试资料。" : "原始资料保存在你的设备。"}
                <br />
                {readOnly
                  ? "不接收上传，不调用外部 AI。"
                  : "AI 外发由你明确开启。"}
              </p>
            </div>
            <button
              className={"nav-item " + (page === "settings" ? "active" : "")}
              onClick={() => navigate("settings")}
            >
              <SettingsIcon size={18} />
              模型与设置
            </button>
            <div className="user-row">
              <div className="avatar">研</div>
              <div>
                <strong>{readOnly ? "示例研究" : "我的研究"}</strong>
                <small>{readOnly ? "合成材料 · 只读" : "个人 · 单用户"}</small>
              </div>
              <span className="local-pill">{readOnly ? "演示" : "本地"}</span>
            </div>
          </div>
        </aside>
        {mobile && (
          <div className="mobile-mask" onClick={() => setMobile(false)} />
        )}
        <div className="workspace">
          <header className="topbar">
            <button
              className="icon-button mobile-menu"
              aria-label="打开导航"
              onClick={() => setMobile(!mobile)}
            >
              <Menu size={21} />
            </button>
            <div className="project-switch">
              <FolderOpen size={17} />
              <select
                aria-label="当前科研项目"
                value={pid}
                onChange={(e) => setPid(e.target.value)}
              >
                <option value="">选择科研项目</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                    {p.archived ? "（已归档）" : ""}
                  </option>
                ))}
              </select>
              <ChevronDown size={13} />
            </div>
            <button
              className="button subtle small"
              disabled={loading || readOnly}
              title={readOnly ? demoReadOnlyHint : undefined}
              onClick={() => {
                setEdit(null);
                setProjectModal(true);
              }}
            >
              <Plus size={15} />
              新建项目
            </button>
            <div className="top-spacer" />
            <span
              className={
                "connection " +
                (settings?.ai_enabled && settings.chat_configured
                  ? "online"
                  : "")
              }
            >
              <span className="status-dot" />
              {settings?.ai_enabled && settings.chat_configured
                ? "AI 已启用"
                : "离线可用"}
            </span>
            <button
              className="icon-button"
              title="模型设置"
              onClick={() => navigate("settings")}
            >
              <SettingsIcon size={18} />
            </button>
          </header>
          {readOnly && (
            <div
              className="public-demo-banner"
              role="note"
              aria-label="公开演示说明"
            >
              <div>
                <strong>公开只读演示</strong>
                <span>
                  仅含合成测试数据，不代表真实科研发现。不支持上传或保存修改；问答展示检索原文，不生成
                  AI 总结。
                </span>
              </div>
              <a
                href="https://github.com/laoxuaner/Research-Assistant"
                target="_blank"
                rel="noreferrer"
              >
                下载源码，体验完整功能 <ArrowUpRight size={15} />
              </a>
            </div>
          )}
          <div className="content-layout">
            <main className="main">
              <div className="page-heading">
                <div>
                  <div className="breadcrumb">
                    工作空间 <span>/</span> {project?.name || "开始研究"}
                  </div>
                  <h1>
                    {page === "overview"
                      ? "研究，从这里继续"
                      : nav.find((n) => n.id === page)?.name || "模型与设置"}
                  </h1>
                  <p>{subtitles[page]}</p>
                </div>
                {page === "overview" && project && (
                  <button
                    className="button secondary"
                    disabled={readOnly}
                    title={readOnly ? demoReadOnlyHint : undefined}
                    onClick={() => {
                      setEdit(project);
                      setProjectModal(true);
                    }}
                  >
                    <Pencil size={14} />
                    编辑项目
                  </button>
                )}
              </div>
              {loadError && (
                <Alert tone="error">
                  {loadError}
                  <button className="text-button" onClick={() => refresh()}>
                    重新连接
                  </button>
                </Alert>
              )}
              {loading ? (
                <Spinner />
              ) : page === "settings" ? (
                <SettingsView
                  settings={settings}
                  onChange={(s) => {
                    setSettings(s);
                    refresh();
                  }}
                  notify={notify}
                  pid={pid}
                />
              ) : !project ? (
                <div className="welcome">
                  <div className="hero-icon">
                    <Layers size={37} />
                  </div>
                  <p className="eyebrow">A CLEARER PATH TO DISCOVERY</p>
                  <h2>给你的研究，一个有条理的开始</h2>
                  <p>
                    连接论文、研究问题与实验结果。
                    <br />
                    从创建第一个项目开始，逐步积累可以追溯的研究证据。
                  </p>
                  <div className="row center">
                    <button
                      className="button primary"
                      disabled={readOnly}
                      onClick={() => setProjectModal(true)}
                    >
                      <Plus size={17} />
                      创建科研项目
                    </button>
                    <button
                      className="button secondary"
                      disabled={demoBusy || readOnly}
                      onClick={importDemo}
                    >
                      {demoBusy ? (
                        <LoaderCircle size={16} className="spin" />
                      ) : (
                        <Database size={16} />
                      )}
                      导入测试示例
                    </button>
                  </div>
                  <div className="welcome-grid">
                    {[
                      [
                        "01",
                        "建立文献证据库",
                        "上传 PDF，检索原文并回到引用页。",
                      ],
                      [
                        "02",
                        "检验你的研究假设",
                        "导入数据，明确设计，运行可复现分析。",
                      ],
                      [
                        "03",
                        "保存完整研究轨迹",
                        "将证据、图表和计算过程一起导出。",
                      ],
                    ].map(([n, t, d]) => (
                      <div key={n}>
                        <span>{n}</span>
                        <h3>{t}</h3>
                        <p>{d}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div key={pid}>
                  {project.archived && (
                    <Alert>
                      该项目已归档。可在“编辑项目”中恢复，历史资料仍可查看。
                    </Alert>
                  )}
                  {page === "overview" && (
                    <Overview
                      project={project}
                      revision={revision}
                      onNavigate={navigate}
                      onDemo={importDemo}
                      demoBusy={demoBusy}
                      notify={notify}
                    />
                  )}{" "}
                  {page === "papers" && (
                    <Library
                      pid={pid}
                      papers={papers}
                      refresh={refresh}
                      notify={notify}
                      onRead={(id, p = 1) =>
                        setReader({ paperId: id, page: p })
                      }
                      onCite={openCitation}
                    />
                  )}{" "}
                  {page === "chat" && (
                    <Chat
                      pid={pid}
                      papers={papers}
                      settings={settings}
                      onCite={openCitation}
                      notify={notify}
                    />
                  )}{" "}
                  {page === "compare" && (
                    <Compare
                      pid={pid}
                      papers={papers}
                      onCite={openCitation}
                      notify={notify}
                    />
                  )}{" "}
                  {page === "experiments" && (
                    <Experiments
                      pid={pid}
                      papers={papers}
                      revision={revision}
                      refresh={refresh}
                      notify={notify}
                      onReports={() => navigate("reports")}
                    />
                  )}{" "}
                  {page === "reports" && (
                    <Reports pid={pid} revision={revision} notify={notify} />
                  )}
                </div>
              )}
              <footer className="page-footer">
                <span>研知 · 让研究有据可循</span>
                <span>
                  {readOnly
                    ? "公开只读演示 · 合成测试材料"
                    : "本地个人工作空间 · v1.0"}
                </span>
              </footer>
            </main>
            {citation && (
              <Evidence
                citation={citation}
                onClose={() => setCitation(null)}
                onOpen={() =>
                  setReader({
                    paperId: citation.paper_id,
                    page: citation.page_number,
                  })
                }
              />
            )}
          </div>
        </div>
        {projectModal && !readOnly && (
          <ProjectForm
            value={edit}
            onClose={() => {
              setProjectModal(false);
              setEdit(null);
            }}
            onSaved={onProjectSaved}
            notify={notify}
          />
        )}{" "}
        {reader && pid && (
          <Reader
            projectId={pid}
            paperId={reader.paperId}
            initialPage={reader.page}
            onClose={() => setReader(null)}
            onSave={refresh}
            onCite={openCitation}
            notify={notify}
          />
        )}{" "}
        {toast && (
          <div
            role="status"
            className={"toast " + (toast.error ? "error" : "")}
          >
            <span>{toast.error ? "!" : <Check size={18} />}</span>
            {toast.text}
            <button
              className="icon-button"
              aria-label="关闭提示"
              onClick={() => setToast(null)}
            >
              <X size={16} />
            </button>
          </div>
        )}
      </div>
    </ReadOnlyDemoContext.Provider>
  );
}
function ProjectForm({
  value,
  onClose,
  onSaved,
  notify,
}: {
  value: Project | null;
  onClose: () => void;
  onSaved: (id: string) => void;
  notify: (s: string, e?: boolean) => void;
}) {
  const [form, setForm] = useState({
      name: value?.name || "",
      question: value?.question || "",
      hypothesis: value?.hypothesis || "",
      tags: (value?.tags || []).join(", "),
      notes: value?.notes || "",
      archived: value?.archived || false,
    }),
    [busy, setBusy] = useState(false);
  const save = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const data = {
        ...form,
        tags: form.tags
          .split(/[,，]/)
          .map((t) => t.trim())
          .filter(Boolean),
      };
      const p = await api<Project>(
        value ? "/projects/" + value.id : "/projects",
        { method: value ? "PATCH" : "POST", body: JSON.stringify(data) },
      );
      await onSaved(p.id);
      notify(value ? "项目已更新" : "项目已创建");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal title={value ? "编辑科研项目" : "创建科研项目"} onClose={onClose}>
      <form onSubmit={save} className="form-body">
        <Field label="项目名称">
          <input
            required
            maxLength={160}
            autoFocus
            value={form.name}
            placeholder="例如：小样本学习中的数据增强策略"
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
        </Field>
        <Field label="研究问题">
          <textarea
            rows={3}
            value={form.question}
            placeholder="你希望回答什么问题？"
            onChange={(e) => setForm({ ...form, question: e.target.value })}
          />
        </Field>
        <Field label="研究假设">
          <textarea
            rows={2}
            value={form.hypothesis}
            onChange={(e) => setForm({ ...form, hypothesis: e.target.value })}
          />
        </Field>
        <Field label="标签（逗号分隔）">
          <input
            value={form.tags}
            onChange={(e) => setForm({ ...form, tags: e.target.value })}
          />
        </Field>
        <Field label="备注">
          <textarea
            rows={2}
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
          />
        </Field>
        {value && (
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.archived}
              onChange={(e) => setForm({ ...form, archived: e.target.checked })}
            />
            <Archive size={15} />
            归档此项目
          </label>
        )}
        <div className="form-actions">
          <button className="button secondary" type="button" onClick={onClose}>
            取消
          </button>
          <button className="button primary" disabled={busy}>
            {busy ? (
              <LoaderCircle size={16} className="spin" />
            ) : (
              <Check size={16} />
            )}
            保存项目
          </button>
        </div>
      </form>
    </Modal>
  );
}
function Overview({
  project,
  revision,
  onNavigate,
  onDemo,
  demoBusy,
  notify,
}: {
  project: Project;
  revision: number;
  onNavigate: (p: Page) => void;
  onDemo: () => void;
  demoBusy: boolean;
  notify: (s: string, e?: boolean) => void;
}) {
  const readOnly = useReadOnlyDemo();
  const [data, setData] = useState<{
      paper_count: number;
      pending_jobs: number;
      experiment_count: number;
      report_count: number;
      recent_experiments: { id: string; name: string; created_at: string }[];
      recent_reports: Report[];
    } | null>(null),
    [jobs, setJobs] = useState<Job[]>([]);
  const reloadOverview = useCallback(
    () =>
      Promise.all([
        api<typeof data>("/projects/" + project.id + "/overview").then(setData),
        api<Job[]>("/projects/" + project.id + "/jobs").then(setJobs),
      ]).catch((e) => notify(e.message, true)),
    [project.id, notify],
  );
  useEffect(() => {
    void reloadOverview();
  }, [reloadOverview, revision]);
  useEffect(() => {
    if (!jobs.some((j) => ["queued", "running"].includes(j.status))) return;
    const timer = setInterval(() => {
      void reloadOverview();
    }, 2000);
    return () => clearInterval(timer);
  }, [jobs, reloadOverview]);
  return (
    <>
      <div className="research-banner">
        <div>
          <p className="eyebrow">CURRENT RESEARCH</p>
          <h2>{project.name}</h2>
          <p>
            {project.question ||
              "为项目补充一个研究问题，让文献阅读与实验分析围绕同一个目标。"}
          </p>
          <div className="row">
            {project.tags.map((t) => (
              <span className="banner-tag" key={t}>
                {t}
              </span>
            ))}
            <span className="banner-tag">
              {project.archived ? "已归档" : "研究进行中"}
            </span>
          </div>
        </div>
        <div className="banner-art" aria-hidden="true">
          <div className="orbit one" />
          <div className="orbit two" />
          <div className="orbit three" />
          <div className="orbit-center">
            <FlaskConical size={31} />
          </div>
          <span className="orbit-point a" />
          <span className="orbit-point b" />
          <span className="orbit-point c" />
        </div>
      </div>
      <div className="stats-grid">
        {[
          {
            label: "篇论文",
            number: data?.paper_count,
            icon: BookOpen,
            color: "teal",
            page: "papers",
          },
          {
            label: "项待处理任务",
            number: data?.pending_jobs,
            icon: Layers,
            color: "amber",
            page: "papers",
          },
          {
            label: "个实验记录",
            number: data?.experiment_count,
            icon: FlaskConical,
            color: "blue",
            page: "experiments",
          },
          {
            label: "份研究报告",
            number: data?.report_count,
            icon: FileText,
            color: "purple",
            page: "reports",
          },
        ].map((c) => (
          <button
            className="stat-card"
            key={c.label}
            onClick={() => onNavigate(c.page as Page)}
          >
            <span className={"stat-icon " + c.color}>
              <c.icon size={21} />
            </span>
            <div>
              <strong>{c.number ?? "—"}</strong>
              <span>{c.label}</span>
            </div>
            <ArrowUpRight size={16} />
          </button>
        ))}
      </div>
      <div className="section-title">
        <h2>推进你的研究</h2>
        <span className="muted tiny">每一步都保留证据与过程</span>
      </div>
      <div className="action-grid">
        {[
          {
            n: "01",
            icon: Upload,
            title: "积累文献证据",
            desc: "导入论文，保留原文与页码，建立可以检索的项目知识库。",
            button: "前往论文库",
            page: "papers",
          },
          {
            n: "02",
            icon: MessageSquare,
            title: "围绕问题深入阅读",
            desc: "带着研究问题对话，从每一条引用回到论文中的原始证据。",
            button: "开始科研问答",
            page: "chat",
          },
          {
            n: "03",
            icon: FlaskConical,
            title: "用实验验证假设",
            desc: "上传实验数据，确认分析设计，生成可复现的统计与图表。",
            button: "配置实验分析",
            page: "experiments",
          },
        ].map((c) => (
          <button
            className="action-card"
            key={c.n}
            onClick={() => onNavigate(c.page as Page)}
          >
            <div className="row between">
              <c.icon size={22} />
              <span>{c.n}</span>
            </div>
            <h3>{c.title}</h3>
            <p>{c.desc}</p>
            <strong>
              {c.button}
              <ArrowRight size={15} />
            </strong>
          </button>
        ))}
      </div>
      <div className="two-col">
        <section className="card">
          <div className="card-heading">
            <h2>最近的实验</h2>
            <button
              className="text-button"
              onClick={() => onNavigate("experiments")}
            >
              查看全部
              <ArrowRight size={13} />
            </button>
          </div>
          {data?.recent_experiments?.length ? (
            data.recent_experiments.map((e) => (
              <button
                className="list-row full"
                key={e.id}
                onClick={() => onNavigate("experiments")}
              >
                <div className="list-icon blue">
                  <FlaskConical size={18} />
                </div>
                <div>
                  <strong>{e.name}</strong>
                  <small>{date(e.created_at)}</small>
                </div>
                <ArrowUpRight size={15} />
              </button>
            ))
          ) : (
            <div className="mini-empty">
              尚无实验记录。添加数据，开始第一次分析。
            </div>
          )}
        </section>
        <section className="card">
          <div className="card-heading">
            <h2>研究假设</h2>
            <Badge tone="teal">待验证</Badge>
          </div>
          <p className="hypothesis">
            {project.hypothesis ||
              "尚未设置研究假设。你可以在项目设置中记录想要验证的预期。"}
          </p>
          <p className="muted tiny">
            将假设与实验设计一同保存，区分已有结论与待验证的研究方向。
          </p>
        </section>
      </div>
      {jobs.some((j) => ["failed", "interrupted"].includes(j.status)) && (
        <section className="card space-top">
          <div className="card-heading">
            <h2>需要关注的任务</h2>
          </div>
          {jobs
            .filter((j) => ["failed", "interrupted"].includes(j.status))
            .slice(0, 4)
            .map((j) => (
              <div className="list-row" key={j.id}>
                <Badge tone="error">{statusLabel[j.status]}</Badge>
                <span>{j.kind}</span>
                <small>{j.error || "请到论文库重试任务"}</small>
              </div>
            ))}
        </section>
      )}
      <div className="demo-note">
        <Database size={17} />
        <span>
          {readOnly
            ? "演示已预置中英文论文、实验统计与报告。可阅读原文、检索证据并下载复现包。"
            : "想先了解完整流程？可显式导入标记为测试材料的中英文论文与实验数据。"}
        </span>
        <button
          className="text-button"
          disabled={demoBusy || readOnly}
          title={readOnly ? "示例材料已预置" : undefined}
          onClick={onDemo}
        >
          导入测试示例
          <ArrowRight size={14} />
        </button>
      </div>
    </>
  );
}
function Library({
  pid,
  papers,
  refresh,
  notify,
  onRead,
  onCite,
}: {
  pid: string;
  papers: Paper[];
  refresh: () => void;
  notify: (s: string, e?: boolean) => void;
  onRead: (id: string, p?: number) => void;
  onCite: (c: Citation) => void;
}) {
  const readOnly = useReadOnlyDemo();
  const [query, setQuery] = useState(""),
    [year, setYear] = useState(""),
    [tags, setTags] = useState(""),
    [selected, setSelected] = useState<string[]>([]),
    [searchResult, setSearchResult] = useState<Citation[] | null>(null),
    [busy, setBusy] = useState(false),
    [mode, setMode] = useState(""),
    [warnings, setWarnings] = useState<string[]>([]),
    [remove, setRemove] = useState<Paper | null>(null);
  const upload = async (files: FileList | null) => {
    if (!files?.length || readOnly) return;
    const fd = new FormData();
    for (const f of Array.from(files)) fd.append("files", f);
    setBusy(true);
    try {
      const r = await api<{ papers: Paper[]; duplicates: string[] }>(
        "/projects/" + pid + "/papers",
        { method: "POST", body: fd },
      );
      notify(
        "已接收 " +
          r.papers.length +
          " 篇论文" +
          (r.duplicates.length
            ? "，" + r.duplicates.length + " 个重复文件已跳过"
            : ""),
      );
      refresh();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
  const search = async (e: FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setBusy(true);
    try {
      const r = await api<{
        results: Citation[];
        mode: string;
        warnings: string[];
      }>(
        "/projects/" + pid + "/search",
        json({
          query,
          paper_ids: selected,
          year: year ? Number(year) : undefined,
          tags: tags.split(/[,，]/).filter(Boolean),
          limit: 20,
        }),
      );
      setSearchResult(r.results);
      setMode(r.mode);
      setWarnings(r.warnings || []);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
  const retry = async (p: Paper) => {
    try {
      await api("/projects/" + pid + "/papers/" + p.id + "/retry", json({}));
      notify("已重新提交解析任务");
      refresh();
    } catch (e) {
      notify((e as Error).message, true);
    }
  };
  const deletePaper = async () => {
    if (!remove) return;
    setBusy(true);
    try {
      await api("/projects/" + pid + "/papers/" + remove.id, {
        method: "DELETE",
      });
      setSelected((s) => s.filter((id) => id !== remove.id));
      setSearchResult(null);
      setRemove(null);
      refresh();
      notify("论文、原始文件与检索索引已删除");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <div className="section-title">
        <div className="row">
          <h2>项目文献</h2>
          <Badge>{papers.length} 篇</Badge>
        </div>
        <label
          className={
            "button primary file-button " + (busy || readOnly ? "disabled" : "")
          }
          title={readOnly ? demoReadOnlyHint : undefined}
        >
          <Upload size={16} />
          {busy ? "正在处理…" : "上传 PDF"}
          <input
            type="file"
            accept=".pdf,application/pdf"
            multiple
            disabled={busy || readOnly}
            onChange={(e) => {
              upload(e.target.files);
              e.target.value = "";
            }}
            aria-label="上传 PDF"
          />
        </label>
      </div>
      <div className="card search-card">
        <form onSubmit={search}>
          <div className="search-input">
            <Search size={19} />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="检索论文中的术语、方法或研究主题…"
              aria-label="论文检索词"
            />
            <button className="button primary" disabled={busy || !query.trim()}>
              {busy ? <LoaderCircle size={16} className="spin" /> : "检索原文"}
            </button>
          </div>
          <div className="filter-row">
            <span className="muted tiny">检索范围</span>
            <Badge>
              {selected.length
                ? selected.length + " 篇选中文献"
                : "当前项目全部文献"}
            </Badge>
            <input
              className="compact-input"
              type="number"
              placeholder="年份"
              aria-label="筛选年份"
              value={year}
              onChange={(e) => setYear(e.target.value)}
            />
            <input
              className="compact-input"
              placeholder="标签（逗号分隔）"
              aria-label="筛选标签"
              value={tags}
              onChange={(e) => setTags(e.target.value)}
            />
            {searchResult && (
              <button
                type="button"
                className="text-button"
                onClick={() => setSearchResult(null)}
              >
                返回全部论文
              </button>
            )}
          </div>
        </form>
      </div>
      {warnings.map((w, i) => (
        <Alert key={i}>{w}</Alert>
      ))}
      {searchResult ? (
        <section className="card space-top">
          <div className="card-heading">
            <h2>
              检索结果 <Badge>{searchResult.length}</Badge>
            </h2>
            <span className="tiny muted">
              {mode === "hybrid" ? "关键词与向量混合检索" : "关键词检索 · BM25"}
            </span>
          </div>
          {searchResult.length ? (
            searchResult.map((c, i) => (
              <article className="search-hit" key={c.chunk_id}>
                <div className="row between">
                  <button
                    className="hit-title"
                    onClick={() => onRead(c.paper_id, c.page_number)}
                  >
                    <FileText size={17} />
                    {c.title}
                  </button>
                  <Badge>第 {c.page_number} 页</Badge>
                </div>
                <p>{c.quote}</p>
                <button className="text-button" onClick={() => onCite(c)}>
                  查看证据 {i + 1}
                  <ArrowUpRight size={14} />
                </button>
              </article>
            ))
          ) : (
            <Empty title="没有找到匹配的原文">
              尝试调整关键词、论文范围或筛选条件。
            </Empty>
          )}
        </section>
      ) : papers.length ? (
        <div className="card space-top">
          <div className="table-scroll">
            <table className="papers-table">
              <thead>
                <tr>
                  <th className="check-cell">
                    <input
                      type="checkbox"
                      aria-label="选择全部论文"
                      checked={
                        papers.length > 0 && selected.length === papers.length
                      }
                      onChange={(e) =>
                        setSelected(
                          e.target.checked ? papers.map((p) => p.id) : [],
                        )
                      }
                    />
                  </th>
                  <th>论文 / 文献信息</th>
                  <th>解析状态</th>
                  <th>标签 / 阅读</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {papers.map((p) => (
                  <tr key={p.id}>
                    <td>
                      <input
                        type="checkbox"
                        aria-label={"选择 " + p.title}
                        checked={selected.includes(p.id)}
                        onChange={(e) =>
                          setSelected((s) =>
                            e.target.checked
                              ? [...s, p.id]
                              : s.filter((id) => id !== p.id),
                          )
                        }
                      />
                    </td>
                    <td>
                      <button
                        className="paper-title"
                        onClick={() => onRead(p.id)}
                      >
                        <div className="paper-icon">
                          <FileText size={20} />
                        </div>
                        <div>
                          <strong>{p.title || p.filename}</strong>
                          <small>
                            {p.authors || "作者待补充"}
                            {p.year ? " · " + p.year : ""}
                          </small>
                          <small>
                            {p.filename} · {fmt(p.size_bytes / 1024, 0)} KB ·{" "}
                            {p.page_count || "—"} 页
                          </small>
                        </div>
                      </button>
                      {p.error && <p className="inline-error">{p.error}</p>}
                    </td>
                    <td>
                      <Badge
                        tone={
                          p.status === "completed"
                            ? "teal"
                            : ["failed", "needs_ocr", "interrupted"].includes(
                                  p.status,
                                )
                              ? "amber"
                              : "neutral"
                        }
                      >
                        {statusLabel[p.status] || p.status}
                      </Badge>
                    </td>
                    <td>
                      <div className="tag-wrap">
                        {(p.tags || []).slice(0, 3).map((t) => (
                          <Badge key={t}>{t}</Badge>
                        ))}
                      </div>
                      <span className="tiny muted">
                        {statusLabel[p.reading_status] || "未读"}
                      </span>
                    </td>
                    <td>
                      <div className="row">
                        {["failed", "interrupted"].includes(p.status) && (
                          <button
                            className="icon-button"
                            title="重试解析"
                            disabled={readOnly}
                            onClick={() => retry(p)}
                          >
                            <RefreshCw size={16} />
                          </button>
                        )}
                        <button
                          className="icon-button"
                          title="阅读论文"
                          aria-label={"阅读 " + p.title}
                          onClick={() => onRead(p.id)}
                        >
                          <ArrowUpRight size={17} />
                        </button>
                        <button
                          className="icon-button danger"
                          title="删除论文"
                          disabled={readOnly}
                          aria-label={"删除 " + p.title}
                          onClick={() => setRemove(p)}
                        >
                          <Trash2 size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="card space-top">
          <Empty title="建立你的第一份文献证据">
            <span>
              上传有文本层的中英文 PDF。文件按哈希去重，解析后可逐页阅读与检索。
              <br />
              扫描版 PDF 将明确标记为“需要 OCR”。
            </span>
          </Empty>
        </div>
      )}
      {remove && (
        <Modal title="删除论文" onClose={() => setRemove(null)}>
          <div className="form-body">
            <p>确定删除《{remove.title}》及其原始文件、文本和检索索引？</p>
            <p className="muted">
              此操作无法从界面恢复。已有报告保留历史引用记录。
            </p>
            <div className="form-actions">
              <button
                className="button secondary"
                onClick={() => setRemove(null)}
              >
                取消
              </button>
              <button
                className="button danger-solid"
                disabled={busy}
                onClick={deletePaper}
              >
                确认删除
              </button>
            </div>
          </div>
        </Modal>
      )}
    </>
  );
}
function Scope({
  papers,
  selected,
  onChange,
}: {
  papers: Paper[];
  selected: string[];
  onChange: (s: string[]) => void;
}) {
  return (
    <details className="scope">
      <summary>
        <BookOpen size={15} />{" "}
        {selected.length
          ? "已选择 " + selected.length + " 篇论文"
          : "当前项目全部论文"}
        <ChevronDown size={13} />
      </summary>
      <div className="scope-options">
        {!papers.length ? (
          <span className="muted">请先上传论文</span>
        ) : (
          papers.map((p) => (
            <label className="checkbox" key={p.id}>
              <input
                type="checkbox"
                checked={selected.includes(p.id)}
                onChange={(e) =>
                  onChange(
                    e.target.checked
                      ? [...selected, p.id]
                      : selected.filter((id) => id !== p.id),
                  )
                }
              />
              {p.title}
            </label>
          ))
        )}
        <button className="text-button" onClick={() => onChange([])}>
          重置为全部论文
        </button>
      </div>
    </details>
  );
}
function Chat({
  pid,
  papers,
  settings,
  onCite,
  notify,
}: {
  pid: string;
  papers: Paper[];
  settings: Settings | null;
  onCite: (c: Citation) => void;
  notify: (s: string, e?: boolean) => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]),
    [question, setQuestion] = useState(""),
    [selected, setSelected] = useState<string[]>([]),
    [busy, setBusy] = useState(false),
    [cid, setCid] = useState(""),
    [histories, setHistories] = useState<Conversation[]>([]);
  const load = useCallback(
    () =>
      api<Conversation[]>("/projects/" + pid + "/conversations")
        .then(setHistories)
        .catch((e) => notify(e.message, true)),
    [pid, notify],
  );
  useEffect(() => {
    load();
  }, [load]);
  const ask = async (e: FormEvent) => {
    e.preventDefault();
    if (!question.trim()) return;
    const q = question.trim();
    setQuestion("");
    setMessages((m) => [...m, { role: "user", content: q, citations: [] }]);
    setBusy(true);
    try {
      const r = await api<{
        answer: string;
        conversation_id: string | null;
        citations: Citation[];
        mode: string;
        warnings: string[];
      }>(
        "/projects/" + pid + "/ask",
        json({
          question: q,
          paper_ids: selected,
          conversation_id: cid || undefined,
        }),
      );
      setCid(r.conversation_id || "");
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: r.answer,
          citations: r.citations || [],
          mode: r.mode,
        },
      ]);
      r.warnings?.forEach((w) => notify(w));
      load();
    } catch (e) {
      setQuestion(q);
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <div className="ai-disclosure">
        <Sparkles size={17} />
        <div>
          <strong>
            {settings?.ai_enabled && settings.chat_configured
              ? "证据驱动的科研问答"
              : "AI 未配置或未启用"}
          </strong>
          <span>
            {settings?.read_only
              ? "公开演示仅检索合成论文的原文片段，不调用外部模型，不保存会话。"
              : settings?.ai_enabled && settings.chat_configured
                ? "回答基于当前项目检索片段，请结合原文审阅。"
                : "当前可检索真实原文片段。设置模型并同意外发后，才能生成 AI 回答。"}
          </span>
        </div>
        <Badge tone="teal">可追溯</Badge>
      </div>
      <div className="chat-layout">
        <section className="card chat-card">
          <div className="card-heading">
            <Scope papers={papers} selected={selected} onChange={setSelected} />
            <button
              className="text-button"
              disabled={busy}
              onClick={() => {
                setMessages([]);
                setCid("");
              }}
            >
              <Plus size={14} />
              新对话
            </button>
          </div>
          <div className="chat-messages">
            {messages.length ? (
              messages.map((m, i) => (
                <article className={"chat-message " + m.role} key={i}>
                  <div className={"message-avatar " + m.role}>
                    {m.role === "user" ? "我" : <Sparkles size={17} />}
                  </div>
                  <div className="message-body">
                    <div className="row between">
                      <strong>
                        {m.role === "user" ? "研究者" : "研知助手"}
                      </strong>
                      {m.mode && (
                        <Badge tone={m.mode === "ai" ? "teal" : "amber"}>
                          {m.mode === "ai"
                            ? "基于文献生成"
                            : m.mode === "no_evidence"
                              ? "证据不足"
                              : "原文检索 · 非 AI 总结"}
                        </Badge>
                      )}
                    </div>
                    <p className="prewrap">{m.content}</p>
                    <Citations items={m.citations || []} onSelect={onCite} />
                  </div>
                </article>
              ))
            ) : (
              <div className="chat-welcome">
                <div className="hero-icon small">
                  <MessageSquare size={26} />
                </div>
                <h2>从一个好问题开始</h2>
                <p>让问题连接已有研究，让证据带来新的思路。</p>
                <div className="prompt-grid">
                  {[
                    "这些论文的研究方法有哪些共同点？",
                    "论文明确报告了哪些实验设置？",
                    "现有研究有哪些未解决的局限？",
                  ].map((t) => (
                    <button key={t} onClick={() => setQuestion(t)}>
                      {t}
                      <ArrowUpRight size={14} />
                    </button>
                  ))}
                </div>
              </div>
            )}
            {busy && <Spinner label="正在检索原文并处理回答…" />}
          </div>
          <form onSubmit={ask} className="chat-composer">
            <textarea
              rows={3}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="提出研究问题，回答将附上可以核查的文献证据…"
              aria-label="研究问题"
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                  e.preventDefault();
                  ask(e);
                }
              }}
            />
            <div className="row between">
              <span className="tiny muted">
                Ctrl + Enter 发送 · 资料不足时明确说明
              </span>
              <button
                className="button primary"
                disabled={busy || !question.trim()}
              >
                {busy ? (
                  <LoaderCircle size={16} className="spin" />
                ) : (
                  <ArrowRight size={16} />
                )}
                发送问题
              </button>
            </div>
          </form>
        </section>
        <aside className="card history">
          <h3>研究对话</h3>
          <p className="tiny muted">对话与引用保存在当前项目中</p>
          {histories.length ? (
            histories.map((c) => (
              <button
                key={c.id}
                className={"history-item " + (cid === c.id ? "active" : "")}
                onClick={() => {
                  setCid(c.id);
                  setMessages(c.messages || []);
                }}
              >
                <MessageSquare size={15} />
                <span>
                  {c.title ||
                    c.messages?.find((m) => m.role === "user")?.content ||
                    "研究对话"}
                </span>
              </button>
            ))
          ) : (
            <p className="tiny muted">暂无历史对话</p>
          )}
        </aside>
      </div>
    </>
  );
}
function Compare({
  pid,
  papers,
  onCite,
  notify,
}: {
  pid: string;
  papers: Paper[];
  onCite: (c: Citation) => void;
  notify: (s: string, e?: boolean) => void;
}) {
  const [selected, setSelected] = useState<string[]>([]),
    [rows, setRows] = useState<
      { paper_id: string; title: string; fields: ReadingField[] }[]
    >([]),
    [busy, setBusy] = useState(false),
    [warnings, setWarnings] = useState<string[]>([]),
    [mode, setMode] = useState("");
  const run = async () => {
    setBusy(true);
    try {
      const r = await api<{
        mode: string;
        rows: typeof rows;
        warnings: string[];
      }>("/projects/" + pid + "/compare", json({ paper_ids: selected }));
      setRows(r.rows);
      setWarnings(r.warnings || []);
      setMode(r.mode);
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <div className="card">
        <div className="card-heading">
          <div>
            <h2>选择对比文献</h2>
            <p className="muted tiny">
              选择 2—5 篇论文，按统一问题梳理证据与研究边界。
            </p>
          </div>
          <button
            className="button primary"
            disabled={busy || selected.length < 2 || selected.length > 5}
            onClick={run}
          >
            {busy ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <GitCompareArrows size={16} />
            )}
            生成对比表
          </button>
        </div>
        <div className="compare-selection">
          {papers.length ? (
            papers.map((p) => (
              <label
                className={
                  "select-paper " + (selected.includes(p.id) ? "selected" : "")
                }
                key={p.id}
              >
                <input
                  type="checkbox"
                  checked={selected.includes(p.id)}
                  disabled={!selected.includes(p.id) && selected.length >= 5}
                  onChange={(e) =>
                    setSelected(
                      e.target.checked
                        ? [...selected, p.id]
                        : selected.filter((id) => id !== p.id),
                    )
                  }
                />
                <FileText size={18} />
                <span>
                  {p.title}
                  <small>
                    {p.year || "年份待补充"} ·{" "}
                    {statusLabel[p.status] || p.status}
                  </small>
                </span>
              </label>
            ))
          ) : (
            <Empty title="先添加两篇论文">
              上传并完成解析后，即可进行文献对比。
            </Empty>
          )}
        </div>
      </div>
      <Alert>
        不同数据集、单位或评价协议下的结果不能直接排序。本表用于梳理信息，不产生未经验证的优劣结论。
      </Alert>
      {warnings.map((w, i) => (
        <Alert key={i}>{w}</Alert>
      ))}
      {rows.length > 0 && (
        <section className="card space-top">
          <div className="card-heading">
            <h2>文献对比矩阵</h2>
            <Badge tone={mode === "ai" ? "teal" : "amber"}>
              {mode === "ai" ? "AI 基于原文生成" : "未配置模型 · 原文检索"}
            </Badge>
          </div>
          <div
            className="comparison-grid"
            style={{
              gridTemplateColumns:
                "repeat(" + rows.length + ", minmax(270px, 1fr))",
            }}
          >
            {rows.map((r) => (
              <article className="comparison-column" key={r.paper_id}>
                <h3>{r.title}</h3>
                {r.fields.map((f, i) => (
                  <section className="reading-field" key={i}>
                    <h4>{f.name}</h4>
                    <p className="prewrap">{f.text}</p>
                    <Citations items={f.citations || []} onSelect={onCite} />
                  </section>
                ))}
              </article>
            ))}
          </div>
        </section>
      )}
    </>
  );
}
function Reports({
  pid,
  revision,
  notify,
}: {
  pid: string;
  revision: number;
  notify: (s: string, e?: boolean) => void;
}) {
  const [reports, setReports] = useState<Report[]>([]),
    [selected, setSelected] = useState<Report | null>(null),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    api<Report[]>("/projects/" + pid + "/reports")
      .then((r) => {
        setReports(r);
        setSelected((c) => r.find((x) => x.id === c?.id) || r[0] || null);
      })
      .catch((e) => notify(e.message, true))
      .finally(() => setLoading(false));
  }, [pid, revision, notify]);
  return loading ? (
    <Spinner />
  ) : !reports.length ? (
    <div className="card">
      <Empty title="保存一份完整的研究报告">
        在实验分析页面完成统计计算，点击“生成研究报告”。
        <br />
        报告将记录数据版本、分析配置、数值结果与研究局限。
      </Empty>
    </div>
  ) : (
    <div className="reports-layout">
      <aside className="card reports-list">
        <div className="card-heading">
          <h3>项目报告</h3>
          <Badge>{reports.length}</Badge>
        </div>
        {reports.map((r) => (
          <button
            key={r.id}
            className={"report-item " + (selected?.id === r.id ? "active" : "")}
            onClick={() => setSelected(r)}
          >
            <FileText size={18} />
            <div>
              <strong>{r.title}</strong>
              <small>{date(r.created_at)}</small>
            </div>
          </button>
        ))}
      </aside>
      {selected && (
        <section className="card report-preview">
          <div className="card-heading">
            <div>
              <h2>{selected.title}</h2>
              <p className="tiny muted">
                {date(selected.created_at)} · 绑定已保存的分析结果
              </p>
            </div>
            <a
              className="button primary"
              href={
                "/api/projects/" +
                pid +
                "/reports/" +
                selected.id +
                "/download?format=zip"
              }
            >
              <Download size={16} />
              完整复现包
            </a>
          </div>
          <div className="download-row">
            {[
              ["md", "Markdown"],
              ["csv", "统计 CSV"],
              ["png", "图表 PNG"],
              ["py", "复现脚本"],
              ["json", "配置 JSON"],
            ].map(([f, t]) => (
              <a
                className="button secondary small"
                key={f}
                href={
                  "/api/projects/" +
                  pid +
                  "/reports/" +
                  selected.id +
                  "/download?format=" +
                  f
                }
              >
                <Download size={13} />
                {t}
              </a>
            ))}
          </div>
          <p className="tiny muted pad-x">
            完整包包含原始数据、配置、依赖版本和复现脚本。下载前请确认分享范围。
          </p>
          <div className="markdown-report rendered-report">
            <Markdown
              remarkPlugins={[remarkGfm]}
              skipHtml
              components={{
                img: ({ src, alt }) => {
                  const kinds: Record<string, string> = {
                    "plot.png": "points",
                    "box.png": "box",
                    "histogram.png": "hist",
                  };
                  const kind = typeof src === "string" ? kinds[src] : undefined;
                  return kind ? (
                    <img
                      src={
                        "/api/projects/" +
                        pid +
                        "/analyses/" +
                        selected.analysis_id +
                        "/plot.png?kind=" +
                        kind
                      }
                      alt={alt || "实验图表"}
                      loading="lazy"
                    />
                  ) : (
                    <span className="muted">
                      [外部图片未自动加载：{alt || "图片"}]
                    </span>
                  );
                },
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noreferrer">
                    {children}
                  </a>
                ),
              }}
            >
              {selected.markdown}
            </Markdown>
          </div>
        </section>
      )}
    </div>
  );
}
function SettingsView({
  settings,
  onChange,
  notify,
  pid,
}: {
  settings: Settings | null;
  onChange: (s: Settings) => void;
  notify: (s: string, e?: boolean) => void;
  pid: string;
}) {
  const readOnly = useReadOnlyDemo();
  const [busy, setBusy] = useState(false),
    [consent, setConsent] = useState(false),
    [indexStatus, setIndexStatus] = useState<Record<string, unknown> | null>(
      null,
    );
  useEffect(() => {
    if (pid)
      api<Record<string, unknown>>("/projects/" + pid + "/embedding-status")
        .then(setIndexStatus)
        .catch(() => {});
  }, [pid]);
  const toggle = async () => {
    if (readOnly) return;
    setBusy(true);
    try {
      const s = await api<Settings>("/settings", {
        method: "PATCH",
        body: JSON.stringify({ ai_enabled: !settings?.ai_enabled }),
      });
      onChange(s);
      notify(s.ai_enabled ? "已启用外部模型调用" : "已关闭外部模型调用");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
  const rebuild = async () => {
    if (readOnly) return;
    setBusy(true);
    try {
      await api("/projects/" + pid + "/embeddings/rebuild", json({}));
      notify("已提交向量索引重建，请在项目任务中查看进度");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
  return !settings ? (
    <Empty title="无法读取设置">请检查后端服务并刷新页面。</Empty>
  ) : (
    <div className="settings-layout">
      {readOnly && (
        <Alert>
          {demoReadOnlyHint}。此环境不配置模型密钥、不调用外部
          AI；以下设置仅供查看。
        </Alert>
      )}
      <section className="card">
        <div className="card-heading">
          <div>
            <h2>外部 AI 模型</h2>
            <p className="tiny muted">
              聊天与向量服务分别配置，密钥仅由后端环境变量读取。
            </p>
          </div>
          <Badge tone={settings.ai_enabled ? "teal" : "amber"}>
            {settings.ai_enabled ? "已启用" : "未启用"}
          </Badge>
        </div>
        <div className="settings-body">
          <div className="model-info">
            <div className="stat-icon teal">
              <MessageSquare size={20} />
            </div>
            <div>
              <h3>聊天模型</h3>
              <p>
                {settings.chat_configured ? settings.chat_model : "未配置模型"}
              </p>
              <small>
                {settings.chat_base_url ||
                  "请在 .env 中填写 AI_BASE_URL、AI_CHAT_MODEL、AI_API_KEY"}
              </small>
            </div>
            <Badge tone={settings.chat_configured ? "teal" : "neutral"}>
              {settings.chat_configured ? "已配置" : "未配置"}
            </Badge>
          </div>
          <div className="model-info">
            <div className="stat-icon blue">
              <Database size={20} />
            </div>
            <div>
              <h3>向量模型</h3>
              <p>
                {settings.embedding_configured
                  ? settings.embedding_model
                  : "未配置模型"}
              </p>
              <small>
                {settings.embedding_base_url ||
                  "请在 .env 中填写 EMBEDDING_BASE_URL、EMBEDDING_MODEL、EMBEDDING_API_KEY"}
              </small>
            </div>
            <Badge tone={settings.embedding_configured ? "teal" : "neutral"}>
              {settings.embedding_configured ? "已配置" : "未配置"}
            </Badge>
          </div>
          <Alert>
            <strong>启用前了解资料外发范围</strong>
            <p>
              问答、阅读卡和文献对比会向所选聊天服务发送研究问题与检索到的论文片段；分析建议会发送研究问题、字段信息、数据概况和少量预览行。向量索引与语义检索会向所选向量服务发送论文切块和检索词。模型只收到上述文本与数据概况，不上传原始
              PDF 文件。完整表格不会发送给模型，密钥仅由后端读取。
            </p>
            <p>
              后端仅调用受校验的固定接口，模型输出不会作为代码运行。请先确认所选服务与你的资料使用要求相符。
            </p>
          </Alert>
          {!settings.ai_enabled && (
            <label className="checkbox">
              <input
                type="checkbox"
                disabled={readOnly}
                checked={consent}
                onChange={(e) => setConsent(e.target.checked)}
              />
              我已了解发送范围，同意将上述资料发送到配置的模型服务。
            </label>
          )}
          <button
            className={
              "button " + (settings.ai_enabled ? "secondary" : "primary")
            }
            disabled={
              readOnly ||
              busy ||
              (!settings.ai_enabled &&
                (!consent ||
                  (!settings.chat_configured &&
                    !settings.embedding_configured)))
            }
            onClick={toggle}
          >
            {busy && <LoaderCircle className="spin" size={15} />}{" "}
            {settings.ai_enabled ? "关闭外部 AI 调用" : "同意并启用 AI"}
          </button>
          <p className="tiny muted">
            修改 .env 后需重启服务；未配置或关闭 AI
            时，上传、阅读、关键词检索、统计和导出继续正常工作。
          </p>
        </div>
      </section>
      <section className="card space-top">
        <div className="card-heading">
          <div>
            <h2>项目向量索引</h2>
            <p className="tiny muted">
              模型、维度或版本发生变化后，应为当前项目重建索引。
            </p>
          </div>
          <button
            className="button secondary"
            disabled={
              readOnly ||
              busy ||
              !pid ||
              !settings.embedding_configured ||
              !settings.ai_enabled
            }
            onClick={rebuild}
          >
            <RefreshCw size={15} />
            重建当前项目索引
          </button>
        </div>
        {indexStatus && (
          <div className="settings-body">
            <div className="settings-metrics">
              <p>
                可检索片段：
                <strong>{String(indexStatus.total_chunks ?? 0)}</strong>
              </p>
              <p>
                当前模型已索引：
                <strong>{String(indexStatus.indexed_chunks ?? 0)}</strong>
              </p>
              <p>
                索引状态：
                <strong>
                  {indexStatus.needs_rebuild
                    ? "需要重建或补全"
                    : "已覆盖当前片段"}
                </strong>
              </p>
            </div>
          </div>
        )}
      </section>
      <section className="card space-top">
        <div className="card-heading">
          <h2>本地资源限制</h2>
          <Badge>后端配置</Badge>
        </div>
        <div className="settings-body">
          <div className="settings-metrics">
            <p>
              单文件大小：
              <strong>{String(settings.limits.max_upload_mb)} MB</strong>
            </p>
            <p>
              PDF 页数上限：
              <strong>{String(settings.limits.max_pdf_pages)} 页</strong>
            </p>
            <p>
              解析时限：
              <strong>
                {String(settings.limits.parse_timeout_seconds)} 秒
              </strong>
            </p>
            <p>
              表格规模上限：
              <strong>
                {String(settings.limits.max_dataset_rows)} 行 ×{" "}
                {String(settings.limits.max_dataset_columns)} 列
              </strong>
            </p>
          </div>
          <p className="tiny muted">
            上传大小、页数、解析时限与模型调用限制均由后端环境变量管理。请参阅项目
            README。
          </p>
        </div>
      </section>
    </div>
  );
}
