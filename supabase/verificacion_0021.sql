-- =====================================================================
-- Verificación de 0021_seguridad_y_fechas.sql — SOLO LECTURA
-- Correr después de aplicar 0021. Resultado esperado al lado de cada fila.
-- =====================================================================
select 'eliminar_registros_bloque: anon / authenticated' as control,
       has_function_privilege('anon', 'public.eliminar_registros_bloque(text, integer[], integer, text)', 'EXECUTE')::text
       || ' / ' || has_function_privilege('authenticated', 'public.eliminar_registros_bloque(text, integer[], integer, text)', 'EXECUTE')::text
       as valor  -- esperado: false / true
union all select 'aplicar_actualizacion_individual: anon / authenticated',
       has_function_privilege('anon', 'public.aplicar_actualizacion_individual(integer, numeric, integer, text)', 'EXECUTE')::text
       || ' / ' || has_function_privilege('authenticated', 'public.aplicar_actualizacion_individual(integer, numeric, integer, text)', 'EXECUTE')::text
       -- esperado: false / true
union all select 'leer_token_whatsapp: anon / authenticated / service_role / postgres',
       has_function_privilege('anon', 'public.leer_token_whatsapp(uuid)', 'EXECUTE')::text
       || ' / ' || has_function_privilege('authenticated', 'public.leer_token_whatsapp(uuid)', 'EXECUTE')::text
       || ' / ' || has_function_privilege('service_role', 'public.leer_token_whatsapp(uuid)', 'EXECUTE')::text
       || ' / ' || has_function_privilege('postgres', 'public.leer_token_whatsapp(uuid)', 'EXECUTE')::text
       -- esperado: false / false / true / true
union all select 'upsert_indice con secreto: anon',
       has_function_privilege('anon', 'public.upsert_indice(text, date, numeric, text)', 'EXECUTE')::text
       -- esperado: true (la función exige el secreto adentro)
union all select 'upsert_indice viejo (sin secreto) existe',
       (to_regprocedure('public.upsert_indice(text, date, numeric)') is not null)::text
       -- esperado: false
union all select 'authenticated puede editar contratos.saldo_actual',
       has_column_privilege('authenticated', 'public.contratos', 'saldo_actual', 'UPDATE')::text
       -- esperado: false
union all select 'authenticated puede editar contratos.alquiler',
       has_column_privilege('authenticated', 'public.contratos', 'alquiler', 'UPDATE')::text
       -- esperado: true
union all select 'postgres (Python) puede editar contratos.saldo_actual',
       has_column_privilege('postgres', 'public.contratos', 'saldo_actual', 'UPDATE')::text
       -- esperado: true
union all select 'impactar_cobro escribe fecha formato Python',
       (pg_get_functiondef('public.impactar_cobro'::regproc)
        like '%DD/MM/YYYY HH24:MI%')::text
       -- esperado: true
union all select 'registrar_liquidacion escribe fecha formato Python',
       (pg_get_functiondef('public.registrar_liquidacion_propietario'::regproc) like '%DD/MM/YYYY HH24:MI%')::text
       -- esperado: true
union all select 'funciones con permiso para anon',
       count(*)::text from pg_proc p
       where p.pronamespace = 'public'::regnamespace and p.prokind = 'f' and has_function_privilege('anon', p.oid, 'EXECUTE');
       -- esperado: 13 (las 12 de antes + el upsert_indice nuevo, que exige el secreto del cron)
