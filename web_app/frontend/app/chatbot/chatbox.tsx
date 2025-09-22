import React, { useRef, useEffect, useState } from "react";

interface ChatBoxProps {
  messages: { id: string; sender: "user" | "bot"; text: string }[];
  loadingBot: boolean;
  onEdit: (id: string, text: string) => void;
  onDelete: (id: string) => void;
  onResend: (id: string) => void;
}
const ChatBox: React.FC<ChatBoxProps> = ({ messages, loadingBot, onEdit, onDelete, onResend }) => {
  const [editId, setEditId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [dots, setDots] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Example: auto scroll
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loadingBot]);

  // Example: loading dots
  useEffect(() => {
    if (!loadingBot) return setDots("");
    const interval = setInterval(() => {
      setDots(prev => (prev.length < 3 ? prev + "." : ""));
    }, 500);
    return () => clearInterval(interval);
  }, [loadingBot]);

  const startEdit = (id: string, current: string) => {
    setEditId(id);
    setEditValue(current);
  };
  const cancelEdit = () => { setEditId(null); setEditValue(""); };
  const saveEdit = () => {
    if (editId) {
      onEdit(editId, editValue.trim());
      cancelEdit();
    }
  };

  // You can lift state up and pass setMessages, setLoading, etc. as props if needed

  return (
  <div className={`flex-1 overflow-hidden rounded-xl border border-gray-700 bg-gray-800 shadow-sm`}> 
    <div className="h-full overflow-y-auto p-4 space-y-3" role="log" aria-live="polite" aria-relevant="additions" aria-label="Chat messages">
        {messages.map((msg) => {
          const isEditing = editId === msg.id;
          return (
            <div key={msg.id} className={`flex items-start gap-0 ${msg.sender === 'user' ? 'justify-end' : ''}`}>
              <div className={`max-w-[80%] rounded-2xl px-4 py-2 text-sm shadow-sm ${msg.sender === 'user' ? 'bg-violet-600 text-white' : 'bg-gray-700 text-gray-100'}`}> 
                {isEditing ? (
                  <div className="flex flex-col gap-2">
                    <textarea
                      value={editValue}
                      onChange={e => setEditValue(e.target.value)}
                      rows={Math.min(8, Math.max(1, editValue.split(/\n/).length))}
                      className="w-full resize-y bg-white/70 dark:bg-gray-800/70 text-inherit border border-gray-300 dark:border-gray-600 rounded-md p-2 text-sm"
                    />
                    <div className="flex gap-2 justify-end">
                      <button onClick={cancelEdit} className="px-2 py-1 text-xs rounded border border-gray-600 bg-gray-800">Cancel</button>
                      <button onClick={saveEdit} className="px-2 py-1 text-xs rounded bg-violet-600 text-white border border-violet-700">Save</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="whitespace-pre-wrap">{msg.text}</div>
                    {msg.sender === 'user' && (
                      <div className="flex gap-1 mt-2 flex-wrap opacity-90">
                        <button className="px-2 py-1 text-xs rounded border border-gray-600 bg-gray-800" onClick={() => startEdit(msg.id, msg.text)}>Edit</button>
                        <button className="px-2 py-1 text-xs rounded border border-gray-600 bg-gray-800" onClick={() => onResend(msg.id)}>Resend</button>
                        <button className="px-2 py-1 text-xs rounded border border-gray-600 bg-gray-800" onClick={() => onDelete(msg.id)}>Delete</button>
                      </div>
                    )}
                  </>
                )}
              </div>
            </div>
          );
        })}
        {loadingBot && (
          <div className="flex items-start gap-0">
            <div className="max-w-[80%] rounded-2xl px-4 py-2 text-sm shadow-sm bg-gray-700 text-gray-100">
              <span><span className="inline-block w-3 h-3 rounded-full bg-gray-400 animate-pulse mr-2" />Under construction{dots}</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
};

export default ChatBox;

