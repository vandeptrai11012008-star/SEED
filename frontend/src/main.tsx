import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import OpsApp from "./ops/OpsApp";
import "./styles.css";

const params = new URLSearchParams(window.location.search);
const showOps = params.get("ops") === "1" || params.get("ops") === "true";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    {showOps ? <OpsApp /> : <App />}
  </React.StrictMode>
);
