/**
 * Frontend TypeScript type definitions matching backend schemas.
 */

export interface VideoItem {
  id: string;
  title: string;
  description?: string | null;
  published_at: string;
  thumbnail_url?: string | null;
  duration_seconds?: number | null;
  view_count?: number | null;
  catchphrase?: string | null;
  synopsis?: string | null;
  mood_tags: string[];
}

export type RowType = 'playlist' | 'tag' | 'featured' | 'recent';

export interface RowItem {
  id: string;
  title: string;
  type: RowType;
  items: VideoItem[];
  total_items: number;
}

export interface FeedResponse {
  billboard: VideoItem | null;
  rows: RowItem[];
  generated_at: string;
}

export interface WatchHistoryItem {
  video: VideoItem;
  watchedAt: number; // epoch timestamp
}
