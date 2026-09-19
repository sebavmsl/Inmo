# Bitácora de diseño — v2

Notas internas de decisiones tomadas en conversación, para generar los
archivos definitivos cuando se pida. No es documentación de usuario final.

---

## Arquitectura de base de datos — decisión confirmada

**Se mantiene una sola base Postgres compartida (Supabase), con `empresa_id`
en cada tabla + RLS para el aislamiento — NO se vuelve al modelo viejo de
un archivo de base de datos por empresa** (que v1 tuvo en algún momento,
de ahí el nombre vestigial `archivo_db`; ya fue migrado a base compartida
antes de esta conversación, y v2 parte de ese estado actual).

Motivo: coherente con la restricción de costo ("gratis") definida al
arrancar el proyecto — múltiples proyectos de Supabase (uno por empresa)
rompen el plan gratis con más de un puñado de empresas, y complican
migraciones, datos compartidos (`indices_historicos`) y el cliente de
conexión de la app (asumiría un solo proyecto fijo).

**El camino queda abierto a futuro, sin rediseñar nada**: como todas las
tablas ya tienen `empresa_id` de forma consistente, aislar una empresa
puntual a su propia base el día que haga falta es un proceso mecánico
(correr las mismas migraciones versionadas en una base nueva + copiar
`WHERE empresa_id = X`) — no requiere tocar el modelo de datos actual.
Sí requeriría, en ese momento: lógica de enrutamiento de conexión en la
app (hoy asume un único proyecto), y decidir cómo alcanzan las piezas
deliberadamente globales (cron de índices, `indices_historicos`) a una
base aislada.

---

## Módulo 3 — Planilla / motor de índices ICL-IPC

**Estado: diseño cerrado.**

- Tabla `indices_historicos (tipo, fecha, valor)` — pública, sin empresa_id, RLS de solo lectura.
- `configuraciones_empresa.cron_indices_habilitado` (bool, default false) — opt-in por empresa, columna NUEVA y separada de `actualizar_alquiler_auto` (que sigue siendo exclusiva del toggle de UX en Módulo 4/recibo, sin tocar).
- Funciones `SECURITY DEFINER`, sin `service_role` en ningún lado (decisión explícita del usuario: "prefiero que sea lo más seguro, no quiero debilitar el acceso a la base de datos"):
  - `upsert_indice(tipo, fecha, valor)` — cron, anon key.
  - `vencer_contratos_automaticamente(p_secret_cron)` — marca `Finalizado` contratos con `fin_contrato <= hoy_argentina` (huso `America/Argentina/Buenos_Aires`, SIN período de gracia — confirmado por el usuario). Corre para TODAS las empresas siempre, sin toggle. Deja rastro: `fecha_finalizacion`, `finalizado_por = 'auto_vencimiento'`.
  - `aplicar_actualizaciones_indices(p_empresa_id, p_secret_cron, p_solo_pendientes default false)` — botón manual (empresa, sin candado por defecto — checkbox "solo pendientes" destildado por defecto, igual comportamiento que v1) o cron (global, `p_solo_pendientes = true` siempre, solo empresas con `cron_indices_habilitado = true`).
- El botón manual en Planilla es un respaldo REAL ante fallo del cron: refresca `indices_historicos` en vivo (no asume que el cron ya corrió) + aplica, todo para la empresa del usuario.
- Un solo Route Handler de cron diario, orden fijo: `vencer_contratos_automaticamente` → refrescar índices → `aplicar_actualizaciones_indices` (global).
- Secreto de cron en Supabase Vault, comparado dentro de las funciones — nunca en variables expuestas al cliente.
- **Columnas nuevas en `contratos`**: `fecha_finalizacion` (date, null), `finalizado_por` ('auto_vencimiento' | 'renovacion' | null — el flujo de renovación existente de v1, líneas 6023-6028 de app.py, NO se toca y sigue sin llenar estas columnas), `archivado` (bool, default false).
- **"Archivar"**: decisión de la empresa (visible/oculto para TODOS sus usuarios, no por-usuario). Filas con `finalizado_por = 'auto_vencimiento' AND archivado = false` se muestran en la Planilla atenuadas, con badge "VENCIDO" y botón "Archivar" → `UPDATE contratos SET archivado = true`. Es un UPDATE normal, protegido por RLS existente — NO necesita función SECURITY DEFINER.
- Pantalla futura (fuera de alcance ahora, solo anotado): ver contratos vencidos administrativamente pero vigentes de hecho — usa `WHERE finalizado_por = 'auto_vencimiento'`.
- **Tabla nueva `planilla_verificaciones`** (empresa_id, codigo_contrato, periodo 'YYYY-MM' — NO confundir con `pagos_historial.periodo`, que es "Mes N de M" relativo al contrato, formato totalmente distinto y sin relación — verificado bool, expensas_adhoc numeric null, verificado_por, verificado_fecha, UNIQUE(codigo_contrato, periodo)). Reemplaza el checkbox efímero de sesión de v1: ahora persiste y es compartido entre usuarios de la empresa (decisión explícita del usuario).
- PDF de planilla: Route Handler server-side con `@react-pdf/renderer`.
- Botón "ir a Pagos" por fila: link a `/pagos?contrato=CODIGO` (reemplaza el hack de session_state+rerun de v1).

### "¿Pagado?" en la Planilla — REDEFINIDO tras revisión completa (inconsistencia encontrada y resuelta esta sesión)
Al hacer una revisión de toda la bitácora, se encontró una inconsistencia real: la Planilla original detectaba "pagado este mes" mirando si `saldo_pendiente = 0` en el pago más reciente de ESE período — válido bajo el modelo viejo de v1 (saldo aislado por período), pero **roto** desde que adoptamos cuenta corriente para `saldo_pendiente` (Módulo 4): con cuenta corriente, un inquilino que pagó el mes completo pero arrastra deuda vieja seguiría con `saldo_pendiente > 0` en su última fila, apareciendo como "no pagó" incorrectamente.

**Definición final, confirmada por el usuario**: `"Pagado" = contratos.saldo_actual <= 0`. Si debe algo (de este mes o arrastrado de antes), aparece PENDIENTE hasta estar completamente al día — coherente con el propósito real del indicador (saber a quién reclamarle), no solo "hubo algún movimiento este mes". Efecto práctico: el envío masivo de WhatsApp (recibo preliminar) pasa a apuntar a cualquier contrato con saldo pendiente, no solo a los sin movimiento puntual este mes. Simplifica la implementación: ya no hace falta ninguna query aparte para este chequeo, es directamente el campo `saldo_actual` ya cacheado.

### Hallazgo — periodo NO es intercambiable entre tablas
`pagos_historial.periodo` = "Mes N de M" (relativo al contrato). `planilla_verificaciones.periodo` = "YYYY-MM" (mes calendario). Dos conceptos distintos, nunca comparar directamente.

---

## Módulo 5 — Carga de Contratos, Propiedades e Inquilinos (diseño en progreso)

### Ampliación del motor de índices — UVA automatizado, "Otro" es aviso no cálculo (decisión de esta sesión)
Al revisar la validación de Módulo 5 (líneas 5628-5656 de app.py: bloquea guardar el contrato si es "mes de actualización" y el alquiler no cambió), se encontró que v1 ofrece 4 índices en el dropdown (`ICL, IPC, UVA, Otro`) pero el motor automático (`calcular_valor_actualizado_icl/ipc`) solo cubre 2. El usuario pidió que TODOS actualicen automáticamente. Investigado y resuelto:

- **UVA**: SÍ tiene fuente pública automatizable — BCRA publica serie diaria (`https://www.bcra.gob.ar/archivos/Pdfs/PublicacionesEstadisticas/diar_uva.xls`), mismo formato/mecanismo que ya se usa para ICL. Se extiende `upsert_indice()` (migración de Módulo 3) para aceptar también `tipo = 'UVA'`, y el cron de refresco diario agrega esta tercera fuente. `aplicar_actualizaciones_indices()` pasa a cubrir ICL/IPC/UVA por igual.
- **"Otro"**: confirmado por el usuario — se negocia caso por caso, sin fórmula ni fuente de datos fija. NO se puede automatizar el cálculo (nadie puede "adivinar" un número que depende de una negociación humana). Lo que SÍ se automatiza es el AVISO: el sistema notifica cuando corresponde actualización para un contrato "Otro" (conecta con Módulo 8 — Recordatorios automáticos, todavía no diseñado en detalle), y la persona carga el valor a mano. La validación de Módulo 5 que bloquea guardar hasta que se cargue un valor distinto al anterior SIGUE SIENDO el mecanismo correcto, pero ahora queda acotada específicamente al caso "Otro" (para ICL/IPC/UVA, el valor ya viene precargado por el motor automático, no debería hacer falta este bloqueo — a revisar si sigue teniendo sentido mantenerlo también para esos tres, o si se vuelve redundante).

**Pendiente de implementación**: extender el tipo `IndiceActualizacion` (ya definido en `lib/types/database.types.ts` como `"ICL" | "IPC" | "fijo"`) — ojo, revisar también que diga `"UVA" | "Otro"` en vez de `"fijo"`, para que coincida con las opciones reales del dropdown de v1.

