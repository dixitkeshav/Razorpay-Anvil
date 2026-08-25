import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import IncidentDetail from "./pages/IncidentDetail";
import OpsOverview from "./pages/OpsOverview";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<OpsOverview />} />
        <Route path="/incidents/:incidentIndex" element={<IncidentDetail />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
