export function StatusMessage({ message }: { message: string | null }) {
  if (!message) return null;
  return <div className={messageClassName(message)}>{message}</div>;
}

function messageClassName(message: string) {
  const isSuccess =
    message.includes("저장되었습니다") ||
    message.includes("완료되었습니다") ||
    message.includes("연결됩니다");
  return `admin-message ${isSuccess ? "" : "error"}`.trim();
}