### Honorarios y garantía — mismo problema que `saldo_actual`, resuelto con patrón "base + ledger" (hallazgo y decisión de esta sesión)
Al revisar la sección "Liquidación de Importes de Agencia" de Módulo 5 (líneas 5659-5730), se encontró que `contratos.honorarios_pagados`, `cuotas_honorarios_pagadas`, `garantia` y `cuotas_deposito_pagadas` tienen DOS caminos de escritura independientes:
1. **Módulo 4 (Pagos)**, línea 4436-4457: acumula automáticamente como efecto secundario de un pago real (patrón "leer viejo + sumar + guardar" — el mismo tipo de mecanismo frágil que ya reemplazamos en saldo).
2. **Módulo 5 (Carga de Contratos)**, línea 5705-5713: `cuotas_honorarios_pagadas` es un campo `number_input` **editable a mano**, sin ninguna validación contra pagos reales — a diferencia del problema de `saldo_actual` (que era una falla de permisos, algo que alguien PODÍA hacer sin que estuviera pensado para eso), acá es una función INTENCIONAL del formulario.

Usuario confirmó: quiere mantener la edición manual en Carga de Contratos, pero sin reabrir el riesgo de desincronización. Solución acordada — patrón "base editable + ledger protegido" (estándar contable):
```
contratos.honorarios_pagados_base       -- editable SOLO en Carga de Contratos (Módulo 5)
contratos.cuotas_honorarios_pagadas_base -- ídem
contratos.garantia_pagada_base           -- ídem, para depósito de garantía
contratos.cuotas_deposito_pagadas_base   -- ídem

Total real (en cualquier pantalla que lo muestre) =
  base + SUM(monto_honorarios / monto_garantia de pagos_historial para ese contrato)
```
- Módulo 5 edita el campo `_base` — pensado específicamente para el "punto de partida" de un contrato migrado o con historia previa a que existiera el registro transaccional en v2.
- Módulo 4 DEJA DE acumular con UPDATE — cada pago es simplemente una fila más del ledger (`pagos_historial.monto_honorarios`/`monto_garantia`), el total se deriva sumando, nunca se pisa.
- Es matemáticamente imposible que la edición de la base rompa un pago real: el ledger nunca se toca desde Módulo 5, la base solo aporta lo anterior a que el ledger exista para ese contrato.

**CORRECCIÓN CRÍTICA — no se renombran las columnas** (hallazgo de esta sesión, al responder una pregunta directa del usuario sobre qué toca la migración): la nota original decía "renombrar `honorarios_pagados` → `honorarios_pagados_base`" — un `RENAME COLUMN` que **rompería a v1**, que sigue leyendo/escribiendo esas columnas con su nombre actual. Esto contradice el principio de "cero cambios a v1" aplicado en todo el resto del diseño; se pasó por alto en este punto puntual. Corregido al mismo patrón usado para `servicios` → `cargo_*`: columnas NUEVAS al lado de las viejas, con un `UPDATE` que copia los valores existentes una sola vez — las columnas originales quedan intactas, v1 no se entera de nada:
```sql
alter table contratos add column honorarios_pagados_base numeric default 0;
alter table contratos add column cuotas_honorarios_pagadas_base int default 0;
alter table contratos add column garantia_pagada_base numeric default 0;
alter table contratos add column cuotas_deposito_pagadas_base int default 0;

update contratos set
  honorarios_pagados_base = honorarios_pagados,
  cuotas_honorarios_pagadas_base = cuotas_honorarios_pagadas,
  garantia_pagada_base = garantia,
  cuotas_deposito_pagadas_base = cuotas_deposito_pagadas;
```
v2 lee/escribe las columnas `_base` nuevas; v1 sigue usando las originales sin ningún cambio.

**RESUELTO (revisión adicional, esta sesión)**: se calcula AL VUELO, sin cachear ni trigger. A diferencia de `saldo_actual` (leído en cada carga de la Planilla, para decenas de contratos a la vez), este total se consulta puntualmente al abrir UN contrato en Pagos — un `SUM` simple sobre `pagos_historial` filtrado por `codigo_contrato`, indexado, rápido incluso con años de historial. No amerita otro trigger.

### `contratos.servicios` — bug confirmado de texto libre mal parseado (hallazgo y decisión de esta sesión)
Al revisar cómo se arma `contratos.servicios` en Módulo 5 (línea 5972: `f"[Alq.Actualizado: {alq_act_fmt} | Imp.Inmob: {cargo_inmobiliario}] {servicios_detalle}"`), se encontró que Módulo 4 (líneas 3740, 3779, 4338) intenta leer de vuelta si el Impuesto Inmobiliario está a cargo del inquilino buscando el substring literal `"[Imp.Inmob: Inquilino]"` — pero el formato real que se guarda tiene el corchete de apertura antes de "Alq.Actualizado", no antes de "Imp.Inmob" (que queda precedido por `"| "`, no `"["`). **El substring buscado nunca puede aparecer en el texto real guardado — el chequeo da `False` siempre**, así que el Impuesto Inmobiliario nunca se cobra al inquilino aunque esté configurado así.

Usuario confirmó con query en producción (`WHERE servicios LIKE '%Imp.Inmob: Inquilino%'`): **0 filas** — nadie activó esa opción en la práctica (el selector arranca por defecto en "Propietario"), así que no hay impacto financiero retroactivo que corregir. Igual se decide resolverlo de raíz para v2, no parchear el regex.

**Decisión**: eliminar el patrón de codificar banderas de negocio como texto libre + substring matching. Cada "a cargo de" (Electricidad, Gas, Municipalidad, OO.SS., Expensas, Impuesto Inmobiliario) pasa a ser una **columna estructurada y tipada** en `contratos`:
```sql
cargo_electricidad      text check (cargo_electricidad in ('Inquilino','Propietario')) default 'Inquilino',
cargo_gas               text check (...) default 'Inquilino',
cargo_municipalidad     text check (...) default 'Inquilino',
cargo_ooss              text check (...) default 'Inquilino',
cargo_expensas          text check (...) default 'Inquilino',
cargo_imp_inmobiliario  text check (...) default 'Propietario'  -- default real de v1
```
Los identificadores de cuenta (NIS, Cta Gas, Finca, Cta OO.SS.) y las notas adicionales, que hoy también viven mezclados en el mismo texto libre, se evalúan por separado si conviene estructurarlos también (columnas propias) o dejarlos como un campo de notas libre — pendiente de definir al generar los archivos, es de menor riesgo porque no se usan para lógica de negocio, solo se muestran.

### Migración de datos existentes de `servicios` a las columnas nuevas (decisión de esta sesión)
Hallazgo adicional: de los 6 flags "a cargo de" codificados en `servicios`, **solo Impuesto Inmobiliario estaba conectado a lógica real** (con el bug ya documentado) — Elec/Gas/Mun/OOSS/Exp se escriben pero nunca se leen de vuelta en ningún lado de v1, son puramente decorativos hoy. Igual se migran los 6, para no perder configuración ya cargada por el usuario.

Usuario confirmó: columnas nuevas (no interfieren con v1) + script de migración que copia los valores ya cargados en v1 a las columnas nuevas de v2, en vez de arrancar todo en blanco. Script (correr una sola vez, después de crear las columnas):
```sql
UPDATE contratos
SET
  cargo_electricidad     = COALESCE((regexp_match(servicios, 'Elec: (\w+)'))[1], 'Inquilino'),
  cargo_gas               = COALESCE((regexp_match(servicios, 'Gas: (\w+)'))[1], 'Inquilino'),
  cargo_municipalidad     = COALESCE((regexp_match(servicios, 'Mun: (\w+)'))[1], 'Inquilino'),
  cargo_ooss              = COALESCE((regexp_match(servicios, 'OOSS: (\w+)'))[1], 'Inquilino'),
  cargo_expensas          = COALESCE((regexp_match(servicios, 'Exp: (\w+)'))[1], 'Inquilino'),
  -- OJO: '\| Inmob:' con la barra adelante — para NO matchear el prefijo roto
  -- "Imp.Inmob: X" (que también contiene la substring "Inmob: X" adentro).
  cargo_imp_inmobiliario  = COALESCE((regexp_match(servicios, '\| Inmob: (\w+)'))[1], 'Propietario')
WHERE servicios IS NOT NULL;
```
No toca `contratos.servicios` (columna original queda intacta, v1 sigue leyendo/escribiendo ahí igual que siempre) — solo llena las columnas nuevas. Idempotente, se puede re-correr sin riesgo.

### Políticas de Supabase Storage — aislamiento de archivos (decisión de esta sesión)
Mismo cuidado que las tablas, pero para Storage (PDFs de comprobantes, subidas de inquilinos en Módulo 9). Usuario confirmó: staff ve TODOS los documentos de su empresa sin restricción adicional (puede acotarse más adelante si hace falta), un inquilino SOLO ve los de su propio contrato — nunca los de otro inquilino, ni de la misma propiedad.

Convención de carpetas: `{bucket}/{empresa_id}/{codigo_contrato}/archivo`

