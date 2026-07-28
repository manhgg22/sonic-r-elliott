import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider, theme } from "antd";
import "@fontsource/be-vietnam-pro/400.css";
import "@fontsource/be-vietnam-pro/500.css";
import "@fontsource/be-vietnam-pro/600.css";
import "@fontsource/be-vietnam-pro/700.css";
import App from "./app/App";
import "./styles/base.css";
import "./styles/antd-overrides.css";
import "./styles/typography.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: "#49d8ed",
          colorInfo: "#49d8ed",
          colorSuccess: "#43d99b",
          colorWarning: "#f5b942",
          colorError: "#ff7185",
          colorBgBase: "#090c16",
          colorBgContainer: "#111625",
          colorBgElevated: "#151b2d",
          colorBorder: "#273049",
          colorText: "#f2f5fb",
          colorTextSecondary: "#7f8aa3",
          borderRadius: 8,
          fontFamily: "\"Be Vietnam Pro\", Arial, sans-serif",
          controlHeight: 34
        },
        components: {
          Button: { primaryShadow: "none", borderRadius: 8 },
          Input: { activeShadow: "0 0 0 2px rgba(73,216,237,.13)" },
          Select: { optionSelectedBg: "#1a3040" },
          Table: { headerBg: "#151b2d", rowHoverBg: "#182036" }
        }
      }}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>
);
