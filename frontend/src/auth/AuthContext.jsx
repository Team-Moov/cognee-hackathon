import React, { createContext, useContext, useEffect, useState } from "react";

/**
 * Lightweight client-side auth for the Groundhog demo.
 * Accounts + session live in localStorage — no backend required. This is a
 * demo-grade gate (not real security); swap for a real auth provider later.
 */

const USERS_KEY = "gh_users";
const SESSION_KEY = "gh_session";

const AuthContext = createContext(null);

function loadUsers() {
  try {
    return JSON.parse(localStorage.getItem(USERS_KEY)) || {};
  } catch {
    return {};
  }
}

function saveUsers(users) {
  localStorage.setItem(USERS_KEY, JSON.stringify(users));
}

// Trivial, non-cryptographic obfuscation — good enough for a local demo.
function scramble(s) {
  try {
    return btoa(unescape(encodeURIComponent(s)));
  } catch {
    return s;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    try {
      const s = JSON.parse(localStorage.getItem(SESSION_KEY));
      if (s?.email) setUser(s);
    } catch {
      /* no session */
    }
    setReady(true);
  }, []);

  function signup({ name, email, password }) {
    email = (email || "").trim().toLowerCase();
    name = (name || "").trim();
    if (!name || !email || !password) throw new Error("All fields are required.");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new Error("Enter a valid email address.");
    if (password.length < 6) throw new Error("Password must be at least 6 characters.");

    const users = loadUsers();
    if (users[email]) throw new Error("An account with this email already exists.");

    users[email] = { name, email, pw: scramble(password) };
    saveUsers(users);

    const session = { name, email };
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    setUser(session);
    return session;
  }

  function login({ email, password }) {
    email = (email || "").trim().toLowerCase();
    if (!email || !password) throw new Error("Enter your email and password.");

    const users = loadUsers();
    const record = users[email];
    if (!record || record.pw !== scramble(password)) {
      throw new Error("Incorrect email or password.");
    }

    const session = { name: record.name, email: record.email };
    localStorage.setItem(SESSION_KEY, JSON.stringify(session));
    setUser(session);
    return session;
  }

  function logout() {
    localStorage.removeItem(SESSION_KEY);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, ready, signup, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
