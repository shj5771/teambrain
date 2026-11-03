import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(120deg, #4f46e5 0%, #0ea5e9 100%)",
          borderRadius: 7,
        }}
      >
        <span style={{ fontSize: 20 }}>🧠</span>
      </div>
    ),
    { ...size },
  );
}
