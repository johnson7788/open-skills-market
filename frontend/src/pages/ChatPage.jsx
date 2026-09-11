import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { marked } from "marked";
import DOMPurify from "dompurify";
import {
  artifactUrl,
  fetchArtifacts,
  fetchChatHistory,
  fetchConversations,
  fetchSkill,
  stopChat,
  streamChat,
} from "../api";
import { getSkillIcon } from "../icons";

// 表格外包一层可横向滚动的容器，避免宽表格撑破聊天区
const mdRenderer = new marked.Renderer();
const renderTable = mdRenderer.table.bind(mdRenderer);
mdRenderer.table = (token) =>
  `<div class="chat-table-wrap">${renderTable(token)}</div>`;

function md(text) {
  return DOMPurify.sanitize(
    marked.parse(text || "", { breaks: true, renderer: mdRenderer })
  );
}

// ── 工具元数据（工具名 → 展示用 label/icon）──────────
const TOOL_META = {
  list_files: { label: "列出目录", icon: "fa-folder-open" },
  read_file: { label: "读取文件", icon: "fa-file-lines" },
  write_file: { label: "写入文件", icon: "fa-file-pen" },
  run_command: { label: "执行命令", icon: "fa-terminal" },
};

function toolMeta(name) {
  return TOOL_META[name] || { label: name || "工具", icon: "fa-wrench" };
}

function isErrorOutput(output) {
  return (
    typeof output === "string" &&
    (output.startsWith("[工具执行异常]") ||
      output.startsWith("[依赖缺失]") ||
      output.startsWith("[未知工具]"))
  );
}

function assistantText(message) {
  if (!message) return "";
  if (message.blocks) {
    return message.blocks
      .filter((b) => b.kind === "text")
      .map((b) => b.text)
      .join("");
  }
  return message.content || "";
}

function formatArgs(args) {
  const raw = args ?? "";
  if (typeof raw === "object") return JSON.stringify(raw, null, 2);
  try {
    return JSON.stringify(JSON.parse(raw), null, 2);
  } catch {
    return raw;
  }
}

function formatResult(output) {
  return output == null ? "" : String(output);
}

