import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { GENRE_LABEL, api, formatTc } from "../api";
import type { Highlight, Job, Segment, VideoDetail } from "../types";

function pickSegment(segments: Segment[], tms: number): Segment | null {
  if (!segments.length) return null;
  return segments.find((s) => tms >= s.start_ms && tms < s.end_ms) || segments[0];
}

export default function BenchPage() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const jumpMs = Number(params.get("t") || 0);
  const videoRef = useRef<HTMLVideoElement>(null);
  const [data, setData] = useState<VideoDetail | null>(null);
  const [err, setErr] = useState("");
  const [tms, setTms] = useState(0);
  const [job, setJob] = useState<Job | null>(null);
  const [saving, setSaving] = useState("");
  const [topic, setTopic] = useState("");
  const [pointsText, setPointsText] = useState("");
  const [technique, setTechnique] = useState("");
  const [hl, setHl] = useState<Partial<Highlight>>({});
  const [tagText, setTagText] = useState("");

  async function load() {
    if (!id) return;
    const v = await api.video(id);
    setData(v);
    if (v.latest_job && (v.latest_job.status === "queued" || v.latest_job.status === "running")) {
      setJob(v.latest_job);
    } else if (v.status === "downloading" && v.latest_job) {
      setJob(v.latest_job);
    }
    return v;
  }

  useEffect(() => {
    load().catch((e) => setErr(e.message));
  }, [id]);

  useEffect(() => {
    if (!jumpMs || !videoRef.current || !data?.file_url) return;
    videoRef.current.currentTime = jumpMs / 1000;
    setTms(jumpMs);
  }, [data?.file_url, jumpMs]);

  useEffect(() => {
    if (!id || !job || (job.status !== "queued" && job.status !== "running")) return;
    const timer = setInterval(async () => {
      try {
        const j = await api.job(id, job.id);
        setJob(j);
        if (j.status === "done" || j.status === "error") {
          await load();
        }
      } catch {
        /* 轮询失败时下一轮再试 */
      }
    }, 1200);
    return () => clearInterval(timer);
  }, [id, job?.id, job?.status]);

  const seg = useMemo(() => pickSegment(data?.segments || [], tms), [data, tms]);

  useEffect(() => {
    if (!seg) return;
    setTopic(seg.topic);
    setPointsText((seg.points || []).join("\n"));
    setTechnique(seg.technique);
    const h = seg.highlight;
    setHl({
      title: h?.title || "",
      copy_advice: h?.copy_advice || "",
      visual_advice: h?.visual_advice || "",
      audience: h?.audience || "",
      in_library: h?.in_library ?? true,
    });
    setTagText((h?.tags || []).map((t) => t.name).join("，"));
  }, [seg?.id]);

  async function startAnalyze() {
    if (!id) return;
    setErr("");
    try {
      const j = await api.analyze(id);
      setJob(j);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "无法开始拉片");
    }
  }

  function seek(ms: number) {
    const el = videoRef.current;
    if (!el) return;
    el.currentTime = ms / 1000;
    setTms(ms);
  }

  async function saveAll() {
    if (!id || !seg) return;
    setSaving("保存中…");
    try {
      await api.saveSegment(id, seg.id, {
        topic,
        technique,
        points: pointsText
          .split(/\n+/)
          .map((s) => s.replace(/^\d+[\.、．]\s*/, "").trim())
          .filter(Boolean),
      });
      if (seg.highlight) {
        await api.saveHighlight(id, seg.highlight.id, {
          ...hl,
          tags: tagText
            .split(/[,，、]/)
            .map((s) => s.trim())
            .filter(Boolean),
        });
      }
      setSaving("已保存");
      await load();
      setTimeout(() => setSaving(""), 1500);
    } catch (e) {
      setSaving(e instanceof Error ? e.message : "保存失败");
    }
  }

  const pct = data?.duration_ms ? Math.min(100, (tms / data.duration_ms) * 100) : 0;
  const activeCueId = (data?.cues || []).find((c) => tms >= c.start_ms && tms < c.end_ms)?.id;

  return (
    <>
      <header className="topbar">
        <div>
          <h1>
            拉片台 <span className="sub">{data?.title || "加载中…"}</span>
          </h1>
        </div>
        <div className="actions">
          <Link className="btn ghost" to="/">
            回片库
          </Link>
          <button className="btn primary" onClick={startAnalyze} disabled={!data || data.status === "downloading"}>
            {data?.segments?.length ? "重新生成草稿" : "开始 AI 拉片"}
          </button>
          <button className="btn" onClick={saveAll} disabled={!seg}>
            保存本段
          </button>
          {saving ? <span className="muted">{saving}</span> : null}
        </div>
      </header>
      <div className="page" style={{ paddingTop: 12 }}>
        {err ? <div className="job-banner err">{err}</div> : null}
        {job && job.status !== "done" ? (
          <div className="job-banner">
            <span>
              {job.status === "error" ? <b className="err">{job.error || job.message}</b> : job.message || "处理中…"}
              <span className="muted"> · {job.progress}%</span>
            </span>
            <span className="muted">{job.step}</span>
          </div>
        ) : null}
        {!data ? (
          <div className="empty">正在打开片子…</div>
        ) : (
          <div className="bench">
            <div className="player">
              {data.file_url ? (
                <video
                  ref={videoRef}
                  src={data.file_url}
                  controls
                  onTimeUpdate={(e) => setTms((e.target as HTMLVideoElement).currentTime * 1000)}
                />
              ) : (
                <div className="empty">视频还在下载或文件不可用</div>
              )}
            </div>
            <aside className="side">
              <div className="row-meta" style={{ marginBottom: 10 }}>
                <span className="pill">{GENRE_LABEL[data.genre] || data.genre}</span>
                <span className="pill">
                  {seg ? `${formatTc(seg.start_ms)}-${formatTc(seg.end_ms)}` : "尚未分段"}
                </span>
              </div>
              <div className="field">
                <label>这一段在讲什么</label>
                <input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="例如：政府穿透式监管的困境" />
              </div>
              <div className="field">
                <label>要点 1 / 2 / 3（每行一条）</label>
                <textarea value={pointsText} onChange={(e) => setPointsText(e.target.value)} />
              </div>
              <div className="field">
                <label>制作手法</label>
                <textarea value={technique} onChange={(e) => setTechnique(e.target.value)} placeholder="字幕、镜头、节奏、信息层级…" />
              </div>
            </aside>
            <div className="progress-bar" onClick={(e) => {
              if (!data.duration_ms) return;
              const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
              seek(((e.clientX - rect.left) / rect.width) * data.duration_ms);
            }}>
              <i style={{ width: `${pct}%` }} />
            </div>
            <div className="script">
              {(data.cues || []).length === 0 ? (
                <div className="empty">还没有逐字稿。点右上角「开始 AI 拉片」。 </div>
              ) : (
                data.cues.map((c) => (
                  <div
                    key={c.id}
                    className={`cue ${activeCueId === c.id ? "on" : ""}`}
                    onClick={() => seek(c.start_ms)}
                  >
                    <div className="tc">{formatTc(c.start_ms)}</div>
                    <p>{c.text}</p>
                  </div>
                ))
              )}
            </div>
            <div className="frames">
              <div className="row-meta" style={{ marginBottom: 8 }}>
                <span>对应画面帧</span>
              </div>
              <div className="frame-grid">
                {(seg?.frames || []).map((f) => (
                  <figure className="frame-item" key={f.id} onClick={() => seek(f.timestamp_ms)} style={{ cursor: "pointer" }}>
                    <img src={f.url} alt="" />
                    <figcaption>
                      {formatTc(f.timestamp_ms)} {f.is_reference ? "· 参考图" : ""}
                      {f.caption ? ` · ${f.caption}` : ""}
                    </figcaption>
                  </figure>
                ))}
              </div>
              {!seg?.frames?.length ? <p className="muted">拉片完成后，这里会列出本段关键帧。</p> : null}
            </div>
            <section className="highlight-card">
              <header>
                <strong>
                  {data.title} 的本段内容（{seg ? `${formatTc(seg.start_ms)}-${formatTc(seg.end_ms)}` : "--"}）
                </strong>
                <label className="check">
                  <input
                    type="checkbox"
                    checked={Boolean(hl.in_library)}
                    onChange={(e) => setHl({ ...hl, in_library: e.target.checked })}
                  />
                  收入灵感库
                </label>
              </header>
              {!seg?.highlight ? (
                <p className="muted">生成草稿后，这里会出现可改的亮点卡。</p>
              ) : (
                <div className="hl-grid">
                  <div className="field" style={{ gridColumn: "1 / -1" }}>
                    <label>亮点标题</label>
                    <input value={hl.title || ""} onChange={(e) => setHl({ ...hl, title: e.target.value })} />
                  </div>
                  <div className="field">
                    <label>文案上可以怎样写（抓住谁的痛点）</label>
                    <textarea
                      value={hl.copy_advice || ""}
                      onChange={(e) => setHl({ ...hl, copy_advice: e.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label>画面上建议展示什么</label>
                    <textarea
                      value={hl.visual_advice || ""}
                      onChange={(e) => setHl({ ...hl, visual_advice: e.target.value })}
                    />
                    <div className="field" style={{ marginTop: 8 }}>
                      <label>受众</label>
                      <input
                        value={hl.audience || ""}
                        onChange={(e) => setHl({ ...hl, audience: e.target.value })}
                        placeholder="如：国企分管领导"
                      />
                    </div>
                    <div className="field">
                      <label>标签（用逗号分隔）</label>
                      <input value={tagText} onChange={(e) => setTagText(e.target.value)} placeholder="痛点开场，数据金句" />
                    </div>
                  </div>
                  <div>
                    <label className="muted">参考图</label>
                    {(seg.frames || [])
                      .filter((f) => f.is_reference)
                      .concat((seg.frames || []).filter((f) => !f.is_reference).slice(0, 2))
                      .slice(0, 3)
                      .map((f) => (
                        <img key={f.id} src={f.url} alt="" style={{ marginTop: 8, border: "1px solid var(--line)" }} />
                      ))}
                  </div>
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </>
  );
}
