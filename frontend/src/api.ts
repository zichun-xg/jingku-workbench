import type { Highlight, Job, Settings, Tag, VideoDetail, VideoItem } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      detail = await res.text();
    }
    throw new Error(typeof detail === "string" ? detail : "请求失败");
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  videos: () => request<VideoItem[]>("/api/videos"),
  video: (id: string) => request<VideoDetail>(`/api/videos/${id}`),
  upload: (file: File, title: string, genre: string) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("title", title);
    fd.append("genre", genre);
    return request<VideoItem>("/api/videos/upload", { method: "POST", body: fd });
  },
  fromUrl: (url: string, title: string, genre: string) =>
    request<{ video: VideoItem; job: Job }>("/api/videos/from-url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, title, genre }),
    }),
  patchVideo: (id: string, payload: Partial<VideoItem>) =>
    request<VideoItem>(`/api/videos/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  deleteVideo: (id: string) => request<{ ok: boolean }>(`/api/videos/${id}`, { method: "DELETE" }),
  analyze: (id: string) => request<Job>(`/api/videos/${id}/analyze`, { method: "POST" }),
  job: (videoId: string, jobId: string) => request<Job>(`/api/videos/${videoId}/jobs/${jobId}`),
  saveCue: (videoId: string, cueId: number, payload: object) =>
    request(`/api/videos/${videoId}/cues/${cueId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  saveSegment: (videoId: string, segmentId: number, payload: object) =>
    request(`/api/videos/${videoId}/segments/${segmentId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  saveHighlight: (videoId: string, highlightId: number, payload: object) =>
    request(`/api/videos/${videoId}/highlights/${highlightId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  highlights: (params: Record<string, string>) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v) q.set(k, v);
    });
    const qs = q.toString();
    return request<Highlight[]>(`/api/highlights${qs ? `?${qs}` : ""}`);
  },
  tags: () => request<Tag[]>("/api/tags"),
  settings: () => request<Settings>("/api/settings"),
  saveSettings: (payload: Settings) =>
    request<Settings>("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
};

export const GENRE_LABEL: Record<string, string> = {
  b2b_demo: "产品演示",
  corp_promo: "企业宣传片",
  other: "其他成片",
};

export const STATUS_LABEL: Record<string, string> = {
  downloading: "下载中",
  ready: "待拉片",
  analyzing: "分析中",
  analyzed: "已拉片",
  error: "出错",
};

export function formatTc(ms: number): string {
  const t = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(t / 3600);
  const m = Math.floor((t % 3600) / 60);
  const s = t % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export function formatDuration(ms: number): string {
  if (!ms) return "--";
  const t = Math.floor(ms / 1000);
  const m = Math.floor(t / 60);
  const s = t % 60;
  return `${m}′${String(s).padStart(2, "0")}″`;
}
