import React, { useEffect } from 'react';
import { X, ExternalLink, Sparkles, Clock, Eye } from 'lucide-react';
import { VideoItem } from '../types';

interface PlayerModalProps {
  video: VideoItem | null;
  isOpen: boolean;
  onClose: () => void;
  onStartWatch?: (video: VideoItem) => void;
}

export const PlayerModal: React.FC<PlayerModalProps> = ({
  video,
  isOpen,
  onClose,
  onStartWatch,
}) => {
  useEffect(() => {
    if (isOpen && video && onStartWatch) {
      onStartWatch(video);
    }
  }, [isOpen, video, onStartWatch]);

  // Handle ESC key to close modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    if (isOpen) {
      document.body.style.overflow = 'hidden';
      window.addEventListener('keydown', handleKeyDown);
    } else {
      document.body.style.overflow = 'unset';
    }

    return () => {
      document.body.style.overflow = 'unset';
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose]);

  if (!isOpen || !video) {
    return null;
  }

  // Format view count
  const formattedViews = video.view_count
    ? video.view_count >= 10000
      ? `${(video.view_count / 10000).toFixed(1)}万回`
      : `${video.view_count.toLocaleString()}回`
    : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 md:p-6 bg-black/85 backdrop-blur-md transition-opacity duration-300 animate-fadeIn"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      {/* Modal Container */}
      <div
        className="relative w-full max-w-5xl bg-[#181818] rounded-t-2xl sm:rounded-xl overflow-hidden shadow-2xl shadow-black border border-white/10 flex flex-col max-h-[95vh] sm:max-h-[90vh]"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute top-2.5 right-2.5 sm:top-3 sm:right-3 z-30 w-9 h-9 sm:w-10 sm:h-10 rounded-full bg-black/80 hover:bg-black/95 active:scale-95 text-white flex items-center justify-center border border-white/20 transition-all cursor-pointer shadow-lg"
          aria-label="動画プレイヤーを閉じる"
        >
          <X className="w-5 h-5" />
        </button>

        {/* YouTube Official IFrame Embed */}
        <div className="relative aspect-video w-full bg-black flex-shrink-0">
          <iframe
            src={`https://www.youtube.com/embed/${video.id}?autoplay=1&rel=0&modestbranding=1&enablejsapi=1`}
            title={video.title}
            allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
            allowFullScreen
            className="w-full h-full border-0"
          />
        </div>

        {/* Video Information & Details */}
        <div
          className="p-3.5 sm:p-6 overflow-y-auto custom-scrollbar space-y-3 sm:space-y-4 bg-gradient-to-b from-[#181818] to-[#121212]"
          style={{ paddingBottom: 'max(1.25rem, env(safe-area-inset-bottom, 1.25rem))' }}
        >
          {/* Header & Badges */}
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-white/10 pb-2.5 sm:pb-3">
            <div className="max-w-full">
              {video.catchphrase && (
                <div className="flex items-center space-x-1.5 text-[11px] sm:text-sm font-bold text-netflix-red mb-0.5 sm:mb-1">
                  <Sparkles className="w-3.5 h-3.5 flex-shrink-0" />
                  <span className="line-clamp-1">{video.catchphrase}</span>
                </div>
              )}
              <h2 className="text-base sm:text-2xl font-bold text-white leading-tight">
                {video.title}
              </h2>
            </div>

            <a
              href={`https://www.youtube.com/watch?v=${video.id}`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center space-x-1.5 text-xs font-semibold bg-white/10 hover:bg-white/20 active:scale-95 text-zinc-200 px-2.5 sm:px-3 py-1.5 rounded-md transition-colors border border-white/10 cursor-pointer"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              <span>YouTubeで開く</span>
            </a>
          </div>

          {/* Stats & Tags Bar */}
          <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-xs text-zinc-400 font-medium">
            {formattedViews && (
              <div className="flex items-center space-x-1 bg-white/5 px-2 py-0.5 sm:px-2.5 sm:py-1 rounded text-[11px] sm:text-xs">
                <Eye className="w-3.5 h-3.5 text-zinc-400" />
                <span>{formattedViews}</span>
              </div>
            )}
            {video.duration_seconds && video.duration_seconds > 0 && (
              <div className="flex items-center space-x-1 bg-white/5 px-2 py-0.5 sm:px-2.5 sm:py-1 rounded text-[11px] sm:text-xs">
                <Clock className="w-3.5 h-3.5 text-zinc-400" />
                <span>{Math.floor(video.duration_seconds / 60)}分</span>
              </div>
            )}
            {video.mood_tags && video.mood_tags.length > 0 && (
              <div className="flex flex-wrap gap-1 sm:gap-1.5 ml-auto">
                {video.mood_tags.map((tag, idx) => (
                  <span
                    key={idx}
                    className="text-[10px] sm:text-xs font-semibold text-netflix-red bg-netflix-red/10 border border-netflix-red/20 px-2 py-0.5 rounded-full"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* AI Synopsis */}
          {video.synopsis && (
            <div className="bg-white/5 rounded-lg p-3 sm:p-4 border border-white/5">
              <h4 className="text-[10px] sm:text-xs font-bold text-zinc-400 uppercase tracking-wider mb-1">
                AIあらすじ
              </h4>
              <p className="text-xs sm:text-base text-zinc-100 leading-relaxed">
                {video.synopsis}
              </p>
            </div>
          )}

          {/* Original YouTube Description */}
          {video.description && (
            <div className="space-y-1 pt-1">
              <h4 className="text-[10px] sm:text-xs font-bold text-zinc-500 uppercase tracking-wider">
                公式概要欄
              </h4>
              <p className="text-[11px] sm:text-xs text-zinc-400 line-clamp-3 hover:line-clamp-none whitespace-pre-line leading-relaxed transition-all">
                {video.description}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
