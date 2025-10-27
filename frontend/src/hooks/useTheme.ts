import { useCallback, useEffect, useState } from "react";

type Theme = "light" | "dark";

const STORAGE_KEY = "compareset-theme";

const prefersDarkScheme = () =>
  window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;

const useTheme = () => {
  const [theme, setTheme] = useState<Theme>(() => {
    if (typeof window === "undefined") {
      return "light";
    }

    const storedTheme = window.localStorage.getItem(STORAGE_KEY) as Theme | null;
    if (storedTheme === "light" || storedTheme === "dark") {
      return storedTheme;
    }

    return prefersDarkScheme() ? "dark" : "light";
  });

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = theme;
    window.localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  useEffect(() => {
    if (!window.matchMedia) {
      return;
    }

    const listener = (event: MediaQueryListEvent) => {
      setTheme(event.matches ? "dark" : "light");
    };

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    media.addEventListener("change", listener);

    return () => media.removeEventListener("change", listener);
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme((current) => (current === "light" ? "dark" : "light"));
  }, []);

  return { theme, toggleTheme };
};

export type { Theme };
export default useTheme;
