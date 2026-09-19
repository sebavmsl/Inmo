import { requireInquilinoContratos } from "@/lib/inquilino/session";
import { logoutPortal } from "@/app/portal/login/actions";

export default async function PortalLayout({ children }: { children: React.ReactNode }) {
  const contratos = await requireInquilinoContratos();

  return (
    <div className="min-h-screen bg-brand-50">
      <header className="border-b border-brand-100 bg-white px-4 py-3">
        <div className="mx-auto flex max-w-3xl items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-brand-900">Portal del Inquilino</p>
            <p className="text-xs text-brand-500">{contratos[0]?.nombreCompleto}</p>
          </div>
          <nav className="flex items-center gap-4 text-sm text-brand-600">
            <a href="/portal/mi-cuenta" className="hover:underline">
              Mi Cuenta
            </a>
            <a href="/portal/subir-comprobante" className="hover:underline">
              Subir Comprobante
            </a>
            <a href="/portal/reclamos" className="hover:underline">
              Reclamos
            </a>
            <form action={logoutPortal}>
              <button type="submit" className="text-brand-400 hover:underline">
                Salir
              </button>
            </form>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-3xl p-4">{children}</main>
    </div>
  );
}
