import React from "react";
import { FormulaSpec } from "../types";

interface FormulaCardProps {
  formula: FormulaSpec;
}

export const FormulaCard: React.FC<FormulaCardProps> = ({ formula }) => {
  return (
    <div
      style={{
        backgroundColor: "#111827",
        border: "1px solid rgba(148, 163, 184, 0.25)",
        borderLeft: "4px solid #F59E0B",
        borderRadius: 14,
        padding: "18px 20px",
        fontFamily: "Inter, system-ui, sans-serif",
      }}
    >
      <div style={{ fontSize: 15, fontWeight: 700, color: "#F59E0B", marginBottom: 8 }}>
        {formula.title}
      </div>
      <div
        style={{
          fontFamily: "IBM Plex Mono, monospace",
          fontSize: 22,
          color: "#F8FAFC",
          backgroundColor: "#0B1120",
          padding: "12px 14px",
          borderRadius: 8,
          marginBottom: 10,
          wordBreak: "break-word",
        }}
      >
        {formula.latex}
      </div>
      {formula.western_latex && (
        <div style={{ fontSize: 14, color: "#38BDF8", marginBottom: 8 }}>
          West: <span style={{ fontFamily: "IBM Plex Mono, monospace" }}>{formula.western_latex}</span>
        </div>
      )}
      {formula.variables && Object.keys(formula.variables).length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 4, marginTop: 6 }}>
          {Object.entries(formula.variables).map(([k, v]) => (
            <div key={k} style={{ fontSize: 14, color: "#CBD5E1" }}>
              <strong style={{ color: "#F8FAFC" }}>{k}</strong> — {v}
            </div>
          ))}
        </div>
      )}
      {formula.source_ref && (
        <div style={{ fontSize: 12, color: "#64748B", marginTop: 10 }}>{formula.source_ref}</div>
      )}
    </div>
  );
};
