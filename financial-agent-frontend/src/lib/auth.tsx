"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { authApi, clearStoredToken, getStoredToken, usersApi } from "@/lib/api";
import type { UserProfile } from "@/lib/types";

interface AuthContextValue {
  profile: UserProfile | null;
  loading: boolean;
  error: string | null;
  refreshProfile: () => Promise<UserProfile | null>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  profile: null,
  loading: false,
  error: null,
  refreshProfile: async () => null,
  logout: () => undefined,
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshProfile = useCallback(async () => {
    if (!getStoredToken()) {
      setProfile(null);
      setLoading(false);
      return null;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await usersApi.me();
      setProfile(data);
      return data;
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load profile.");
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(() => {
    void authApi.logout().catch(() => undefined);
    clearStoredToken();
    setProfile(null);
    window.location.href = "/login";
  }, []);

  useEffect(() => {
    void refreshProfile();
  }, [refreshProfile]);

  const value = useMemo(
    () => ({ profile, loading, error, refreshProfile, logout }),
    [profile, loading, error, refreshProfile, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  return useContext(AuthContext);
}
