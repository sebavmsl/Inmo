"use client";

import { useState } from "react";
import { useFormStatus } from "react-dom";
import { aceptarTerminos } from "@/app/(protected)/terminos/actions";

function BotonContinuar({ disabled }: { disabled: boolean }) {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={disabled || pending}
      className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {pending ? "Guardando..." : "Continuar →"}
    </button>
  );
}

export function AceptarTerminosForm() {
  const [acepto, setAcepto] = useState(false);

  return (
    <form action={aceptarTerminos} className="space-y-3">
      <label className="flex items-start gap-2 text-sm text-brand-800">
        <input
          type="checkbox"
          checked={acepto}
          onChange={(e) => setAcepto(e.target.checked)}
          className="mt-0.5"
        />
        He leído y acepto los Términos y Condiciones de Uso
      </label>
      <BotonContinuar disabled={!acepto} />
    </form>
  );
}
