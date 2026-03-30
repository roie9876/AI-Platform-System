"use client";

import { useState } from "react";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { ChevronDown, ChevronRight, Play, CheckCircle2, XCircle, Loader2 } from "lucide-react";

export interface ToolCallEvent {
  name: string;
  arguments: Record<string, unknown>;
}

export interface ToolResultEvent {
  name: string;
  result: Record<string, unknown>;
  status: "success" | "error";
}

interface CodeExecutionBlockProps {
  toolCall: ToolCallEvent;
  toolResult?: ToolResultEvent;
}

export function CodeExecutionBlock({ toolCall, toolResult }: CodeExecutionBlockProps) {
  const [expanded, setExpanded] = useState(false);
  const isCodeInterpreter = toolCall.name === "code_interpreter";
  const code = isCodeInterpreter ? (toolCall.arguments.code as string) || "" : "";
  const isRunning = !toolResult;
  const isSuccess = toolResult?.status === "success";
  const displayName = isCodeInterpreter
    ? "Python"
    : toolCall.name.replace(/^mcp__/, "").replace(/_/g, " ");

  return (
    <div className="my-2 rounded-lg border border-gray-200 bg-white overflow-hidden">
      {/* Header bar */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-gray-50 transition-colors"
      >
        {isRunning ? (
          <Loader2 className="h-4 w-4 text-blue-500 animate-spin flex-shrink-0" />
        ) : isSuccess ? (
          <CheckCircle2 className="h-4 w-4 text-green-500 flex-shrink-0" />
        ) : (
          <XCircle className="h-4 w-4 text-red-500 flex-shrink-0" />
        )}

        <Play className="h-3 w-3 text-gray-400 flex-shrink-0" />

        <span className="text-xs font-medium text-gray-700 flex-1">
          {isRunning
            ? `Executing ${displayName}...`
            : isCodeInterpreter
            ? `Analyzed with ${displayName}`
            : `Ran ${displayName}`}
        </span>

        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-gray-400" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-gray-400" />
        )}
      </button>

      {/* Collapsible body */}
      {expanded && (
        <div className="border-t border-gray-200">
          {/* Code / Arguments */}
          {isCodeInterpreter && code ? (
            <SyntaxHighlighter
              style={oneLight}
              language="python"
              PreTag="div"
              customStyle={{ margin: 0, fontSize: "12px", background: "#fafafa", borderRadius: 0 }}
            >
              {code}
            </SyntaxHighlighter>
          ) : (
            <div className="px-3 py-2 bg-gray-50 text-xs font-mono text-gray-600 overflow-x-auto">
              <pre>{JSON.stringify(toolCall.arguments, null, 2)}</pre>
            </div>
          )}

          {/* Result */}
          {toolResult && (
            <div className="border-t border-gray-200">
              <div className="px-3 py-1.5 bg-gray-100 text-[10px] font-medium text-gray-500 uppercase tracking-wider">
                Output
              </div>
              <div className="px-3 py-2 bg-gray-50 text-xs overflow-x-auto">
                {isCodeInterpreter ? (
                  <CodeInterpreterOutput result={toolResult.result} />
                ) : (
                  <pre className="font-mono text-gray-700 whitespace-pre-wrap">
                    {JSON.stringify(toolResult.result, null, 2)}
                  </pre>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function CodeInterpreterOutput({ result }: { result: Record<string, unknown> }) {
  const stdout = (result.stdout as string) || "";
  const stderr = (result.stderr as string) || "";
  const error = (result.error as string) || (result.message as string) || "";

  if (error && !stdout) {
    return <pre className="font-mono text-red-600 whitespace-pre-wrap">{error}</pre>;
  }

  return (
    <div className="space-y-1">
      {stdout && (
        <pre className="font-mono text-gray-800 whitespace-pre-wrap">{stdout}</pre>
      )}
      {stderr && (
        <pre className="font-mono text-orange-600 whitespace-pre-wrap text-[11px]">{stderr}</pre>
      )}
    </div>
  );
}
