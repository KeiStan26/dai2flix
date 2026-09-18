import React from 'react';
import { Play, Info, Sparkles, Flame } from 'lucide-react';
import { VideoItem } from '../types';

interface BillboardProps {
  video: VideoItem | null;
  onPlay: (video: VideoItem) => void;
  onDetail: (video: VideoItem) => void;
}

export const Billboard: React.FC<BillboardProps> = ({ video, onPlay, onDetail }) => {
  if (!video) {
    return (
      <div className="relative h-[65vh] md:h-[80vh] w-full bg-gradient-to-b from-zinc-900 to-[#141414] flex items-center justify-center">
        <div className="text-center text-zinc-500">
          <p className="text-lg font-semibold">現在動画データを読み込み中...</p>
        </div>
      </div>
    );
  }

  // Choose best image
  const bgImage = video.thumbnail_url || `https://i.ytimg.com/vi/${video.id}/maxresdefault.jpg`;

  return (
    <div id="feed-top" className="relative min-h-[500px] h-[72vh] sm:h-[80vh] md:h-[85vh] w-full overflow-hidden select-none">
      {/* Background Image Banner */}
      <img
        src={bgImage}
        alt={video.title}
        className="absolute inset-0 w-full h-full object-cover object-center filter brightness-90 transform scale-105 transition-transform duration-1000"
      />

      {/* Netflix Vignette Gradients */}
      {/* Bottom fade into black page background */}
      <div className="absolute inset-0 bg-gradient-to-t from-[#141414] via-[#141414]/50 to-transparent" />
      {/* Left to right dark gradient for text readability */}
      <div className="absolute inset-0 bg-gradient-to-r from-black/95 via-black/70 to-transparent w-full md:w-3/4" />
      {/* Top subtle fade for navbar */}
      <div className="absolute top-0 inset-x-0 h-28 sm:h-36 bg-gradient-to-b from-black/85 to-transparent" />

      {/* Content Container */}
      <div className="absolute bottom-[10%] sm:bottom-[15%] md:bottom-[18%] left-3 sm:left-6 md:left-12 right-3 sm:right-6 md:right-auto max-w-xl lg:max-w-3xl space-y-2.5 sm:space-y-4 z-10">
        {/* Series Banner Badge */}
        <div className="flex items-center space-x-2">
          <span className="flex items-center space-x-1 text-[10px] sm:text-xs font-black uppercase tracking-wider bg-netflix-red text-white px-2 py-0.5 rounded shadow">
            <Flame className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
            <span>注目の大型企画</span>
          </span>
          {video.mood_tags && video.mood_tags.length > 0 && (
            <span className="text-[10px] sm:text-xs font-semibold text-zinc-300 bg-white/10 backdrop-blur-md px-2 py-0.5 rounded border border-white/10">
              {video.mood_tags[0]}
            </span>
          )}
        </div>

        {/* AI Catchphrase */}
        {video.catchphrase && (
          <div className="flex items-center space-x-1.5 text-netflix-red font-black text-xs sm:text-base md:text-lg tracking-wide drop-shadow-md">
            <Sparkles className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-netflix-red flex-shrink-0 animate-pulse" />
            <span className="line-clamp-1">{video.catchphrase}</span>
          </div>
        )}

        {/* Title */}
        <h1 className="text-xl sm:text-3xl md:text-5xl lg:text-6xl font-black text-white leading-tight tracking-tight drop-shadow-lg line-clamp-2 sm:line-clamp-3">
          {video.title}
        </h1>

        {/* Synopsis / Description Teaser */}
        <p className="text-xs sm:text-sm md:text-base text-zinc-200 line-clamp-2 sm:line-clamp-3 leading-relaxed drop-shadow max-w-xl">
          {video.synopsis || video.description || 'だいにぐるーぷによる究極の大型エンターテインメント。予測不能な心理戦と極限サバイバルが今、幕を開ける。'}
        </p>

        {/* Action Buttons */}
        <div className="flex items-center space-x-2.5 sm:space-x-3 pt-1 sm:pt-2">
          <button
            onClick={() => onPlay(video)}
            className="flex-1 sm:flex-initial flex items-center justify-center space-x-2 bg-white hover:bg-zinc-200 active:scale-95 text-black px-5 sm:px-8 py-2.5 sm:py-3 rounded-md font-bold text-xs sm:text-sm md:text-base transition-all duration-200 shadow-xl shadow-black/60 cursor-pointer"
          >
            <Play className="w-4 h-4 sm:w-5 sm:h-5 fill-current ml-0.5" />
            <span>再生</span>
          </button>

          <button
            onClick={() => onDetail(video)}
            className="flex-1 sm:flex-initial flex items-center justify-center space-x-2 bg-zinc-600/70 hover:bg-zinc-600/90 active:scale-95 text-white px-4 sm:px-7 py-2.5 sm:py-3 rounded-md font-bold text-xs sm:text-sm md:text-base transition-all duration-200 backdrop-blur-md border border-white/10 shadow-lg cursor-pointer"
          >
            <Info className="w-4 h-4 sm:w-5 sm:h-5" />
            <span>詳細情報</span>
          </button>
        </div>
      </div>
    </div>
  );
};
