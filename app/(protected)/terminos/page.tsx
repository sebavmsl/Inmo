import { requireSessionProfile } from "@/lib/auth/session";
import { AceptarTerminosForm } from "@/components/auth/AceptarTerminosForm";
import { TERMINOS_TEXTO } from "@/lib/legal/terminos";

/**
 * Puerto de la pestaña "terminos" de app.py (líneas ~7660-7681) y del
 * bloque de aceptación obligatoria (líneas ~1250-1271). El texto legal es
 * el mismo, movido a lib/legal/terminos.ts para no mezclarlo con JSX.
 */
export default async function TerminosPage() {
  const perfil = await requireSessionProfile();

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="mb-1 text-xl font-semibold text-brand-900">
        Términos y Condiciones de Uso
      </h1>

      {perfil.terminosAceptados ? (
        <p className="mb-4 rounded-md bg-green-50 px-3 py-2 text-sm text-green-700">
          ✅ Ya aceptaste los Términos y Condiciones.
        </p>
      ) : (
        <p className="mb-4 rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-700">
          ⚠️ Términos pendientes de aceptación.
        </p>
      )}

      <div className="max-h-[400px] overflow-y-auto rounded-lg border border-brand-100 bg-white p-4 text-sm leading-relaxed text-brand-800 whitespace-pre-wrap">
        {TERMINOS_TEXTO}
      </div>

      {!perfil.terminosAceptados && (
        <div className="mt-4">
          <AceptarTerminosForm />
        </div>
      )}
    </div>
  );
}