```sql
create policy "staff_lee_comprobantes" on storage.objects for select
  using (
    bucket_id in ('comprobantes-pago', 'comprobantes-inquilino')
    and (auth_rol() = 'superadmin' or (storage.foldername(name))[1] = auth_empresa_id()::text)
  );

create policy "inquilino_lee_sus_comprobantes" on storage.objects for select
  using (
    bucket_id in ('comprobantes-pago', 'comprobantes-inquilino')
    and (storage.foldername(name))[2] in (
      select codigo from contratos where dni_inquilino in (select dni from inquilinos where auth_user_id = auth.uid())
    )
  );

create policy "inquilino_sube_comprobantes" on storage.objects for insert
  with check (
    bucket_id = 'comprobantes-inquilino'
    and (storage.foldername(name))[2] in (
      select codigo from contratos where dni_inquilino in (select dni from inquilinos where auth_user_id = auth.uid())
    )
  );
```
Aislamiento a nivel de base (RLS), no solo de UI — un inquilino no puede ver la carpeta de otro ni con la URL a mano. Usa comparación por conjunto (no la función escalar `auth_inquilino_dni()`) por el mismo motivo del caso de borde de multi-tenencia corregido en Módulo 9 — mismo DNI, dos empresas, un solo auth_user_id.

### Estados de `contratos.estado` — decisión de esta sesión
v1 ofrece 6 opciones en el dropdown de carga (`estados_disponibles`, línea 5214 de app.py), pero solo `Activo` y `Finalizado` están conectados a alguna lógica real — las otras 4 aparecen ÚNICAMENTE en esa lista, en ningún otro lugar del código (ni en las 6 queries que filtran `estado = 'Activo'`, ni en ninguna función). Confirmado con el usuario, estado por estado:

| Estado | Confirmado uso real en producción | Decisión v2 |
|---|---|---|
| `Activo` | Sí | Se mantiene, único valor "activo" en cualquier query |
| `Finalizado` | Sí | Se mantiene |
| `Cancelado` | Terminación anticipada (motivo distinto, mismo efecto que Finalizado) | Se mantiene como estado terminal aparte — mismo tratamiento que Finalizado en las queries (nunca cuenta como activo), pero se preserva el motivo para auditoría/reportes futuros |
| `Revalorizado` | Confirmado: NUNCA usado en la práctica ("sigue activo pero se cambió el canon locativo" — pero como ninguna query lo trata como activo, si alguna vez se usó, ese contrato quedó invisible en todo v1 sin que nadie lo note) | Eliminado del dropdown de v2. Pendiente: usuario va a correr `SELECT ... WHERE estado IN ('Revalorizado','Inhabitado')` para confirmar que no hay filas huérfanas en datos reales |
| `Vencido` | Confirmado: duplicado semántico de `Finalizado` (mismo significado, dos strings distintos por inconsistencia de carga a lo largo del tiempo) | NO se ofrece como opción nueva en v2. Toda query de v2 que busque "no activo" trata `'Vencido'` y `'Finalizado'` como equivalentes (ej. `estado NOT IN ('Activo')` o `estado IN ('Finalizado','Vencido','Cancelado')` según el caso) — SIN migrar datos históricos por ahora (decisión explícita: mínimo impacto en datos existentes de v1, se evalúa migrar más adelante) |
| `Inhabitado` | Pendiente de confirmar (usuario no está seguro) — igual que Revalorizado, corre la misma query de control | Conceptualmente describe una PROPIEDAD sin contrato activo, no un estado de un contrato puntual — es un error de modelado en v1 que ese valor esté en el dropdown de `contratos.estado`. Eliminado del dropdown de v2. Pasa a ser un indicador CALCULADO en la pantalla de propiedades: `¿tiene algún contrato con estado='Activo'? No → mostrar como vacante`. No requiere columna ni cambio de esquema. |

### Estados de `contratos.estado` — CONFIRMADO Y CERRADO con datos reales
Usuario corrió `SELECT estado, COUNT(*) FROM contratos GROUP BY estado` en producción: **solo existen `Activo` (30) y `Finalizado` (6)**. Cero filas con `Vencido`, `Cancelado`, `Revalorizado`, `Inhabitado`, ni variantes de mayúsculas/minúsculas. No hace falta ningún resguardo de compatibilidad con datos viejos.

**Enum final para v2**: `estado: "Activo" | "Finalizado"`. `Cancelado` queda disponible como opción futura en el formulario de carga (para distinguir "terminación anticipada" de "terminación normal" el día que se necesite), sin lógica especial por ahora — mismo tratamiento que `Finalizado` en todas las queries. `Revalorizado`, `Vencido` e `Inhabitado` NO se ofrecen en v2 (ver justificación arriba).

Pendiente de implementación: actualizar `lib/types/database.types.ts` (`contratos.estado`) al enum final cuando se generen los archivos.

### Auto-finalizado del contrato viejo al renovar — REGLA FINAL (revisada esta sesión)
v1 (líneas 6023-6028) siempre marca `Finalizado` sin distinguir el motivo. Para v2, el usuario pidió calcular automáticamente si corresponde `Finalizado` o `Cancelado`, según si el contrato viejo ya cumplió su curso o se cortó antes de tiempo:
```
Al cargar un contrato nuevo para una propiedad con un contrato "Activo" existente:

  ¿fin_contrato_viejo <= fin del mes actual?          (ya terminó o termina este mes)
  O ¿mes_contrato_viejo >= calc_duracion_viejo?        (ya no le quedan períodos por pagar)

  → Si CUALQUIERA es cierta: el viejo pasa a FINALIZADO (terminó su curso normal)
  → Si NINGUNA es cierta: el viejo pasa a CANCELADO (se cortó antes de tiempo)
```
Se ejecuta SIEMPRE (sin la condición `if state_contrato == "Activo"` de v1 — ver decisión anterior), y completa `finalizado_por = 'renovacion'` + `fecha_finalizacion = NULL` en la fila que se cierra.

`Revalorizado` queda CONFIRMADO eliminado del dropdown de v2 (el usuario aclaró que mencionarlo en el mensaje anterior fue solo una forma de hablar, no un pedido de mantenerlo).

### Tabla nueva `auditoria_cambios` — auditoría detallada, genérica (decisión ampliada esta sesión)
Idea original del usuario: registrar cada creación/edición de un CONTRATO, con el detalle de qué cambió. Se evaluó el costo (comparación de columnas en memoria por edición, volumen bajo — contratos/propiedades/inquilinos se editan esporádicamente, no como pagos_historial que recibe una fila por cobro) y se confirmó que no amerita ninguna optimización especial (a diferencia de `saldo_actual`/`pagos_historial`, que sí la necesitan por alto volumen y concurrencia real). Luego el usuario pidió extenderlo también a Propiedades e Inquilinos — se diseñó como UNA tabla genérica + UNA función de trigger reutilizable en las 3 tablas, en vez de triplicar la lógica:

```sql
create table auditoria_cambios (
  id bigserial primary key,
  empresa_id int not null,
  tabla text not null,          -- 'contratos' | 'propiedades' | 'inquilinos'
  registro_id text not null,    -- el id de la fila afectada
  tipo_evento text not null,    -- 'creacion' | 'edicion'
  cambios jsonb,                -- solo los campos que cambiaron: {"alquiler": {"antes": X, "despues": Y}, ...}
  realizado_por text,           -- username, o 'sistema' para eventos automáticos (cron)
  fecha timestamptz not null default now()
);
```

**Se llena con UN trigger genérico** (usa `TG_TABLE_NAME` para saber en qué tabla corre, y `jsonb_object_keys` para comparar OLD/NEW campo por campo sin listar columnas a mano), aplicado a `contratos`, `propiedades` e `inquilinos` por igual — mismo principio que `saldo_actual`: nadie puede editar sin que quede loggeado, no depende de que el código de turno se acuerde de llamarlo. `realizado_por` se resuelve buscando el `username` a partir de `auth.uid()` (con fallback a `'sistema'` para operaciones sin usuario logueado, como el cron de vencimiento automático).

Pendiente de implementación: escribir la migración completa (tabla + función + los 3 triggers + política RLS de solo lectura) cuando se generen los archivos de Módulo 5. Reemplaza el diseño anterior de `contratos_historial` (limitado a una sola tabla).

### Interacción entre triggers — ruido en `auditoria_cambios` por cada pago (hallazgo de la revisión completa, esta sesión)
Al revisar toda la bitácora junta, se encontró una interacción no considerada entre dos triggers diseñados en momentos distintos: `trg_recalcular_saldo` (Módulo 4, sobre `pagos_historial`) hace `UPDATE contratos SET saldo_actual = ...` en cada pago — y esa misma UPDATE sobre `contratos` **dispara también** el trigger genérico de `auditoria_cambios` (Módulo 5, `AFTER UPDATE ON contratos`), generando una entrada de auditoría tipo "edición" por CADA pago registrado (ya que `saldo_actual` cambió), aunque nadie haya tocado el contrato a propósito.

**Consecuencia si no se corrige**: `auditoria_cambios` se llena de ruido — una entrada por cada cobro, diluyendo el valor real de la auditoría (que es rastrear ediciones humanas intencionales como cambios de alquiler, no fluctuaciones rutinarias de saldo).

**Corrección**: la función `fn_auditar_cambios()` debe excluir explícitamente la columna `saldo_actual` al comparar OLD vs NEW — cualquier otro cambio en `contratos` sigue quedando registrado normalmente, solo se ignora esta columna puntual (mantenida por su propio trigger dedicado, no necesita doble registro). Pendiente de implementación: agregar el filtro (`if v_key != 'saldo_actual' then ...`) dentro del loop de comparación de columnas cuando se escriba la función.

