import { ImageResponse } from "next/og";
import { brand } from "../data/content";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(120deg, #4f46e5 0%, #0ea5e9 100%)",
          color: "#ffffff",
          fontFamily: "sans-serif",
        }}
      >
        <div style={{ fontSize: 96, marginBottom: 24, display: "flex" }}>🧠</div>
        <div style={{ fontSize: 72, fontWeight: 700, display: "flex" }}>{brand.name}</div>
        <div style={{ fontSize: 36, marginTop: 20, opacity: 0.9, display: "flex" }}>
          {brand.tagline}
        </div>
      </div>
    ),
    { ...size },
  );
}
