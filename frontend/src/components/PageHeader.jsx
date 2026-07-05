import React from "react";

export default function PageHeader({ title, subtitle }) {
  return (
    <div className="mb-6 border-b border-line/60 pb-5">
      <div className="space-y-2">
        <h1 className="font-title text-3xl font-semibold tracking-[-0.02em] text-espresso sm:text-4xl">
          {title}
        </h1>
        {subtitle ? (
          <p className="max-w-2xl text-sm leading-6 text-muted">{subtitle}</p>
        ) : null}
      </div>
      <div className="mt-4 h-px w-full bg-gradient-to-r from-line via-line/50 to-transparent" />
    </div>
  );
}
