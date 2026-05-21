export async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData;
  const headers = init?.body && !isFormData
    ? { "Content-Type": "application/json", ...(init.headers as Record<string, string> | undefined) }
    : init?.headers;
  let response: Response;
  try {
    response = await fetch(url, {
      credentials: "include",
      headers,
      ...init,
    });
  } catch {
    throw new Error("서버 응답을 받지 못했습니다. 네트워크 상태를 확인한 뒤 다시 시도해 주세요.");
  }
  if (!response.ok) {
    let message = `Request failed: ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) {
        message = body.detail;
      }
    } catch {
      // Keep the status-based message when the response has no JSON body.
    }
    throw new Error(message);
  }
  return response.json();
}
