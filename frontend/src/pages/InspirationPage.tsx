import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { GENRE_LABEL, api } from "../api";
import type { Highlight, Tag } from "../types";

export default function InspirationPage() {
  const nav = useNavigate();
  const [items, setItems] = useState<Highlight[]>([]);
  const [tags, setTags] = useState<Tag[]>([]);
  const [tag, setTag] = useState("");
  const [genre, setGenre] = useState("");
  const [audience, setAudience] = useState("");
  const [q, setQ] = useState("");

  async function load() {
    const [list, tagRows] = await Promise.all([
      api.highlights({ tag, genre, audience, q }),
      api.tags(),
    ]);
    setItems(list);
    setTags(tagRows);
  }

  useEffect(() => {
    load().catch(() => setItems([]));
  }, [tag, genre, audience]);

  return (
    <>
      <header className="topbar">
        <div>
          <h1>
            灵感库 <span className="sub">按标签筛优秀成片的写法、画面和分镜逻辑</span>
          </h1>
        </div>
      </header>
      <div className="page">
        <div className="insp-filters">
          <input
            placeholder="搜索文案 / 标题 / 受众"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") load();
            }}
          />
          <select value={genre} onChange={(e) => setGenre(e.target.value)}>
            <option value="">全部片种</option>
            <option value="b2b_demo">产品演示</option>
            <option value="corp_promo">企业宣传片</option>
            <option value="other">其他成片</option>
          </select>
          <select value={tag} onChange={(e) => setTag(e.target.value)}>
            <option value="">全部标签</option>
            {tags.map((t) => (
              <option key={t.id} value={t.name}>
                {t.name}
              </option>
            ))}
          </select>
          <input placeholder="受众，如 行业决策人" value={audience} onChange={(e) => setAudience(e.target.value)} />
          <button className="btn" onClick={load}>
            筛选
          </button>
        </div>
        {items.length === 0 ? (
          <div className="empty">还没有入库的亮点。先去片库导入视频，在拉片台勾选「收入灵感库」。</div>
        ) : (
          <div className="grid-cards">
            {items.map((h) => (
              <article className="card insp-card" key={h.id}>
                {h.reference_frames[0] ? (
                  <div className="thumb">
                    <img src={h.reference_frames[0].url} alt="" />
                  </div>
                ) : null}
                <div className="body">
                  <div className="row-meta">
                    <span className="pill">{GENRE_LABEL[h.genre] || h.genre}</span>
                    <span className="pill">{h.time_label}</span>
                    {h.audience ? <span className="pill">{h.audience}</span> : null}
                  </div>
                  <h3 style={{ marginTop: 10 }}>{h.title}</h3>
                  <p className="muted">
                    《{h.video_title}》 · {h.time_label}
                  </p>
                  <p className="quote">{h.copy_advice}</p>
                  <p className="muted">{h.visual_advice}</p>
                  <div className="tags" style={{ marginTop: 10 }}>
                    {h.tags.map((t) => (
                      <span className="tag" key={t.id}>
                        {t.name}
                      </span>
                    ))}
                  </div>
                  <div className="actions" style={{ marginTop: 12 }}>
                    <button
                      className="btn primary"
                      onClick={() => nav(`/bench/${h.video_id}?t=${h.start_ms}`)}
                    >
                      回到原片这段
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </div>
    </>
  );
}
