"use client";

import { useState, useEffect, useRef } from "react";
import { useSession } from "next-auth/react";
import { Send, FlaskConical, XCircle, Trash2, Stethoscope } from "lucide-react";
import { useChatStore } from "@/store/chatStore";
import { ChatMessageBubble } from "@/components/chat/ChatMessageBubble";
import { TypingIndicator } from "@/components/chat/TypingIndicator";

export default function DoctorAssistantPage() {
  const { data: session } = useSession();
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  const { 
    messages, 
    isConnected, 
    isTyping, 
    error, 
    connect, 
    disconnect, 
    sendMessage,
    streamingContent,
    clearHistory
  } = useChatStore();

  useEffect(() => {
    if (session?.accessToken) {
      connect(session.accessToken);
    }
    return () => {
      disconnect();
    };
  }, [session, connect, disconnect]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping, streamingContent]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !isConnected) return;
    
    sendMessage(input);
    setInput("");
  };

  return (
    <div className="flex flex-col h-[calc(100vh-theme(spacing.16))] bg-gradient-to-br from-gray-950 via-slate-900 to-gray-950" style={{ fontFamily: "'Inter', sans-serif" }}>
      
      {/* Header */}
      <div className="flex-shrink-0 px-6 py-4 border-b border-white/5 flex items-center justify-between bg-gray-900/50 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-600/20 border border-indigo-500/30 rounded-xl">
            <FlaskConical className="h-5 w-5 text-indigo-400" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">Clinical Copilot</h1>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`h-2 w-2 rounded-full ${isConnected ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.5)]" : "bg-red-500"}`} />
              <span className="text-xs text-gray-400 font-medium">
                {isConnected ? "Connected • Ready for Clinical Query" : "Disconnected • Reconnecting..."}
              </span>
            </div>
          </div>
        </div>

        <button
          onClick={clearHistory}
          disabled={messages.length === 0}
          className="flex items-center gap-2 px-3 py-1.5 bg-white/5 hover:bg-white/10 disabled:opacity-30 border border-white/10 rounded-lg text-xs text-gray-300 transition-colors"
        >
          <Trash2 className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Clear Session</span>
        </button>
      </div>

      {/* Connection Error Banner */}
      {error && (
        <div className="flex-shrink-0 bg-red-950/50 border-b border-red-900/50 px-6 py-3 flex items-center gap-3 text-red-200 text-sm">
          <XCircle className="h-4 w-4" />
          <span>{error}</span>
        </div>
      )}

      {/* Messages Window */}
      <div className="flex-1 overflow-y-auto px-4 py-6 sm:px-6">
        <div className="max-w-4xl mx-auto space-y-6">
          
          {/* Welcome Message */}
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-20 text-center animate-in fade-in zoom-in duration-500">
              <div className="h-16 w-16 bg-indigo-900/30 border border-indigo-500/20 rounded-2xl flex items-center justify-center mb-6">
                <Stethoscope className="h-8 w-8 text-indigo-400" />
              </div>
              <h2 className="text-xl font-bold text-white mb-2">Clinical Copilot Online</h2>
              <p className="text-gray-400 text-sm max-w-sm mb-8 leading-relaxed">
                Your AI assistant can analyze symptoms, review medication interactions, and pull patient history to assist with clinical workflows.
              </p>
              
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full max-w-lg">
                {[
                  "Draft a differential diagnosis for a 35yo with acute LUQ pain.",
                  "Review the patient's interactions for Apixaban and Ibuprofen.",
                  "Summarize the recent lipid panel results.",
                  "What are the guidelines for pediatric asthma exacerbation?"
                ].map((suggestion) => (
                  <button 
                    key={suggestion}
                    onClick={() => { setInput(suggestion); }}
                    className="px-4 py-3 bg-gray-800/40 hover:bg-gray-800/80 border border-white/5 rounded-xl text-xs text-gray-300 text-left transition-colors"
                  >
                    &quot;{suggestion}&quot;
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Chat History */}
          {messages.map((msg) => (
            <ChatMessageBubble 
              key={msg.id}
              role={msg.role}
              content={msg.content}
              intent={msg.intent}
            />
          ))}

          {/* Streaming active chunk (if any) */}
          {streamingContent && (
            <ChatMessageBubble 
              role="assistant"
              content={streamingContent}
              isStreaming={true}
            />
          )}

          {/* Typing Indicator */}
          {isTyping && !streamingContent && <TypingIndicator />}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="flex-shrink-0 p-4 sm:p-6 bg-gray-950 border-t border-white/5">
        <div className="max-w-4xl mx-auto relative">
          <form onSubmit={handleSubmit} className="relative flex items-center">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask a clinical question..."
              disabled={!isConnected}
              className="w-full bg-gray-900 border border-white/10 rounded-2xl pl-5 pr-14 py-4 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500/50 transition-all text-sm disabled:opacity-50 shadow-xl shadow-black/20"
            />
            <button
              type="submit"
              disabled={!input.trim() || !isConnected}
              className="absolute right-2 p-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-800 disabled:text-gray-500 text-white rounded-xl transition-colors shadow-lg"
            >
              <Send className="h-4 w-4 ml-0.5" />
            </button>
          </form>
          <div className="text-center mt-3">
            <p className="text-[11px] text-gray-600">
              For clinical decision support only. The physician is solely responsible for determining final diagnosis and treatments.
            </p>
          </div>
        </div>
      </div>

    </div>
  );
}