---

## Módulo 4 — Pagos (Registrar/Emitir Recibo)

**Estado: diseño cerrado**, salvo el trigger de saldo (ver más abajo, corregido en esta sesión).

### Conceptos editables + impactar cobro
- Recalcula ICL/IPC EN VIVO cada vez que se abre un contrato en Pagos (decisión explícita del usuario, igual que v1) — función propia, DISTINTA a `aplicar_actualizaciones_indices()` porque la elegibilidad es diferente (v1 mira "meses desde la última actualización aplicada", no "prox_actualizacion cae este mes"). No necesita SECURITY DEFINER: corre con usuario logueado, sobre contrato de su propia empresa, RLS normal alcanza.
- Honorarios y garantía: planes de cuotas idénticos en su lógica (total pactado ÷ cuotas pactadas, capado por saldo restante). Se portan 1:1, sin decisiones pendientes.
- Al confirmar: INSERT en `pagos_historial` + 3 UPDATE en `contratos` (mes_contrato, alquiler vigente, prox_actualizacion) — SOLO en pago Normal, NUNCA en Complemento (evita duplicar el avance del mes vivo).

### Tipos de pago
- **Normal**: primer pago del período.
- **Complemento**: ya existe fila para el período — NO dispara los 3 efectos secundarios sobre `contratos`. En el PDF, la línea de alquiler se suprime (reemplazada por "Complemento de pago — Alquiler ya registrado", monto $0) para no dar impresión de cobro duplicado.
- **Corrección**: ajuste manual, monto puede ser negativo (devolución).

### Saldo de contratos — MODELO FINAL: cuenta corriente (cambio de diseño respecto a v1)
Decisión del usuario: "quiero una implementación de v2 lo más limpia posible, con la menor cantidad de parches, que v1 y v2 sean lo más independientes una de otra". Con eso se descartó:
- ❌ Columna persistente actualizada desde código de aplicación (se desincroniza si alguien cobra desde v1).
- ❌ Fallback de texto libre en `comentario` para saldos viejos (confirmado con el usuario vía query real: 68/69 filas de prueba tenían comentario vacío, 1 sola con discrepancia que resultó ser un pago de prueba — se borró, no era un patrón real).
- ❌ Modelo "todo o nada" de v1 para saldar períodos viejos, y también se descartó la alternativa "parcial/proporcional" que propuse — el modelo de cuenta corriente vuelve la pregunta irrelevante.

**Modelo adoptado**: cada fila nueva de `pagos_historial.saldo_pendiente` guarda el **acumulado total** a esa fecha, no un saldo aislado de su propio período:
```
saldo_pendiente_nueva_fila = saldo_actual_antes + cargos_de_este_movimiento − pagado_de_este_movimiento
```
Unifica los 3 tipos de pago en una sola fórmula (Normal: cargos=alquiler+servicios del mes; Complemento: cargos=0; Corrección: cargos=diferencia ingresada, pagado=0). Sin `max(0, ...)` — un sobrepago queda como saldo negativo (a favor), corrigiendo un bug real de v1 donde el sobrepago se perdía sin dejar rastro.

**`contratos.saldo_actual`** (columna cacheada, numeric, default 0) mantenida por un **TRIGGER** de Postgres (`trg_recalcular_saldo` sobre INSERT/UPDATE/DELETE de `pagos_historial`) — NO por código de aplicación, para que v1 y v2 puedan seguir escribiendo pagos en paralelo sin coordinarse ni acoplarse. El día que se deje de usar v1, no hay que tocar nada de este mecanismo (nunca dependió de que v1 existiera).

**Fórmula del trigger — CORREGIDA en esta sesión** (ver `0003_saldo_contratos.sql`, ya corregido en el proyecto):
- ❌ Versión inicial (con bug): sumaba `saldo_pendiente` de la última fila de CADA período (`DISTINCT ON (periodo)`) — esto asume que cada fila es un saldo aislado. Bajo el modelo de cuenta corriente esto DUPLICA deuda ya arrastrada.
- ✅ Versión corregida: toma únicamente el `saldo_pendiente` de la fila más reciente del contrato en general (`ORDER BY id DESC LIMIT 1`, sin agrupar por período) — porque esa fila, bajo el modelo de cuenta corriente, YA incluye todo lo arrastrado.
- ✅ Backfill: **resuelto** con el mismo criterio de arriba (verificado con números concretos: la fórmula `total_a_cubrir` de v1 hornea la deuda vieja en cada fila nueva, así que la última fila del contrato ya es el total real acumulado — incluso para datos históricos de v1, aunque el mecanismo "todo o nada" nunca haya llegado a saldar los períodos viejos). No hace falta sumar entre períodos ni para el arranque histórico ni en el trigger — misma query en los dos casos.

### Hallazgo — posible bug de doble conteo en el propio v1
La lógica de v1 que arma `_saldos_anteriores_detalle` para mostrar en pantalla suma el `saldo_pendiente` de TODOS los períodos previos por separado. Si un inquilino se atrasa en más de un período consecutivo sin que el mecanismo "todo o nada" llegue a saldar todo de una vez, cada período viejo ya trae la deuda de los anteriores adentro (por la fórmula de `total_a_cubrir`) — sumarlos todos cuenta la misma deuda varias veces. Posible bug real en v1, independiente de v2, no confirmado en producción, pendiente que el usuario lo revise si le importa.

### Concurrencia al impactar cobro — hallazgo de esta sesión
Con el modelo de cuenta corriente, el cálculo del nuevo `saldo_pendiente` depende de LEER `saldo_actual` antes de escribir (`saldo_nuevo = saldo_actual_antes + cargos − pagado`). Dos cobros simultáneos al MISMO contrato (incluso de períodos distintos, a diferencia de v1) pueden generar un "lost update" si no se serializan. v1 ya resuelve esto con `pg_advisory_xact_lock(hashtext(codigo|periodo))` antes de leer/escribir — para v2 el candado tiene que ser por **contrato completo**, no por contrato+período (porque ahora todos los períodos comparten el mismo número corriente):
```sql
SELECT pg_advisory_xact_lock(hashtext(codigo_contrato));
-- recién ahí leer saldo_actual, calcular, e insertar la fila nueva
```
Pendiente: incluir este lock en el Server Action de "Impactar Cobro" cuando se genere el archivo.

### Permisos a nivel de columna — hallazgo de esta sesión
`saldo_actual` es la primera columna que se diseña para que NADIE la edite directamente — siempre a través del trigger. Las políticas RLS de la migración 0001 (`for all using (empresa_id = auth_empresa_id())`) cubren la fila entera de `contratos`, así que sin una restricción aparte, cualquier usuario autenticado podría hacer `UPDATE contratos SET saldo_actual = X` directo desde el cliente y pisar el saldo real sin pasar por `pagos_historial` ni por el trigger. Ya agregado a `0003_saldo_contratos.sql`:
```sql
revoke update (saldo_actual) on contratos from authenticated;
```
Esto es a nivel de COLUMNA (Postgres lo soporta), no toca las políticas RLS de fila ni el resto de columnas editables de `contratos`. Confirma que `recalcular_saldo_actual()` necesita seguir siendo `SECURITY DEFINER` — es la única puerta que queda abierta para escribir esa columna.

### `pagos_historial` como libro contable de solo inserción — hallazgo de esta sesión
Confirmado revisando app.py: v1 tiene UN SOLO lugar que hace `UPDATE` sobre `pagos_historial` en todo el archivo — el paso de "saldar períodos anteriores" (línea 4402), que el modelo de cuenta corriente ya reemplaza por completo. Ninguna otra función depende de editar una fila ya guardada. Con las políticas RLS actuales, cualquier usuario podría editar o borrar una fila vieja desde el cliente — rompiendo la confiabilidad del historial, y en el caso de la fila más reciente de un contrato, corrompiendo `saldo_actual` indirectamente (el trigger tomaría el valor editado como válido). Agregado a `0003_saldo_contratos.sql`:
```sql
revoke update, delete on pagos_historial from authenticated;
```
Cualquier corrección pasa a hacerse SIEMPRE agregando una fila tipo Corrección — nunca editando el pasado. No afecta al acceso directo a Postgres (rol `postgres`, usado para tareas administrativas puntuales vía SQL Editor).

### PDF/WhatsApp del comprobante
- PDF: Route Handler server-side con `@react-pdf/renderer`, mismo contenido que v1 (incluye supresión de línea de alquiler en Complemento, aviso de próxima actualización si cae en el período siguiente).
- **Mejora sobre v1 — contexto del Complemento en el PDF** (decisión del usuario, esta sesión): v1 muestra el Comprobante de un Complemento sin ninguna referencia al comprobante original que dejó el saldo pendiente — "Total Consolidado Percibido" queda en $0,00 y el monto real solo aparece suelto en el cuadro de "Monto Abonado", sin contexto. Para v2: agregar columna nueva `pagos_historial.comprobante_referencia` (text, nullable — solo se completa en pagos tipo Complemento, con el `nro_comprobante` de la fila Normal que dejó el saldo pendiente de ese período). El PDF de un Complemento pasa a mostrar:
  ```
  Total del período                    $ 500.000,00
  Ya abonado (Comprobante RC-...)     − $ 300.000,00
  ────────────────────────────────────
  Este pago cubre el saldo pendiente    $ 200.000,00
  ```
  en vez del "$0,00" desconectado que muestra v1 hoy. Requiere que, al insertar una fila Complemento, se busque el `nro_comprobante` de la última fila Normal de ese mismo período y se guarde en `comprobante_referencia`.
