// Appearance preference: follow the system, or force light/dark.

export type Theme = "system" | "light" | "dark";
const THEME_KEY = "bos.theme";

export function storedTheme(): Theme {
  try {
    return (localStorage.getItem(THEME_KEY) as Theme) || "system";
  } catch {
    return "system";
  }
}

export function applyTheme(theme: Theme = storedTheme()): Theme {
  if (theme === "system") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", theme);
  return theme;
}

export function saveTheme(theme: Theme): void {
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {
    /* storage unavailable — applies for this visit only */
  }
  applyTheme(theme);
}
