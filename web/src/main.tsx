import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import Ask from "./pages/Ask";
import IncidentDetail from "./pages/IncidentDetail";
import Incidents from "./pages/Incidents";
import Interventions from "./pages/Interventions";
import Ledger from "./pages/Ledger";
import Merchants from "./pages/Merchants";
import Overview from "./pages/Overview";
import Policies from "./pages/Policies";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Overview />} />
        <Route path="/incidents" element={<Incidents />} />
        <Route path="/incidents/:incidentIndex" element={<IncidentDetail />} />
        <Route path="/interventions" element={<Interventions />} />
        <Route path="/ledger" element={<Ledger />} />
        <Route path="/merchants" element={<Merchants />} />
        <Route path="/policies" element={<Policies />} />
        <Route path="/ask" element={<Ask />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
