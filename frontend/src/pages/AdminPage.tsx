import type { IconComponent } from "../types";

export function AdminPage({ icon: Icon, title }: { icon: IconComponent; title: string }) {
  return (
    <section className="blank-page">
      <Icon size={34} />
      <h1>{title}</h1>
      <p>관리 API와 테이블 UI를 연결할 빈 페이지입니다.</p>
      <div className="placeholder-toolbar">
        <span>create</span>
        <span>update</span>
        <span>delete</span>
        <span>audit</span>
      </div>
    </section>
  );
}
