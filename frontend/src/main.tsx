import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider, theme } from "antd";
import "@fontsource/be-vietnam-pro/400.css";
import "@fontsource/be-vietnam-pro/500.css";
import "@fontsource/be-vietnam-pro/600.css";
import "@fontsource/be-vietnam-pro/700.css";
import App from "./App";
import "./styles.css";
import "./antd-overrides.css";
import "./typography.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider
      theme={{
        algorithm: theme.darkAlgorithm,
        token: {
          colorPrimary: "#19d9ec",
          colorInfo: "#19d9ec",
          colorSuccess: "#35e48c",
          colorWarning: "#ffbe3f",
          colorError: "#ff6b76",
          colorBgBase: "#071014",
          colorBgContainer: "#0b161a",
          colorBgElevated: "#101c20",
          colorBorder: "#223238",
          colorText: "#d9e5e7",
          colorTextSecondary: "#71868e",
          borderRadius: 2,
          fontFamily: "\"Be Vietnam Pro\", Arial, sans-serif",
          controlHeight: 30
        },
        components: {
          Button: { primaryShadow: "none", borderRadius: 2 },
          Input: { activeShadow: "0 0 0 1px rgba(25,217,236,.2)" },
          Select: { optionSelectedBg: "#102e35" },
          Table: { headerBg: "#0f1c20", rowHoverBg: "#102328" }
        }
      }}
    >
      <App />
    </ConfigProvider>
  </React.StrictMode>
);
