import React, { createContext, useContext } from "react";

/**
 * Auth is intentionally removed from the UI flow.
 * The app now opens directly into the dashboard and uses a default local user.
 */

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const user = { name: "Researcher", email: "researcher@local" };
  const ready = true;

  function signup() {
    return user;
  }

  function login() {
    return user;
  }

  function logout() {
    return undefined;
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
