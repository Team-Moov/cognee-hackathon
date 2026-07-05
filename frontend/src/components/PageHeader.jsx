import React from "react";

export default function PageHeader({ title, subtitle }) {
  return (
    <div className="mb-4">
      <div>
        <h1 className="font-title text-5xl font-semibold tracking-tight text-slate-100 sm:text-6xl">
          {title}
        </h1>
        {subtitle ? (
          <p className="mt-3 text-sm leading-7 text-slate-300 tracking-wide">{subtitle}</p>
        ) : null}
      </div>
    </div>
  );
}
