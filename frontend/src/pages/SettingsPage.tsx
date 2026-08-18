import { FormEvent, useEffect, useState } from "react";
import { api } from "../api";
import type { Settings } from "../types";

const empty: Settings = {
  asr_provider: "whisper",
  asr_model: "small",
  asr_api_key: "",
  asr_base_url: "",
  text_provider: "openai_compatible",
  text_model: "qwen-plus",
  text_api_key: "",
  text_base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
  vision_provider: "openai_compatible",
  vision_model: "qwen-vl-plus",
  vision_api_key: "",
  vision_base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
  use_same_key: true,
  presets: [],
};

export default function SettingsPage() {
  const [form, setForm] = useState<Settings>(empty);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    api.settings().then(setForm).catch((e) => setMsg(e.message));
  }, []);

  function applyPreset(id: string) {
    const p = form.presets?.find((x) => x.id === id);
    if (!p) return;
    setForm({
      ...form,
      text_base_url: p.text_base_url,
      text_model: p.text_model,
      vision_base_url: p.vision_base_url,
      vision_model: p.vision_model,
      text_provider: "openai_compatible",
      vision_provider: "openai_compatible",
    });
  }

  async function onSubmit(ev: FormEvent) {
    ev.preventDefault();
    setMsg("保存中…");
    try {
      const saved = await api.saveSettings(form);
      setForm(saved);
      setMsg("已保存到本机，不会上传到 git。");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "保存失败");
    }
  }

  return (
    <>
      <header className="topbar">
        <div>
          <h1>
            设置 <span className="sub">转写、看画面、写亮点可以配不同模型</span>
          </h1>
        </div>
      </header>
      <div className="page">
        <p className="hint">
          推荐先申请阿里云百炼（通义）的 API Key。转写默认用电脑本地 Whisper，不花云端额度；写亮点和看画面走你填的国内模型。
          原片文件留在本机，发给模型的只有文案和少量截图。
        </p>
        <div className="preset-row">
          {(form.presets || []).map((p) => (
            <button key={p.id} className="btn" type="button" onClick={() => applyPreset(p.id)} title={p.hint}>
              {p.label}
            </button>
          ))}
        </div>
        <form onSubmit={onSubmit}>
          <label className="check">
            <input
              type="checkbox"
              checked={form.use_same_key}
              onChange={(e) => setForm({ ...form, use_same_key: e.target.checked })}
            />
            看画面和写亮点用同一把 Key（最常见）
          </label>
          <div className="settings-grid">
            <section className="card" style={{ padding: 16 }}>
              <h3>写亮点（文本模型）</h3>
              <div className="field">
                <label>接口地址</label>
                <input
                  value={form.text_base_url}
                  onChange={(e) => setForm({ ...form, text_base_url: e.target.value })}
                />
              </div>
              <div className="field">
                <label>模型名</label>
                <input value={form.text_model} onChange={(e) => setForm({ ...form, text_model: e.target.value })} />
              </div>
              <div className="field">
                <label>API Key {form.text_api_key_set ? "（已保存，留空则不修改）" : ""}</label>
                <input
                  type="password"
                  value={form.text_api_key}
                  onChange={(e) => setForm({ ...form, text_api_key: e.target.value })}
                  placeholder={form.text_api_key_set ? "••••••" : "sk-..."}
                />
              </div>
            </section>
            <section className="card" style={{ padding: 16 }}>
              <h3>看画面（视觉模型）</h3>
              <div className="field">
                <label>接口地址</label>
                <input
                  value={form.vision_base_url}
                  onChange={(e) => setForm({ ...form, vision_base_url: e.target.value })}
                />
              </div>
              <div className="field">
                <label>模型名</label>
                <input
                  value={form.vision_model}
                  onChange={(e) => setForm({ ...form, vision_model: e.target.value })}
                />
              </div>
              {!form.use_same_key ? (
                <div className="field">
                  <label>API Key {form.vision_api_key_set ? "（已保存，留空则不修改）" : ""}</label>
                  <input
                    type="password"
                    value={form.vision_api_key}
                    onChange={(e) => setForm({ ...form, vision_api_key: e.target.value })}
                  />
                </div>
              ) : (
                <p className="hint">已勾选同一把 Key，这里不用再填。</p>
              )}
            </section>
            <section className="card" style={{ padding: 16 }}>
              <h3>转写（语音变文字）</h3>
              <div className="field">
                <label>方式</label>
                <select
                  value={form.asr_provider}
                  onChange={(e) => setForm({ ...form, asr_provider: e.target.value })}
                >
                  <option value="dashscope">通义转写（推荐，用已填的百炼 Key，不访问 HuggingFace）</option>
                  <option value="whisper">本地 Whisper（需能下载 HuggingFace 模型）</option>
                  <option value="openai_compatible">云端 OpenAI 兼容转写</option>
                </select>
              </div>
              <div className="field">
                <label>模型名</label>
                <input
                  value={form.asr_model}
                  onChange={(e) => setForm({ ...form, asr_model: e.target.value })}
                  placeholder="small / medium / large-v3"
                />
              </div>
              {form.asr_provider === "openai_compatible" ? (
                <>
                  <div className="field">
                    <label>接口地址</label>
                    <input
                      value={form.asr_base_url}
                      onChange={(e) => setForm({ ...form, asr_base_url: e.target.value })}
                    />
                  </div>
                  <div className="field">
                    <label>API Key {form.asr_api_key_set ? "（已保存，留空则不修改）" : ""}</label>
                    <input
                      type="password"
                      value={form.asr_api_key}
                      onChange={(e) => setForm({ ...form, asr_api_key: e.target.value })}
                    />
                  </div>
                </>
              ) : (
                <p className="hint">
                  第一次选本地 Whisper 会下载模型。若出现 403，说明访问 HuggingFace 被代理拦住，请改用「通义转写」。
                </p>
              )}
            </section>
          </div>
          <div className="actions" style={{ marginTop: 18 }}>
            <button className="btn primary">保存设置</button>
            {msg ? <span className="muted">{msg}</span> : null}
          </div>
        </form>
      </div>
    </>
  );
}
