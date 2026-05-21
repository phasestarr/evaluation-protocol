import { Shield } from "lucide-react";
import { PlaceholderPage } from "../../shared/ui/PlaceholderPage/PlaceholderPage";

export function AccessDeniedPage() {
  return (
    <PlaceholderPage
      icon={Shield}
      title="접근 권한 없음"
      description="현재 계정으로는 이 화면을 열 수 없습니다."
      chips={["user", "manager", "admin"]}
    />
  );
}
