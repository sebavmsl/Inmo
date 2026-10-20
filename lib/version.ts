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
 *
 * V2.011 — onceava entrega: diagnóstico de "Editar Contrato" (Carga)
 *   colgado en "Cargando…" tras habilitar el selector global. La causa
 *   de fondo era de base de datos (ver migraciones 0019 y 0020, no
 *   versionan acá porque no son código de la app):
 *   - components/carga/EditarContrato.tsx: bug de UI que ya existía
 *     antes de esta sesión (mismo patrón en GestionUsuarios.tsx,
 *     FormularioGrupo.tsx, EditarPropiedad.tsx, EditarInquilino.tsx, no
 *     tocados todavía) — si `listarContratos()` tira un error, no había
 *     catch, así que el estado "cargando" quedaba en true para siempre:
 *     un error real se veía IDÉNTICO a una consulta lenta, sin ningún
 *     mensaje. Se agrega try/catch + mensaje de error + botón
 *     "Reintentar", para que de acá en más un error se vea como error.
 *
 * V2.012 — doceava entrega: causa real del error que tapaba "Editar
 *   Contrato" ("A 'use server' file can only export async functions,
 *   found object"). lib/concurrencia/queries.ts (módulo de ediciones
 *   simultáneas, preexistente — no se tocó en esta sesión hasta ahora)
 *   exportaba `TABLAS_CON_LOCK`, un array — un archivo "use server"
 *   SOLO puede exportar funciones async, cualquier otro export (una
 *   constante, un array, un objeto) rompe el render en producción.
 *   Se deja de exportar el array (nada fuera del archivo lo necesitaba,
 *   solo el tipo derivado `TablaConLock`, que sigue exportado — los
 *   tipos no cuentan para esta regla, se borran en runtime). Se revisó
 *   el resto del proyecto buscando el mismo patrón en los otros 16
 *   archivos "use server" y no aparece en ningún otro lugar.
 *
 * V2.013 — treceava entrega: dos bugs reales en el cálculo/visualización
 *   del alquiler actualizado, encontrados comparando directamente contra
 *   app.py (Módulo 3 y Módulo 4) a partir de un caso real en producción
 *   (contrato recién creado mostrando un alquiler más del doble del
 *   esperado). Ninguno de los dos es un bug de la fórmula del índice en
 *   sí (esa se verificó contra el ICL real del BCRA y está bien) — son
 *   dos piezas de lógica de v1 que faltaban en el puerto original:
 *
 *   1. lib/indices/alquilerVigente.ts (nuevo) — puerto de
 *      `_alquiler_display()` (app.py línea 3018): v1 solo confía en
 *      `alquiler_calculado` si `alquiler_calculado_fecha` es del mes
 *      calendario ACTUAL; si no, cae a `alquiler`/`monto_inicial`. El
 *      puerto original usaba `alquiler_calculado` siempre que no fuera
 *      null, sin este chequeo — un valor de un ciclo viejo (o de un
 *      ciclo que todavía no llegó) quedaba mostrándose indefinidamente.
 *      Aplicado en los 4 lugares que mostraban/usaban este valor:
 *      Planilla (lib/planilla/queries.ts), envío masivo de recibo
 *      preliminar por WhatsApp (app/(protected)/planilla/actions.ts —
 *      podía mandarle al inquilino un monto inflado), el portal del
 *      inquilino (app/portal/mi-cuenta/page.tsx), y el monto sugerido
 *      al registrar un pago (lib/pagos/queries.ts).
 *
 *   2. lib/indices/ultimaActualizacion.ts (nuevo) — puerto de la
 *      sección "REPLICACIÓN DE ALERTAS DE ACTUALIZACIÓN" de app.py
 *      (Módulo 4, líneas 3569-3813). El bug más importante: al abrir un
 *      contrato en Pagos, lib/pagos/queries.ts recalculaba SIEMPRE el
 *      índice contra "inicio_contrato + 1 × frecuencia" — un único
 *      punto fijo. Para un contrato recién creado (como el del caso
 *      real) eso apunta a una fecha FUTURA sin datos de índice
 *      publicados todavía; para uno con más de un ciclo de historia,
 *      apunta a una fecha vieja, no a la actualización vigente real. v1
 *      en cambio avanza la "próxima actualización" ciclo por ciclo
 *      hasta encontrar una fecha que todavía no pasó, retrocede un
 *      ciclo para obtener la ÚLTIMA actualización ya vencida, y exige
 *      que haya pasado al menos un ciclo completo antes de calcular
 *      nada — si no, no calcula, y se muestra alquiler/monto_inicial
 *      (punto 1). La fórmula de cálculo en sí (lib/indices/calculo.ts)
 *      no cambió — solo qué fecha se le pasa como objetivo.
 *
 * V2.014 — catorceava entrega: bug real en producción reportado por el
 *   usuario ("en la version 2, me aparecen pagos todos los contrato"),
 *   confirmado por contraste directo con v1: en Python, la Planilla
 *   distingue correctamente pagos de pendientes; en v2, TODOS los
 *   contratos aparecían "pagado". Causa: el puerto original definía
 *   `pagado` como `contratos.saldo_actual <= 0` — el saldo de cuenta
 *   corriente GLOBAL y acumulado del contrato (ver DESIGN_LOG.md,
 *   "Saldo de contratos — MODELO FINAL"). v1 en cambio (app.py, línea
 *   ~1549, `_cached_planilla_cobranzas_mes`) define "pagado" como
 *   "¿existe un pago registrado en `pagos_historial` con `fecha` dentro
 *   del mes calendario ACTUAL, y ese pago puntual dejó `saldo_pendiente`
 *   en 0?" — sin ningún pago cargado este mes, es SIEMPRE pendiente, sin
 *   importar cuánto se haya saldado en meses anteriores. Con `saldo_actual`
 *   como criterio, un contrato que había quedado en $0 el mes pasado
 *   (o que arrancó en $0) y todavía no tuvo ningún movimiento cargado
 *   este mes aparecía "pagado" igual — en la práctica, casi todos los
 *   contratos, apenas empezando a operar en v2.
 *
 *   Fix: nuevo módulo lib/pagos/pagoMesActual.ts, puerto exacto de la
 *   lógica de v1 — `obtenerUltimoPagoDelMesPorContrato()` busca, por
 *   contrato, el último pago con `fecha` dentro del mes calendario
 *   actual, y `estaPagadoEsteMes()` decide en base a ESE pago puntual
 *   (no en base a `saldo_actual`). Aplicado en los 2 lugares que usaban
 *   el criterio viejo: la columna "Pagado" de la Planilla
 *   (lib/planilla/queries.ts) y el filtro de omisión del envío masivo de
 *   recibo preliminar por WhatsApp (app/(protected)/planilla/actions.ts
 *   — antes podía omitir el envío a alguien que en realidad no pagó
 *   nada este mes). La columna "Saldo" sigue mostrando `saldo_actual`
 *   sin cambios — sigue siendo el criterio correcto para "cuánto se
 *   debe en total", que es una pregunta distinta de "¿pagó este mes?".
 *
 * V2.015 — Entrega 1 (base). Ver docs/DESIGN_LOG.md, "Entrega 1".
 *   NOTA: a diferencia de entradas anteriores, este changelog lista solo
 *   lo que está en este commit. Se verificó que el arreglo anunciado en
 *   V2.012 (TABLAS_CON_LOCK) nunca había llegado al código; se aplica acá.
 *   - supabase/migrations/0021_seguridad_y_fechas.sql (se corre a mano):
 *     chequeo de rol seguro ante NULL en eliminar_empresa_completa,
 *     eliminar_registros_bloque, aplicar_actualizacion_individual y
 *     contratos_elegibles_actualizacion (solo usuarios logueados);
 *     upsert_indice exige el secreto del cron; tokens de WhatsApp solo para
 *     service_role; saldo_actual no editable desde la API; auditoría de
 *     contratos (no tenía `id`) e ignora saldo_actual/updated_at;
 *     updated_at no cambia si solo cambió el saldo; impactar_cobro y
 *     registrar_liquidacion_propietario escriben la fecha en formato Python
 *     ("DD/MM/YYYY HH:MM", hora Argentina).
 *   - supabase/foto_base/esquema_2026-09-29.sql: foto del esquema real (no
 *     se ejecuta). supabase/verificacion_0021.sql: consulta de control.
 *   - lib/fechas.ts (nuevo): lectura/escritura única de fechas. Aplicado en
 *     "pagado este mes" (Planilla), Historial (orden por número de pago),
 *     Reporte de Cobros (filtro de fechas), Rendición (filtro de mes),
 *     métricas de Gastos, Portal del inquilino, PDFs, WhatsApp, export CSV.
 *   - Historial: filtro explícito por empresa (superadmin).
 *   - Panel de Gestión: editar usuarios usa `username` (no existe
 *     usuarios_central.id); presencia/conflicto de edición también.
 *   - lib/concurrencia/queries.ts: deja de exportar TABLAS_CON_LOCK.
 *   - WhatsApp: el token se lee solo en el servidor (service_role) y con el
 *     parámetro correcto (`p_secret_id`; antes fallaba siempre).
 *   - Cron: pasa el secreto a upsert_indice (el cron sigue desactivado en
 *     Vercel; su paso de "aplicar índices" se rediseña en el módulo
 *     WhatsApp y cron).
 *
 * V2.016 — arreglo rápido sobre la Entrega 1 (pruebas del 20/10/2026):
 *   - WhatsApp: el número del pool (`whatsapp_numeros`, RLS sin políticas)
 *     se lee en el servidor con service_role, después de validar la
 *     empresa con la sesión del usuario. Antes la v2 decía "WhatsApp no
 *     está configurado" y no enviaba preliminares ni comprobantes.
 *   - Planilla: el envío masivo devuelve el motivo del error en vez de
 *     tirarlo (en producción solo se veía el error genérico de Next.js), y
 *     solo toma verificaciones de la empresa activa.
 *   - supabase/migrations/0022_permisos_sin_recursion.sql (se corre a mano):
 *     la política admin_gestiona_permisos_empresa se consultaba a sí misma
 *     ("infinite recursion detected in policy"); ahora usa
 *     auth_pestanas_propias(). Arregla guardar usuarios en Panel de Gestión.
 *   - Carga de contratos: el selector de "Editar contrato" compara el código
 *     como texto (llega como número desde la base y nunca coincidía). Mismo
 *     arreglo en dos comparaciones del Portal del inquilino.
 *   - Historial: la tabla de pagos usa los mismos filtros (fechas y usuario)
 *     que el Reporte de Cobros.
 *
 * V2.017 — arreglos de las pruebas de V2.016 (20/10/2026):
 *   - Comprobante por WhatsApp: misma plantilla aprobada que Python
 *     ("comprobante_pago_con_pdf"; la v2 pedía "comprobante_pago_alquiler"
 *     y Meta la rechazaba), dirección de la propiedad en vez del alias,
 *     monto formateado y teléfono sin espacios ni guiones.
 *   - Comprobante y preliminar masivo: el inquilino se busca por DNI dentro
 *     de la empresa (el mismo DNI puede estar en dos empresas).
 *   - Pagos: "Monto abonado" se completa con el total a cubrir (saldo que
 *     arrastra + conceptos del mes) hasta que se edite a mano.
 *   - Reporte de Cobros: "Desde" arranca el 1 de enero del año actual.
 */
export const APP_VERSION = "V2.017";
