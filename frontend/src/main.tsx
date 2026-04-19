import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import "./styles/global.css";

const queryClient = new QueryClient();
const appBasePath = import.meta.env.VITE_APP_BASE_PATH ?? "/";
const routerBasePath =
  appBasePath !== "/" && appBasePath.endsWith("/")
    ? appBasePath.slice(0, -1)
    : appBasePath;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter basename={routerBasePath}>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
