"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Copy, Check } from "lucide-react";
import { useState, useCallback } from "react";

interface MarkdownRendererProps {
  content: string;
}

function CopyButton({ code }: { code: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [code]);

  return (
    <button
      onClick={handleCopy}
      className="absolute top-2 right-2 p-1 rounded bg-gray-200 hover:bg-gray-300 text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity"
      title="Copy code"
    >
      {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
    </button>
  );
}

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || "");
          const codeString = String(children).replace(/\n$/, "");

          if (match) {
            return (
              <div className="relative group my-2 rounded-md overflow-hidden border border-gray-200">
                <div className="flex items-center justify-between bg-gray-100 px-3 py-1 text-[11px] font-medium text-gray-500 border-b border-gray-200">
                  <span>{match[1]}</span>
                </div>
                <CopyButton code={codeString} />
                <SyntaxHighlighter
                  style={oneLight}
                  language={match[1]}
                  PreTag="div"
                  customStyle={{ margin: 0, fontSize: "13px", background: "#fafafa" }}
                >
                  {codeString}
                </SyntaxHighlighter>
              </div>
            );
          }
          return (
            <code className="bg-gray-200 text-gray-800 px-1 py-0.5 rounded text-[13px]" {...props}>
              {children}
            </code>
          );
        },
        p({ children }) {
          return <p className="mb-2 last:mb-0">{children}</p>;
        },
        ul({ children }) {
          return <ul className="list-disc ml-4 mb-2">{children}</ul>;
        },
        ol({ children }) {
          return <ol className="list-decimal ml-4 mb-2">{children}</ol>;
        },
        li({ children }) {
          return <li className="mb-0.5">{children}</li>;
        },
        h1({ children }) {
          return <h1 className="text-lg font-bold mb-2">{children}</h1>;
        },
        h2({ children }) {
          return <h2 className="text-base font-bold mb-1.5">{children}</h2>;
        },
        h3({ children }) {
          return <h3 className="text-sm font-bold mb-1">{children}</h3>;
        },
        table({ children }) {
          return (
            <div className="overflow-x-auto my-2">
              <table className="min-w-full border-collapse border border-gray-300 text-xs">
                {children}
              </table>
            </div>
          );
        },
        th({ children }) {
          return <th className="border border-gray-300 bg-gray-100 px-2 py-1 text-left font-medium">{children}</th>;
        },
        td({ children }) {
          return <td className="border border-gray-300 px-2 py-1">{children}</td>;
        },
        blockquote({ children }) {
          return <blockquote className="border-l-3 border-gray-300 pl-3 italic text-gray-600 my-2">{children}</blockquote>;
        },
        a({ href, children }) {
          return (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
              {children}
            </a>
          );
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}
