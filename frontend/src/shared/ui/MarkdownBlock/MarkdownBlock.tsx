import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import "./MarkdownBlock.css";

const markdownComponents: Components = {
  table({ node: _node, children, ...props }) {
    return (
      <div className="markdown-table-wrap">
        <table {...props}>{children}</table>
      </div>
    );
  },
};

export function MarkdownBlock({ content }: { content: string }) {
  const normalized = content.trim();
  if (!normalized) return null;

  return (
    <div className="markdown-block">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
        {normalized}
      </ReactMarkdown>
    </div>
  );
}
