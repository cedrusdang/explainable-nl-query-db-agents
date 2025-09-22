import React, { useState, useRef, useEffect } from "react";

interface InsertBoxProps {
  onSend: (text: string) => void;
  sending: boolean;
}

const InsertBox: React.FC<InsertBoxProps> = ({ onSend, sending }) => {
  const [input, setInput] = useState("");
  const [runAnim, setRunAnim] = useState(false);
  const textRef = useRef<HTMLTextAreaElement | null>(null);

  // Auto resize up to 15 lines
  useEffect(() => {
    const el = textRef.current;
    if (!el) return;
    const lineHeight = 20; // approximate
    const maxLines = 15;
    const maxHeight = lineHeight * maxLines;
    el.style.height = 'auto';
    const newH = Math.min(el.scrollHeight, maxHeight);
    el.style.height = newH + 'px';
    if (el.scrollHeight > maxHeight) {
      el.style.overflowY = 'auto';
    } else {
      el.style.overflowY = 'hidden';
    }
  }, [input]);

  const handleSend = () => {
    if (!input.trim() || sending) return;
    setRunAnim(true);
    onSend(input);
    setInput("");
    setTimeout(() => setRunAnim(false), 500);
  };

  return (
  <div className="flex items-end gap-2 border-t border-gray-700 pt-3">
      <textarea
        ref={textRef}
        value={input}
        className="flex-1 min-h-9 max-h-64 border border-gray-600 rounded-md bg-gray-800 p-2 text-sm text-gray-100 focus:outline-none focus:ring-2 focus:ring-violet-500"
        onChange={e => setInput(e.target.value)}
        onKeyDown={e => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
          }
        }}
        placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
        disabled={sending}
        rows={1}
        style={{ resize: "none" }}
    aria-label="Message input"
      />
      <button
        onClick={handleSend}
  className={`inline-flex items-center justify-center rounded-md px-3 py-2 bg-violet-600 text-white hover:bg-violet-700 transition border border-violet-700 ${runAnim ? 'scale-95' : ''}`}
        disabled={sending || !input.trim()}
        title="Send"
    aria-label="Send message"
      >
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
      </button>
    </div>
  );
};

export default InsertBox;

