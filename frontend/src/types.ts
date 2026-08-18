export type Genre = "b2b_demo" | "corp_promo" | "other";

export type VideoStatus = "downloading" | "ready" | "analyzing" | "analyzed" | "error";

export interface Tag {
  id: number;
  name: string;
  category: string;
}

export interface Frame {
  id: number;
  segment_id: number | null;
  timestamp_ms: number;
  file_path: string;
  caption: string;
  is_reference: boolean;
  url: string;
}

export interface Highlight {
  id: number;
  video_id: string;
  segment_id: number | null;
  title: string;
  copy_advice: string;
  visual_advice: string;
  audience: string;
  in_library: boolean;
  tags: Tag[];
  video_title: string;
  genre: string;
  start_ms: number;
  end_ms: number;
  time_label: string;
  reference_frames: Frame[];
}

export interface Cue {
  id: number;
  start_ms: number;
  end_ms: number;
  text: string;
  sort_order: number;
}

export interface Segment {
  id: number;
  start_ms: number;
  end_ms: number;
  topic: string;
  points: string[];
  technique: string;
  sort_order: number;
  frames: Frame[];
  highlight: Highlight | null;
}

export interface Job {
  id: string;
  video_id: string;
  job_type: string;
  status: string;
  step: string;
  progress: number;
  message: string;
  error: string;
}

export interface VideoItem {
  id: string;
  title: string;
  source_type: string;
  source_url: string;
  genre: Genre | string;
  duration_ms: number;
  status: VideoStatus | string;
  error_message: string;
  thumb_url: string;
  created_at: string;
  highlight_count: number;
}

export interface VideoDetail extends VideoItem {
  file_url: string;
  cues: Cue[];
  segments: Segment[];
  latest_job: Job | null;
}

export interface Settings {
  asr_provider: string;
  asr_model: string;
  asr_api_key: string;
  asr_base_url: string;
  asr_api_key_set?: boolean;
  text_provider: string;
  text_model: string;
  text_api_key: string;
  text_base_url: string;
  text_api_key_set?: boolean;
  vision_provider: string;
  vision_model: string;
  vision_api_key: string;
  vision_base_url: string;
  vision_api_key_set?: boolean;
  use_same_key: boolean;
  presets?: Array<{
    id: string;
    label: string;
    hint: string;
    text_base_url: string;
    text_model: string;
    vision_base_url: string;
    vision_model: string;
  }>;
}
