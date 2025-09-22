// This file handles user authentication (login, logout, token storage)

const API_URL = process.env.NEXT_PUBLIC_API_URL

export async function login(username: string, password: string) {
  const res = await fetch(`${API_URL}/api/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  })

  if (!res.ok) throw new Error("Login failed")

  const data = await res.json()
  localStorage.setItem("access", data.access)
  localStorage.setItem("refresh", data.refresh)
  return data
}
