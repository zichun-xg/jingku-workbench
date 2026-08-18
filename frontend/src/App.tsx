import { NavLink, Route, Routes } from "react-router-dom";
import BenchPage from "./pages/BenchPage";
import InspirationPage from "./pages/InspirationPage";
import SettingsPage from "./pages/SettingsPage";
import VideosPage from "./pages/VideosPage";

export default function App() {
  return (
    <div className="app">
      <header className="mast">
        <div className="brand">镜库</div>
        <nav className="nav">
          <NavLink to="/" end>
            片库
          </NavLink>
          <NavLink to="/inspiration">灵感</NavLink>
          <NavLink to="/settings">设置</NavLink>
        </nav>
      </header>
      <div className="stage">
        <Routes>
          <Route path="/" element={<VideosPage />} />
          <Route path="/bench/:id" element={<BenchPage />} />
          <Route path="/inspiration" element={<InspirationPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </div>
    </div>
  );
}
