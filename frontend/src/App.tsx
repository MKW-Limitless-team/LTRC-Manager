import { Navigate, Route, Routes } from "react-router-dom";

import { AppPage } from "./pages/AppPage";
import { LoginPage } from "./pages/LoginPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/app" element={<AppPage />} />
      <Route path="*" element={<Navigate to="/app" replace />} />
    </Routes>
  );
}
