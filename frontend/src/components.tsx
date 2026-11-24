import {
  Children,
  cloneElement,
  isValidElement,
  Fragment,
  useId,
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type ReactElement,
} from "react";
import {
  X,
  FileText,
  LoaderCircle,
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  Download,
  BookOpen,
  Save,
} from "lucide-react";
import * as pdfjs from "pdfjs-dist";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.mjs?url";
import {
  api,
  json,
  type Paper,
  type Citation,
  type ReadingField,
  fmt,
} from "./api";
pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
export const statusLabel: Record<string, string> = {
  queued: "排队中",
  running: "处理中",
  completed: "已就绪",
  failed: "处理失败",
  interrupted: "已中断",
  needs_ocr: "需要 OCR",
  unread: "未读",
  reading: "阅读中",
  read: "已读",
};
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <span className={"badge " + tone}>{children}</span>;
}
export function Empty({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <div className="empty-icon">
        <BookOpen size={27} />
      </div>
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function Spinner({ label = "正在加载…" }: { label?: string }) {
  return (
    <div className="loading">
      <LoaderCircle className="spin" size={18} />
      {label}
    </div>
  );
}
export function Alert({
  children,
  tone = "info",
}: {
  children: ReactNode;
  tone?: string;
}) {
  return <div className={"alert " + tone}>{children}</div>;
}
export function Field({
  label,
  children,
  hint,
}: {
  label: string;
  children: ReactNode;
  hint?: string;
}) {
  const id = useId();
  const nameControls = (nodes: ReactNode): ReactNode =>
    Children.map(nodes, (child) => {
      if (!isValidElement(child)) return child;
      const element = child as ReactElement<{
        children?: ReactNode;
        "aria-label"?: string;
        "aria-labelledby"?: string;
        "aria-describedby"?: string;
      }>;
      if (
        typeof element.type === "string" &&
        ["input", "select", "textarea"].includes(element.type)
      ) {
        if (element.props["aria-label"] || element.props["aria-labelledby"])
          return element;
        return cloneElement(element, {
          "aria-labelledby": id,
          "aria-describedby": hint ? id + "-hint" : undefined,
        });
      }
      return element.type === Fragment
        ? cloneElement(element, {}, nameControls(element.props.children))
        : element;
    });
  return (
    <label className="field">
      <span id={id}>{label}</span>
      {nameControls(children)}
      {hint && <small id={id + "-hint"}>{hint}</small>}
    </label>
  );
}
export function Modal({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const old = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab") {
        const list = ref.current?.querySelectorAll<HTMLElement>(
          "button,input,select,textarea,a[href]",
        );
        if (!list?.length) return;
        const first = list[0],
          last = list[list.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    ref.current?.focus();
    return () => {
      document.body.style.overflow = old;
      document.removeEventListener("keydown", key);
    };
  }, [onClose]);
  return (
    <div
      className="modal-scrim"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className={"modal " + (wide ? "wide" : "")}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        ref={ref}
      >
        <div className="modal-head">
          <h2>{title}</h2>
          <button className="icon-button" aria-label="关闭" onClick={onClose}>
            <X size={20} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
export function Citations({
  items,
  onSelect,
}: {
  items: Citation[];
  onSelect: (c: Citation) => void;
}) {
  return (
    <div className="citations">
      {items.map((c, i) => (
        <button
          key={c.chunk_id + "-" + i}
          className="citation-button"
          title={c.quote}
          onClick={() => onSelect(c)}
        >
          <FileText size={13} />
          {i + 1} · {c.title} <span>p.{c.page_number}</span>
        </button>
      ))}
    </div>
  );
}
export function Evidence({
  citation,
  onOpen,
  onClose,
}: {
  citation: Citation;
  onOpen: () => void;
  onClose: () => void;
}) {
  return (
    <aside className="evidence">
      <div className="row between">
        <h3>证据原文</h3>
        <button className="icon-button" aria-label="收起证据" onClick={onClose}>
          <X size={17} />
        </button>
      </div>
      <Badge tone="teal">PDF 第 {citation.page_number} 页</Badge>
      <h4>{citation.title}</h4>
      <blockquote>{citation.quote}</blockquote>
      <p className="muted tiny">
        引用标识与原文经过匹配检查。引用存在并不代表结论已经得到充分证明。
      </p>
      <button className="button secondary full" onClick={onOpen}>
        打开原文对应页
        <ArrowUpRight size={15} />
      </button>
    </aside>
  );
}
export function Reader({
  projectId,
  paperId,
  initialPage,
  onClose,
  onSave,
  onCite,
  notify,
}: {
  projectId: string;
  paperId: string;
  initialPage: number;
  onClose: () => void;
  onSave: () => void;
  onCite: (c: Citation) => void;
  notify: (s: string, error?: boolean) => void;
}) {
  const [paper, setPaper] = useState<Paper | null>(null),
    [page, setPage] = useState(initialPage),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [tab, setTab] = useState("text"),
    [fields, setFields] = useState<ReadingField[]>([]),
    [busy, setBusy] = useState(false),
    [pdfError, setPdfError] = useState("");
  const canvas = useRef<HTMLCanvasElement>(null);
  const doc = useRef<pdfjs.PDFDocumentProxy | null>(null);
  const url = "/api/projects/" + projectId + "/papers/" + paperId + "/file";
  useEffect(() => {
    let cancelled = false;
    api<Paper>(`/projects/${projectId}/papers/${paperId}`)
      .then((p) => {
        if (!cancelled) setPaper(p);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
    const task = pdfjs.getDocument({
      url,
      cMapUrl: "/pdfjs/cmaps/",
      cMapPacked: true,
      standardFontDataUrl: "/pdfjs/standard_fonts/",
      isEvalSupported: false,
    });
    task.promise
      .then((d) => {
        if (cancelled) {
          d.destroy();
          return;
        }
        doc.current = d;
        setPage((p) => Math.min(p, d.numPages));
      })
      .catch((e) => {
        if (!cancelled) setPdfError(String(e.message));
      });
    return () => {
      cancelled = true;
      task.destroy();
      doc.current = null;
    };
  }, [projectId, paperId, url]);
  useEffect(() => {
    if (!paper || !canvas.current) return;
    let task: pdfjs.RenderTask | undefined;
    let stopped = false;
    async function render() {
      try {
        const d = doc.current;
        if (!d) {
          window.setTimeout(() => {
            if (!stopped) render();
          }, 150);
          return;
        }
        const p = await d.getPage(page);
        if (stopped || !canvas.current) return;
        const viewport = p.getViewport({ scale: 1.35 });
        const c = canvas.current;
        c.height = viewport.height;
        c.width = viewport.width;
        const context = c.getContext("2d");
        if (context) {
          task = p.render({ canvasContext: context, viewport });
          await task.promise;
        }
      } catch (e) {
        if (
          !stopped &&
          e instanceof Error &&
          e.name !== "RenderingCancelledException"
        )
          setPdfError(e.message);
      }
    }
    render();
    return () => {
      stopped = true;
      task?.cancel();
    };
  }, [paper, page]);
  const save = async () => {
    if (!paper) return;
    setBusy(true);
    try {
      await api(`/projects/${projectId}/papers/${paperId}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: paper.title,
          authors: paper.authors,
          year: paper.year,
          doi: paper.doi,
          tags: paper.tags,
          reading_status: paper.reading_status,
          notes: paper.notes,
        }),
      });
      notify("论文信息已保存");
      onSave();
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
  const readingCard = async () => {
    setBusy(true);
    try {
      const r = await api<{
        fields: ReadingField[];
        mode: string;
        warnings: string[];
      }>(`/projects/${projectId}/papers/${paperId}/reading-card`, json({}));
      setFields(r.fields);
      setTab("card");
      r.warnings?.forEach((w) => notify(w));
      if (r.mode === "offline")
        notify("未配置模型：阅读卡仅展示已有原文，不代表 AI 总结");
    } catch (e) {
      notify((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal title={paper?.title || "论文阅读"} onClose={onClose} wide>
      {loading ? (
        <Spinner />
      ) : error ? (
        <Alert tone="error">{error}</Alert>
      ) : (
        paper && (
          <div className="reader">
            <div className="pdf-pane">
              <div className="pdf-toolbar">
                <button
                  className="icon-button"
                  aria-label="上一页"
                  disabled={page <= 1}
                  onClick={() => setPage(page - 1)}
                >
                  <ChevronLeft size={18} />
                </button>
                <label className="row">
                  第{" "}
                  <input
                    aria-label="PDF 页码"
                    type="number"
                    min="1"
                    max={paper.page_count || 1}
                    value={page}
                    onChange={(e) =>
                      setPage(
                        Math.max(
                          1,
                          Math.min(
                            paper.page_count || 1,
                            Number(e.target.value) || 1,
                          ),
                        ),
                      )
                    }
                  />{" "}
                  / {paper.page_count || "—"} 页
                </label>
                <button
                  className="icon-button"
                  aria-label="下一页"
                  disabled={page >= (paper.page_count || 1)}
                  onClick={() => setPage(page + 1)}
                >
                  <ChevronRight size={18} />
                </button>
                <a
                  className="icon-button"
                  href={url}
                  target="_blank"
                  rel="noreferrer"
                  aria-label="下载原始 PDF"
                >
                  <Download size={17} />
                </a>
              </div>
              <div className="pdf-canvas">
                {pdfError ? (
                  <Alert tone="error">
                    PDF 预览失败：{pdfError}。可下载原始文件继续阅读。
                  </Alert>
                ) : (
                  <canvas ref={canvas} aria-label={"PDF 第 " + page + " 页"} />
                )}
              </div>
            </div>
            <div className="reader-info">
              <div className="tabs small-tabs">
                {[
                  ["text", "逐页文本"],
                  ["metadata", "信息笔记"],
                  ["card", "阅读卡"],
                ].map(([k, t]) => (
                  <button
                    className={tab === k ? "active" : ""}
                    key={k}
                    onClick={() => setTab(k)}
                  >
                    {t}
                  </button>
                ))}
              </div>
              {tab === "text" ? (
                <>
                  <p className="eyebrow">EXTRACTED TEXT / 第 {page} 页</p>
                  <p className="text-preview">
                    {paper.pages?.find((p) => p.page_number === page)?.text ||
                      "本页未提取到文本。扫描页面需要 OCR。"}
                  </p>
                </>
              ) : tab === "metadata" ? (
                <div className="form-grid single">
                  <Field label="标题">
                    <input
                      value={paper.title}
                      onChange={(e) =>
                        setPaper({ ...paper, title: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="作者">
                    <input
                      value={paper.authors || ""}
                      onChange={(e) =>
                        setPaper({ ...paper, authors: e.target.value })
                      }
                    />
                  </Field>
                  <div className="form-grid">
                    <Field label="年份">
                      <input
                        type="number"
                        min="1000"
                        max="2200"
                        value={paper.year || ""}
                        onChange={(e) =>
                          setPaper({
                            ...paper,
                            year: e.target.value
                              ? Number(e.target.value)
                              : null,
                          })
                        }
                      />
                    </Field>
                    <Field label="阅读状态">
                      <select
                        value={paper.reading_status || "unread"}
                        onChange={(e) =>
                          setPaper({ ...paper, reading_status: e.target.value })
                        }
                      >
                        <option value="unread">未读</option>
                        <option value="reading">阅读中</option>
                        <option value="read">已读</option>
                      </select>
                    </Field>
                  </div>
                  <Field label="DOI">
                    <input
                      value={paper.doi || ""}
                      onChange={(e) =>
                        setPaper({ ...paper, doi: e.target.value })
                      }
                    />
                  </Field>
                  <Field label="标签（逗号分隔）">
                    <input
                      value={(paper.tags || []).join(",")}
                      onChange={(e) =>
                        setPaper({
                          ...paper,
                          tags: e.target.value.split(/[,，]/).filter(Boolean),
                        })
                      }
                    />
                  </Field>
                  <Field label="阅读笔记">
                    <textarea
                      rows={6}
                      value={paper.notes || ""}
                      onChange={(e) =>
                        setPaper({ ...paper, notes: e.target.value })
                      }
                    />
                  </Field>
                  <button
                    className="button primary"
                    disabled={busy}
                    onClick={save}
                  >
                    <Save size={15} />
                    保存信息
                  </button>
                </div>
              ) : (
                <>
                  <button
                    className="button secondary full"
                    disabled={busy}
                    onClick={readingCard}
                  >
                    {busy ? (
                      <LoaderCircle size={15} className="spin" />
                    ) : (
                      <BookOpen size={15} />
                    )}
                    生成结构化阅读卡
                  </button>
                  <p className="tiny muted">
                    研究问题、方法、数据、实验设置、主要结果和局限。缺失内容明确标注。
                  </p>
                  {fields.map((f, i) => (
                    <section className="reading-field" key={i}>
                      <h4>{f.name}</h4>
                      <p className="prewrap">{f.text}</p>
                      <Citations
                        items={f.citations || []}
                        onSelect={(c) => {
                          setPage(c.page_number);
                          onCite(c);
                        }}
                      />
                    </section>
                  ))}
                </>
              )}
            </div>
          </div>
        )
      )}
    </Modal>
  );
}
export function DataTable({
  rows,
  columns,
  max = 15,
}: {
  rows: Record<string, unknown>[];
  columns: string[];
  max?: number;
}) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c}>{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, max).map((r, i) => (
            <tr key={i}>
              {columns.map((c) => (
                <td key={c} title={String(r[c] ?? "")}>
                  {r[c] == null ? (
                    <span className="muted">缺失</span>
                  ) : typeof r[c] === "object" ? (
                    JSON.stringify(r[c])
                  ) : (
                    fmt(r[c])
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {!rows.length && <p className="muted pad">暂无记录</p>}
    </div>
  );
}
