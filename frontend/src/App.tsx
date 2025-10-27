import CompareSetViewer from "./components/CompareSetViewer";
import useTheme from "./hooks/useTheme";

const App: React.FC = () => {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className={`app theme-${theme}`}>
      <CompareSetViewer theme={theme} onToggleTheme={toggleTheme} />
    </div>
  );
};

export default App;
