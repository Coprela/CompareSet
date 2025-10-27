import { Theme } from "../hooks/useTheme";

type ThemeToggleProps = {
  theme: Theme;
  onToggle: () => void;
};

const ThemeToggle: React.FC<ThemeToggleProps> = ({ theme, onToggle }) => (
  <button
    type="button"
    className="theme-toggle"
    onClick={onToggle}
    aria-label={`Activate ${theme === "light" ? "dark" : "light"} mode`}
    title={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
  >
    <span aria-hidden>{theme === "light" ? "🌞" : "🌙"}</span>
  </button>
);

export default ThemeToggle;
