"use client"

import React, { useState, useCallback, useEffect, useRef } from "react";
import Menu from "./menu";
import ChatBox from "./chatbox";
import InsertBox from "./insert_box";

export interface ChatMessage {
	id: string;
	sender: "user" | "bot";
	text: string;
	createdAt: number;
	updatedAt?: number;
}

export default function ChatbotPage() {
	const [menuMinimized, setMenuMinimized] = useState(false);
	const [messages, setMessages] = useState<ChatMessage[]>([]);
	const [loadingBot, setLoadingBot] = useState(false);
	const [entering, setEntering] = useState(true);
	// Floating button state (only visible when minimized)
	const [btnPos, setBtnPos] = useState<{ x: number; y: number }>({ x: 16, y: 16 });
	const draggingRef = useRef(false);
	const startOffsetRef = useRef<{ dx: number; dy: number }>({ dx: 0, dy: 0 });
	const btnSizeRef = useRef<{ w: number; h: number }>({ w: 48, h: 48 });
	const btnRef = useRef<HTMLButtonElement | null>(null);
	const movedRef = useRef(false);

	useEffect(() => {
		// entrance overlay
		const t = setTimeout(() => setEntering(false), 600);
		return () => clearTimeout(t);
	}, []);

	// Helpers to clamp within viewport
	const clamp = (val: number, min: number, max: number) => Math.max(min, Math.min(max, val));

	const beginDragAt = (clientX: number, clientY: number) => {
		draggingRef.current = true;
		movedRef.current = false;
		// Measure button size (if ref available)
		if (btnRef.current) {
			const rect = btnRef.current.getBoundingClientRect();
			btnSizeRef.current = { w: rect.width, h: rect.height };
		}
		startOffsetRef.current = { dx: clientX - btnPos.x, dy: clientY - btnPos.y };
	};

	const onDragMove = (clientX: number, clientY: number) => {
		if (!draggingRef.current) return;
		movedRef.current = true;
		const margin = 8;
		const { w, h } = btnSizeRef.current;
		const vw = typeof window !== "undefined" ? window.innerWidth : 0;
		const vh = typeof window !== "undefined" ? window.innerHeight : 0;
		const x = clamp(clientX - startOffsetRef.current.dx, margin, Math.max(margin, vw - w - margin));
		const y = clamp(clientY - startOffsetRef.current.dy, margin, Math.max(margin, vh - h - margin));
		setBtnPos({ x, y });
	};

	const endDrag = () => {
		draggingRef.current = false;
		startOffsetRef.current = { dx: 0, dy: 0 };
	};

	// Mouse handlers
	const handleMouseDown: React.MouseEventHandler<HTMLButtonElement> = (e) => {
		e.preventDefault();
		beginDragAt(e.clientX, e.clientY);
		const onMove = (evt: MouseEvent) => onDragMove(evt.clientX, evt.clientY);
		const onUp = () => {
			window.removeEventListener("mousemove", onMove);
			window.removeEventListener("mouseup", onUp);
			endDrag();
		};
		window.addEventListener("mousemove", onMove);
		window.addEventListener("mouseup", onUp);
	};

	// Touch handlers
	const handleTouchStart: React.TouchEventHandler<HTMLButtonElement> = (e) => {
		const t = e.touches[0];
		beginDragAt(t.clientX, t.clientY);
		const onMove = (evt: TouchEvent) => {
			if (evt.touches.length > 0) {
				const tt = evt.touches[0];
				onDragMove(tt.clientX, tt.clientY);
			}
		};
		const onEnd = () => {
			window.removeEventListener("touchmove", onMove);
			window.removeEventListener("touchend", onEnd);
			endDrag();
		};
		window.addEventListener("touchmove", onMove, { passive: false });
		window.addEventListener("touchend", onEnd);
	};

	// Generate id helper
	const genId = () => crypto.randomUUID();

	const sendUserMessage = useCallback((text: string) => {
		if (!text.trim()) return;
		const userMsg: ChatMessage = { id: genId(), sender: "user", text: text.trim(), createdAt: Date.now() };
		setMessages(prev => [...prev, userMsg]);
		// Simulate bot reply
		setLoadingBot(true);
		setTimeout(() => {
			setMessages(prev => [...prev, { id: genId(), sender: "bot", text: "Under construction", createdAt: Date.now() }]);
			setLoadingBot(false);
		}, 650);
	}, []);

	const editMessage = useCallback((id: string, newText: string) => {
		setMessages(prev => prev.map(m => m.id === id ? { ...m, text: newText, updatedAt: Date.now() } : m));
	}, []);

	const deleteMessage = useCallback((id: string) => {
		setMessages(prev => {
			const idx = prev.findIndex(m => m.id === id);
			if (idx === -1) return prev;
			const toDelete: string[] = [id];
			// If user message followed by bot answer -> also remove answer
			if (prev[idx].sender === "user" && prev[idx+1] && prev[idx+1].sender === "bot") {
				toDelete.push(prev[idx+1].id);
			}
			return prev.filter(m => !toDelete.includes(m.id));
		});
	}, []);

	const resendUserMessage = useCallback((id: string) => {
		setMessages(prev => {
			const idx = prev.findIndex(m => m.id === id && m.sender === "user");
			if (idx === -1) return prev;
			// Remove existing bot reply if immediately after
			let next = [...prev];
			if (next[idx+1] && next[idx+1].sender === "bot") {
				next.splice(idx+1, 1);
			}
			return next;
		});
		setLoadingBot(true);
		setTimeout(() => {
			setMessages(prev => {
				const idx = prev.findIndex(m => m.id === id);
				if (idx === -1) return prev; // user removed mid-flight
				const insertionIndex = idx + 1;
				const copy = [...prev];
				copy.splice(insertionIndex, 0, { id: genId(), sender: "bot", text: "Under construction", createdAt: Date.now() });
				return copy;
			});
			setLoadingBot(false);
		}, 520);
	}, []);

	return (
		<div className={`min-h-screen w-full flex bg-gray-900 text-gray-100 relative`}> 
			{/* Desktop sidebar with smooth slide */}
			<aside
				className={`hidden md:flex md:fixed md:inset-y-0 md:left-0 w-72 border-r border-gray-700 bg-gray-900/80 backdrop-blur-sm transition-transform duration-300 ease-in-out will-change-transform z-30 ${menuMinimized ? "-translate-x-full" : "translate-x-0"}`}
				aria-hidden={menuMinimized}
			>
				<div className="w-72">
					<Menu minimized={menuMinimized} setMinimized={setMenuMinimized} />
				</div>
			</aside>

			{/* Mobile overlay menu */}
			{!menuMinimized && (
				<div className="md:hidden">
					<div className="fixed inset-0 z-40 bg-black/50" onClick={() => setMenuMinimized(true)} />
					<div className="fixed left-0 top-0 bottom-0 z-50 w-72 max-w-[80vw] bg-gray-900 border-r border-gray-700 p-4 shadow-xl">
						<Menu minimized={menuMinimized} setMinimized={setMenuMinimized} />
					</div>
				</div>
			)}

			<main className={`flex flex-col h-screen w-full relative transition-all duration-300 ease-in-out ${menuMinimized ? "md:pl-0" : "md:pl-72"}`}>
				<div className="flex flex-col flex-1 max-w-4xl w-full mx-auto px-4 py-6 gap-4">
					<ChatBox
						messages={messages}
						loadingBot={loadingBot}
						onEdit={editMessage}
						onDelete={deleteMessage}
						onResend={resendUserMessage}
					/>
					<InsertBox onSend={sendUserMessage} sending={loadingBot} />
				</div>
			</main>
			{menuMinimized && (
				<button
					ref={btnRef}
					className="fixed z-50 select-none cursor-grab active:cursor-grabbing rounded-full h-10 md:h-11 px-3 md:px-4 flex items-center gap-2 text-gray-100 bg-gray-800/70 hover:bg-gray-800/90 border border-white/10 shadow-lg backdrop-blur-md transition-colors"
					style={{ left: btnPos.x, top: btnPos.y }}
					onMouseDown={handleMouseDown}
					onTouchStart={handleTouchStart}
					onClick={(e) => {
						// Suppress click if the button was dragged
						if (movedRef.current) {
							e.preventDefault();
							return;
						}
						setMenuMinimized(false);
					}}
					title="Open menu"
					aria-label="Open menu"
				>
					{/* Icon + label */}
					<svg className="w-4 h-4 text-violet-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
						<line x1="3" y1="7" x2="21" y2="7" />
						<line x1="3" y1="12" x2="21" y2="12" />
						<line x1="3" y1="17" x2="16" y2="17" />
					</svg>
					<span className="text-xs md:text-sm font-medium">Menu</span>
				</button>
			)}

			{/* Entering overlay */}
			{entering && (
				<div className="absolute inset-0 grid place-items-center bg-gray-900/70 backdrop-blur-sm">
					<div className="flex items-center gap-3 text-gray-200">
						<span role="img" aria-label="cat" className="text-2xl animate-bounce">🐱</span>
						<span>Loading chat…</span>
					</div>
				</div>
			)}
		</div>
	);
}

