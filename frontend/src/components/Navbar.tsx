import React, { useState, useEffect } from 'react';
import { Film, History, PlayCircle, Crown } from 'lucide-react';

interface NavbarProps {
  onSearchClick?: () => void;
  onHistoryClick?: () => void;
  activeTab: 'public' | 'membership';
  onTabChange: (tab: 'public' | 'membership') => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  onHistoryClick,
  activeTab,
  onTabChange,
}) => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [useImageLogo, setUseImageLogo] = useState(true);

  useEffect(() => {
    const handleScroll = () => {
      if (window.scrollY > 40) {
        setIsScrolled(true);
      } else {
        setIsScrolled(false);
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-40 transition-all duration-300 ${
        isScrolled
          ? 'bg-[#141414]/95 backdrop-blur-md shadow-2xl py-2.5 sm:py-3 border-b border-white/5'
          : 'bg-gradient-to-b from-black/95 via-black/60 to-transparent py-3 sm:py-5'
      }`}
      style={{ paddingTop: 'max(0.75rem, env(safe-area-inset-top, 0.75rem))' }}
    >
      <div className="max-w-[1700px] mx-auto px-3 sm:px-6 md:px-12 flex items-center justify-between">
        {/* Brand Logo & View Mode Tabs */}
        <div className="flex items-center space-x-3 sm:space-x-6 md:space-x-8">
          <a
            href="/"
            className="flex items-center space-x-1.5 sm:space-x-2 group focus:outline-none select-none"
            aria-label="DAI2FLIX Home"
          >
            {useImageLogo ? (
              <img
                src="/logo.png"
                alt="DAI2FLIX"
                className="h-7 sm:h-8 md:h-9 w-auto object-contain transition-transform group-hover:scale-105"
                onError={() => setUseImageLogo(false)}
              />
            ) : (
              <div className="flex items-center space-x-1.5 sm:space-x-2">
                <div className="w-7 h-7 sm:w-8 sm:h-8 rounded bg-netflix-red flex items-center justify-center font-black text-white shadow-lg shadow-netflix-red/40 group-hover:scale-105 transition-transform">
                  <Film className="w-4 h-4 sm:w-5 sm:h-5" />
                </div>
                <span className="text-xl sm:text-2xl font-black tracking-wider text-netflix-red uppercase drop-shadow-md">
                  DAI2<span className="text-white ml-0.5">FLIX</span>
                </span>
              </div>
            )}
          </a>

          {/* Mode Tabs (Public vs Membership) */}
          <div className="flex items-center bg-black/70 p-0.5 rounded-full border border-white/10 text-[11px] sm:text-xs">
            <button
              onClick={() => onTabChange('public')}
              className={`px-2.5 sm:px-3.5 py-1 rounded-full font-bold transition-all cursor-pointer ${
                activeTab === 'public'
                  ? 'bg-white text-black shadow-md'
                  : 'text-zinc-400 hover:text-white'
              }`}
            >
              一般公開
            </button>
            <button
              onClick={() => onTabChange('membership')}
              className={`px-2.5 sm:px-3.5 py-1 rounded-full font-bold transition-all flex items-center space-x-1 cursor-pointer ${
                activeTab === 'membership'
                  ? 'bg-gradient-to-r from-amber-400 to-yellow-500 text-black shadow-md shadow-amber-500/20'
                  : 'text-amber-400/80 hover:text-amber-300'
              }`}
            >
              <Crown className="w-3 h-3 fill-current" />
              <span>メンバー限定</span>
            </button>
          </div>

          {/* Section Anchors */}
          {activeTab === 'public' ? (
            <nav className="hidden lg:flex items-center space-x-5 text-sm font-medium text-zinc-300">
              <a href="#feed-top" className="hover:text-white transition-colors">
                ホーム
              </a>
              <a href="#row_recent" className="hover:text-white transition-colors">
                新着エピソード
              </a>
              <a href="#playlists" className="hover:text-white transition-colors">
                大型企画シリーズ
              </a>
              <a href="#ai-categories" className="hover:text-white transition-colors">
                AIムード別
              </a>
            </nav>
          ) : (
            <nav className="hidden lg:flex items-center space-x-5 text-sm font-medium text-amber-200/80">
              <a href="#feed-top" className="hover:text-amber-300 transition-colors">
                ホーム
              </a>
              <a href="#row_membership" className="hover:text-amber-300 transition-colors">
                新着アーカイブ
              </a>
              <a href="#membership-categories" className="hover:text-amber-300 transition-colors">
                限定ムード別
              </a>
            </nav>
          )}
        </div>

        {/* Action Controls */}
        <div className="flex items-center space-x-2 sm:space-x-4 text-zinc-300">
          <button
            onClick={onHistoryClick}
            className="flex items-center space-x-1 sm:space-x-1.5 px-2.5 sm:px-3 py-1.5 rounded-full text-xs font-semibold bg-white/10 hover:bg-white/20 active:scale-95 hover:text-white transition-all backdrop-blur-sm border border-white/10 cursor-pointer"
            title="最近観た作品へ移動"
            aria-label="視聴履歴"
          >
            <History className="w-3.5 h-3.5 text-netflix-red" />
            <span className="hidden sm:inline">視聴履歴</span>
          </button>

          <a
            href="https://www.youtube.com/@dai2group"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center space-x-1 sm:space-x-1.5 px-2.5 sm:px-3 py-1.5 rounded-full text-xs font-bold bg-netflix-red hover:bg-netflix-darkRed active:scale-95 text-white transition-all shadow-md shadow-netflix-red/30 cursor-pointer"
          >
            <PlayCircle className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">公式YouTube</span>
          </a>
        </div>
      </div>
    </header>
  );
};
