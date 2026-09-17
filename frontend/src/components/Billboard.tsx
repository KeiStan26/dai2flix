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
    <div id="feed-top" className="relative h-[70vh] sm:h-[80vh] md:h-[85vh] w-full overflow-hidden select-none">
      {/* Background Image Banner */}
      <img
        src={bgImage}
        alt={video.title}
        className="absolute inset-0 w-full h-full object-cover object-center filter brightness-90 transform scale-105 transition-transform duration-1000"
      />

      {/* Netflix Vignette Gradients */}
      {/* Bottom fade into black page background */}
      <div className="absolute inset-0 bg-gradient-to-t from-[#141414] via-[#141414]/40 to-transparent" />
      {/* Left to right dark gradient for text readability */}
      <div className="absolute inset-0 bg-gradient-to-r from-black/95 via-black/60 to-transparent w-full md:w-3/4" />
      {/* Top subtle fade for navbar */}
      <div className="absolute top-0 inset-x-0 h-32 bg-gradient-to-b from-black/80 to-transparent" />

      {/* Content Container */}
      <div className="absolute bottom-[18%] sm:bottom-[20%] left-4 md:left-12 max-w-2xl lg:max-w-3xl space-y-4 z-10">
        {/* Series Banner Badge */}
        <div className="flex items-center space-x-2">
          <span className="flex items-center space-x-1 text-xs font-black uppercase tracking-wider bg-netflix-red text-white px-2 py-0.5 rounded shadow">
            <Flame className="w-3.5 h-3.5" />
            <span>注目の大型企画</span>
          </span>
          {video.mood_tags && video.mood_tags.length > 0 && (
            <span className="hidden sm:inline-block text-xs font-semibold text-zinc-300 bg-white/10 backdrop-blur-md px-2 py-0.5 rounded border border-white/10">
              {video.mood_tags[0]}
            </span>
          )}
        </div>

        {/* AI Catchphrase */}
        {video.catchphrase && (
          <div className="flex items-center space-x-1.5 text-netflix-red font-black text-sm sm:text-base md:text-lg tracking-wide drop-shadow-md">
            <Sparkles className="w-4 h-4 text-netflix-red animate-pulse" />
            <span>{video.catchphrase}</span>
          </div>
        )}

        {/* Title */}
        <h1 className="text-2xl sm:text-4xl md:text-5xl lg:text-6xl font-black text-white leading-tight tracking-tight drop-shadow-lg">
          {video.title}
        </h1>

        {/* Synopsis / Description Teaser */}
        <p className="text-xs sm:text-sm md:text-base text-zinc-200 line-clamp-3 leading-relaxed drop-shadow max-w-xl">
          {video.synopsis || video.description || 'だいにぐるーぷによる究極の大型エンターテインメント。予測不能な心理戦と極限サバイバルが今、幕を開ける。'}
        </p>

        {/* Action Buttons */}
        <div className="flex items-center space-x-3 pt-2">
          <button
            onClick={() => onPlay(video)}
            className="flex items-center justify-center space-x-2 bg-white hover:bg-zinc-200 text-black px-6 sm:px-8 py-2.5 sm:py-3 rounded-md font-bold text-sm sm:text-base transition-all duration-200 hover:scale-105 shadow-xl shadow-black/60 cursor-pointer"
          >
            <Play className="w-5 h-5 fill-current ml-0.5" />
            <span>再生</span>
          </button>

          <button
            onClick={() => onDetail(video)}
            className="flex items-center justify-center space-x-2 bg-zinc-600/70 hover:bg-zinc-600/90 text-white px-5 sm:px-7 py-2.5 sm:py-3 rounded-md font-bold text-sm sm:text-base transition-all duration-200 hover:scale-105 backdrop-blur-md border border-white/10 shadow-lg cursor-pointer"
          >
            <Info className="w-5 h-5" />
            <span>詳細情報</span>
          </button>
        </div>
      </div>
    </div>
  );
};
