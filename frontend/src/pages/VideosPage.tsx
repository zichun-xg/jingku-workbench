import { FormEvent, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { GENRE_LABEL, STATUS_LABEL, api, formatDuration } from "../api";
import type { VideoItem } from "../types";

export default function VideosPage() {
  const nav = useNavigate();
  const [items, setItems] = useState<VideoItem[]>([]);
  const [err, setErr] = useState("");
  const [hot, setHot] = useState(false);
  const [showUrl, setShowUrl] = useState(false);
  const [genre, setGenre] = useState("b2b_demo");
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setItems(await api.videos());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "加载失败");
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);

  async function onFiles(files: FileList | null) {
    if (!files?.length) return;
    setBusy(true);
    setErr("");
    try {
      for (const file of Array.from(files)) {
        await api.upload(file, title || file.name.replace(/\.[^.]+$/, ""), genre);
      }
      setTitle("");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "导入失败");
    } finally {
      setBusy(false);
    }
  }

  async function submitUrl(ev: FormEvent) {
    ev.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const res = await api.fromUrl(url, title, genre);
      setShowUrl(false);
      setUrl("");
      setTitle("");
      await load();
      nav(`/bench/${res.video.id}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "下载失败");
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    if (!confirm("确定从片库删除这条视频？本地文件也会一起删掉。")) return;
    await api.deleteVideo(id);
    await load();
  }

  return (
    <>
      <header className="topbar">
        <div>
          <h1>
            片库 <span className="sub">把优秀成片收进来，再送去拉片</span>
          </h1>
        </div>
        <div className="actions">
          <select value={genre} onChange={(e) => setGenre(e.target.value)}>
            <option value="b2b_demo">产品演示</option>
            <option value="corp_promo">企业宣传片</option>
            <option value="other">其他成片</option>
          </select>
          <button className="btn ghost" onClick={() => setShowUrl(true)}>
            从链接导入
          </button>
          <label className="btn primary">
            导入本地文件
            <input
              type="file"
              accept="video/*"
              multiple
              hidden
              onChange={(e) => onFiles(e.target.files)}
            />
          </label>
        </div>
      </header>
      <div className="page">
        {err ? <div className="job-banner err">{err}</div> : null}
        <div
          className={`drop ${hot ? "hot" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setHot(true);
          }}
          onDragLeave={() => setHot(false)}
          onDrop={(e) => {
            e.preventDefault();
            setHot(false);
            onFiles(e.dataTransfer.files);
          }}
        >
          {busy ? "正在处理…" : "把视频拖到这里，或点右上角导入。片种用右上角下拉框先选好。"}
        </div>
        {items.length === 0 ? (
          <div className="empty">片库还是空的。先丢进一条你觉得拍得好的视频。</div>
        ) : (
          <div className="grid-cards">
            {items.map((v) => (
              <article className="card" key={v.id}>
                <div className="thumb" onClick={() => nav(`/bench/${v.id}`)} style={{ cursor: "pointer" }}>
                  {v.thumb_url ? <img src={v.thumb_url} alt="" /> : null}
                </div>
                <div className="meta">
                  <h3>{v.title}</h3>
                  <div className="row-meta">
                    <span className="pill">{GENRE_LABEL[v.genre] || v.genre}</span>
                    <span className={`pill ${v.status === "error" ? "err" : v.status === "analyzed" ? "ok" : "warn"}`}>
                      {STATUS_LABEL[v.status] || v.status}
                    </span>
                    <span>{formatDuration(v.duration_ms)}</span>
                    <span>{v.highlight_count} 条亮点</span>
                  </div>
                  {v.error_message ? <p className="hint">{v.error_message}</p> : null}
                  <div className="actions" style={{ marginTop: 12 }}>
                    <button className="btn primary" onClick={() => nav(`/bench/${v.id}`)}>
                      打开拉片台
                    </button>
                    <button className="btn ghost" onClick={() => remove(v.id)}>
                      删除
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
      {showUrl ? (
        <div className="modal-back" onClick={() => setShowUrl(false)}>
          <form className="modal" onClick={(e) => e.stopPropagation()} onSubmit={submitUrl}>
            <h2>从公开链接导入</h2>
            <p className="hint">支持 B 站、直链 MP4 等公开页面。网盘请先自己下载再导入本地文件。</p>
            <div className="field">
              <label>链接</label>
              <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" required />
            </div>
            <div className="field">
              <label>标题（可空，下载后也能改）</label>
              <input value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="actions">
              <button className="btn ghost" type="button" onClick={() => setShowUrl(false)}>
                取消
              </button>
              <button className="btn primary" disabled={busy}>
                开始下载
              </button>
            </div>
          </form>
        </div>
      ) : null}
    </>
  );
}
