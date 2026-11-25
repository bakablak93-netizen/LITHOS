import React from "react";

const HYPHEN_SYMBOL_MAP: Record<string, [string, string]> = {
  "ро-вп": ["ρ", "вп"],
  "ро-в": ["ρ", "в"],
  "ро-к": ["ρ", "к"],
  "ро-п": ["ρ", "п"],
  "ро-ф": ["ρ", "ф"],
  "альфа-СП": ["α", "СП"],
  "Р-п": ["P", "п"],
  "P-п": ["P", "п"],
  "Р-н": ["P", "н"],
  "P-н": ["P", "н"],
  "К-п": ["K", "п"],
  "K-п": ["K", "п"],
  "К-в": ["K", "в"],
  "K-в": ["K", "в"],
  "К-нг": ["K", "нг"],
  "K-нг": ["K", "нг"],
  "R-к": ["R", "к"],
  "r-с": ["r", "с"],
  "p-к": ["p", "к"],
  "p-с": ["p", "с"],
};

const TOKEN_RE =
  /(ро-вп|ро-в|ро-к|ро-п|ро-ф|альфа-СП|Р-п|P-п|Р-н|P-н|К-п|K-п|К-в|K-в|К-нг|K-нг|R-к|r-с|p-к|p-с|[A-Za-zА-Яа-яЁёαβγρΔκμϕφ]+_[A-Za-zА-Яа-яЁё0-9]+|[A-Za-zА-Яа-яЁёαβγρΔκμϕφ]+\^[A-Za-z0-9]+)/g;

export const MathText: React.FC<{ text: string; className?: string }> = ({ text, className }) => {
  if (!text) return null;
  const parts = text.split(TOKEN_RE);

  return (
    <span className={className}>
      {parts.map((part, idx) => {
        if (!part) return null;

        if (HYPHEN_SYMBOL_MAP[part]) {
          const [base, sub] = HYPHEN_SYMBOL_MAP[part];
          return (
            <span key={idx} className="whitespace-nowrap font-medium text-slate-200">
              {base}
              <sub className="text-[0.72em] leading-none">{sub}</sub>
            </span>
          );
        }

        const subIdx = part.indexOf("_");
        if (subIdx > 0 && subIdx < part.length - 1) {
          const base = part.slice(0, subIdx);
          const sub = part.slice(subIdx + 1);
          return (
            <span key={idx} className="whitespace-nowrap">
              {base}
              <sub className="text-[0.72em] leading-none">{sub}</sub>
            </span>
          );
        }

        const supIdx = part.indexOf("^");
        if (supIdx > 0 && supIdx < part.length - 1) {
          const base = part.slice(0, supIdx);
          const sup = part.slice(supIdx + 1);
          return (
            <span key={idx} className="whitespace-nowrap">
              {base}
              <sup className="text-[0.72em] leading-none">{sup}</sup>
            </span>
          );
        }

        return <React.Fragment key={idx}>{part}</React.Fragment>;
      })}
    </span>
  );
};

/** Превращает простые LaTeX-формулы из курса в чистый типографический вид с нижними/верхними индексами. */
export function cleanLatexToText(latex: string): string {
  if (!latex) return "";
  let s = latex;
  // Избавляемся от \text{...} и \operatorname{...}
  s = s.replace(/\\text\{([^}]*)\}/g, "$1");
  s = s.replace(/\\operatorname\{([^}]*)\}/g, "$1");
  s = s.replace(/\\vec\{([^}]*)\}/g, "$1");
  // \frac{A}{B} -> (A) / (B) или A / B для простых выражений
  for (let i = 0; i < 3; i++) {
    s = s.replace(/\\frac\{([^{}]+)\}\{([^{}]+)\}/g, (_, num: string, den: string) => {
      const n = num.includes(" ") || num.includes("+") || num.includes("-") ? `(${num})` : num;
      const d = den.includes(" ") || den.includes("+") || den.includes("-") ? `(${den})` : den;
      return `${n} / ${d}`;
    });
  }
  s = s
    .replace(/\\rho/g, "ρ")
    .replace(/\\alpha/g, "α")
    .replace(/\\kappa/g, "κ")
    .replace(/\\mu/g, "μ")
    .replace(/\\pi/g, "π")
    .replace(/\\phi/g, "φ")
    .replace(/\\Delta/g, "Δ")
    .replace(/\\nabla/g, "∇")
    .replace(/\\cdot/g, "·")
    .replace(/\\quad/g, "   |   ")
    .replace(/\\lg/g, "lg")
    .replace(/\\ln/g, "ln")
    .replace(/\\log_\{10\}/g, "log₁₀")
    .replace(/\\sqrt\{([^}]+)\}/g, "√($1)")
    .replace(/_\{([^}]+)\}/g, "_$1")
    .replace(/\^\{([^}]+)\}/g, "^$1")
    .replace(/\\/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return s;
}
