-- =====================================================================
-- esquema_2026-09-29.sql — FOTO DEL ESQUEMA REAL (29/09/2026)
--
-- ⚠️  NO EJECUTAR CONTRA PRODUCCIÓN. Es documentación: describe la base tal
-- como estaba el 29/09/2026 (leída con las consultas de diagnóstico), con
-- las migraciones 0001–0018 ya aplicadas, cambios hechos a mano y objetos
-- creados por Python. Sirve como referencia y como punto de partida para
-- recrear la base en un entorno de prueba.
--
-- Después de esta foto se aplicaron, en este orden:
--   - 29/09/2026: revoke de 8 funciones (ver sección final).
--   - 0021_seguridad_y_fechas.sql.
-- Generado automáticamente; el orden de creación no garantiza que corra
-- de punta a punta sin ajustes (dependencias entre funciones y tablas).
-- =====================================================================

-- ── Tablas ──────────────────────────────────────────────────────────

create table public.auditoria_cambios (
  id bigint default nextval('auditoria_cambios_id_seq'::regclass) not null,
  empresa_id integer not null,
  tabla text not null,
  registro_id text not null,
  tipo_evento text not null,
  cambios jsonb,
  realizado_por text,
  fecha timestamp with time zone default now() not null,
  constraint auditoria_cambios_pkey PRIMARY KEY (id)
);
alter table public.auditoria_cambios enable row level security;

create table public.comprobantes_inquilino (
  id bigint default nextval('comprobantes_inquilino_id_seq'::regclass) not null,
  empresa_id integer not null,
  codigo_contrato integer not null,
  storage_path text not null,
  monto_declarado numeric,
  fecha_subida timestamp with time zone default now() not null,
  estado text default 'pendiente'::text not null,
  revisado_por text,
  fecha_revision timestamp with time zone,
  constraint comprobantes_inquilino_pkey PRIMARY KEY (id),
  constraint comprobantes_inquilino_estado_check CHECK ((estado = ANY (ARRAY['pendiente'::text, 'aprobado'::text, 'rechazado'::text])))
);
alter table public.comprobantes_inquilino enable row level security;

create table public.configuraciones_empresa (
  empresa_id integer not null,
  actualizar_alquiler_auto boolean default true,
  whatsapp_habilitado boolean default false,
  whatsapp_token text,
  whatsapp_phone_id text,
  whatsapp_credenciales_propias boolean default false,
  whatsapp_numero_id integer,
  whatsapp_token_secret_id uuid,
  cron_indices_habilitado boolean default false not null,
  timeout_inactividad_minutos integer default 30 not null,
  ultima_cotizacion_usd numeric,
  ultima_cotizacion_fecha timestamp with time zone,
  constraint configuraciones_empresa_pkey PRIMARY KEY (empresa_id),
  constraint timeout_inactividad_minutos_positivo CHECK ((timeout_inactividad_minutos > 0))
);
alter table public.configuraciones_empresa enable row level security;

create table public.contratos (
  codigo integer default nextval('contratos_codigo_seq'::regclass) not null,
  empresa_id integer not null,
  alias_propiedad text,
  dni_inquilino text,
  estado text not null,
  inicio_contrato text,
  fin_contrato text,
  calc_duracion integer,
  act_contrato integer,
  indice text,
  monto_inicial real,
  alquiler real,
  prox_actualizacion text,
  mes_contrato integer,
  mes_actualizacion_contrato integer,
  servicios text,
  honorarios numeric,
  monto_honorarios real,
  cuota_honorarios integer,
  honorarios_pagados real default 0,
  cuotas_honorarios_pagadas integer default 0,
  tipo_de_garantie text,
  monto_garantia real,
  garantia text,
  garantia_pagada real default 0,
  cuotas_deposito integer default 1,
  cuotas_deposito_pagadas integer default 0,
  imp_inmobiliario real default 0,
  expensas real default 0,
  edesal real default 0,
  gas real default 0,
  municipalidad real default 0,
  ooss real default 0,
  servicios_total real default 0,
  cochera real default 0,
  alquiler_cobrado real default 0,
  total_pagado real default 0,
  alquiler_calculado numeric,
  alquiler_calculado_fecha text,
  saldo_actual numeric default 0 not null,
  fecha_finalizacion date,
  finalizado_por text,
  archivado boolean default false not null,
  honorarios_pagados_base numeric default 0 not null,
  cuotas_honorarios_pagadas_base integer default 0 not null,
  garantia_pagada_base numeric default 0 not null,
  cuotas_deposito_pagadas_base integer default 0 not null,
  cargo_electricidad text default 'Inquilino'::text,
  cargo_gas text default 'Inquilino'::text,
  cargo_municipalidad text default 'Inquilino'::text,
  cargo_ooss text default 'Inquilino'::text,
  cargo_expensas text default 'Inquilino'::text,
  cargo_imp_inmobiliario text default 'Propietario'::text,
  updated_at timestamp with time zone default now() not null,
  constraint contratos_pkey PRIMARY KEY (codigo),
  constraint contratos_cargo_electricidad_check CHECK ((cargo_electricidad = ANY (ARRAY['Inquilino'::text, 'Propietario'::text]))),
  constraint contratos_cargo_expensas_check CHECK ((cargo_expensas = ANY (ARRAY['Inquilino'::text, 'Propietario'::text]))),
  constraint contratos_cargo_gas_check CHECK ((cargo_gas = ANY (ARRAY['Inquilino'::text, 'Propietario'::text]))),
  constraint contratos_cargo_imp_inmobiliario_check CHECK ((cargo_imp_inmobiliario = ANY (ARRAY['Inquilino'::text, 'Propietario'::text]))),
  constraint contratos_cargo_municipalidad_check CHECK ((cargo_municipalidad = ANY (ARRAY['Inquilino'::text, 'Propietario'::text]))),
  constraint contratos_cargo_ooss_check CHECK ((cargo_ooss = ANY (ARRAY['Inquilino'::text, 'Propietario'::text]))),
  constraint contratos_finalizado_por_check CHECK ((finalizado_por = ANY (ARRAY['auto_vencimiento'::text, 'renovacion'::text])))
);
alter table public.contratos enable row level security;

create table public.ediciones_presencia (
  id bigint default nextval('ediciones_presencia_id_seq'::regclass) not null,
  empresa_id integer not null,
  tabla text not null,
  registro_id text not null,
  username text not null,
  actualizado_en timestamp with time zone default now() not null,
  constraint ediciones_presencia_pkey PRIMARY KEY (id),
  constraint ediciones_presencia_tabla_registro_id_username_key UNIQUE (tabla, registro_id, username)
);
alter table public.ediciones_presencia enable row level security;

create table public.empresas (
  id integer default nextval('empresas_id_seq'::regclass) not null,
  nombre_comercial text not null,
  archivo_db text not null,
  constraint empresas_pkey PRIMARY KEY (id),
  constraint empresas_archivo_db_key UNIQUE (archivo_db)
);
alter table public.empresas enable row level security;

create table public.gastos_propiedades (
  id integer default nextval('gastos_propiedades_id_seq'::regclass) not null,
  empresa_id integer not null,
  propiedad_id integer,
  fecha text not null,
  categoria text not null,
  descripcion text,
  monto real not null,
  proveedor text,
  comprobante text,
  pagado_por text,
  observaciones text,
  tipo_gasto text default 'Extraordinario'::text,
  cobrado boolean default false,
  periodo_cobrado text,
  cotizacion_usd numeric default 0,
  constraint gastos_propiedades_pkey PRIMARY KEY (id)
);
alter table public.gastos_propiedades enable row level security;

