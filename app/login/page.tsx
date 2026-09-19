import { LoginForm } from "@/components/auth/LoginForm";
import { APP_VERSION } from "@/lib/version";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-brand-50 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-semibold text-brand-900">
            Sistema de Gestión Inmobiliaria
          </h1>
          <p className="mt-1 text-sm text-brand-600">Ingresá con tu usuario para continuar</p>
        </div>

        <div className="rounded-xl border border-brand-100 bg-white p-6 shadow-sm">
          <LoginForm />
        </div>

        <p className="mt-6 text-center text-xs text-brand-400">
          Solicitá tu acceso a contacto@controlz.net.ar · {APP_VERSION}
        </p>
      </div>
    </div>
  );
}