- Botón WhatsApp al inquilino: template Meta `comprobante_pago_alquiler` — **plantillas ya aprobadas por Meta, incluida la de PDF adjunto** (confirmado por el usuario esta sesión). Adjuntar el PDF generado al mensaje de WhatsApp, ya no queda pendiente/comentado como en v1.
- Botón "Enviarme a mí": simple link `wa.me` con texto precargado, sin usar la API de WhatsApp Business — se porta directo, sin decisiones pendientes.

---

## Limpieza de datos pendiente (fuera del código, acción del usuario en producción)

- Fila `pagos_historial.id = 33` (contrato 28, "Mes 5 de 12") — confirmado por el usuario como pago de prueba, a borrar con la transacción ya provista en el chat. Verificar que se haya ejecutado antes de considerar los datos de producción "limpios" para testear el nuevo modelo de saldo.

---

## Pendiente antes de generar archivos de Módulo 4

1. ~~Corregir el backfill de `0003_saldo_contratos.sql`~~ ✅ Resuelto esta sesión — mismo criterio que el trigger (última fila del contrato, sin agrupar por período).
2. ~~Confirmar si el template de WhatsApp con PDF adjunto ya fue aprobado por Meta.~~ ✅ Confirmado: aprobado. Adjuntar PDF al mensaje de WhatsApp del comprobante.
3. Agregar columna `pagos_historial.comprobante_referencia` (ver sección PDF/WhatsApp arriba) y la lógica para completarla en pagos Complemento.
4. Confirmar si el usuario corrió la query de control de "posible doble conteo" en v1 y si le importa que se corrija ahí también (fuera de alcance de v2, pero el usuario puede querer saberlo).
5. Implementar el advisory lock por contrato (`pg_advisory_xact_lock(hashtext(codigo_contrato))`) en el Server Action de "Impactar Cobro" — ver sección "Concurrencia al impactar cobro" arriba. Sin esto, dos cobros simultáneos al mismo contrato pueden perder un pago silenciosamente.

**Estado general: sin pendientes bloqueantes.** El punto 3 es una tarea de implementación (no una decisión abierta), y el punto 4 es informativo, no bloquea nada de v2. Módulo 3 y Módulo 4 están listos para generar archivos cuando el usuario lo pida.

---

## Módulo 10 — Panel de Gestión (diseño en progreso)

### Alta de empresa nueva — único lugar de v2 que necesita `service_role` (decisión de esta sesión)
Hallazgo: revisando "Crear Usuarios" en v1 (línea 6340+), se confirmó que **no existe ningún `INSERT INTO empresas` en todo `app.py`** — la tabla `empresas` se lee y hasta se puede borrar desde el Panel de Gestión, pero nunca se crea desde la app. Alta de empresa nueva hoy es 100% manual, por fuera del sistema. Usuario confirmó que quiere un flujo real y atómico en v2: crear empresa + primer usuario admin juntos.

**Por qué este es el único caso legítimo de `service_role` en todo el proyecto**: crear un usuario en Supabase Auth requiere la Admin API (`supabase.auth.admin.createUser/inviteUserByEmail`), que no es una operación de base de datos — no existe ninguna función SQL que la reemplace, a diferencia de todo lo demás que resolvimos con `SECURITY DEFINER`. Se restringe a un único Server Action, protegido por chequeo explícito de `rol === 'superadmin'`.

**Flujo diseñado**:
1. Validar `rol === 'superadmin'` en el propio Server Action.
2. `supabase.auth.admin.inviteUserByEmail(email)` — manda link mágico, evita generar/comunicar contraseña provisoria a mano. Devuelve `auth_user_id`.
3. En una transacción de Postgres: `INSERT INTO empresas` + `INSERT INTO usuarios_central` (con el `auth_user_id` del paso 2, `rol = 'admin'`) + permisos iniciales (todas las pestañas habilitadas para ese primer admin) + `INSERT INTO configuraciones_empresa` (ver corrección abajo).
4. Si el paso 3 falla, limpieza de compensación: `supabase.auth.admin.deleteUser()` sobre el usuario huérfano creado en el paso 2 (no es atómico de punta a punta porque el paso 2 vive fuera de Postgres, pero con esta compensación no queda nada a medio crear).

**Corrección — falta el INSERT de `configuraciones_empresa` (revisión adicional, esta sesión)**: el diseño original del paso 3 no incluía crear la fila en `configuraciones_empresa`. En v1 esa fila se crea perezosamente (`ON CONFLICT DO NOTHING`) la primera vez que alguien visita Configuraciones — frágil pero eventualmente se autocompleta. Sin este INSERT en el alta atómica de v2, una empresa nueva quedaría sin fila ahí hasta la primera visita a esa pantalla, con comportamiento inconsistente mientras tanto según si cada query usa `LEFT JOIN + COALESCE` (trata la ausencia como `false`) o un `JOIN` normal (la excluye silenciosamente). Se agrega al mismo paso 3:
```sql
INSERT INTO configuraciones_empresa (empresa_id, cron_indices_habilitado, whatsapp_habilitado, actualizar_alquiler_auto)
VALUES (nueva_empresa_id, false, false, true);
```
Toda empresa nueva arranca con una fila completa desde el primer segundo, sin depender de que alguien visite una pantalla para que exista.

**`archivo_db` / `password_hash` para usuarios creados por este flujo nuevo**: confirmado que estas columnas son `NOT NULL` hoy (`information_schema.columns`). Usuario confirmó que no busca que estos usuarios nuevos puedan loguearse en v1 — se decide relajar la constraint en vez de rellenar con placeholders falsos:
```sql
alter table usuarios_central alter column archivo_db drop not null;
alter table usuarios_central alter column password_hash drop not null;
```
No afecta a v1: sigue completando esas columnas con datos reales para los usuarios que él mismo crea, como siempre — la relajación solo habilita que v2 las deje `NULL` cuando corresponda, no le exige nada a v1.

### Eliminar empresa — dos bugs confirmados en v1, resueltos con función `SECURITY DEFINER` (hallazgo y decisión de esta sesión)
Revisando "Eliminar Empresa" (línea 7100-7143), se confirmaron dos bugs reales:
1. **`permisos_usuario` nunca se borra**: el propio código tiene un comentario en otro lugar (línea 6704) reconociendo *"permisos_usuario no tiene empresa_id — filtrar solo por username"* — pero el borrado de empresa igual intenta `DELETE FROM permisos_usuario WHERE empresa_id = %s`, que siempre falla (columna inexistente) y queda silenciado por un `try/except: pass` genérico por tabla. Cada empresa borrada hasta ahora dejó sus filas de `permisos_usuario` huérfanas.
2. **`liquidaciones_propietarios` y `configuraciones_empresa` no están en la lista de tablas a borrar** (`["pagos_historial", "gastos_propiedades", "permisos_usuario", "contratos", "inquilinos", "propiedades"]`), a pesar de tener `empresa_id` y usarse en otras partes del sistema — quedan huérfanas también.

