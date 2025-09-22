import React from "react";

interface MenuProps {
  minimized: boolean;
  setMinimized: (m: boolean) => void;
}

const Menu: React.FC<MenuProps> = ({ minimized, setMinimized }) => {
  if (minimized) return null;
  return (
    <aside className={`w-72 flex-shrink-0 h-screen p-4 border-r border-gray-700 bg-gray-900`}> 
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold">NL to SQL chatbot</h1>
        <button
          onClick={() => setMinimized(true)}
          className="inline-flex items-center gap-1 rounded-full h-8 px-3 text-xs font-medium text-gray-100 bg-gray-800/70 hover:bg-gray-800/90 border border-white/10 shadow-sm backdrop-blur-md transition-colors"
          title="Minimize menu"
          aria-label="Minimize menu"
        >
          <svg className="w-3.5 h-3.5 text-gray-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          <span>Hide</span>
        </button>
      </div>
      {/* Theme removed: single dark theme */}
    </aside>
  );
};

export default Menu;

