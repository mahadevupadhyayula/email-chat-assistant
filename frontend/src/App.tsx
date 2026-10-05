import { useEffect, useState } from "react";

type ApiStatus = "checking" | "ok" | "unreachable";

// Temporary: the only allowed fetch outside lib/. Replaced in Unit 04.
export default function App() {
  const [status, setStatus] = useState<ApiStatus>("checking");

  useEffect(() => {
    fetch("/api/health")
      .then((res) => res.json() as Promise<{ status: string }>)
      .then((body) => setStatus(body.status === "ok" ? "ok" : "unreachable"))
      .catch(() => setStatus("unreachable"));
  }, []);

  return (
    <main>
      <h1>Email Assistant Chat</h1>
      <p>API: {status}</p>
    </main>
  );
}
