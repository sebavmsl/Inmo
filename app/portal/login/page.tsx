"use client";

import { useFormState, useFormStatus } from "react-dom";
import { useSearchParams } from "next/navigation";
import { loginPortal, type LoginPortalState } from "@/app/portal/login/actions";

const initialState: LoginPortalState = { error: null };

function BotonIngresar() {
  const { pending } = useFormStatus();
  return (
    <button
      type="submit"
      disabled={pending}
      className="w-full rounded-lg bg-brand-600 px-4 py-2.5 font-medium text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {pending ? "Ingresando..." : "Ingresar"}
    </button>
  );
}

export default function PortalLoginPage() {
  const [state, formAction] = useFormState(loginPortal, initialState);
  const searchParams = useSearchParams();
  const motivo = searchParams.get("motivo");

  return (
    <div className="flex min-h-screen items-center justify-center bg-brand-50 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-semibold text-brand-900">Portal del Inquilino</h1>
          <p className="mt-1 text-sm text-brand-600">Consultá tu contrato y tus pagos</p>
        </div>

        {motivo === "inactividad" && (
          <p className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-center text-xs text-amber-700">
            Se cerró tu sesión por inactividad. Volvé a ingresar para continuar.
          </p>
        )}

        <div className="rounded-xl border border-brand-100 bg-white p-6 shadow-sm">
          <form action={formAction} className="space-y-4">
            <div>
              <label htmlFor="email" className="mb-1 block text-sm font-medium text-brand-800">
                Email
              </label>
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                className="w-full rounded-lg border border-brand-200 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
              />
            </div>
            <div>
              <label htmlFor="password" className="mb-1 block text-sm font-medium text-brand-800">
                Contraseña
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                className="w-full rounded-lg border border-brand-200 px-3 py-2 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
              />
            </div>
            {state.error && (
              <p role="alert" className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
                {state.error}
              </p>
            )}
            <BotonIngresar />
          </form>
        </div>
      </div>
    </div>
  );
}
