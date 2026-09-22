/**
 * Versión del sistema v2. A partir de V2.001 se numera cada entrega de
 * archivos de la sesión de depuración (un incremento por cada tanda de
 * archivos entregada), reemplazando el esquema de numeración anterior
 * (V.201/V.202). Se muestra como sello fijo en el Sidebar y en el pie
 * del login.
 *
 * V2.001 — primera entrega de la depuración: bug de seguridad de
 * permisos no validados del lado del servidor (páginas + Server
 * Actions de planilla, pagos, carga, auxiliares, gastos, rendición;
 * rutas de PDF; envío de comprobante por WhatsApp), más el fix del link
 * roto de "Descargar comprobante" en el Portal del Inquilino.
 *
 * V2.002 — segunda entrega:
 *   - Módulo 5 (WhatsApp masivo, Planilla): 3 bugs corregidos (filtro de
 *     saldo, cochera faltante en el total, variables incompletas del
 *     template de WhatsApp).
 *   - Historial de Pagos: tabla ampliada a paridad con v1 + Reporte de
 *     Cobros (filtro por fecha/usuario, export CSV).
 *   - Rendición a Propietarios: reescrita — PDF horizontal, detalle de
 *     recibos, flag nueva "expensas administradas por el propietario".
 *   - Categorización transversal de conceptos (lib/conceptos/categorias.ts)
 *     — corrige un doble conteo en el total "Servicios" que arrastraban
 *     Historial de Pagos y Rendición.
 *   - Portal Inquilino: bandejas de staff para Comprobantes (aprobar/
 *     rechazar) y Reclamos (estado, respuesta, vínculo con Gastos) +
 *     fix de UX en el lado del inquilino (selector de contrato en vez
 *     de texto libre).
 *   - Panel de Gestión: migración masiva por CSV (importar/exportar
 *     Propiedades, Inquilinos, Contratos, Gastos; exportar además Pagos
 *     y Permisos), y selector de empresa agregado a Borrado en Bloque.
 *
 * V2.003 — tercera entrega:
 *   - Planilla de Contratos: para superadmin (que no tiene empresa_id
 *     propio) ya no se mezclan los contratos de todas las inmobiliarias
 *     en una sola tabla — por defecto se muestran los contratos sin
 *     empresa asignada ("huérfanos"), con un desplegable para elegir una
 *     empresa puntual. El PDF ("Descargar PDF") respeta el mismo filtro.
 *
 * V2.004 — cuarta entrega (fix de build de Vercel): 3 errores reales de
 *   `tsconfig.json` (`strict` + `noUncheckedIndexedAccess`) que rompían
 *   `npm run build` — no se pueden detectar sin compilar de verdad, y en
 *   este entorno de trabajo no hay acceso a npm install, así que no
 *   salieron hasta el build real en Vercel:
 *   - actions-csv.ts (exportarTablaCsv, pagos_historial): `Object.keys`
 *     sobre `filas[0]` sin confirmar que existe.
 *   - csv-migracion/columnas.ts (parsearFechaFlexible): grupos de
 *     captura de regex (`d`, `m`) usados sin fallback.
 *   - csv-migracion/parseCsv.ts: mismo patrón en el filtro de líneas en
 *     blanco (`f[0]`).
 *
 * V2.005 — quinta entrega (segundo fix de build de Vercel): otro error
 *   real de compilación en el mismo módulo (actions-csv.ts,
 *   exportarTablaCsv): el `.select()` de la rama de tablas importables
 *   arma la lista de campos en runtime (`camposSql.join(", ")`), y
 *   Supabase no puede validar esa lista contra el schema en tiempo de
 *   compilación — tipa el resultado como "GenericStringError" en vez de
 *   la fila real, así que el cast directo a `Record<string, unknown>`
 *   fallaba. Se corrige pasando por `unknown` primero. Se revisó el
 *   resto del proyecto buscando el mismo patrón (`.select()` con string
 *   armado en runtime) y no aparece en ningún otro lugar.
 *
 * V2.006 — sexto fix de build: bug preexistente (de antes de esta
 *   sesión, en EditarPropiedad.tsx y FormularioPropiedad.tsx) — el
 *   helper `input()` de cada formulario aceptaba como clave CUALQUIER
 *   campo del estado, incluido el único que es boolean (el checkbox de
 *   "expensas administradas por el propietario"), así que `datos[k]`
 *   tipaba "string | boolean" y `<input value=...>` no acepta boolean.
 *   Se corrige acotando el tipo de la clave a los campos de texto
 *   (Exclude<..., "expensasAdministradaPorPropietario">). Se revisó el
 *   resto del proyecto buscando el mismo patrón (helper de input con
 *   clave genérica sobre un estado de tipos mixtos) y no aparece en
 *   ningún otro lugar — el único otro caso similar (FormularioConceptos,
 *   Pagos) usa un estado con todos los campos `number`, sin este problema.
 *
 * V2.007 — cuarto fix de build: GestionUsuarios.tsx llama a
 *   actualizarUsuario() o a crearUsuarioEnEmpresa() según haya o no
 *   `usuario` (edición vs. alta), y después lee `res.conflicto` sobre el
 *   resultado de cualquiera de las dos — pero crearUsuarioEnEmpresa()
 *   nunca declaraba ese campo en su tipo de retorno (un alta no puede
 *   tener conflicto de edición concurrente, no hay fila previa), así que
 *   el tipo unión de `res` no lo tenía. Se agrega `conflicto?: boolean`
 *   a su tipo de retorno (siempre undefined en la práctica, solo para
 *   que ambos tipos calcen). Se revisó el resto del proyecto buscando el
 *   mismo patrón (un handler que llama a una de dos Server Actions según
 *   una condición y lee un campo del resultado) y no aparece en ningún
 *   otro lugar.
 *
 * V2.008 — octava entrega: selector global de empresa activa para
 *   superadmin. Corrige el enfoque de V2.003 (que había quedado limitado
 *   a un desplegable propio de la Planilla): ahora hay un ÚNICO
 *   desplegable, siempre visible arriba del todo en el Sidebar (solo
 *   para superadmin), que define con qué empresa trabaja en TODOS los
 *   módulos a la vez — tanto para ver datos como para cargar/editar.
 *   - lib/auth/empresaActivaCookie.ts (nuevo): nombre de la cookie
 *     httpOnly `sa_empresa_activa` que guarda la elección.
 *   - app/(protected)/actions.ts (nuevo): Server Action
 *     `seleccionarEmpresaActiva()`, solo para superadmin, setea/borra la
 *     cookie y hace `revalidatePath("/", "layout")` para que toda la app
 *     se refresque con el nuevo contexto.
 *   - components/layout/SelectorEmpresaActiva.tsx (nuevo) +
 *     components/layout/Sidebar.tsx: el desplegable en sí, con "Sin
 *     empresa asignada (huérfanos)" como opción además de la lista de
 *     empresas.
 *   - lib/auth/session.ts (getSessionProfile): pieza central del fix.
 *     `empresaId`/`nombreEmpresa` ya eran el criterio usado en TODA la
 *     app —tanto en filtros de lectura como al escribir altas/ediciones
 *     (`empresa_id: perfil.empresaId`)— así que en vez de agregar un
 *     parámetro nuevo por todos lados, acá mismo se resuelve: si es
 *     superadmin, lee la cookie y reemplaza `empresaId`/`nombreEmpresa`
 *     por los de la empresa elegida (o se queda con `null`/"huérfanos"
 *     por defecto si no hay cookie o la empresa ya no existe). Esto
 *     corrige automáticamente, sin tocarlos, todos los módulos que ya
 *     usaban `perfil.empresaId` para escribir (varias Server Actions ya
 *     tenían la guarda "Usuario sin empresa asociada" cuando era null) y
 *     los que ya filtraban lectura con el patrón
 *     `perfil.empresaId ? ... : []` (Rendición, Concurrencia).
 *   - Módulos a los que sí hubo que agregarles el filtro de lectura
 *     explícito (porque RLS no acota nada para superadmin, que la
 *     bypassea) siguiendo el mismo patrón (`empresaFiltro?: number |
 *     null`, `.eq(...)` o `.is(..., null)` según corresponda): Auxiliares
 *     (propiedades, inquilinos), Carga (listado de contratos), Pagos
 *     (contrato por código Y selector de contratos activos — esto último
 *     además cierra un hueco real: por URL `?contrato=` un superadmin
 *     podía operar sobre el contrato de cualquier empresa sin haberla
 *     elegido), Gastos (historial, métricas, y el selector de
 *     propiedades del formulario de carga), Historial de Pagos,
 *     Dashboard (contratos activos, caja histórica — el comentario del
 *     archivo decía que RLS ya filtraba, pero no había filtro real de
 *     código), Portal Inquilino (comprobantes, reclamos).
 *   - Planilla: se saca el desplegable propio agregado en V2.003
 *     (`SelectorEmpresaPlanilla.tsx`, eliminado) y el módulo pasa a usar
 *     el criterio global igual que el resto — mismo comportamiento,
 *     ahora unificado.
 *   - Fix adicional encontrado en el camino (Panel de Gestión, alta de
 *     usuario): al crear un usuario en una empresa puntual (elegida en
 *     el selector propio del Panel, independiente del selector global),
 *     se guardaba mal el campo `nombre_empresa` — tomaba el de la
 *     empresa activa de superadmin en vez de la empresa realmente
 *     elegida para el alta. Corregido.
 *   - Los selectores de empresa propios de Panel de Gestión (Borrado en
 *     Bloque, CSV Migración, alta de usuarios) NO se tocan — son
 *     herramientas administrativas cross-empresa a propósito, con un
 *     propósito distinto al de "con qué empresa trabajo en el día a
 *     día", así que quedan independientes del selector global.
 *   - Bug de compilación encontrado en la revisión final (mismo patrón
 *     que ya rompió el build dos veces, V2.004): historial/queries.ts,
 *     `calcularMesAnio`, usaba `match[1]` sin fallback pese a haber
 *     validado solo `match` (no cada grupo de captura). Corregido antes
 *     de esta entrega para no repetir el mismo error de build.
 *   - Gap conocido, no corregido en esta entrega (fuera de alcance): las
 *     Server Actions de mutación por ID en portal-inquilino/actions.ts
 *     (revisarComprobante, actualizarReclamo, vincularGastoAReclamo) no
 *     verifican la empresa del registro — solo explotable por un
 *     superadmin adivinando/armando el ID de un registro de otra
 *     empresa.
 *
 * V2.009 — novena entrega: Sidebar colapsable a "solo íconos".
 *   - components/layout/Sidebar.tsx: botón (« / ») que alterna entre
 *     ancho completo (w-64) y solo íconos (w-16). Preferencia puramente
 *     de pantalla — se guarda en localStorage (no en cookie/servidor, no
 *     tiene sentido revalidar nada por esto). Con el menú colapsado cada
 *     ítem muestra únicamente su ícono, con el nombre del módulo como
 *     tooltip (title) en vez de texto.
 *   - components/layout/SelectorEmpresaActiva.tsx: el desplegable de
 *     empresa activa (V2.008) no entra en el ancho colapsado — en vez de
 *     armar un popover, con el Sidebar colapsado se muestra solo un
 *     botón con el ícono 🏢 (tooltip: empresa activa actual); al
 *     hacerle clic expande el Sidebar para volver al <select> de
 *     siempre y poder elegir. No hay conflicto funcional entre ambas
 *     features: el selector nunca desaparece, solo cambia de forma
 *     según el estado del menú.
 *
 * V2.010 — décima entrega: cierra el gap de defensa en profundidad de
 *   Portal Inquilino que había quedado pendiente en V2.008. No era una
 *   escalada de privilegios (superadmin ya bypassea RLS por diseño de su
 *   rol), pero permitía que, actuando con la empresa activa del selector
 *   global, superadmin tocara sin querer un registro de OTRA empresa
 *   conociendo/adivinando su id (ids correlativos). Se agrega el mismo
 *   filtro por empresa activa que ya usan las lecturas del módulo
 *   (lib/portal-inquilino/queries.ts) también a las escrituras por id:
 *   - revisarComprobante: no aprueba/rechaza un comprobante de otra empresa.
 *   - actualizarReclamo: no actualiza un reclamo de otra empresa.
 *   - vincularGastoAReclamo: no vincula un gasto a un reclamo de otra empresa.
 *   - crearGastoDesdeReclamo: mismo chequeo en el vínculo gasto→reclamo
 *     del paso final (el gasto en sí ya se creaba bien scopeado a la
 *     empresa activa desde antes).
 *   En los cuatro casos, si el registro no pertenece a la empresa activa
 *   la acción ahora devuelve un error explícito en vez de fallar en
 *   silencio o tocar el registro equivocado.
 */
export const APP_VERSION = "V2.010";