// 生成会话 ID：每次进入（或切换 skill）都是一次新会话，用来隔离产物与历史
function newConversationId() {
  try {
    return crypto.randomUUID();
  } catch {
    return `conv-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  }
}

// 将助手的流式时间线块分组：连续的 tool 块合并为一个工具组
function groupBlocks(blocks, { busy = false, isLast = false } = {}) {
  const items = [];
  (blocks || []).forEach((block, index) => {
    if (block.kind === "text") {
      if (block.text) items.push({ type: "text", text: block.text });
      return;
    }
    if (block.kind === "reasoning") {
      items.push({
        type: "reasoning",
        reasoning: block.reasoning,
        active: busy && isLast && index === blocks.length - 1,
      });
      return;
    }
    const last = items[items.length - 1];
    if (last && last.type === "tools") last.tools.push(block);
    else items.push({ type: "tools", tools: [block] });
  });
  return items;
}

// 推理过程折叠块（reasoning-box）
function ReasoningBlock({ reasoning, active }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="reasoning-box">
      <button
        type="button"
        className={`reasoning-summary${active ? " reasoning-summary-active" : ""}`}
        onClick={() => !active && setOpen((v) => !v)}
        disabled={active}
        aria-expanded={!active && open}
      >
        <span className="reasoning-leading">
          {active ? (
            <i className="fa-solid fa-spinner fa-spin" aria-hidden="true" />
          ) : (
            <i className="fa-solid fa-brain" aria-hidden="true" />
          )}
        </span>
        <span className="reasoning-title">{active ? "思考中…" : "推理过程"}</span>
        {!active && (
          <span className="reasoning-trailing">
            <i
              className={`fa-solid ${open ? "fa-chevron-up" : "fa-chevron-down"}`}
              aria-hidden="true"
            />
          </span>
        )}
      </button>
      {!active && open && (
        <div className="reasoning-panel">
          <div
            className="reasoning-content chat-markdown"
            dangerouslySetInnerHTML={{ __html: md(reasoning) }}
          />
        </div>
      )}
    </div>
  );
}

function ToolItem({ tool }) {
  const [open, setOpen] = useState(tool.status === "running");
  const meta = toolMeta(tool.name);
  const status =
    tool.status === "running" ? "running" : tool.status === "error" ? "error" : "completed";

  return (
    <div className={`tool-item${open ? " tool-item-open" : ""}`}>
      <button type="button" className="tool-item-header" onClick={() => setOpen((v) => !v)}>
        <span className={`tool-item-status tool-item-status-${status}`}>
          {status === "running" ? (
            <i className="fa-solid fa-spinner fa-spin" aria-hidden="true" />
          ) : status === "error" ? (
            <i className="fa-solid fa-circle-xmark" aria-hidden="true" />
          ) : (
            <i className="fa-solid fa-circle-check" aria-hidden="true" />
          )}
        </span>
        <span className="tool-item-name">
          {status === "running" && (
            <>
              正在调用工具&nbsp;<b>{meta.label}</b>
            </>
          )}
          {status === "completed" && (
            <>
              工具&nbsp;<b>{meta.label}</b>&nbsp;执行完成
            </>
          )}
          {status === "error" && (
            <>
              工具&nbsp;<b>{meta.label}</b>&nbsp;执行失败
              {tool.output && <span className="tool-item-error-msg">（{tool.output}）</span>}
            </>
          )}
        </span>
        <span className="tool-item-chevron">
          <i className={`fa-solid ${open ? "fa-chevron-up" : "fa-chevron-down"}`} aria-hidden="true" />
        </span>
      </button>
      {open && (
        <div className="tool-item-body">
          {tool.arguments != null && tool.arguments !== "" && (
            <div className="tool-item-section">
              <div className="tool-item-section-title">参数</div>
              <pre className="tool-item-pre">{formatArgs(tool.arguments)}</pre>
            </div>
          )}
          {tool.output != null && (
            <div className="tool-item-section">
              <div className="tool-item-section-title">结果</div>
              <pre className="tool-item-pre">{formatResult(tool.output)}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ToolGroup({ tools }) {
  const active = tools.some((t) => t.status === "running");
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(active);
  }, [active]);

  const summaryTitle =
    tools.length === 1
      ? `调用: ${toolMeta(tools[0].name).label}`
      : `已调用 ${tools.length} 个工具`;

  const namesMeta =
    tools.length > 1 ? [...new Set(tools.map((t) => toolMeta(t.name).label))].join(" · ") : "";

  const statusSummary = (() => {
    const states = tools.map((t) =>
      t.status === "running" ? "running" : t.status === "error" ? "error" : "completed"
    );
    if (states.length && states.every((s) => s === "completed")) return "已完成";
    const errCount = states.filter((s) => s === "error").length;
    const runCount = states.filter((s) => s === "running").length;
    return [errCount ? `${errCount} 失败` : "", runCount ? `${runCount} 进行中` : ""]
      .filter(Boolean)
      .join(" · ");
  })();

  return (
    <div className="tool-group">
      <button
        type="button"
        className="tool-group-summary"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="tool-group-icon">
          <i className="fa-solid fa-atom" aria-hidden="true" />
        </span>
        <span className="tool-group-content">
          <span className="tool-group-title">{summaryTitle}</span>
          {namesMeta && (
            <>
              <span className="tool-group-sep">·</span>
              <span className="tool-group-meta">{namesMeta}</span>
            </>
          )}
          {statusSummary && <span className="tool-group-status">{statusSummary}</span>}
        </span>
        <span className="tool-group-chevron">
          <i className={`fa-solid ${open ? "fa-chevron-up" : "fa-chevron-down"}`} aria-hidden="true" />
        </span>
      </button>
      {open && (
        <div className="tool-group-panel">
          {tools.map((tool, j) => (
            <ToolItem key={j} tool={tool} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function ChatPage() {
  const { slug } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const cidFromUrl = searchParams.get("cid") || null;
  const [skill, setSkill] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [artifacts, setArtifacts] = useState([]);
  const [lastUserText, setLastUserText] = useState("");
  const preErrorMessages = useRef([]);
  const bottomRef = useRef(null);
  const abortRef = useRef(null);
  const [conversationId, setConversationId] = useState(cidFromUrl);

  function loadMessages(d) {
    return (d.messages || []).map((m) => {
      if (m.role !== "assistant") return { role: m.role, content: m.content };
      const blocks = [];
      if (m.reasoning) blocks.push({ kind: "reasoning", reasoning: m.reasoning });
      if (m.content) blocks.push({ kind: "text", text: m.content });
      return { role: "assistant", blocks };
    });
  }

  // 进入页面：优先用 URL 里的 cid；否则恢复该技能最近一次会话；都没有则开新会话
  useEffect(() => {
    let cancelled = false;
    setSkill(null);
    setError("");
    fetchSkill(slug).then((s) => !cancelled && setSkill(s)).catch(() => {});

    (async () => {
      let cid = cidFromUrl;
      if (!cid) {
        try {
          const d = await fetchConversations(slug);
          cid = d.items && d.items[0] ? d.items[0].cid : null;
        } catch {
          cid = null;
        }
      }
      if (cancelled) return;

      if (!cid) {
        setConversationId(newConversationId());
        setMessages([]);
        setArtifacts([]);
        return;
      }

      if (!cidFromUrl) setSearchParams({ cid }, { replace: true });
      setConversationId(cid);
      setMessages([]);
      setArtifacts([]);
      try {
        const h = await fetchChatHistory(slug, cid);
        if (!cancelled) setMessages(loadMessages(h));
      } catch {
        /* ignore */
      }
      try {
        const a = await fetchArtifacts(slug, cid);
        if (!cancelled) setArtifacts(a.files || []);
      } catch {
        /* ignore */
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [slug, cidFromUrl]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, artifacts]);

  function newChat() {
    if (busy) return;
    setSearchParams({ cid: newConversationId() }, { replace: true });
  }

  async function send(text) {
    const content = (text ?? input).trim();
    if (!content || busy) return;
    setInput("");
    setError("");
    setLastUserText(content);
    preErrorMessages.current = messages;

    let cid = conversationId;
    if (!cid) {
      cid = newConversationId();
      setConversationId(cid);
      setSearchParams({ cid }, { replace: true });
    }

    const userMsg = { role: "user", content };
    const base = [...messages, userMsg];
    const assistant = { role: "assistant", blocks: [] };
    setMessages([...base, assistant]);
    setBusy(true);
    setArtifacts([]);

    const apiHistory = base
      .map((m) => ({
        role: m.role,
        content: m.role === "assistant" ? assistantText(m) : m.content,
      }))
      .filter((m) => m.role !== "assistant" || m.content);

    const answerStartMs = Date.now();
    abortRef.current = new AbortController();
    try {
      await streamChat({
        slug,
        messages: apiHistory,
        conversationId: cid,
        signal: abortRef.current.signal,
        onEvent: (event, data) => {
          if (event === "text") {
            const delta = data.delta ?? "";
            const last = assistant.blocks[assistant.blocks.length - 1];
            if (last && last.kind === "text") last.text += delta;
            else assistant.blocks.push({ kind: "text", text: delta });
          } else if (event === "reasoning") {
            const delta = data.delta ?? "";
            const last = assistant.blocks[assistant.blocks.length - 1];
            if (last && last.kind === "reasoning") last.reasoning += delta;
            else assistant.blocks.push({ kind: "reasoning", reasoning: delta });
          } else if (event === "tool") {
            if (data.output != null) {
              const pending = [...assistant.blocks]
                .reverse()
                .find((b) => b.kind === "tool" && b.status === "running");
              if (pending) {
                pending.output = data.output;
                pending.status = isErrorOutput(data.output) ? "error" : "completed";
              } else {
                assistant.blocks.push({
                  kind: "tool",
                  name: data.name,
                  arguments: undefined,
                  output: data.output,
                  status: isErrorOutput(data.output) ? "error" : "completed",
                });
              }
            } else {
              assistant.blocks.push({
                kind: "tool",
                name: data.name,
                arguments: data.arguments,
                output: null,
                status: "running",
              });
            }
          } else if (event === "error") {
            setError(data.message || "出错了");
          }
          setMessages([...base, { ...assistant, blocks: [...assistant.blocks] }]);
        },
      });
      try {
        const d = await fetchArtifacts(slug, cid);
        // 只列出本次问答新增/修改的文件（按文件修改时间过滤）
        const fresh = (d.files || []).filter(
          (f) => (f.mtime ?? 0) * 1000 >= answerStartMs - 1000
        );
        setArtifacts(fresh);
      } catch {
        /* 忽略产物拉取失败 */
      }
    } catch (e) {
      if (e && e.name !== "AbortError") setError(e.message || String(e));
    } finally {
      abortRef.current = null;
      setBusy(false);
      window.dispatchEvent(new Event("conversations-changed"));
    }
  }

  function retry() {
    if (!lastUserText || busy) return;
    setMessages(preErrorMessages.current.map((m) => ({ ...m })));
    setError("");
    send(lastUserText);
  }

  function stop() {
    stopChat(slug, conversationId);
    abortRef.current?.abort();
    setBusy(false);
  }

  return (
    <div className="chat-page">
      <header className="chat-header">
        <Link to="/" className="chat-back">
          <i className="fa-solid fa-arrow-left" aria-hidden="true" /> 返回
        </Link>
        <div className="chat-header-title">
          <span className="chat-header-name">{skill?.name || slug}</span>
          <span className="chat-header-slug">{slug}</span>
        </div>
        <button type="button" className="chat-new-chat" onClick={newChat} title="开始一个新对话">
            <i className="fa-solid fa-plus" aria-hidden="true" /> 新对话
          </button>
          <span className="chat-header-badge">技能试用</span>
      </header>

      <div className="chat-messages">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <div
              className="chat-empty-icon"
              style={skill ? { background: getSkillIcon(skill).background } : undefined}
            >
              {skill ? (
                <span aria-hidden="true">{getSkillIcon(skill).glyph}</span>
              ) : (
                <i className="fa-solid fa-wand-magic-sparkles" aria-hidden="true" />
              )}
            </div>
            <p>试试这个技能吧</p>
            <p className="chat-empty-sub">
              输入你的需求，助手会读取「{skill?.name || slug}」的说明并按需执行它的脚本。
            </p>
            {Array.isArray(skill?.examples) && skill.examples.length > 0 && (
              <div className="chat-examples">
                {skill.examples.map((q, idx) => (
                  <button
                    key={idx}
                    type="button"
                    className="chat-example-chip"
                    onClick={() => send(q)}
                    disabled={busy}
                  >
                    <i className="fa-solid fa-lightbulb" aria-hidden="true" />
                    <span>{q}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          messages.map((m, i) => {
            if (m.role !== "assistant") {
              return (
                <div key={i} className="chat-msg chat-msg-user">
                  <div className="chat-bubble chat-bubble-user">{m.content}</div>
                </div>
              );
            }

            const isLast = i === messages.length - 1;
            const items = groupBlocks(m.blocks, { busy, isLast });

            return (
              <div key={i} className="chat-msg chat-msg-assistant">
                <div className="chat-msg-assistant-body">
                  {isLast && busy && items.length === 0 && (
                    <div className="assistant-thinking">
                      <i className="fa-solid fa-spinner fa-spin" aria-hidden="true" /> 思考中…
                    </div>
                  )}
                  {items.map((it, k) => {
                    if (it.type === "text") {
                      return (
                        <div
                          key={k}
                          className="chat-markdown"
                          dangerouslySetInnerHTML={{ __html: md(it.text) }}
                        />
                      );
                    }
                    if (it.type === "reasoning") {
                      return <ReasoningBlock key={k} reasoning={it.reasoning} active={it.active} />;
                    }
                    return <ToolGroup key={k} tools={it.tools} />;
                  })}
                </div>
              </div>
            );
          })
        )}

        {artifacts.length > 0 && (
          <div className="chat-artifacts">
            <div className="chat-artifacts-title">
              <i className="fa-solid fa-box-open" aria-hidden="true" /> 产物
            </div>
            {artifacts.map((f) => {
              const isImage = /\.(png|jpe?g|gif|webp|svg)$/i.test(f.path);
              if (isImage) {
                return (
                  <figure key={f.path} className="chat-artifact-image">
                    <img src={artifactUrl(slug, f.path, conversationId)} alt={f.path} loading="lazy" />
                    <figcaption>
                      <a href={artifactUrl(slug, f.path, conversationId)} target="_blank" rel="noreferrer">
                        {f.path} · {(f.size / 1024).toFixed(1)} KB
                      </a>
                    </figcaption>
                  </figure>
                );
              }
              return (
                <a
                  key={f.path}
                  className="chat-artifact"
                  href={artifactUrl(slug, f.path, conversationId)}
                  target="_blank"
                  rel="noreferrer"
                >
                  <i className="fa-solid fa-file-lines" aria-hidden="true" />
                  <span>{f.path}</span>
                  <span className="chat-artifact-size">{(f.size / 1024).toFixed(1)} KB</span>
                </a>
              );
            })}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {error && (
        <div className="chat-error-row">
          <span className="chat-error-text">{error}</span>
          <button type="button" className="chat-retry" onClick={retry}>
            <i className="fa-solid fa-rotate-right" aria-hidden="true" /> 重试
          </button>
        </div>
      )}

      <footer className="chat-input">
        <textarea
          rows={1}
          value={input}
          placeholder="输入你的需求，回车发送…"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
          disabled={busy}
        />
        {busy ? (
          <button type="button" className="chat-stop" onClick={stop} title="停止生成" aria-label="停止生成">
            <i className="fa-solid fa-stop" aria-hidden="true" />
          </button>
        ) : (
          <button type="button" className="chat-send" onClick={() => send()} disabled={!input.trim()}>
            <i className="fa-solid fa-paper-plane" aria-hidden="true" />
          </button>
        )}
      </footer>
    </div>
  );
}