**Decisión para v2**: reemplazar el loop con `try/except: pass` (que esconde errores) por una función `SECURITY DEFINER`:
```sql
eliminar_empresa_completa(p_empresa_id int, p_confirmacion_nombre text)
```
- Valida `auth_rol() = 'superadmin'` + que `p_confirmacion_nombre` coincida con el nombre real de la empresa (mismo patrón "escribí el nombre para confirmar" que ya tiene v1)
- Borra en una sola transacción real (todo o nada, sin silenciar errores): `pagos_historial`, `gastos_propiedades`, `contratos`, `inquilinos`, `propiedades`, `liquidaciones_propietarios`, `configuraciones_empresa`, `planilla_verificaciones`, `whatsapp_recordatorios`, `whatsapp_recordatorios_log`, `comprobantes_inquilino`, `reclamos_inquilino`, y `permisos_usuario` **filtrado por username** (arreglando el bug #1), no por `empresa_id`
- **`usuarios_central` NO se borra — decisión explícita del usuario** (revisión adicional, esta sesión: ni v1 ni el diseño original de esta función lo hacían, se confirmó que es intencional): los usuarios del staff de la empresa eliminada quedan con su fila intacta (`empresa_id` apuntando a una empresa que ya no existe), por si se reasignan a otra empresa más adelante. Sus cuentas de Supabase Auth (si ya migraron) siguen activas pero no ven nada útil — RLS los deja afuera de todo, ya que ningún `contratos.empresa_id` va a matchear su `empresa_id` huérfano.
- **Lista de tablas a mantener sincronizada**: cada vez que se agregue una tabla nueva con `empresa_id` al esquema (como pasó con `planilla_verificaciones`, `whatsapp_recordatorios*`, `comprobantes_inquilino`, `reclamos_inquilino` — todas agregadas en momentos distintos de esta conversación), hay que sumarla acá también. Se encontraron 2 veces en esta sesión tablas nuevas que quedaron afuera de esta función por no haberla actualizado en el momento — vale la pena revisarla una vez más justo antes de generar el archivo final, por si se agregó algo después de esta nota.
- **`auditoria_cambios` se preserva** — decisión explícita del usuario: mantener el rastro histórico de auditoría incluso después de que la empresa ya no exista, en vez de borrarlo también.

### Editar Usuario — cambio de contraseña unificado con la migración v1→v2 pendiente desde el inicio (decisión de esta sesión)
Hallazgo: en "Editar Usuario" (línea 6440), v1 deja escribir una contraseña nueva directo (campo de texto, hasheado con bcrypt). En v2 no existe ningún campo de contraseña editable — cambiar la contraseña de otro usuario también requiere la Admin API de Supabase (`service_role`), igual que crear un usuario nuevo.

Usuario definió el mecanismo: reset por link de email, con el superadmin/admin escribiendo o confirmando la dirección de email antes de mandarlo (no asumir que ya está bien cargada). **Esto resuelve, unificado, el pendiente de migración de autenticación que había quedado abierto desde el arranque del proyecto** (README original: cómo pasar usuarios de v1 con `password_hash`/bcrypt, sin `auth_user_id` ni email confirmado, a Supabase Auth):

```
Server Action "Enviar link de acceso" (admin/superadmin, con service_role):

  ¿el usuario ya tiene auth_user_id?
    NO  → primera vez (viene de v1, sin migrar) → supabase.auth.admin.inviteUserByEmail(email)
          → al volver, guardar auth_user_id + email en usuarios_central
    SÍ  → ya tiene cuenta v2 → supabase.auth.resetPasswordForEmail(email)
          → no se toca usuarios_central, ya está vinculado
```

Mismo patrón de seguridad que "Crear Usuarios": Server Action protegido por rol, `service_role` únicamente ahí adentro, nunca expuesto al cliente. Un admin (no superadmin) solo puede operar sobre usuarios de su propia empresa (`empresa_id` coincide).

---

## Módulo 8 — Recordatorios Automáticos por WhatsApp

### Bug GRAVE confirmado: el motor de envío ignora por completo el offset configurado (hallazgo de esta sesión)
Revisando el motor automático (líneas 2129-2253) contra la pantalla de configuración (líneas 7352-7459), se encontró una desconexión total entre lo que la UI promete y lo que el código hace:

- La UI dice "Agregar recordatorio X días antes" (hasta 365 para vencimiento, hasta 28 para actualización) — sugiere que se compara contra la fecha real de cada contrato.
- El motor real NUNCA hace esa comparación. Toma `_hoy_dia = hoy.day` (día calendario de hoy, 1-31) y busca `whatsapp_recordatorios WHERE dia_del_mes = _hoy_dia` (línea 2145) — comparando el número guardado (que la UI trata como un OFFSET de días) contra el día del mes actual, sin relación real con "antes de qué evento".
- Si encuentra coincidencia, manda el mensaje a **TODOS los contratos activos con teléfono** (línea 2175, loop sin ningún filtro de fecha por contrato) — no solo a los que efectivamente están a N días de su vencimiento/actualización.

**Consecuencia si se usa tal cual**: cada mes, en el día que coincida con el número configurado, TODOS los inquilinos reciben el aviso — sin importar si su contrato vence en 2 días o en 20 meses. Es spam masivo mensual, no un recordatorio dirigido.

**Verificado en producción** (`SELECT ... FROM configuraciones_empresa ce JOIN empresas ... LEFT JOIN whatsapp_recordatorios wr`): las 2 empresas tienen WhatsApp habilitado, pero **cero filas en `whatsapp_recordatorios`** — nunca se cargó ningún recordatorio. El bug nunca disparó, cero inquilinos afectados. Se resuelve igual de raíz para v2, no se replica el mecanismo roto.

### Diseño corregido para v2
```
Para cada contrato activo con teléfono:
  días_hasta_evento = fecha_del_evento (fin_contrato o prox_actualizacion) − hoy

  ¿existe un recordatorio ACTIVO configurado con offset = días_hasta_evento?
    → SÍ: mandar el mensaje a ESE contrato puntual
    → NO: no mandar nada para ese contrato hoy
```
La comparación se hace **por contrato individual**, contra SU fecha real — no un chequeo global de "día del mes" que dispara a ciegas para toda la cartera.

**Renombre de columna**: `whatsapp_recordatorios.dia_del_mes` → `dias_antes` en v2 — el nombre viejo ya sugería (incorrectamente) "día del mes calendario", que es exactamente la confusión que causó el bug. El nombre nuevo refleja lo que realmente es: un offset en días antes del evento.

### Deduplicación — recuperando `whatsapp_recordatorios_log` (hallazgo de revisión adicional, esta sesión)
El diseño corregido del motor (arriba) no tenía ningún resguardo contra envíos duplicados el mismo día — por ejemplo, si el cron reintenta tras una falla transitoria, o corre dos veces por error. Esto retoma la tabla `whatsapp_recordatorios_log` mencionada de pasada al mapear la arquitectura de WhatsApp al principio de la conversación, que se había perdido de vista al rediseñar la lógica del bug:
```sql
whatsapp_recordatorios_log (
  empresa_id, codigo_contrato, tipo, fecha_envio date, enviado boolean,
  UNIQUE (codigo_contrato, tipo, fecha_envio)
)
```
El motor corregido chequea esta tabla antes de mandar cada mensaje (¿ya existe fila para este contrato+tipo+hoy? → saltear). El `UNIQUE` es la red de seguridad real: aunque el código intentara enviarlo dos veces, el segundo `INSERT` falla por duplicado en vez de reenviar el mensaje.

Esta lógica corregida se integra naturalmente al cron diario consolidado ya diseñado en Módulo 3 (vencer → refrescar índices → aplicar índices) — puede sumarse como un cuarto paso, o correr como su propio Route Handler de cron aparte; a definir cuando se generen los archivos, según cuánto tarde cada paso en la práctica.

### Los 4 ítems originales de Módulo 8 — mapeo final, sin trabajo de diseño adicional
| Ítem original | Dónde está diseñado | Formato del mensaje |
|---|---|---|
| Vencimiento | Motor automático (este Módulo 8, recién corregido) | Texto (template WhatsApp, sin adjunto) |
| Actualización | Motor automático (este Módulo 8, recién corregido) | Texto (template WhatsApp, sin adjunto) |
| Recibo preliminar | Ya diseñado en Módulo 3 (Planilla) | **Solo texto** — template `recibo_preliminar_alquiler` con variables (nombre, mes, dirección, montos, fecha), confirmado en código (líneas 2693-2701): NO adjunta PDF ni ningún media |
| Comprobante definitivo | Ya diseñado en Módulo 4 (Pagos) | **Texto + PDF adjunto** (plantillas ya aprobadas por Meta, confirmado por el usuario) |

Diferencia importante para no confundir al implementar: preliminar es aviso rápido sin PDF (antes de cobrar), comprobante es el respaldo formal con PDF (después de cobrar). Módulo 8 no requiere ningún archivo/función nueva más allá de lo ya cubierto en Módulos 3 y 4, más el motor de vencimiento/actualización corregido arriba.

---

## Módulo 10 — resto (CSV, borrado en bloque)

### CSV de importación masiva — sin hallazgos de lógica de negocio, un detalle de consistencia
Revisado el importador de contratos (líneas 6752-6850+): es mecánico (mapeo columna CSV → columna DB vía `MAPEO_CONTRATOS`, valida que la propiedad/inquilino referenciado exista antes de insertar). No se encontraron bugs de negocio. Único detalle a cuidar en la implementación: el import escribe directo a `honorarios_pagados` y `garantia_pagada` (línea 6842) — el importador de v2 debe apuntar a las columnas nuevas `honorarios_pagados_base`/`garantia_pagada_base` (agregadas al lado de las originales, ver sección de Módulo 5 — no reemplazan a las viejas, que siguen siendo las que usa v1).

### Borrado en bloque (superadmin) — conflicto con `REVOKE DELETE` de pagos_historial, resuelto con función dedicada (hallazgo y decisión de esta sesión)
El panel "Gestión de Datos Central: Eliminar Filas / Registros en Bloque" (líneas 7152-7273) incluye `pagos_historial` en `TABLAS_PERMITIDAS` — permite al superadmin borrar filas de pagos en lote, con confirmación de tipeo (`"FORZAR BORRADO N FILAS"`). Esto **contradice directamente** la decisión ya tomada de `revoke update, delete on pagos_historial from authenticated` (pagos_historial como libro contable de solo inserción).

Usuario eligió resolver con una función `SECURITY DEFINER` dedicada — mismo patrón que el resto de operaciones sensibles de Módulo 10:
```sql
create or replace function eliminar_registros_bloque(
  p_tabla text, p_ids int[], p_empresa_id int, p_confirmacion text
)
returns int
language plpgsql
security definer
as $$
declare v_deleted int;
begin
  if auth_rol() != 'superadmin' then raise exception 'Solo superadmin puede usar esta función'; end if;
  if p_tabla not in ('contratos', 'inquilinos', 'propiedades', 'pagos_historial') then
    raise exception 'Tabla no permitida: %', p_tabla;
  end if;
  if p_confirmacion != format('FORZAR BORRADO %s FILAS', array_length(p_ids, 1)) then
    raise exception 'Confirmación incorrecta';
  end if;

  -- Validación de integridad referencial (revisión adicional, esta sesión):
  -- al no haber FK real entre contratos.alias_propiedad/dni_inquilino y
  -- propiedades/inquilinos (decisión deliberada, ver Módulo 3 — evita romper
  -- inserts de v1 por desajustes de mayúsculas/espacios), no hay ningún
  -- candado nativo que impida borrar una propiedad/inquilino con contratos
  -- activos apuntándole. Sin este chequeo, un borrado por error deja
  -- contratos con referencias rotas, fallando en silencio en cualquier
  -- pantalla que busque esos datos. Se valida acá, dentro de la función:
  if p_tabla = 'propiedades' then
    if exists (
      select 1 from contratos
      where empresa_id = p_empresa_id
        and alias_propiedad in (select alias_propiedad from propiedades where id = any(p_ids))
    ) then
      raise exception 'No se puede borrar: hay contratos que referencian estas propiedades';
    end if;
  elsif p_tabla = 'inquilinos' then
    if exists (
      select 1 from contratos
      where empresa_id = p_empresa_id
        and dni_inquilino in (select dni from inquilinos where id = any(p_ids))
    ) then
      raise exception 'No se puede borrar: hay contratos que referencian estos inquilinos';
    end if;
  end if;

  -- Registrar en auditoria_cambios ANTES de borrar (tipo_evento = 'borrado_masivo'),
  -- una vez por tabla afectada, con to_jsonb() de la fila completa antes de perderla.

  execute format('delete from %I where empresa_id = $1 and id = any($2)', p_tabla)
    using p_empresa_id, p_ids;
  get diagnostics v_deleted = row_count;
  return v_deleted;
end;
$$;
```

**Mejora sobre v1 de paso**: en v1 la frase de confirmación solo se valida en el código Python (Streamlit) — nada impide técnicamente saltearla llamando directo a la base. En v2 la validación vive DENTRO de la función, imposible de saltear.

Es la única puerta que puede cruzar el `REVOKE` de `pagos_historial` — angosta (allowlist fija de 4 tablas), auditada (queda registro en `auditoria_cambios` de qué se borró y quién, con el contenido completo de las filas antes de perderlas), y restringida a superadmin.

Pendiente de implementación: escribir el bloque completo de inserts a `auditoria_cambios` (uno por tabla, ya que la estructura de columnas difiere entre `contratos`/`inquilinos`/`propiedades`/`pagos_historial`) cuando se generen los archivos.

Nota menor de código: v1 tiene una rama muerta (`_TABLAS_SIN_EID` en líneas 7189/7192/7248) que nunca se alcanza porque el dropdown de selección de tabla (línea 7177-7182) solo ofrece las 4 tablas de `TABLAS_PERMITIDAS` — no se porta a v2, no tiene ningún propósito.

---

## Módulo 6 — Historial de Pagos

### "Retención Agencia" hardcodeada en $0 — bug de conexión, resuelto con el campo real que ya existe (hallazgo y decisión de esta sesión)
La query de `_cached_historial_pagos` (línea 1626) tiene `0 AS "_pct_admin"` literal — la columna "RETENCIÓN AGENCIA ($)" del reporte de Historial de Pagos siempre muestra $0, para todos los pagos, sin excepción. Parece una funcionalidad que quedó sin terminar de conectar.

Se encontró que **ya existe el dato real en otro lado**: `contratos.honorarios_pct` (campo por contrato, usado en Carga de Contratos línea 5667 para estimar la retención mensual: `alquiler × honorarios_pct / 100`). Usuario confirmó: el porcentaje es individual por contrato (no un valor único de empresa), con **7% como default al crear un contrato nuevo**.

**Nota importante**: v1 hoy usa **5%** como default cuando no hay valor previo (línea 5345) — el 7% es un cambio deliberado de v2 respecto al comportamiento actual de v1, no un simple port.

**CORRECCIÓN** (encontrada al diseñar Módulo 7/Rendición, revirtiendo la primera versión de esta decisión): la propuesta original de este apartado (join a `contratos.honorarios_pct`, recalcular con `alquiler`) estaba mal encaminada. Rastreando la cadena completa se encontró que Módulo 4 YA calcula y guarda este valor correctamente en cada pago:
```python
_ret_agencia = round(monto_abonado * c_datos['honorarios'] / 100.0, 2)  # honorarios = honorarios_pct del contrato
# se guarda en pagos_historial.monto_gasto_admin
```
Confirmado además en Módulo 7 (Rendición a Propietarios, línea 8362): la "Comisión Administrativa" real que se descuenta al propietario en la liquidación sale de `SUM(gasto_admin)` — es decir, de esta misma columna `monto_gasto_admin`, ya calculada sobre `monto_abonado` (lo efectivamente cobrado), no sobre el alquiler teórico.

**Decisión final para v2**: el fix de Módulo 6 NO necesita join a `contratos` ni recalcular nada — simplemente agregar `ph.monto_gasto_admin` a la query del Historial de Pagos (hoy ni siquiera se selecciona esa columna). El dato correcto ya existe, guardado por Módulo 4 en el momento de cada pago. De paso, renombrar el alias de salida `_pct_admin` (nombre engañoso, no es un porcentaje, es un monto en pesos) a algo como `_retencion_agencia`.

---

## Módulo 7 — Gastos de Propiedades

### Registro de gasto (individual/compartido) — sin hallazgos
Prorrateo entre propiedades de un grupo (`propiedades.grupo`, texto libre) en partes iguales (`monto / cantidad_unidades`). Lógica correcta, sin bugs. Nota menor sin importancia: el redondeo por unidad puede dejar centavos de diferencia contra el total original en divisiones no exactas — irrelevante en la práctica.

### Retención de gastos en Rendición — bug de atomicidad confirmado, resuelto con función única (hallazgo y decisión de esta sesión)
`_obtener_gastos_retencion_pendientes()` trae gastos "Extraordinarios" pagados por alguien que no sea el Propietario (Inmobiliaria/Inquilino/Otro) y no marcados `cobrado`, para retenerlos de la próxima liquidación. Al confirmar la liquidación (línea 8520-8548), se encontró que son **dos transacciones completamente separadas**:
1. `INSERT INTO liquidaciones_propietarios` — su propia conexión, se confirma sola.
2. `_marcar_gastos_como_cobrados()` (línea 1457) — conexión APARTE, llamada después, con un `except: pass` que silencia cualquier error.

Si el paso 2 falla después de que el paso 1 ya se confirmó, los gastos quedan `cobrado = FALSE` — y se van a retener DE NUEVO en la próxima liquidación de ese propietario, duplicando el descuento. Riesgo real, no solo teórico (a diferencia de otros hallazgos de esta sesión, este no depende de una configuración que nunca se activó — puede pasar en cualquier liquidación futura).

**Decisión**: unificar en una sola función SQL (sin `SECURITY DEFINER` — operación normal, ya cubierta por RLS, solo necesita atomicidad):
```sql
create or replace function registrar_liquidacion_propietario(
  p_empresa_id int, p_propietario text, p_periodo text,
  p_monto_calculado numeric, p_saldo_anterior numeric, p_retencion_gastos numeric,
  p_monto_a_liquidar numeric, p_monto_liquidado numeric, p_saldo_pendiente numeric,
  p_ids_gastos int[], p_registrado_por text
)
returns void
language plpgsql
as $$
begin
  insert into liquidaciones_propietarios (...) values (...)
    on conflict (empresa_id, propietario, periodo) do update set ...;
  update gastos_propiedades set cobrado = true, periodo_cobrado = p_periodo
    where empresa_id = p_empresa_id and id = any(p_ids_gastos);
end;
$$;
```
Al ser una sola función, Postgres la corre como una transacción única automáticamente — si el `UPDATE` de gastos falla, el `INSERT` de la liquidación se revierte también. No puede quedar un estado a medias.

### Aclaración importante: dos conceptos distintos comparten el nombre "honorarios" (para no confundirlos al implementar)
Al diseñar esto se encontró una confusión real (cometida y corregida en esta misma sesión, ver corrección en Módulo 6 arriba) — hay DOS cosas separadas usando la palabra "honorarios":

1. **`contratos.honorarios_pct`** → usado para calcular la **comisión administrativa continua**, mes a mes: `_ret_agencia = monto_abonado × honorarios_pct / 100`, guardada en `pagos_historial.monto_gasto_admin` en cada pago. Es lo que Rendición a Propietarios descuenta como "Comisión Adm." del Neto a Rendir.
2. **`monto_honorarios` / `honorarios_pagados_base` + ledger** (diseño de Módulo 5, patrón "base + ledger") → un **fee fijo aparte, pagado en cuotas** (total pactado ÷ cuotas pactadas), completamente independiente del punto 1. En Rendición aparece como parte de "Otros" (informativo, NO se descuenta del Neto a Rendir).

Son dos mecanismos distintos que casualmente comparten la raíz del nombre — al implementar, mantener las variables/columnas claramente diferenciadas (`honorarios_pct`/`gasto_admin` para la comisión continua vs. `honorarios_base`/ledger para el fee en cuotas) para no repetir la confusión.

---

## Módulo 9 — Portal del Inquilino (diseño desde cero, sin equivalente en v1)

Único módulo sin código previo que portar — v1 no tiene nada parecido. Diseño completo definido esta sesión:

### Autenticación
`inquilinos` recibe las mismas columnas que ya tiene `usuarios_central`: `auth_user_id uuid references auth.users(id)` (`email` ya existe). Usuario eligió cuenta completa (no link mágico sin contraseña) — mismo Server Action "Enviar link de acceso" ya diseñado para el staff, con un parámetro para indicar si apunta a `usuarios_central` o `inquilinos`. Sin diseño nuevo en esta parte.

### Aislamiento de datos (RLS nuevo)
Un inquilino no pertenece a una empresa — pertenece a su propio contrato. Función espejo de `auth_empresa_id()`:
```sql
create function auth_inquilino_dni() returns text
language sql security definer stable as $$
  select dni from inquilinos where auth_user_id = auth.uid();
$$;
```
Políticas RLS ADICIONALES (se combinan con OR sobre las del staff, no las reemplazan) en `contratos` (`dni_inquilino = auth_inquilino_dni()`), `pagos_historial` (vía join a sus contratos), y los PDFs de sus propios comprobantes en Storage. Nunca ve otros contratos, ni otros inquilinos de la misma propiedad.

**Corrección — caso de borde de multi-tenencia (revisión adicional, esta sesión)**: el mismo DNI puede ser inquilino de DOS empresas distintas usando v2 (persona real, dos contratos, dos filas en `inquilinos`, pero UN solo `auth_user_id`/email). `auth_inquilino_dni()` como función escalar (asume una sola fila por `auth_user_id`) se rompe en este caso. Corregido a comparación por conjunto, en cada política RLS:
```sql
-- En vez de: dni_inquilino = auth_inquilino_dni()
-- Usar:      dni_inquilino IN (SELECT dni FROM inquilinos WHERE auth_user_id = auth.uid())
```
Con esto, `inquilinos.auth_user_id` puede repetirse (mismo `auth.users.id` en varias filas, una por empresa) sin romper nada — la persona ve los contratos de ambas empresas sin conflicto. Pendiente de implementación: al invitar a un inquilino nuevo (Server Action "Enviar link de acceso"), si el email YA tiene una cuenta de Supabase Auth (porque ya es inquilino de otra empresa), reusar ese `auth_user_id` en vez de intentar crear una cuenta nueva (fallaría, Supabase no permite emails duplicados) — requiere un chequeo previo (`admin.getUserByEmail` o similar) antes de invitar.

### Acciones del inquilino (usuario confirmó: además de consulta, necesita poder actuar)

**Subir comprobante de pago** — tabla nueva:
```sql
comprobantes_inquilino (empresa_id, codigo_contrato, storage_path, monto_declarado, fecha_subida, estado: 'pendiente'|'aprobado'|'rechazado')
```
NO carga un pago real en `pagos_historial` automáticamente — queda pendiente de revisión en una bandeja nueva dentro de Módulo 4. El staff, si corresponde, registra el cobro real por el flujo normal ya diseñado, con el comprobante subido como respaldo visual. Evita que alguien se "autodeclare" un pago que nunca llegó.

**Avisar un problema** — tabla nueva:
```sql
reclamos_inquilino (empresa_id, codigo_contrato, descripcion, estado: 'abierto'|'en_progreso'|'resuelto', fecha, respuesta_staff, gasto_id int references gastos_propiedades(id) NULL)
```
Aparece en una bandeja para el staff. **`gasto_id` (decisión de esta sesión)**: nullable, conecta un reclamo con el gasto real que generó al resolverlo (ej. una reparación) — trazabilidad en los dos sentidos: desde el reclamo se ve qué gasto generó, y desde `gastos_propiedades` se puede ver de qué reclamo vino. El staff puede crear el gasto directo desde la pantalla del reclamo (precarga propiedad/fecha) o vincular uno ya cargado aparte.

---

## Verificación explícita: ¿el SQL altera el funcionamiento de v1? (auditoría pedida por el usuario, esta sesión)

Chequeo sistemático, con evidencia concreta del código, de los 4 riesgos clásicos al modificar una base compartida:

1. **¿Algún `INSERT` de v1 depende de la posición de las columnas (forma sin lista explícita)?** NO — confirmado revisando cada `INSERT INTO` de las tablas que tocamos (`contratos` líneas 6031/6887, `propiedades` línea 6165, `inquilinos` línea 6100, `pagos_historial` líneas 3376/4371, `usuarios_central` línea 6364, `configuraciones_empresa` línea 7307): TODOS nombran las columnas explícitamente. Agregar columnas nuevas es seguro — quedan al final, v1 nunca las menciona.
2. **¿v1 lee resultados por posición (`row[0]`) en vez de por nombre?** NO — confirmado: usa `psycopg2.extras.RealDictCursor` (línea 183), cada fila se accede por nombre de columna (`row['alquiler']`). Columnas nuevas son invisibles para v1, sin romper nada.
3. **¿Los `REVOKE` afectan al rol que usa v1?** NO — confirmado: v1 se conecta siempre como `postgres.<ref>` (línea 169), nunca como `authenticated` (que es a quien apuntan todos los `REVOKE` de esta sesión). v1 sigue teniendo acceso total, sin restricciones nuevas.
4. **¿Los triggers nuevos podrían tirar una excepción y bloquear la escritura original de v1?** Riesgo real encontrado y corregido: como los triggers corren en la MISMA transacción que el `INSERT`/`UPDATE` que los dispara (sea de v1 o v2), cualquier excepción adentro del trigger (por ejemplo, si `auditoria_cambios.empresa_id NOT NULL` se violara por algún caso de borde de datos) arrastraría también la escritura original. Corrección: envolver ambos triggers (`fn_auditar_cambios`, `recalcular_saldo_actual`) en un bloque `EXCEPTION WHEN OTHERS THEN return NEW/NULL` — un fallo en auditoría o en el cacheo de saldo NUNCA debe poder bloquear la operación real del usuario, ni en v1 ni en v2. Pendiente de implementación: agregar este bloque a ambas funciones cuando se generen los archivos finales.

**Conclusión de la auditoría**: ninguna migración diseñada en esta conversación hace `DROP TABLE`, `DROP COLUMN`, `DELETE` de datos existentes, ni `RENAME` de columnas que v1 usa (el único caso encontrado de rename ya fue corregido arriba, a columnas nuevas + copia). Las únicas dos operaciones que borran datos (`eliminar_empresa_completa`, `eliminar_registros_bloque`) son funciones opt-in, jamás se ejecutan como parte de aplicar las migraciones.

---

## Implementación — hallazgos durante la generación de código (Módulo 8 y Módulo 3)

### Módulo 8: tablas `whatsapp_recordatorios`/`whatsapp_recordatorios_log` YA EXISTEN en producción
Al escribir la migración se encontró que estas tablas no son nuevas — las creó v1 (confirmado porque la query de verificación de esta sesión, que devolvió 0 filas, solo funciona si la tabla existe). La nota de diseño decía "renombrar `dia_del_mes` → `dias_antes`" — mismo error de rename que ya se había corregido una vez para `honorarios_pagados`. Corregido en `0010_whatsapp_recordatorios.sql`: columna `dias_antes` nueva, al lado de `dia_del_mes` (intacta, v1 sigue usándola).

También se encontró que el cron (sin sesión de usuario) no puede leer `whatsapp_recordatorios`/`contratos`/`configuraciones_empresa` de todas las empresas con el cliente normal (RLS se lo bloquea, `auth_empresa_id()` es null sin sesión) — se agregaron dos funciones `SECURITY DEFINER` no contempladas en el diseño original: `obtener_recordatorios_pendientes()` (hace la comparación real por contrato — es, literalmente, el fix del bug) y `obtener_credenciales_whatsapp_cron()`. Protegidas con el mismo secreto de cron que las funciones de Módulo 3.

### Módulo 3: `indices_historicos` no puede servir de caché para el cron sin un backfill histórico
Al implementar el paso 3 del cron ("aplicar índices"), se intentó optimizarlo para leer de `indices_historicos` (ya refrescada por el paso 2) en vez de pegarle de nuevo a BCRA/datos.gob.ar por cada contrato elegible. Se encontró que esto **rompería silenciosamente** la actualización de cualquier contrato con más de ~30 días de antigüedad: el paso 2 solo refresca datos RECIENTES (el año actual), pero calcular el índice de un contrato viejo necesita el valor del índice **en la fecha en que arrancó ese contrato**, que puede ser de años atrás — dato que `indices_historicos` nunca tendría sin un backfill histórico completo (no diseñado, fuera de alcance por ahora).

**Corrección real aplicada**: en vez de una tabla de caché, se agregó una **caché en memoria por año**, dentro de `lib/indices/fuentes.ts`, que vive solo mientras dura una ejecución del cron — evita pedirle el mismo año a BCRA más de una vez por corrida (el problema real que se quería resolver), sin la falla de cobertura histórica de la tabla. `calcularValorActualizado()` sigue siendo una sola función, usada tanto por el botón manual como por el cron — ya no hace falta una versión "de caché" aparte. `indices_historicos` se sigue llenando igual (serie completa, no recortada a 30 días) como registro de referencia para el futuro, pero el cálculo ya no depende de leerla.