create table public.indices_historicos (
  tipo text not null,
  fecha date not null,
  valor numeric not null,
  constraint indices_historicos_pkey PRIMARY KEY (tipo, fecha),
  constraint indices_historicos_tipo_check CHECK ((tipo = ANY (ARRAY['ICL'::text, 'IPC'::text, 'UVA'::text])))
);
alter table public.indices_historicos enable row level security;

create table public.inquilinos (
  id integer default nextval('inquilinos_id_seq'::regclass) not null,
  empresa_id integer not null,
  apellidos text not null,
  nombres text not null,
  dni text,
  telefono text,
  email text,
  auth_user_id uuid,
  updated_at timestamp with time zone default now() not null,
  constraint inquilinos_pkey PRIMARY KEY (id),
  constraint inquilinos_empresa_id_dni_key UNIQUE (empresa_id, dni)
);
alter table public.inquilinos enable row level security;

create table public.liquidaciones_propietarios (
  id integer default nextval('liquidaciones_propietarios_id_seq'::regclass) not null,
  empresa_id integer not null,
  propietario text not null,
  periodo text not null,
  monto_calculado numeric default 0,
  saldo_anterior numeric default 0,
  monto_a_liquidar numeric default 0,
  monto_liquidado numeric default 0,
  saldo_pendiente numeric default 0,
  fecha_liquidacion text,
  registrado_por text,
  comentario text,
  monto_retencion_gastos numeric default 0,
  constraint liquidaciones_propietarios_pkey PRIMARY KEY (id),
  constraint liquidaciones_propietarios_empresa_id_propietario_periodo_key UNIQUE (empresa_id, propietario, periodo)
);
alter table public.liquidaciones_propietarios enable row level security;

create table public.pagos_historial (
  id integer default nextval('pagos_historial_id_seq'::regclass) not null,
  empresa_id integer not null,
  codigo_contrato integer,
  username text,
  pestana text,
  fecha text,
  periodo text,
  inquilino text,
  propiedad text,
  monto_alquiler real default 0,
  monto_expensas real default 0,
  monto_edesal real default 0,
  monto_gas real default 0,
  monto_municipalidad real default 0,
  monto_cochera real default 0,
  monto_ooss real default 0,
  monto_imp_inmobiliario real default 0,
  monto_honorarios real default 0,
  monto_garantia real default 0,
  monto_abonado real default 0,
  saldo_pendiente real default 0,
  saldos_anteriores real default 0,
  metodo_pago text,
  comentario text,
  cotizacion_usd numeric default 0,
  registrado_por character varying default ''::character varying,
  nro_comprobante character varying default ''::character varying,
  monto_gasto_admin numeric default 0,
  concepto_extra_desc text default ''::text,
  monto_concepto_extra numeric default 0,
  tipo_pago text default 'Normal'::text,
  comprobante_referencia text,
  constraint pagos_historial_pkey PRIMARY KEY (id)
);
alter table public.pagos_historial enable row level security;

create table public.permisos_usuario (
  id integer default nextval('permisos_usuario_id_seq'::regclass) not null,
  username text not null,
  pestana text not null,
  constraint permisos_usuario_pkey PRIMARY KEY (id),
  constraint permisos_usuario_username_pestana_key UNIQUE (username, pestana)
);
alter table public.permisos_usuario enable row level security;

create table public.planilla_verificaciones (
  id bigint default nextval('planilla_verificaciones_id_seq'::regclass) not null,
  empresa_id integer not null,
  codigo_contrato integer not null,
  periodo text not null,
  verificado boolean default false not null,
  expensas_adhoc numeric,
  verificado_por text,
  verificado_fecha timestamp with time zone,
  constraint planilla_verificaciones_pkey PRIMARY KEY (id),
  constraint planilla_verificaciones_codigo_contrato_periodo_key UNIQUE (codigo_contrato, periodo)
);
alter table public.planilla_verificaciones enable row level security;

create table public.propiedades (
  id integer default nextval('propiedades_id_seq'::regclass) not null,
  empresa_id integer not null,
  alias_propiedad text not null,
  calle text not null,
  numero text not null,
  departamento text,
  propietario text,
  ciudad text,
  provincia text,
  tipo text,
  nis text,
  cuenta_gas text,
  finca text,
  cuenta_ooss text,
  nro_padron text,
  grupo text,
  updated_at timestamp with time zone default now() not null,
  expensas_administrada_por_propietario boolean default false not null,
  constraint propiedades_pkey PRIMARY KEY (id),
  constraint propiedades_empresa_id_alias_propiedad_key UNIQUE (empresa_id, alias_propiedad)
);
alter table public.propiedades enable row level security;

create table public.reclamos_inquilino (
  id bigint default nextval('reclamos_inquilino_id_seq'::regclass) not null,
  empresa_id integer not null,
  codigo_contrato integer not null,
  descripcion text not null,
  estado text default 'abierto'::text not null,
  fecha timestamp with time zone default now() not null,
  respuesta_staff text,
  gasto_id integer,
  constraint reclamos_inquilino_pkey PRIMARY KEY (id),
  constraint reclamos_inquilino_estado_check CHECK ((estado = ANY (ARRAY['abierto'::text, 'en_progreso'::text, 'resuelto'::text])))
);
alter table public.reclamos_inquilino enable row level security;

create table public.usuarios_central (
  username text not null,
  password_hash text,
  nombre_empresa text not null,
  archivo_db text,
  rol text default 'user'::text not null,
  apellidos text,
  nombres text,
  telefono text,
  propietario_filtro text,
  terminos_aceptados boolean default false,
  terminos_fecha text,
  auth_user_id uuid,
  email text,
  empresa_id integer,
  updated_at timestamp with time zone default now() not null,
  constraint usuarios_central_pkey PRIMARY KEY (username)
);
alter table public.usuarios_central enable row level security;

create table public.whatsapp_numeros (
  id integer default nextval('whatsapp_numeros_id_seq'::regclass) not null,
  nombre text not null,
  phone_id text not null,
  activo boolean default true,
  creado_en text default (now())::text,
  token_secret_id uuid,
  constraint whatsapp_numeros_pkey PRIMARY KEY (id)
);
alter table public.whatsapp_numeros enable row level security;

create table public.whatsapp_recordatorios (
  id integer default nextval('whatsapp_recordatorios_id_seq'::regclass) not null,
  empresa_id integer,
  tipo text not null,
  activo boolean default true,
  dia_del_mes integer,
  dias_antes integer,
  constraint whatsapp_recordatorios_pkey PRIMARY KEY (id)
);
alter table public.whatsapp_recordatorios enable row level security;

create table public.whatsapp_recordatorios_log (
  id integer default nextval('whatsapp_recordatorios_log_id_seq'::regclass) not null,
  empresa_id integer,
  tipo text,
  codigo_contrato integer,
  fecha_envio text,
  enviado boolean default true,
  constraint whatsapp_recordatorios_log_pkey PRIMARY KEY (id),
  constraint whatsapp_recordatorios_log_dedup_key UNIQUE (codigo_contrato, tipo, fecha_envio)
);
alter table public.whatsapp_recordatorios_log enable row level security;

-- ── Claves foráneas ─────────────────────────────────────────────────

