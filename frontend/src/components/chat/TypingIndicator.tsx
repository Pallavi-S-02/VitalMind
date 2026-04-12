import { Bot } from "lucide-react";

export function TypingIndicator() {
  return (
    <div className="flex w-full justify-start mt-2">
      <div className="flex gap-4">
        {/* Avatar */}
        <div className="flex-shrink-0 mt-1 h-8 w-8 rounded-full bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center">
          <Bot className="h-4 w-4 text-indigo-400" />
        </div>

        {/* Bubbles */}
        <div className="bg-gray-800/80 border border-white/10 rounded-2xl px-5 py-4 rounded-tl-sm flex items-center gap-1.5 h-12">
          <div className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce [animation-delay:-0.3s]" />
          <div className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce [animation-delay:-0.15s]" />
          <div className="w-1.5 h-1.5 bg-gray-500 rounded-full animate-bounce" />
        </div>
      </div>
    </div>
  );
}
