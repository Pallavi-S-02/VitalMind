import React from "react";
import { User, Bot, ShieldAlert, Activity, Pill } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatMessageBubbleProps {
  role: "user" | "assistant" | "system";
  content: string;
  intent?: string;
  isStreaming?: boolean;
}

export function ChatMessageBubble({ role, content, intent, isStreaming }: ChatMessageBubbleProps) {
  const isUser = role === "user";

  // Quick formatter to bold text wrapped in ** and handle newlines
  const formatContent = (text: string) => {
    if (!text || typeof text !== 'string') return null;
    return text.split('\n').map((line, i) => {
      // Split on **...**
      const parts = line.split(/(\*\*.*?\*\*)/g);
      
      return (
        <React.Fragment key={i}>
          {parts.map((part, j) => {
            if (part.startsWith('**') && part.endsWith('**')) {
              return <strong key={j} className="font-semibold text-white">{part.slice(2, -2)}</strong>;
            }
            return part;
          })}
          {i !== text.split('\n').length - 1 && <br />}
        </React.Fragment>
      );
    });
  };

  return (
    <div className={cn("flex w-full group", isUser ? "justify-end" : "justify-start")}>
      <div className={cn("flex max-w-[85%] gap-4", isUser ? "flex-row-reverse" : "flex-row")}>
        
        {/* Avatar */}
        <div className="flex-shrink-0 mt-1">
          {isUser ? (
            <div className="h-8 w-8 rounded-full bg-blue-600/20 border border-blue-500/30 flex items-center justify-center">
              <User className="h-4 w-4 text-blue-400" />
            </div>
          ) : (
            <div className={cn(
              "h-8 w-8 rounded-full border flex items-center justify-center",
              getAvatarDynamicStyles(intent)
            )}>
              {getAvatarDynamicIcon(intent)}
            </div>
          )}
        </div>

        {/* Bubble content */}
        <div className={cn(
          "flex flex-col",
          isUser ? "items-end" : "items-start"
        )}>
          {/* Agent Badge (if assistant and intent exists) */}
          {!isUser && intent && (
            <span className="text-[10px] font-semibold tracking-wider uppercase text-gray-500 mb-1 ml-1 opacity-0 group-hover:opacity-100 transition-opacity">
              {getAgentName(intent)}
            </span>
          )}

          <div className={cn(
            "px-5 py-3.5 rounded-2xl text-sm leading-relaxed",
            isUser 
              ? "bg-blue-600 text-white rounded-tr-sm" 
              : "bg-gray-800/80 border border-white/10 text-gray-200 rounded-tl-sm shadow-sm"
          )}>
            {formatContent(content)}
            {isStreaming && (
              <span className="ml-1 inline-block h-4 w-2 bg-indigo-400 animate-pulse" />
            )}
          </div>
        </div>

      </div>
    </div>
  );
}

// Helpers for dynamic styling based on the active agent intent
function getAgentName(intent: string) {
  switch(intent) {
    case 'symptom_check': return 'Symptom Analyst';
    case 'drug_interaction': return 'Medication Specialist';
    case 'triage': return 'Triage Evaluator';
    case 'general_medical': return 'General AI';
    default: return 'Orchestrator';
  }
}

function getAvatarDynamicStyles(intent?: string) {
  switch(intent) {
    case 'symptom_check': return 'bg-cyan-600/20 border-cyan-500/30';
    case 'drug_interaction': return 'bg-violet-600/20 border-violet-500/30';
    case 'triage': return 'bg-orange-600/20 border-orange-500/30';
    default: return 'bg-indigo-600/20 border-indigo-500/30';
  }
}

function getAvatarDynamicIcon(intent?: string) {
  switch(intent) {
    case 'symptom_check': return <Activity className="h-4 w-4 text-cyan-400" />;
    case 'drug_interaction': return <Pill className="h-4 w-4 text-violet-400" />;
    case 'triage': return <ShieldAlert className="h-4 w-4 text-orange-400" />;
    default: return <Bot className="h-4 w-4 text-indigo-400" />;
  }
}