alter table configuraciones_empresa add constraint configuraciones_empresa_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES empresas(id);
alter table configuraciones_empresa add constraint configuraciones_empresa_whatsapp_numero_id_fkey FOREIGN KEY (whatsapp_numero_id) REFERENCES whatsapp_numeros(id);
alter table contratos add constraint contratos_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES empresas(id);
alter table ediciones_presencia add constraint ediciones_presencia_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES empresas(id);
alter table gastos_propiedades add constraint gastos_propiedades_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES empresas(id);
alter table gastos_propiedades add constraint gastos_propiedades_propiedad_id_fkey FOREIGN KEY (propiedad_id) REFERENCES propiedades(id);
alter table inquilinos add constraint inquilinos_auth_user_id_fkey FOREIGN KEY (auth_user_id) REFERENCES auth.users(id);
alter table inquilinos add constraint inquilinos_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES empresas(id);
alter table pagos_historial add constraint pagos_historial_codigo_contrato_fkey FOREIGN KEY (codigo_contrato) REFERENCES contratos(codigo);
alter table pagos_historial add constraint pagos_historial_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES empresas(id);
alter table propiedades add constraint propiedades_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES empresas(id);
alter table reclamos_inquilino add constraint reclamos_inquilino_gasto_id_fkey FOREIGN KEY (gasto_id) REFERENCES gastos_propiedades(id);
alter table usuarios_central add constraint usuarios_central_auth_user_id_fkey FOREIGN KEY (auth_user_id) REFERENCES auth.users(id);
alter table usuarios_central add constraint usuarios_central_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES empresas(id);
alter table whatsapp_recordatorios add constraint whatsapp_recordatorios_empresa_id_fkey FOREIGN KEY (empresa_id) REFERENCES empresas(id);

-- ── Índices (los de PK/UNIQUE los crean las constraints) ────────────

CREATE INDEX idx_comprobantes_inquilino_empresa_id ON public.comprobantes_inquilino USING btree (empresa_id);
CREATE INDEX idx_configuraciones_empresa_empresa_id ON public.configuraciones_empresa USING btree (empresa_id);
CREATE INDEX idx_contratos_empresa_id ON public.contratos USING btree (empresa_id);
CREATE INDEX ediciones_presencia_lookup ON public.ediciones_presencia USING btree (tabla, registro_id, actualizado_en);
CREATE INDEX idx_gastos_propiedades_empresa_id ON public.gastos_propiedades USING btree (empresa_id);
CREATE INDEX idx_inquilinos_empresa_id ON public.inquilinos USING btree (empresa_id);
CREATE INDEX idx_liquidaciones_propietarios_empresa_id ON public.liquidaciones_propietarios USING btree (empresa_id);
CREATE INDEX idx_pagos_historial_empresa_id ON public.pagos_historial USING btree (empresa_id);
CREATE UNIQUE INDEX uq_pagos_nro_comprobante ON public.pagos_historial USING btree (nro_comprobante) WHERE ((nro_comprobante IS NOT NULL) AND ((nro_comprobante)::text <> ''::text));
CREATE INDEX idx_propiedades_empresa_id ON public.propiedades USING btree (empresa_id);
CREATE INDEX idx_reclamos_inquilino_empresa_id ON public.reclamos_inquilino USING btree (empresa_id);
CREATE INDEX idx_usuarios_central_empresa_id ON public.usuarios_central USING btree (empresa_id);
CREATE UNIQUE INDEX usuarios_central_auth_user_id_key ON public.usuarios_central USING btree (auth_user_id);
CREATE UNIQUE INDEX usuarios_central_email_key ON public.usuarios_central USING btree (email);

-- ── Funciones ───────────────────────────────────────────────────────

