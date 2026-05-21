import type { IconComponent } from "../../../shared/types";
import { PlaceholderPage } from "../../../shared/ui/PlaceholderPage/PlaceholderPage";

export function AdminResultsPage({ icon, title }: { icon: IconComponent; title: string }) {
  return (
    <PlaceholderPage
      icon={icon}
      title={title}
      description="스냅샷 결과 조회 테이블과 drill-down 화면이 연결될 예정입니다."
      chips={["create", "update", "delete", "audit"]}
    />
  );
}
