"use client";

import { useState, useRef, useEffect } from "react";
import { Send, User, Bot, Loader2, ExternalLink } from "lucide-react";

interface Citation {
  doc_id: string;
  label: string;
  url: string;
  kind: string;
}

interface Message {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
}

interface AgnesChatProps {
  proposalId?: number;
  initialGreeting?: string;
  compact?: boolean;
}

export default function AgnesChat({ proposalId, initialGreeting, compact = false }: AgnesChatProps) {
  const defaultGreeting = "Hello! I am Agnes, your AI Supply Chain Manager. Ask me anything about your supply chain data, consolidation proposals, or ingredient substitutions.";
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: initialGreeting || defaultGreeting }
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = { role: "user", content: input };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const payload: any = {
        messages: [...messages, userMessage].map((m) => ({
          role: m.role,
          content: m.content
        }))
      };
      if (proposalId) {
        payload.proposal_id = proposalId;
      }

      const response = await fetch("http://127.0.0.1:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        throw new Error("Chat request failed");
      }

      const data = await response.json();
      setMessages((prev) => [...prev, { role: "assistant", content: data.answer || "No response.", citations: data.citations }]);
    } catch (err) {
      console.error(err);
      setMessages((prev) => [...prev, { role: "assistant", content: "Error: Could not reach the chat agent. Is the backend running?" }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={`flex flex-col mx-auto rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden animate-in fade-in duration-500 ${compact ? 'h-[600px] w-full' : 'h-[calc(100vh-8rem)] max-w-4xl'}`}>
      {/* Header */}
      <div className="border-b border-slate-200 bg-slate-50 px-6 py-4 flex items-center gap-3">
        <div className="h-10 w-10 rounded-lg bg-indigo-600 text-white flex items-center justify-center">
          <Bot className="h-6 w-6" />
        </div>
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Agnes Chat {proposalId && `(Proposal #${proposalId})`}</h2>
          <p className="text-xs text-slate-500">Powered by RAG & Vector Search</p>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-slate-50/50">
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-4 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
            <div className={`shrink-0 h-8 w-8 rounded-full flex items-center justify-center ${
              msg.role === "user" ? "bg-slate-900 text-white" : "bg-indigo-100 text-indigo-600"
            }`}>
              {msg.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
            </div>
            <div className="max-w-[80%] flex flex-col gap-2">
              <div className={`rounded-2xl px-4 py-3 text-sm shadow-sm whitespace-pre-wrap ${
                msg.role === "user" 
                  ? "bg-slate-900 text-white rounded-tr-sm" 
                  : "bg-white border border-slate-200 text-slate-800 rounded-tl-sm"
              }`}>
                {msg.content}
              </div>
              {msg.citations && msg.citations.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-1">
                  {msg.citations.map((cit, idx) => (
                    cit.url ? (
                      <a key={idx} href={cit.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 px-2 py-1 bg-indigo-50 text-indigo-700 text-xs rounded-md border border-indigo-100 hover:bg-indigo-100 transition-colors">
                        <span className="font-medium">[{cit.doc_id}]</span> {cit.label}
                        <ExternalLink className="h-3 w-3 ml-1" />
                      </a>
                    ) : (
                      <span key={idx} className="inline-flex items-center gap-1 px-2 py-1 bg-slate-100 text-slate-700 text-xs rounded-md border border-slate-200">
                        <span className="font-medium">[{cit.doc_id}]</span> {cit.label}
                      </span>
                    )
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex gap-4">
            <div className="shrink-0 h-8 w-8 rounded-full bg-indigo-100 text-indigo-600 flex items-center justify-center">
              <Bot className="h-4 w-4" />
            </div>
            <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-sm px-4 py-3 flex items-center gap-2 shadow-sm text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin" /> Thinking...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="p-4 bg-white border-t border-slate-200">
        <form onSubmit={handleSubmit} className="relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about consolidation, suppliers, or missing ingredients..."
            className="w-full rounded-full border border-slate-300 bg-slate-50 pl-6 pr-12 py-3 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="absolute right-2 p-2 rounded-full text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:hover:bg-indigo-600 transition-colors"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