-- actualizar_token_whatsapp (security definer: True)
CREATE OR REPLACE FUNCTION public.actualizar_token_whatsapp(p_secret_id uuid, p_token text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
BEGIN
    PERFORM vault.update_secret(p_secret_id, p_token);
END;
$function$;

-- aplicar_actualizacion_individual (security definer: True)
CREATE OR REPLACE FUNCTION public.aplicar_actualizacion_individual(p_codigo_contrato integer, p_valor_calculado numeric, p_empresa_id integer, p_secret_cron text DEFAULT NULL::text)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
declare
  v_secret_real text;
  v_contrato record;
  v_hoy date := current_date;
begin
  -- Autorización: o bien el secreto de cron es correcto (modo global),
  -- o el empresa_id coincide con el de quien llama (modo manual).
  if p_secret_cron is not null then
    select decrypted_secret into v_secret_real
    from vault.decrypted_secrets where name = 'cron_secret';
    if p_secret_cron != v_secret_real then
      raise exception 'Secreto de cron inválido';
    end if;
  elsif p_empresa_id != auth_empresa_id() and auth_rol() != 'superadmin' then
    raise exception 'No autorizado para operar sobre esta empresa';
  end if;

  select * into v_contrato from contratos
  where codigo = p_codigo_contrato and empresa_id = p_empresa_id and estado = 'Activo';

  if v_contrato is null then
    return false;
  end if;

  update contratos
  set alquiler_calculado = p_valor_calculado,
      alquiler_calculado_fecha = v_hoy
  where codigo = p_codigo_contrato and empresa_id = p_empresa_id;

  return true;
exception when others then
  -- Blindaje: nunca debe bloquear otras actualizaciones del mismo lote.
  return false;
end;
$function$;

-- auth_empresa_id (security definer: True)
CREATE OR REPLACE FUNCTION public.auth_empresa_id()
 RETURNS integer
 LANGUAGE sql
 STABLE SECURITY DEFINER
AS $function$
  select empresa_id from usuarios_central where auth_user_id = auth.uid();
$function$;

-- auth_rol (security definer: True)
CREATE OR REPLACE FUNCTION public.auth_rol()
 RETURNS text
 LANGUAGE sql
 STABLE SECURITY DEFINER
AS $function$
  select rol from usuarios_central where auth_user_id = auth.uid();
$function$;

-- calcular_valores_contrato (security definer: False)
CREATE OR REPLACE FUNCTION public.calcular_valores_contrato()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    -- Solo procesar contratos Activos con fecha de inicio
    IF NEW.inicio_contrato IS NULL OR NEW.inicio_contrato = '' THEN
        RETURN NEW;
    END IF;

    -- Calcular fin_contrato si es NULL
    IF (NEW.fin_contrato IS NULL OR NEW.fin_contrato = '') 
       AND NEW.calc_duracion IS NOT NULL AND NEW.calc_duracion > 0 THEN
        NEW.fin_contrato := (NEW.inicio_contrato::date + 
                             NEW.calc_duracion * INTERVAL '1 month')::date::text;
    END IF;

    -- Calcular prox_actualizacion si es NULL
    IF (NEW.prox_actualizacion IS NULL OR NEW.prox_actualizacion = '')
       AND NEW.act_contrato IS NOT NULL AND NEW.act_contrato > 0 THEN
        NEW.prox_actualizacion := (
            NEW.inicio_contrato::date + 
            (
                CEIL(
                    (CURRENT_DATE - NEW.inicio_contrato::date)::numeric / 
                    (NEW.act_contrato * 30.44)
                ) * NEW.act_contrato
            ) * INTERVAL '1 month'
        )::date::text;
    END IF;

    -- Inicializar mes_contrato en 1 si es NULL
    IF NEW.mes_contrato IS NULL THEN
        NEW.mes_contrato := 1;
    END IF;

    -- Inicializar mes_actualizacion_contrato si es NULL
    IF NEW.mes_actualizacion_contrato IS NULL AND NEW.act_contrato IS NOT NULL THEN
        NEW.mes_actualizacion_contrato := NEW.act_contrato;
    END IF;

    RETURN NEW;
END;
$function$;

-- contratos_elegibles_actualizacion (security definer: True)
CREATE OR REPLACE FUNCTION public.contratos_elegibles_actualizacion(p_empresa_id integer, p_solo_pendientes boolean DEFAULT false)
 RETURNS TABLE(codigo integer, empresa_id integer, alias_propiedad text, monto_inicial numeric, fecha_inicio text, indice text, frecuencia_meses integer)
 LANGUAGE sql
 STABLE SECURITY DEFINER
AS $function$
  -- Notas de esquema real (auditado contra volcado de producción + app.py):
  --   • `contratos` no tiene columna `fecha_inicio` — es `inicio_contrato`.
  --     Se alias-ea acá para no tocar el código TypeScript que ya consume
  --     el resultado de esta función como `fecha_inicio`.
  --   • `inicio_contrato`, `prox_actualizacion` y `alquiler_calculado_fecha`
  --     son TEXT en la base real (no `date`) — de ahí el ::date explícito
  --     abajo. Se devuelve `fecha_inicio` como texto tal cual (sin castear)
  --     para no romper si algún registro viejo no está en formato ISO.
  --   • No existe `frecuencia_actualizacion` (enum de texto asumido) — la
  --     frecuencia real ya está en `act_contrato`, un integer con la
  --     cantidad de meses directamente (1, 2, 3, 4, 6, 12, 24 — confirmado
  --     contra app.py, "opciones_meses").
  select
    c.codigo, c.empresa_id, c.alias_propiedad, c.monto_inicial,
    c.inicio_contrato as fecha_inicio,
    c.indice,
    coalesce(c.act_contrato, 6) as frecuencia_meses
  from contratos c
  join configuraciones_empresa ce on ce.empresa_id = c.empresa_id
  where c.estado = 'Activo'
    and c.indice in ('ICL', 'IPC', 'UVA')
    and c.prox_actualizacion is not null
    and date_trunc('month', c.prox_actualizacion::date) = date_trunc('month', current_date)
    and (p_empresa_id is null or c.empresa_id = p_empresa_id)
    and (p_empresa_id is not null or ce.cron_indices_habilitado = true) -- modo cron: solo empresas opt-in
    and (
      not p_solo_pendientes
      or c.alquiler_calculado_fecha is null
      or date_trunc('month', c.alquiler_calculado_fecha::date) != date_trunc('month', current_date)
    );
$function$;

-- eliminar_empresa_completa (security definer: True)
CREATE OR REPLACE FUNCTION public.eliminar_empresa_completa(p_empresa_id integer, p_confirmacion_nombre text)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
declare
  v_nombre_real text;
  v_usernames text[];
begin
  if auth_rol() != 'superadmin' then
    raise exception 'Solo superadmin puede eliminar una empresa';
  end if;

  select nombre_comercial into v_nombre_real from empresas where id = p_empresa_id;
  if v_nombre_real is null then
    raise exception 'Empresa no encontrada';
  end if;
  if p_confirmacion_nombre != v_nombre_real then
    raise exception 'El nombre de confirmación no coincide';
  end if;

  -- usernames del staff de esta empresa, para el borrado de permisos_usuario
  -- (que no tiene empresa_id — se filtra por username, arreglando el bug #1)
  select array_agg(username) into v_usernames from usuarios_central where empresa_id = p_empresa_id;

  delete from pagos_historial where empresa_id = p_empresa_id;
  delete from gastos_propiedades where empresa_id = p_empresa_id;
  delete from contratos where empresa_id = p_empresa_id;
  delete from inquilinos where empresa_id = p_empresa_id;
  delete from propiedades where empresa_id = p_empresa_id;
  delete from liquidaciones_propietarios where empresa_id = p_empresa_id;
  delete from configuraciones_empresa where empresa_id = p_empresa_id;
  delete from planilla_verificaciones where empresa_id = p_empresa_id;
  delete from whatsapp_recordatorios where empresa_id = p_empresa_id;
  delete from whatsapp_recordatorios_log where empresa_id = p_empresa_id;
  delete from comprobantes_inquilino where empresa_id = p_empresa_id;
  delete from reclamos_inquilino where empresa_id = p_empresa_id;
  if v_usernames is not null then
    delete from permisos_usuario where username = any(v_usernames);
  end if;
  -- usuarios_central y auditoria_cambios NO se borran — decisión
  -- explícita del usuario (ver DESIGN_LOG.md).
  delete from empresas where id = p_empresa_id;
end;
$function$;

-- eliminar_registros_bloque (security definer: True)
CREATE OR REPLACE FUNCTION public.eliminar_registros_bloque(p_tabla text, p_ids integer[], p_empresa_id integer, p_confirmacion text)
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
declare
  v_deleted int;
  v_username text;
  v_col_id text;
begin
  if auth_rol() != 'superadmin' then
    raise exception 'Solo superadmin puede usar esta función';
  end if;
  if p_tabla not in ('contratos', 'inquilinos', 'propiedades', 'pagos_historial') then
    raise exception 'Tabla no permitida: %', p_tabla;
  end if;

  -- `contratos` no tiene columna `id` en la base real — su identificador
  -- es `codigo` (integer). Las otras 3 tablas sí usan `id`. p_ids sigue
  -- siendo un array de enteros en los dos casos (para contratos, son
  -- códigos de contrato, no ids).
  v_col_id := case when p_tabla = 'contratos' then 'codigo' else 'id' end;
  if p_confirmacion != format('FORZAR BORRADO %s FILAS', array_length(p_ids, 1)) then
    raise exception 'Confirmación incorrecta';
  end if;

  -- Validación de integridad referencial (ver DESIGN_LOG.md): sin FK real
  -- entre contratos y propiedades/inquilinos, hay que chequear a mano
  -- que no queden contratos con referencias rotas.
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

  select username into v_username from usuarios_central where auth_user_id = auth.uid();

  -- Auditoría ANTES de borrar (tipo_evento = 'borrado_masivo'), con el
  -- contenido completo de cada fila antes de perderla. Se arma con SQL
  -- dinámico porque la estructura de columnas difiere entre tablas.
  execute format(
    'insert into auditoria_cambios (empresa_id, tabla, registro_id, tipo_evento, cambios, realizado_por)
     select %L, %L, %I::text, ''borrado_masivo'', to_jsonb(t), %L
     from %I t where empresa_id = %L and %I = any(%L::int[])',
    p_empresa_id, p_tabla, v_col_id, coalesce(v_username, 'sistema'), p_tabla, p_empresa_id, v_col_id, p_ids
  );

  execute format('delete from %I where empresa_id = $1 and %I = any($2)', p_tabla, v_col_id)
    using p_empresa_id, p_ids;
  get diagnostics v_deleted = row_count;
  return v_deleted;
end;
$function$;

-- fn_auditar_cambios (security definer: True)
CREATE OR REPLACE FUNCTION public.fn_auditar_cambios()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
declare
  v_cambios jsonb := '{}'::jsonb;
  v_key text;
  v_username text;
begin
  select username into v_username from usuarios_central where auth_user_id = auth.uid();
  v_username := coalesce(v_username, 'sistema');

  if TG_OP = 'INSERT' then
    insert into auditoria_cambios (empresa_id, tabla, registro_id, tipo_evento, cambios, realizado_por)
    values (NEW.empresa_id, TG_TABLE_NAME, NEW.id::text, 'creacion', to_jsonb(NEW), v_username);
    return NEW;

  elsif TG_OP = 'UPDATE' then
    for v_key in select jsonb_object_keys(to_jsonb(NEW)) loop
      -- saldo_actual se excluye a propósito (ver DESIGN_LOG.md,
      -- "Interacción entre triggers — ruido en auditoria_cambios"):
      -- cambia en CADA pago vía trg_recalcular_saldo, y loggearlo acá
      -- inundaría la auditoría con una entrada por cada cobro en vez de
      -- reservarla para ediciones humanas intencionales.
      if v_key = 'saldo_actual' then
        continue;
      end if;
      if to_jsonb(OLD)->v_key is distinct from to_jsonb(NEW)->v_key then
        v_cambios := v_cambios || jsonb_build_object(v_key,
          jsonb_build_object('antes', to_jsonb(OLD)->v_key, 'despues', to_jsonb(NEW)->v_key));
      end if;
    end loop;

    if v_cambios != '{}'::jsonb then
      insert into auditoria_cambios (empresa_id, tabla, registro_id, tipo_evento, cambios, realizado_por)
      values (NEW.empresa_id, TG_TABLE_NAME, NEW.id::text, 'edicion', v_cambios, v_username);
    end if;
    return NEW;
  end if;

  return null;
exception when others then
  -- Blindaje (ver DESIGN_LOG.md, auditoría "¿el SQL altera el
  -- funcionamiento de v1?"): un fallo acá nunca debe bloquear la
  -- escritura real del contrato/propiedad/inquilino.
  return coalesce(NEW, OLD);
end;
$function$;

-- fn_set_updated_at (security definer: False)
CREATE OR REPLACE FUNCTION public.fn_set_updated_at()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
begin
  new.updated_at := now();
  return new;
end;
$function$;

-- guardar_token_whatsapp (security definer: True)
CREATE OR REPLACE FUNCTION public.guardar_token_whatsapp(p_nombre text, p_token text)
 RETURNS uuid
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
          DECLARE
              v_secret_id UUID;
              BEGIN
                  v_secret_id := vault.create_secret(p_token, p_nombre);
                      RETURN v_secret_id;
                      END;
                      $function$;

-- impactar_cobro (security definer: False)
CREATE OR REPLACE FUNCTION public.impactar_cobro(p_codigo_contrato integer, p_empresa_id integer, p_tipo_pago text, p_periodo text, p_monto_alquiler numeric, p_monto_expensas numeric, p_monto_edesal numeric, p_monto_gas numeric, p_monto_municipalidad numeric, p_monto_cochera numeric, p_monto_ooss numeric, p_monto_imp_inmobiliario numeric, p_monto_honorarios numeric, p_monto_garantia numeric, p_monto_concepto_extra numeric, p_diferencia_correccion numeric, p_monto_abonado numeric, p_metodo_pago text, p_comentario text, p_cotizacion_usd numeric, p_registrado_por text)
 RETURNS TABLE(ok boolean, nro_comprobante text, saldo_nuevo numeric, mensaje_error text)
 LANGUAGE plpgsql
AS $function$
declare
  v_contrato record;
  v_cargos numeric;
  v_pagado numeric;
  v_monto_para_comision numeric;
  v_saldo_nuevo numeric;
  v_gasto_admin numeric;
  v_nro_comprobante text;
  v_comprobante_referencia text;
begin
  -- 1. Candado — por CONTRATO completo (no por contrato+período como
  --    v1), porque con cuenta corriente todos los períodos comparten el
  --    mismo saldo. Dura toda esta transacción/función.
  perform pg_advisory_xact_lock(p_codigo_contrato::bigint);

  -- 2. Leer el contrato FRESCO, ya adentro del candado.
  -- La columna real de % de comisión es `honorarios`, no `honorarios_pct`
  -- (confirmado contra app.py — ver database.types.ts para el detalle).
  select codigo, alias_propiedad, saldo_actual, honorarios, mes_contrato
  into v_contrato
  from contratos
  where codigo = p_codigo_contrato and empresa_id = p_empresa_id;

  if v_contrato is null then
    return query select false, null::text, null::numeric, 'Contrato no encontrado'::text;
    return;
  end if;

  -- 3. Fórmula única de cuenta corriente (ver DESIGN_LOG.md)
  if p_tipo_pago = 'Normal' then
    v_cargos := coalesce(p_monto_alquiler,0) + coalesce(p_monto_expensas,0) + coalesce(p_monto_edesal,0)
              + coalesce(p_monto_gas,0) + coalesce(p_monto_municipalidad,0) + coalesce(p_monto_cochera,0)
              + coalesce(p_monto_ooss,0) + coalesce(p_monto_imp_inmobiliario,0) + coalesce(p_monto_honorarios,0)
              + coalesce(p_monto_garantia,0) + coalesce(p_monto_concepto_extra,0);
    v_pagado := p_monto_abonado;
    v_monto_para_comision := p_monto_abonado;
  elsif p_tipo_pago = 'Complemento' then
    v_cargos := 0;
    v_pagado := p_monto_abonado;
    v_monto_para_comision := p_monto_abonado;
  elsif p_tipo_pago = 'Corrección' then
    v_cargos := coalesce(p_diferencia_correccion, 0);
    v_pagado := 0;
    v_monto_para_comision := coalesce(p_diferencia_correccion, 0);
  else
    return query select false, null::text, null::numeric, format('Tipo de pago inválido: %s', p_tipo_pago)::text;
    return;
  end if;

  v_saldo_nuevo := coalesce(v_contrato.saldo_actual, 0) + v_cargos - v_pagado;
  v_gasto_admin := round(v_monto_para_comision * coalesce(v_contrato.honorarios, 0) / 100.0, 2);
  v_nro_comprobante := 'RC-' || p_codigo_contrato || '-' || to_char(now(), 'YYMMDDHH24MISS');

  -- 4. Complemento: contexto del comprobante Normal de este período
  if p_tipo_pago = 'Complemento' then
    select nro_comprobante into v_comprobante_referencia
    from pagos_historial
    where codigo_contrato = p_codigo_contrato and periodo = p_periodo and tipo_pago = 'Normal'
    order by id desc limit 1;
  end if;

  -- 5. Insertar — pagos_historial es de solo inserción (ver DESIGN_LOG.md)
  insert into pagos_historial (
    empresa_id, codigo_contrato, propiedad, tipo_pago, periodo, fecha, username,
    monto_alquiler, monto_expensas, monto_edesal, monto_gas, monto_municipalidad,
    monto_cochera, monto_ooss, monto_imp_inmobiliario, monto_honorarios, monto_garantia,
    monto_gasto_admin, monto_concepto_extra, monto_abonado, saldo_pendiente,
    metodo_pago, cotizacion_usd, registrado_por, nro_comprobante, comentario,
    comprobante_referencia
  ) values (
    p_empresa_id, p_codigo_contrato, v_contrato.alias_propiedad, p_tipo_pago, p_periodo, now(), p_registrado_por,
    coalesce(p_monto_alquiler,0), coalesce(p_monto_expensas,0), coalesce(p_monto_edesal,0),
    coalesce(p_monto_gas,0), coalesce(p_monto_municipalidad,0), coalesce(p_monto_cochera,0),
    coalesce(p_monto_ooss,0), coalesce(p_monto_imp_inmobiliario,0), coalesce(p_monto_honorarios,0),
    coalesce(p_monto_garantia,0), v_gasto_admin, coalesce(p_monto_concepto_extra,0),
    case when p_tipo_pago = 'Corrección' then coalesce(p_diferencia_correccion,0) else p_monto_abonado end,
    v_saldo_nuevo, p_metodo_pago, p_cotizacion_usd, p_registrado_por, v_nro_comprobante, p_comentario,
    v_comprobante_referencia
  );
  -- trg_recalcular_saldo (0003) actualiza contratos.saldo_actual solo
  -- al confirmarse este INSERT — sigue siendo la única puerta de escritura.

  -- 6. Efectos secundarios — SOLO en pago Normal (ver DESIGN_LOG.md)
  if p_tipo_pago = 'Normal' then
    update contratos
    set mes_contrato = coalesce(v_contrato.mes_contrato, 0) + 1,
        alquiler = case when p_monto_alquiler > 0 then p_monto_alquiler else alquiler end
    where codigo = p_codigo_contrato and empresa_id = p_empresa_id;
  end if;

  return query select true, v_nro_comprobante, v_saldo_nuevo, null::text;
end;
$function$;

-- intentar_reservar_recordatorio (security definer: True)
CREATE OR REPLACE FUNCTION public.intentar_reservar_recordatorio(p_empresa_id integer, p_codigo_contrato integer, p_tipo text, p_secret_cron text)
 RETURNS boolean
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
declare
  v_secret_real text;
  v_reservado boolean;
begin
  select decrypted_secret into v_secret_real
  from vault.decrypted_secrets where name = 'cron_secret';

  if p_secret_cron is null or p_secret_cron != v_secret_real then
    raise exception 'Secreto de cron inválido';
  end if;

  -- fecha_envio es TEXT en la base real (no date) — cast explícito.
  insert into whatsapp_recordatorios_log (empresa_id, codigo_contrato, tipo, fecha_envio, enviado)
  values (p_empresa_id, p_codigo_contrato, p_tipo, current_date::text, true)
  on conflict (codigo_contrato, tipo, fecha_envio) do nothing;

  get diagnostics v_reservado = row_count;
  return v_reservado > 0;
exception when others then
  -- Blindaje: si algo falla acá (mismo criterio que los triggers de saldo/
  -- auditoría), nunca debe tirar abajo el resto del proceso del cron —
  -- simplemente no se manda ese recordatorio puntual, se reintenta mañana.
  return false;
end;
$function$;

-- leer_token_whatsapp (security definer: True)
CREATE OR REPLACE FUNCTION public.leer_token_whatsapp(p_secret_id uuid)
 RETURNS text
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
DECLARE
    v_token TEXT;
BEGIN
    SELECT decrypted_secret INTO v_token
    FROM vault.decrypted_secrets
    WHERE id = p_secret_id;
    RETURN v_token;
END;
$function$;

-- obtener_credenciales_whatsapp_cron (security definer: True)
CREATE OR REPLACE FUNCTION public.obtener_credenciales_whatsapp_cron(p_empresa_id integer, p_secret_cron text)
 RETURNS TABLE(phone_id text, token text)
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
declare
  v_secret_real text;
  v_row record;
  v_secret_id text;
  v_phone_id text;
begin
  select decrypted_secret into v_secret_real
  from vault.decrypted_secrets where name = 'cron_secret';

  if p_secret_cron is null or p_secret_cron != v_secret_real then
    raise exception 'Secreto de cron inválido';
  end if;

  select ce.whatsapp_credenciales_propias, ce.whatsapp_phone_id, ce.whatsapp_token_secret_id,
         wn.phone_id as pool_phone_id, wn.token_secret_id as pool_secret_id
  into v_row
  from configuraciones_empresa ce
  left join whatsapp_numeros wn on wn.id = ce.whatsapp_numero_id
  where ce.empresa_id = p_empresa_id;

  if v_row is null then
    return;
  end if;

  if v_row.whatsapp_credenciales_propias then
    v_secret_id := v_row.whatsapp_token_secret_id;
    v_phone_id := v_row.whatsapp_phone_id;
  else
    v_secret_id := v_row.pool_secret_id;
    v_phone_id := v_row.pool_phone_id;
  end if;

  if v_secret_id is null or v_phone_id is null then
    return;
  end if;

  return query
  select v_phone_id, leer_token_whatsapp(v_secret_id);
end;
$function$;

-- obtener_recordatorios_pendientes (security definer: True)
CREATE OR REPLACE FUNCTION public.obtener_recordatorios_pendientes(p_secret_cron text)
 RETURNS TABLE(empresa_id integer, codigo_contrato text, tipo text, telefono text, nombre text, direccion text, fecha_evento text, indice text)
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
declare
  v_secret_real text;
begin
  select decrypted_secret into v_secret_real
  from vault.decrypted_secrets where name = 'cron_secret';

  if p_secret_cron is null or p_secret_cron != v_secret_real then
    raise exception 'Secreto de cron inválido';
  end if;

  return query
  select
    c.empresa_id,
    c.codigo::text as codigo_contrato,
    r.tipo,
    regexp_replace(coalesce(i.telefono, ''), '[\s-]', '', 'g') as telefono,
    trim(coalesce(i.nombres, '') || ' ' || coalesce(i.apellidos, '')) as nombre,
    trim(
      coalesce(p.calle, '') || ' ' || coalesce(p.numero, '') ||
      case when p.piso is not null and p.piso != '' then ' Piso ' || p.piso else '' end ||
      case when p.departamento is not null and p.departamento != '' then ' Depto ' || p.departamento else '' end
    ) as direccion,
    case when r.tipo = 'vencimiento' then c.fin_contrato else c.prox_actualizacion end as fecha_evento,
    c.indice
  from contratos c
  join whatsapp_recordatorios r on r.empresa_id = c.empresa_id and r.activo = true and r.dias_antes is not null
  join configuraciones_empresa ce on ce.empresa_id = c.empresa_id and ce.whatsapp_habilitado = true
  join inquilinos i on i.dni = c.dni_inquilino and i.empresa_id = c.empresa_id
  join propiedades p on p.alias_propiedad = c.alias_propiedad and p.empresa_id = c.empresa_id
  where c.estado = 'Activo'
    and coalesce(i.telefono, '') != ''
    and (
      (r.tipo = 'vencimiento' and c.fin_contrato is not null
        and (c.fin_contrato::date - current_date) = r.dias_antes)
      or
      (r.tipo = 'actualizacion' and c.prox_actualizacion is not null
        and (c.prox_actualizacion::date - current_date) = r.dias_antes)
    )
    -- No repetir si ya se reservó/envió hoy para este contrato+tipo.
    -- Cast a ::text de ambos lados porque no tenemos confirmado si
    -- whatsapp_recordatorios_log.codigo_contrato (tabla pre-existente de
    -- v1) es text o integer — así funciona sin importar cuál sea.
    and not exists (
      select 1 from whatsapp_recordatorios_log l
      where l.codigo_contrato::text = c.codigo::text and l.tipo = r.tipo and l.fecha_envio = current_date::text
    );
end;
$function$;

-- recalcular_saldo_actual (security definer: True)
CREATE OR REPLACE FUNCTION public.recalcular_saldo_actual()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
declare
  v_codigo int;
  v_saldo numeric;
begin
  v_codigo := coalesce(new.codigo_contrato, old.codigo_contrato);

  select saldo_pendiente
  into v_saldo
  from pagos_historial
  where codigo_contrato = v_codigo
  order by id desc
  limit 1;

  update contratos
  set saldo_actual = coalesce(v_saldo, 0)
  where codigo = v_codigo;

  return null; -- trigger AFTER: el valor de retorno se ignora
exception when others then
  -- Blindaje: un fallo acá (por ejemplo, un caso de borde de datos que no
  -- contemplamos) NUNCA debe poder bloquear la escritura real de un pago
  -- en pagos_historial — ni la de v1 ni la de v2. En el peor caso, se
  -- pierde este recálculo puntual de saldo_actual (se corrige solo en el
  -- próximo pago de ese contrato), pero el INSERT/UPDATE original que
  -- disparó el trigger siempre se completa.
  return null;
end;
$function$;

-- registrar_liquidacion_propietario (security definer: False)
CREATE OR REPLACE FUNCTION public.registrar_liquidacion_propietario(p_empresa_id integer, p_propietario text, p_periodo text, p_monto_calculado numeric, p_saldo_anterior numeric, p_monto_retencion_gastos numeric, p_monto_a_liquidar numeric, p_monto_liquidado numeric, p_saldo_pendiente numeric, p_ids_gastos integer[], p_registrado_por text)
 RETURNS void
 LANGUAGE plpgsql
AS $function$
begin
  insert into liquidaciones_propietarios (
    empresa_id, propietario, periodo, monto_calculado, saldo_anterior,
    monto_retencion_gastos, monto_a_liquidar, monto_liquidado,
    saldo_pendiente, fecha_liquidacion, registrado_por
  ) values (
    p_empresa_id, p_propietario, p_periodo, p_monto_calculado, p_saldo_anterior,
    p_monto_retencion_gastos, p_monto_a_liquidar, p_monto_liquidado,
    p_saldo_pendiente, now(), p_registrado_por
  )
  on conflict (empresa_id, propietario, periodo) do update set
    monto_calculado = excluded.monto_calculado,
    saldo_anterior = excluded.saldo_anterior,
    monto_retencion_gastos = excluded.monto_retencion_gastos,
    monto_a_liquidar = excluded.monto_a_liquidar,
    monto_liquidado = excluded.monto_liquidado,
    saldo_pendiente = excluded.saldo_pendiente,
    fecha_liquidacion = excluded.fecha_liquidacion,
    registrado_por = excluded.registrado_por;

  if p_ids_gastos is not null and array_length(p_ids_gastos, 1) > 0 then
    update gastos_propiedades
    set cobrado = true, periodo_cobrado = p_periodo
    where empresa_id = p_empresa_id and id = any(p_ids_gastos);
  end if;
  -- Si el UPDATE de arriba fallara por algún motivo, todo lo anterior
  -- (el INSERT de la liquidación) se revierte también — misma función,
  -- misma transacción. Ya no puede quedar un estado a medias.
end;
$function$;

-- upsert_indice (security definer: True)
CREATE OR REPLACE FUNCTION public.upsert_indice(p_tipo text, p_fecha date, p_valor numeric)
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
begin
  if p_tipo not in ('ICL', 'IPC', 'UVA') then
    raise exception 'Tipo de índice no válido: %', p_tipo;
  end if;
  if p_valor is null or p_valor <= 0 then
    raise exception 'Valor de índice inválido: %', p_valor;
  end if;

  insert into indices_historicos (tipo, fecha, valor)
  values (p_tipo, p_fecha, p_valor)
  on conflict (tipo, fecha) do update set valor = excluded.valor;
end;
$function$;

-- vencer_contratos_automaticamente (security definer: True)
CREATE OR REPLACE FUNCTION public.vencer_contratos_automaticamente(p_secret_cron text)
 RETURNS integer
 LANGUAGE plpgsql
 SECURITY DEFINER
AS $function$
declare
  v_secret_real text;
  v_hoy_ar date;
  v_afectados int;
begin
  select decrypted_secret into v_secret_real
  from vault.decrypted_secrets where name = 'cron_secret';

  if p_secret_cron is null or p_secret_cron != v_secret_real then
    raise exception 'Secreto de cron inválido';
  end if;

  v_hoy_ar := (now() at time zone 'America/Argentina/Buenos_Aires')::date;

  update contratos
  set estado = 'Finalizado',
      fecha_finalizacion = v_hoy_ar,
      finalizado_por = 'auto_vencimiento'
  where estado = 'Activo'
    and fin_contrato is not null
    and fin_contrato::date <= v_hoy_ar; -- fin_contrato es text en la base real

  get diagnostics v_afectados = row_count;
  return v_afectados;
end;
$function$;

-- ── Triggers ────────────────────────────────────────────────────────

CREATE TRIGGER trg_auditar AFTER INSERT OR UPDATE ON public.contratos FOR EACH ROW EXECUTE FUNCTION fn_auditar_cambios();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.contratos FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trigger_calcular_contrato BEFORE INSERT OR UPDATE ON public.contratos FOR EACH ROW EXECUTE FUNCTION calcular_valores_contrato();
CREATE TRIGGER trg_auditar AFTER INSERT OR UPDATE ON public.inquilinos FOR EACH ROW EXECUTE FUNCTION fn_auditar_cambios();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.inquilinos FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_recalcular_saldo AFTER INSERT OR DELETE OR UPDATE ON public.pagos_historial FOR EACH ROW EXECUTE FUNCTION recalcular_saldo_actual();
CREATE TRIGGER trg_auditar AFTER INSERT OR UPDATE ON public.propiedades FOR EACH ROW EXECUTE FUNCTION fn_auditar_cambios();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.propiedades FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();
CREATE TRIGGER trg_set_updated_at BEFORE UPDATE ON public.usuarios_central FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();

-- ── Políticas RLS ───────────────────────────────────────────────────

create policy "empresa_isolation_select" on public.auditoria_cambios for select to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "inquilino_lee_sus_comprobantes_subidos" on public.comprobantes_inquilino for select to public
  using ((codigo_contrato IN ( SELECT c.codigo
   FROM contratos c
  WHERE (c.dni_inquilino IN ( SELECT inquilinos.dni
           FROM inquilinos
          WHERE (inquilinos.auth_user_id = auth.uid()))))));

create policy "inquilino_sube_comprobantes" on public.comprobantes_inquilino for insert to public
  with check ((codigo_contrato IN ( SELECT c.codigo
   FROM contratos c
  WHERE (c.dni_inquilino IN ( SELECT inquilinos.dni
           FROM inquilinos
          WHERE (inquilinos.auth_user_id = auth.uid()))))));

create policy "staff_actualiza_comprobantes_inquilino" on public.comprobantes_inquilino for update to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())))
  with check (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "staff_lee_comprobantes_inquilino" on public.comprobantes_inquilino for select to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "empresa_isolation_select" on public.configuraciones_empresa for select to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "empresa_isolation_write" on public.configuraciones_empresa for all to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())))
  with check (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "empresa_isolation_select" on public.contratos for select to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "empresa_isolation_write" on public.contratos for all to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())))
  with check (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "inquilino_lee_sus_contratos" on public.contratos for select to public
  using ((dni_inquilino IN ( SELECT inquilinos.dni
   FROM inquilinos
  WHERE (inquilinos.auth_user_id = auth.uid()))));

create policy "empresa_isolation_select" on public.ediciones_presencia for select to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "propia_presencia" on public.ediciones_presencia for all to public
  using (((username = ( SELECT usuarios_central.username
   FROM usuarios_central
  WHERE (usuarios_central.auth_user_id = auth.uid()))) AND (empresa_id = auth_empresa_id())))
  with check (((username = ( SELECT usuarios_central.username
   FROM usuarios_central
  WHERE (usuarios_central.auth_user_id = auth.uid()))) AND (empresa_id = auth_empresa_id())));

create policy "empresas_escritura_superadmin" on public.empresas for all to public
  using ((auth_rol() = 'superadmin'::text))
  with check ((auth_rol() = 'superadmin'::text));

create policy "empresas_lectura_autenticados" on public.empresas for select to public
  using ((auth.role() = 'authenticated'::text));

create policy "empresa_isolation_select" on public.gastos_propiedades for select to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "empresa_isolation_write" on public.gastos_propiedades for all to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())))
  with check (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "lectura_publica" on public.indices_historicos for select to public
  using (true);

create policy "empresa_isolation_select" on public.inquilinos for select to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "empresa_isolation_write" on public.inquilinos for all to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())))
  with check (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "inquilino_lee_su_propia_fila" on public.inquilinos for select to public
  using ((auth_user_id = auth.uid()));

create policy "empresa_isolation_select" on public.liquidaciones_propietarios for select to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "empresa_isolation_write" on public.liquidaciones_propietarios for all to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())))
  with check (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "empresa_isolation_select" on public.pagos_historial for select to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "empresa_isolation_write" on public.pagos_historial for all to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())))
  with check (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "inquilino_lee_sus_pagos" on public.pagos_historial for select to public
  using ((codigo_contrato IN ( SELECT c.codigo
   FROM contratos c
  WHERE (c.dni_inquilino IN ( SELECT inquilinos.dni
           FROM inquilinos
          WHERE (inquilinos.auth_user_id = auth.uid()))))));

create policy "admin_gestiona_permisos_empresa" on public.permisos_usuario for all to public
  using (((auth_rol() = 'admin'::text) AND (username IN ( SELECT usuarios_central.username
   FROM usuarios_central
  WHERE ((usuarios_central.empresa_id = auth_empresa_id()) AND (usuarios_central.rol <> 'superadmin'::text))))))
  with check (((auth_rol() = 'admin'::text) AND (username IN ( SELECT usuarios_central.username
   FROM usuarios_central
  WHERE ((usuarios_central.empresa_id = auth_empresa_id()) AND (usuarios_central.rol <> 'superadmin'::text)))) AND (pestana IN ( SELECT pp.pestana
   FROM (permisos_usuario pp
     JOIN usuarios_central u ON ((u.username = pp.username)))
  WHERE (u.auth_user_id = auth.uid())))));

create policy "admin_ve_permisos_empresa" on public.permisos_usuario for select to public
  using (((auth_rol() = 'admin'::text) AND (username IN ( SELECT usuarios_central.username
   FROM usuarios_central
  WHERE (usuarios_central.empresa_id = auth_empresa_id())))));

create policy "propios_permisos" on public.permisos_usuario for select to public
  using (((auth_rol() = 'superadmin'::text) OR (username = ( SELECT usuarios_central.username
   FROM usuarios_central
  WHERE (usuarios_central.auth_user_id = auth.uid())))));

create policy "superadmin_gestiona_cualquier_permiso" on public.permisos_usuario for all to public
  using ((auth_rol() = 'superadmin'::text))
  with check ((auth_rol() = 'superadmin'::text));

create policy "empresa_isolation" on public.planilla_verificaciones for all to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())))
  with check (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "empresa_isolation_select" on public.propiedades for select to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "empresa_isolation_write" on public.propiedades for all to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())))
  with check (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "inquilino_crea_reclamos" on public.reclamos_inquilino for insert to public
  with check ((codigo_contrato IN ( SELECT c.codigo
   FROM contratos c
  WHERE (c.dni_inquilino IN ( SELECT inquilinos.dni
           FROM inquilinos
          WHERE (inquilinos.auth_user_id = auth.uid()))))));

create policy "inquilino_lee_sus_reclamos" on public.reclamos_inquilino for select to public
  using ((codigo_contrato IN ( SELECT c.codigo
   FROM contratos c
  WHERE (c.dni_inquilino IN ( SELECT inquilinos.dni
           FROM inquilinos
          WHERE (inquilinos.auth_user_id = auth.uid()))))));

create policy "staff_actualiza_reclamos" on public.reclamos_inquilino for update to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())))
  with check (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "staff_lee_reclamos" on public.reclamos_inquilino for select to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "admin_crea_usuarios_empresa" on public.usuarios_central for insert to public
  with check (((auth_rol() = 'admin'::text) AND (empresa_id = auth_empresa_id()) AND (rol = ANY (ARRAY['user'::text, 'propietario'::text]))));

create policy "admin_edita_usuarios_empresa" on public.usuarios_central for update to public
  using (((auth_rol() = 'admin'::text) AND (empresa_id = auth_empresa_id()) AND (rol <> 'superadmin'::text)))
  with check (((auth_rol() = 'admin'::text) AND (empresa_id = auth_empresa_id()) AND (rol <> 'superadmin'::text)));

create policy "admin_ve_usuarios_empresa" on public.usuarios_central for select to public
  using (((auth_rol() = 'admin'::text) AND (empresa_id = auth_empresa_id())));

create policy "propio_perfil" on public.usuarios_central for select to public
  using (((auth_rol() = 'superadmin'::text) OR (auth_user_id = auth.uid())));

create policy "propio_perfil_update" on public.usuarios_central for update to public
  using ((auth_user_id = auth.uid()))
  with check ((auth_user_id = auth.uid()));

create policy "superadmin_crea_cualquier_usuario" on public.usuarios_central for insert to public
  with check ((auth_rol() = 'superadmin'::text));

create policy "superadmin_edita_cualquier_usuario" on public.usuarios_central for update to public
  using ((auth_rol() = 'superadmin'::text))
  with check ((auth_rol() = 'superadmin'::text));

create policy "empresa_isolation_select" on public.whatsapp_recordatorios for select to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "empresa_isolation_write" on public.whatsapp_recordatorios for all to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())))
  with check (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "empresa_isolation_select" on public.whatsapp_recordatorios_log for select to public
  using (((auth_rol() = 'superadmin'::text) OR (empresa_id = auth_empresa_id())));

create policy "inquilino_lee_sus_comprobantes" on storage.objects for select to public
  using (((bucket_id = ANY (ARRAY['comprobantes-pago'::text, 'comprobantes-inquilino'::text])) AND ((storage.foldername(name))[2] IN ( SELECT (contratos.codigo)::text AS codigo
   FROM contratos
  WHERE (contratos.dni_inquilino IN ( SELECT inquilinos.dni
           FROM inquilinos
          WHERE (inquilinos.auth_user_id = auth.uid())))))));

create policy "inquilino_sube_comprobantes_storage" on storage.objects for insert to public
  with check (((bucket_id = 'comprobantes-inquilino'::text) AND ((storage.foldername(name))[2] IN ( SELECT (contratos.codigo)::text AS codigo
   FROM contratos
  WHERE (contratos.dni_inquilino IN ( SELECT inquilinos.dni
           FROM inquilinos
          WHERE (inquilinos.auth_user_id = auth.uid())))))));

create policy "staff_lee_comprobantes" on storage.objects for select to public
  using (((bucket_id = ANY (ARRAY['comprobantes-pago'::text, 'comprobantes-inquilino'::text])) AND ((auth_rol() = 'superadmin'::text) OR ((storage.foldername(name))[1] = (auth_empresa_id())::text))));

-- ── Storage ─────────────────────────────────────────────────────────
-- bucket comprobantes-pago (public: False)
-- bucket comprobantes-inquilino (public: False)

-- ── Vault (solo nombres) ────────────────────────────────────────────
-- cron_secret
-- wa_num_ControlZ

-- ── Extensiones ─────────────────────────────────────────────────────
-- pg_stat_statements 1.11
-- pgcrypto 1.3
-- plpgsql 1.0
-- supabase_vault 0.3.1
-- uuid-ossp 1.1

-- ── Permisos ────────────────────────────────────────────────────────
-- El 29/09/2026 anon y authenticated tenían todos los privilegios de
-- tabla por defecto de Supabase (RLS hace el filtrado), salvo
-- pagos_historial, donde authenticated no tenía UPDATE ni DELETE.
-- Ese mismo día se aplicó, después de la foto:
revoke execute on function public.eliminar_registros_bloque(text, integer[], integer, text) from public, anon, authenticated;
revoke execute on function public.eliminar_empresa_completa(integer, text) from public, anon, authenticated;
revoke execute on function public.aplicar_actualizacion_individual(integer, numeric, integer, text) from public, anon, authenticated;
revoke execute on function public.contratos_elegibles_actualizacion(integer, boolean) from public, anon, authenticated;
revoke execute on function public.leer_token_whatsapp(uuid) from public, anon, authenticated;
revoke execute on function public.guardar_token_whatsapp(text, text) from public, anon, authenticated;
revoke execute on function public.actualizar_token_whatsapp(uuid, text) from public, anon, authenticated;
revoke execute on function public.upsert_indice(text, date, numeric) from public, anon, authenticated;
