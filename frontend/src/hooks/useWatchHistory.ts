import { useState, useEffect, useCallback } from 'react';
import { VideoItem, RowItem } from '../types';

const STORAGE_KEY = 'dai2flix_watch_history_v1';
const MAX_HISTORY_ITEMS = 20;

export function useWatchHistory() {
  const [history, setHistory] = useState<VideoItem[]>([]);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed: VideoItem[] = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          setHistory(parsed);
        }
      }
    } catch (e) {
      console.warn('Failed to parse watch history from localStorage:', e);
    }
  }, []);

  // Add or bump a video to top of history
  const addToHistory = useCallback((video: VideoItem) => {
    setHistory((prev) => {
      // Remove if existing
      const filtered = prev.filter((item) => item.id !== video.id);
      const updated = [video, ...filtered].slice(0, MAX_HISTORY_ITEMS);

      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      } catch (e) {
        console.warn('Failed to persist watch history:', e);
      }

      return updated;
    });
  }, []);

  // Remove single video from history
  const removeFromHistory = useCallback((videoId: string) => {
    setHistory((prev) => {
      const updated = prev.filter((item) => item.id !== videoId);
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
      } catch (e) {
        console.warn('Failed to persist watch history after removal:', e);
      }
      return updated;
    });
  }, []);

  // Clear all history
  const clearHistory = useCallback(() => {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (e) {
      console.warn('Failed to clear watch history:', e);
    }
    setHistory([]);
  }, []);

  // Dynamically generate a RowItem when history exists
  const historyRow: RowItem | null =
    history.length > 0
      ? {
          id: 'row_watch_history',
          title: '最近観た作品（もう一度観る）',
          type: 'recent',
          items: history,
          total_items: history.length,
        }
      : null;

  return {
    history,
    historyRow,
    addToHistory,
    removeFromHistory,
    clearHistory,
  };
}
