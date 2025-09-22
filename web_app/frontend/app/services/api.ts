// This file handles API requests with token-based authentication
const API_URL = process.env.NEXT_PUBLIC_API_URL

export async function apiFetch(endpoint: string, options: RequestInit = {}) {
  const token = localStorage.getItem("access")

  const res = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      ...(options.headers || {}),
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
  })

  if (res.status === 401) {
    // TODO: refresh token flow
  }

  return res.json()
}