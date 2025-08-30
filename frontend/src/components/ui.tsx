import React from "react";

export function classNames(...xs: Array<string | false | null | undefined>) {
  return xs.filter(Boolean).join(" ");
}

export type Tone = "neutral" | "good" | "warn" | "bad" | "primary";

type PillProps = { children: React.ReactNode; tone?: Tone };
export const Pill: React.FC<PillProps> = ({ children, tone = "neutral" }) => (
  <span
    className={classNames(
      "inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset",
      tone === "good" && "bg-green-50 text-green-700 ring-green-200",
      tone === "warn" && "bg-yellow-50 text-yellow-700 ring-yellow-200",
      tone === "bad" && "bg-red-50 text-red-700 ring-red-200",
      tone === "primary" && "bg-indigo-50 text-indigo-700 ring-indigo-200",
      tone === "neutral" && "bg-slate-100 text-slate-700 ring-slate-200"
    )}
  >
    {children}
  </span>
);

type CardProps = { title?: React.ReactNode; subtitle?: React.ReactNode; children?: React.ReactNode; footer?: React.ReactNode; actions?: React.ReactNode };
export const Card: React.FC<CardProps> = ({ title, subtitle, children, footer, actions }) => (
  <div className="rounded-2xl bg-white p-5 shadow-sm ring-1 ring-slate-200/50">
    <div className="mb-4 flex items-start justify-between gap-4">
      <div>
        {title && <h3 className="text-base font-semibold text-slate-900">{title}</h3>}
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions}
    </div>
    <div className="space-y-4">{children}</div>
    {footer && <div className="mt-4 border-t pt-4 text-sm text-slate-500">{footer}</div>}
  </div>
);

type TextAreaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement>;
export const TextArea: React.FC<TextAreaProps> = (props) => (
  <textarea
    {...props}
    className={classNames(
      "w-full rounded-xl border-slate-300 bg-white p-3 text-sm shadow-sm outline-none transition",
      "focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/50",
      props.className || ""
    )}
  />
);

type InputProps = React.InputHTMLAttributes<HTMLInputElement>;
export const Input: React.FC<InputProps> = (props) => (
  <input
    {...props}
    className={classNames(
      "w-full rounded-xl border-slate-300 bg-white px-3 py-2 text-sm shadow-sm outline-none transition",
      "focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/50",
      props.className || ""
    )}
  />
);

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & { loading?: boolean; tone?: "primary" | "ghost" | "danger" };
export const Button: React.FC<ButtonProps> = ({ children, loading, tone = "primary", ...rest }) => (
  <button
    {...rest}
    disabled={loading || rest.disabled}
    className={classNames(
      "inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold shadow-sm transition-colors",
      "disabled:cursor-not-allowed disabled:opacity-50",
      tone === "primary" && "bg-indigo-600 text-black hover:bg-indigo-700",
      tone === "ghost" && "bg-slate-100 text-black text-slate-800 hover:bg-slate-200",
      tone === "danger" && "bg-rose-600 text-black hover:bg-rose-700",
      rest.className || ""
    )}
  >
    {loading && (
      <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" aria-hidden>
        <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" strokeWidth="4" opacity=".2" />
        <path d="M22 12a10 10 0 0 1-10 10" fill="none" stroke="currentColor" strokeWidth="4" />
      </svg>
    )}
    {children}
  </button>
);