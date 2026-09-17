import React, { useRef, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { RowItem, VideoItem } from '../types';
import { Card } from './Card';

interface RowProps {
  row: RowItem;
  onSelectVideo: (video: VideoItem) => void;
}

export const Row: React.FC<RowProps> = ({ row, onSelectVideo }) => {
  const rowRef = useRef<HTMLDivElement>(null);
  const [isMoved, setIsMoved] = useState(false);

  const handleScroll = (direction: 'left' | 'right') => {
    setIsMoved(true);
    if (rowRef.current) {
      const { scrollLeft, clientWidth } = rowRef.current;
      const scrollAmount = clientWidth * 0.75;
      const scrollTo = direction === 'left' ? scrollLeft - scrollAmount : scrollLeft + scrollAmount;

      rowRef.current.scrollTo({
        left: scrollTo,
        behavior: 'smooth',
      });
    }
  };

  if (!row.items || row.items.length === 0) {
    return null;
  }

  return (
    <div id={row.id} className="space-y-2 md:space-y-3 my-6 md:my-8 px-4 md:px-12 relative group/row">
      {/* Row Header */}
      <div className="flex items-baseline justify-between">
        <h2 className="text-base sm:text-lg md:text-xl font-bold text-white tracking-wide flex items-center space-x-2">
          <span>{row.title}</span>
          <span className="text-xs text-zinc-500 font-normal">
            ({row.items.length})
          </span>
        </h2>
      </div>

      {/* Row Container with Scroll Controls */}
      <div className="relative">
        {/* Left Arrow Button */}
        <button
          onClick={() => handleScroll('left')}
          className={`absolute top-0 bottom-0 left-0 z-30 w-10 sm:w-12 bg-black/60 hover:bg-black/90 text-white flex items-center justify-center transition-all duration-300 opacity-0 group-hover/row:opacity-100 backdrop-blur-xs rounded-r-md ${
            !isMoved ? 'hidden' : 'flex'
          }`}
          aria-label="Scroll left"
        >
          <ChevronLeft className="w-7 h-7 hover:scale-125 transition-transform" />
        </button>

        {/* Horizontal Slider */}
        <div
          ref={rowRef}
          className="flex items-center space-x-3 sm:space-x-4 overflow-x-auto no-scrollbar scroll-smooth py-3 px-1"
        >
          {row.items.map((video) => (
            <Card key={`${row.id}_${video.id}`} video={video} onSelect={onSelectVideo} />
          ))}
        </div>

        {/* Right Arrow Button */}
        <button
          onClick={() => handleScroll('right')}
          className="absolute top-0 bottom-0 right-0 z-30 w-10 sm:w-12 bg-black/60 hover:bg-black/90 text-white flex items-center justify-center transition-all duration-300 opacity-0 group-hover/row:opacity-100 backdrop-blur-xs rounded-l-md"
          aria-label="Scroll right"
        >
          <ChevronRight className="w-7 h-7 hover:scale-125 transition-transform" />
        </button>
      </div>
    </div>
  );
};
