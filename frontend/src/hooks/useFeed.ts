import { useState, useEffect, useCallback } from 'react';
import { FeedResponse } from '../types';

export function useFeed() {
  const [data, setData] = useState<FeedResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchFeed = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch('/api/v1/feed?limit_per_row=25');

      if (!res.ok) {
        throw new Error(`サーバーからデータを取得できませんでした (HTTP ${res.status})`);
      }

      const feedData: FeedResponse = await res.json();
      setData(feedData);
    } catch (err: unknown) {
      console.error('Failed to fetch feed:', err);
      setError(err instanceof Error ? err.message : '予期せぬエラーが発生しました');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFeed();
  }, [fetchFeed]);

  return { data, loading, error, refetch: fetchFeed };
}
