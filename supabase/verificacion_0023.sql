-- =====================================================================
-- Verificación de 0023_carga_contratos.sql — SOLO LECTURA
-- Correr después de aplicar 0023. Resultado esperado al lado de cada fila.
-- =====================================================================
select 'columnas nuevas en contratos' as control,
       count(*)::text as valor  -- esperado: 5
from information_schema.columns
where table_schema = 'public' and table_name = 'contratos'
  and column_name in ('dia_vencimiento', 'cochera_monto_inicial', 'cochera_actualiza_con_indice', 'cargo_general_servicios', 'monto_pagare')
union all select 'pagos_historial.monto_cargo_general existe',
       (count(*) = 1)::text  -- esperado: true
from information_schema.columns
where table_schema = 'public' and table_name = 'pagos_historial' and column_name = 'monto_cargo_general'
union all select 'contratos sin cochera inicial',
       count(*)::text  -- esperado: 0
from public.contratos where cochera_monto_inicial is null
union all select 'authenticated puede editar dia_vencimiento',
       has_column_privilege('authenticated', 'public.contratos', 'dia_vencimiento', 'UPDATE')::text  -- esperado: true
union all select 'authenticated sigue sin poder editar saldo_actual',
       has_column_privilege('authenticated', 'public.contratos', 'saldo_actual', 'UPDATE')::text  -- esperado: false
union all select 'authenticated puede usar la secuencia de códigos',
       has_sequence_privilege('authenticated', 'public.contratos_codigo_seq', 'USAGE')::text  -- esperado: true
union all select 'crear_contrato_v2: anon / authenticated',
       has_function_privilege('anon', 'public.crear_contrato_v2(jsonb, jsonb)', 'EXECUTE')::text
       || ' / ' || has_function_privilege('authenticated', 'public.crear_contrato_v2(jsonb, jsonb)', 'EXECUTE')::text
       -- esperado: false / true
union all select 'secuencia de contratos por delante del último código',
       ((select last_value from public.contratos_codigo_seq) >= (select coalesce(max(codigo), 0) from public.contratos))::text
       -- esperado: true (si da false, avisame antes de cargar un contrato)
union all select 'funciones con permiso para anon',
       count(*)::text from pg_proc p
       where p.pronamespace = 'public'::regnamespace and p.prokind = 'f' and has_function_privilege('anon', p.oid, 'EXECUTE');
       -- esperado: 13 (igual que después de 0021)
