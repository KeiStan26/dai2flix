import React from 'react';
import { Play, Clock, Eye, Sparkles } from 'lucide-react';
import { VideoItem } from '../types';

interface CardProps {
  video: VideoItem;
  onSelect: (video: VideoItem) => void;
}

// Format duration in seconds to "1時間12分" or "45分"
function formatDuration(seconds?: number | null): string | null {
  if (!seconds || seconds <= 0) return null;
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);

  if (hours > 0) {
    return `${hours}時間${minutes}分`;
  }
  return `${minutes}分`;
}

// Format view count into Japanese "万回"
function formatViewCount(views?: number | null): string | null {
  if (!views || views <= 0) return null;
  if (views >= 10000) {
    const man = (views / 10000).toFixed(1).replace('.0', '');
    return `${man}万回視聴`;
  }
  return `${views.toLocaleString()}回視聴`;
}

export const Card: React.FC<CardProps> = ({ video, onSelect }) => {
  const durationText = formatDuration(video.duration_seconds);
  const viewCountText = formatViewCount(video.view_count);

  return (
    <div
      onClick={() => onSelect(video)}
      className="group relative flex-shrink-0 w-[200px] sm:w-[250px] md:w-[280px] lg:w-[320px] snap-start cursor-pointer select-none rounded-md overflow-hidden bg-netflix-card border border-white/5 transition-all duration-200 active:scale-[0.97] md:hover:scale-105 md:hover:z-20 md:hover:shadow-2xl md:hover:shadow-black md:hover:border-white/20"
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect(video);
        }
      }}
    >
      {/* Thumbnail Aspect Ratio 16:9 */}
      <div className="relative aspect-video w-full overflow-hidden bg-zinc-900">
        <img
          src={video.thumbnail_url || `https://i.ytimg.com/vi/${video.id}/hqdefault.jpg`}
          alt={video.title}
          loading="lazy"
          className="w-full h-full object-cover object-center transition-transform duration-500 md:group-hover:scale-110"
        />

        {/* Gradient Overlay */}
        <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/20 to-transparent opacity-60 md:group-hover:opacity-80 transition-opacity" />

        {/* Play Icon overlay on hover (Desktop) */}
        <div className="hidden md:flex absolute inset-0 items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none">
          <div className="w-12 h-12 rounded-full bg-white/90 text-black flex items-center justify-center shadow-lg shadow-black/80 transform scale-75 group-hover:scale-100 transition-transform duration-300">
            <Play className="w-6 h-6 fill-current ml-0.5" />
          </div>
        </div>

        {/* Bottom Bar Info on Thumbnail */}
        <div className="absolute bottom-1.5 sm:bottom-2 left-1.5 sm:left-2 right-1.5 sm:right-2 flex items-center justify-between text-[10px] sm:text-[11px] font-semibold text-zinc-300 drop-shadow">
          {durationText ? (
            <span className="flex items-center space-x-1 bg-black/70 px-1.5 py-0.5 rounded backdrop-blur-xs">
              <Clock className="w-3 h-3 text-zinc-400" />
              <span>{durationText}</span>
            </span>
          ) : <span />}

          {viewCountText && (
            <span className="flex items-center space-x-1 bg-black/70 px-1.5 py-0.5 rounded backdrop-blur-xs">
              <Eye className="w-3 h-3 text-zinc-400" />
              <span>{viewCountText}</span>
            </span>
          )}
        </div>
      </div>

      {/* Metadata Body */}
      <div className="p-2.5 sm:p-3 bg-gradient-to-b from-[#181818] to-[#121212] flex flex-col justify-between min-h-[85px] sm:min-h-[96px]">
        <div>
          {/* AI Catchphrase badge if present */}
          {video.catchphrase && (
            <div className="flex items-center space-x-1 text-[10px] sm:text-[11px] font-bold text-netflix-red line-clamp-1 mb-0.5 sm:mb-1">
              <Sparkles className="w-3 h-3 flex-shrink-0" />
              <span>{video.catchphrase}</span>
            </div>
          )}

          {/* Title */}
          <h3 className="text-[11px] sm:text-xs md:text-sm font-bold text-white line-clamp-2 leading-snug md:group-hover:text-zinc-100 transition-colors">
            {video.title}
          </h3>
        </div>

        {/* Mood Tags */}
        {video.mood_tags && video.mood_tags.length > 0 && (
          <div className="mt-1.5 sm:mt-2 flex flex-wrap gap-1">
            {video.mood_tags.slice(0, 2).map((tag, idx) => (
              <span
                key={idx}
                className="text-[9px] sm:text-[10px] font-medium text-zinc-400 bg-white/5 border border-white/5 px-1 sm:px-1.5 py-0.5 rounded"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
