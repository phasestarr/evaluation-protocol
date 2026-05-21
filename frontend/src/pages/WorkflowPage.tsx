import type { IconComponent } from "../types";

export function WorkflowPage({ icon: Icon, title }: { icon: IconComponent; title: string }) {
  return (
    <section className="blank-page">
      <Icon size={34} />
      <h1>{title}</h1>
      <p>평가 입력 폼이 들어갈 영역입니다.</p>
      <div className="placeholder-toolbar">
        <span>not_started</span>
        <span>in_progress</span>
        <span>submitted</span>
        <span>finalized</span>
      </div>
    </section>
  );
}
