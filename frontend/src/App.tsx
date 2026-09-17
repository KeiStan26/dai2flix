import React, { useState } from 'react';
import { Navbar } from './components/Navbar';
import { Billboard } from './components/Billboard';
import { Row } from './components/Row';
import { PlayerModal } from './components/PlayerModal';
import { useFeed } from './hooks/useFeed';
import { useWatchHistory } from './hooks/useWatchHistory';
import { VideoItem } from './types';
import { AlertCircle, Film, RefreshCw } from 'lucide-react';

export const App: React.FC = () => {
  const { data, loading, error, refetch } = useFeed();
  const { historyRow, addToHistory } = useWatchHistory();

  const [selectedVideo, setSelectedVideo] = useState<VideoItem | null>(null);
  const [isPlayerOpen, setIsPlayerOpen] = useState<boolean>(false);

  const handleOpenVideo = (video: VideoItem) => {
    setSelectedVideo(video);
    setIsPlayerOpen(true);
  };

  const handleClosePlayer = () => {
    setIsPlayerOpen(false);
  };

  return (
    <div className="min-h-screen bg-[#141414] text-white flex flex-col font-sans selection:bg-netflix-red selection:text-white">
      {/* Top Floating Navbar */}
      <Navbar
        onHistoryClick={() => {
          const el = document.getElementById('row_watch_history');
          if (el) {
            el.scrollIntoView({ behavior: 'smooth' });
          }
        }}
      />

      {/* Main Content Area */}
      <main className="flex-1 pb-16">
        {/* Loading State */}
        {loading && !data && (
          <div className="h-screen w-full flex flex-col items-center justify-center space-y-4 bg-[#141414]">
            <div className="w-12 h-12 border-4 border-netflix-red border-t-transparent rounded-full animate-spin" />
            <p className="text-zinc-400 font-semibold tracking-wider animate-pulse">
              DAINI FLIX を読み込み中...
            </p>
          </div>
        )}

        {/* Error State */}
        {error && !data && (
          <div className="h-screen w-full flex flex-col items-center justify-center px-4 text-center bg-[#141414]">
            <AlertCircle className="w-16 h-16 text-netflix-red mb-4 animate-bounce" />
            <h2 className="text-2xl font-black mb-2">動画フィードの取得に失敗しました</h2>
            <p className="text-zinc-400 max-w-md mb-6">{error}</p>
            <button
              onClick={() => refetch()}
              className="flex items-center space-x-2 bg-netflix-red hover:bg-netflix-darkRed text-white px-6 py-2.5 rounded-md font-bold transition-transform hover:scale-105 shadow-lg"
            >
              <RefreshCw className="w-4 h-4" />
              <span>再試行する</span>
            </button>
          </div>
        )}

        {/* Loaded Content */}
        {data && (
          <>
            {/* 1. Hero Billboard Banner */}
            <Billboard
              video={data.billboard}
              onPlay={handleOpenVideo}
              onDetail={handleOpenVideo}
            />

            {/* Negative margin container for Netflix row overlap on billboard bottom */}
            <div className="-mt-16 sm:-mt-24 md:-mt-32 relative z-20 space-y-6">
              {/* 2. Dynamically Injected Watch History Row (Highest Priority) */}
              {historyRow && (
                <div id="row_watch_history" className="animate-fadeIn">
                  <Row row={historyRow} onSelectVideo={handleOpenVideo} />
                </div>
              )}

              {/* 3. Server Aggregated Rows (Playlists, Mood Tags, Recents) */}
              {data.rows.map((row) => (
                <Row key={row.id} row={row} onSelectVideo={handleOpenVideo} />
              ))}
            </div>
          </>
        )}
      </main>

      {/* Video Playback Modal with YouTube IFrame */}
      <PlayerModal
        video={selectedVideo}
        isOpen={isPlayerOpen}
        onClose={handleClosePlayer}
        onStartWatch={addToHistory}
      />

      {/* Footer */}
      <footer className="border-t border-white/10 bg-black/60 py-12 px-4 md:px-12 text-zinc-500 text-xs text-center space-y-3">
        <div className="flex items-center justify-center space-x-2 text-zinc-400 font-bold">
          <Film className="w-4 h-4 text-netflix-red" />
          <span>DAINI FLIX - だいにぐるーぷ非公式ファンメイドVOD</span>
        </div>
        <p className="max-w-2xl mx-auto leading-relaxed">
          本サービスはYouTubeクリエイター「だいにぐるーぷ」様のファンメイド・アーカイブビューアーです。
          動画および著作権はすべて「だいにぐるーぷ」様およびYouTube公式に帰属します。動画再生はYouTube公式埋め込みプレイヤーにより提供されます。
        </p>
        <p className="text-[11px] text-zinc-600">
          Powered by FastAPI, SQLite (WAL), React, Tailwind CSS, Google Gemini API & YouTube Data API v3
        </p>
      </footer>
    </div>
  );
};
