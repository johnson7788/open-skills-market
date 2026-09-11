import { createContext, useContext, useEffect, useState } from "react";
import { fetchMe, getToken, loginApi, logoutApi, setToken } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      setLoading(false);
      return;
    }
    fetchMe()
      .then((d) => setUser(d.user))
      .catch(() => setToken(""))
      .finally(() => setLoading(false));
  }, []);

  async function login(username) {
    const d = await loginApi(username);
    setToken(d.token);
    setUser(d.user);
    return d.user;
  }

  function logout() {
    logoutApi();
    setToken("");
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
