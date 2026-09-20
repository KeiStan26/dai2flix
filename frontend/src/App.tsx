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
        {/* Loading Skeleton State */}
        {loading && !data && (
          <div className="w-full space-y-6 sm:space-y-8 animate-fadeIn">
            {/* Billboard Skeleton */}
            <div className="relative min-h-[500px] h-[72vh] sm:h-[80vh] md:h-[85vh] w-full bg-[#181818] animate-shimmer overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-t from-[#141414] via-[#141414]/50 to-transparent" />
              <div className="absolute bottom-[10%] sm:bottom-[15%] left-3 sm:left-6 md:left-12 space-y-3 max-w-xl">
                <div className="w-28 h-5 bg-white/10 rounded" />
                <div className="w-48 h-4 bg-white/10 rounded" />
                <div className="w-full sm:w-96 h-8 sm:h-12 bg-white/10 rounded" />
                <div className="w-4/5 h-4 bg-white/10 rounded" />
                <div className="flex space-x-3 pt-2">
                  <div className="w-24 sm:w-32 h-10 bg-white/20 rounded-md" />
                  <div className="w-24 sm:w-32 h-10 bg-white/10 rounded-md" />
                </div>
              </div>
            </div>

            {/* Row Skeletons */}
            <div className="-mt-12 sm:-mt-20 md:-mt-28 relative z-20 space-y-6 sm:space-y-8 px-3 sm:px-6 md:px-12">
              {[1, 2, 3].map((idx) => (
                <div key={idx} className="space-y-3">
                  <div className="w-36 sm:w-48 h-5 bg-white/10 rounded" />
                  <div className="flex space-x-3 overflow-hidden">
                    {[1, 2, 3, 4, 5].map((cardIdx) => (
                      <div
                        key={cardIdx}
                        className="flex-shrink-0 w-[200px] sm:w-[250px] md:w-[280px] aspect-video bg-[#1e1e1e] rounded-md animate-shimmer border border-white/5"
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Error State */}
        {error && !data && (
          <div className="h-screen w-full flex flex-col items-center justify-center px-4 text-center bg-[#141414]">
            <AlertCircle className="w-16 h-16 text-netflix-red mb-4 animate-bounce" />
            <h2 className="text-xl sm:text-2xl font-black mb-2">動画フィードの取得に失敗しました</h2>
            <p className="text-zinc-400 max-w-md text-sm mb-6">{error}</p>
            <button
              onClick={() => refetch()}
              className="flex items-center space-x-2 bg-netflix-red hover:bg-netflix-darkRed active:scale-95 text-white px-6 py-2.5 rounded-md font-bold transition-transform shadow-lg cursor-pointer"
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
            <div className="-mt-12 sm:-mt-20 md:-mt-28 relative z-20 space-y-4 sm:space-y-6">
              {/* 2. Dynamically Injected Watch History Row (Highest Priority) */}
              {historyRow && (
                <div id="row_watch_history" className="animate-fadeIn">
                  <Row row={historyRow} onSelectVideo={handleOpenVideo} />
                </div>
              )}

              {/* 3. Server Aggregated Rows (Playlists, Mood Tags, Recents) */}
              {data.rows.map((row, idx) => {
                const isFirstPlaylist =
                  row.type === 'playlist' &&
                  (idx === 0 || data.rows[idx - 1].type !== 'playlist');

                const isFirstTag =
                  row.type === 'tag' &&
                  (idx === 0 || data.rows[idx - 1].type !== 'tag');

                const isFirstMembership =
                  row.type === 'membership' &&
                  (idx === 0 || data.rows[idx - 1].type !== 'membership');

                return (
                  <React.Fragment key={row.id}>
                    {isFirstMembership && <div id="row_membership" className="scroll-mt-24 sm:scroll-mt-28" />}
                    {isFirstPlaylist && <div id="playlists" className="scroll-mt-24 sm:scroll-mt-28" />}
                    {isFirstTag && <div id="ai-categories" className="scroll-mt-24 sm:scroll-mt-28" />}
                    <Row row={row} onSelectVideo={handleOpenVideo} />
                  </React.Fragment>
                );
              })}
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
          <span>DAI2FLIX - だいにぐるーぷ非公式ファンメイドVOD</span>
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
