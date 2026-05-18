import { Shield } from "lucide-react";
import { WorkflowPage } from "./WorkflowPage";

export function AccessDeniedPage() {
  return <WorkflowPage icon={Shield} title="접근 권한 없음" />;
}
