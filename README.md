# Sistema de Gestión Inmobiliaria — v2.000

Reescritura del sistema (v1 en Streamlit/Python) sobre **Next.js 14 (App Router) +
TypeScript + Supabase**, manteniendo la misma base de datos PostgreSQL de Supabase.

La v1 sigue funcionando en paralelo sin tocarse. Esta v2 se conecta a la **misma
base de datos** pero reemplaza el sistema de login manual (bcrypt) por **Supabase
Auth**, y usa **Row Level Security (RLS)** para el aislamiento multi-empresa en vez
de filtrar todo a mano en cada query, como hacía app.py.

---

## 1. Stack

| Capa        | Tecnología                                             |
|-------------|---------------------------------------------------------|
| Frontend/BE | Next.js 14 (App Router, Server Components + Server Actions) |
| Lenguaje    | TypeScript                                              |
| Estilos     | Tailwind CSS                                            |
| Auth        | Supabase Auth (email + password)                        |
| Base de datos | Supabase / PostgreSQL (existente, sin cambios de esquema salvo lo indicado abajo) |
| Storage     | Supabase Storage (bucket `comprobantes` para PDFs)       |
| PDF         | `@react-pdf/renderer` (reemplaza ReportLab)              |
| Hosting     | Vercel (plan gratis)                                     |
| WhatsApp    | Meta Business API (Cloud API)                            |

## 2. Por qué esta estructura

- **App Router + Server Components**: las páginas que solo leen datos (dashboard,
  planilla, historial) se renderizan en el servidor y consultan Supabase
  directamente con el cliente `server.ts`, sin exponer lógica de negocio al
  browser. Los formularios interactivos (carga de contratos, registrar pago) son
  Client Components que llaman a **Server Actions**.
- **RLS en vez de `archivo_db` a mano**: en v1, cada tabla se filtraba manualmente
  por `empresa_id` en cada query de Python. En v2, las políticas RLS de
  PostgreSQL hacen ese filtro a nivel de base de datos, así que aunque un bug de
  frontend olvide filtrar, Postgres igual no deja ver datos de otra empresa.
  Ver `supabase/migrations/0001_v2_auth_setup.sql`.
- **Grupo de rutas `(protected)`**: agrupa todas las pantallas que requieren
  sesión, sin agregar `/protected/` a la URL. El `layout.tsx` de ese grupo hace
  de guardia (redirige a `/login` si no hay sesión) y renderiza el menú lateral
  según rol/permisos — el equivalente directo al bloque
  "CONFIGURACIÓN DINÁMICA DE PESTAÑAS" de `app.py`.
- **`middleware.ts`**: refresca la sesión de Supabase en cada request (necesario
  con `@supabase/ssr`) y hace el primer corte de redirección `/login` ↔ `/dashboard`.

## 3. Estructura de carpetas

```
inmobiliaria-v2/
├── middleware.ts                 # Refresca sesión Supabase + redirects base
├── app/
│   ├── layout.tsx                # Layout raíz (fuentes, <html>, providers)
│   ├── globals.css
│   ├── page.tsx                  # "/" → redirige a /dashboard o /login
│   ├── login/
│   │   └── page.tsx              # Pantalla de login (Módulo 1)
│   ├── auth/
│   │   └── logout/route.ts       # POST → cierra sesión
│   └── (protected)/
│       ├── layout.tsx            # Guardia de sesión + T&C + Sidebar (Módulo 1/11)
│       ├── terminos/page.tsx     # Aceptación de Términos y Condiciones (Módulo 11)
│       ├── dashboard/page.tsx    # Módulo 2 (placeholder por ahora)
│       ├── planilla/page.tsx     # Módulo 3 (placeholder)
│       ├── pagos/page.tsx        # Módulo 4 (placeholder)
│       ├── historial-pagos/page.tsx  # Módulo 6 (placeholder)
│       ├── carga/page.tsx        # Módulo 5 (placeholder)
│       ├── auxiliares/page.tsx   # Módulo 5 (placeholder)
│       ├── gastos/page.tsx       # Módulo 7 (placeholder)
│       ├── rendicion/page.tsx    # Liquidación a propietarios (placeholder)
│       └── panel-gestion/page.tsx # Módulo 10 (placeholder)
├── lib/
│   ├── supabase/
│   │   ├── client.ts             # Cliente Supabase para Client Components
│   │   ├── server.ts             # Cliente Supabase para Server Components/Actions
│   │   └── middleware.ts         # Helper usado por middleware.ts
│   ├── auth/
│   │   ├── session.ts            # getSessionProfile(): sesión + fila usuarios_central
│   │   └── permissions.ts        # Tabla maestra de pestañas + lógica de visibilidad por rol
│   └── types/
│       └── database.types.ts     # Tipos TS de las tablas (a regenerar con la CLI de Supabase)
├── components/
│   ├── auth/LoginForm.tsx
│   └── layout/Sidebar.tsx
├── supabase/
│   └── migrations/
│       └── 0001_v2_auth_setup.sql   # Columna auth_user_id + políticas RLS
├── package.json
├── tsconfig.json
├── tailwind.config.ts
└── .env.local.example
```

## 4. Variables de entorno

Copiar `.env.local.example` a `.env.local` y completar:

```
NEXT_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon-key>
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>   # solo server-side, nunca al cliente
```

El `service_role` key se usa únicamente en `lib/supabase/server.ts` para tareas
puntuales de administración (ej: crear usuarios de Supabase Auth desde el Panel
de Gestión). Nunca se expone con el prefijo `NEXT_PUBLIC_`.

## 5. Migración de autenticación (v1 bcrypt → v2 Supabase Auth)

`usuarios_central` sigue siendo la tabla "perfil" (rol, empresa, permisos,
términos aceptados), pero deja de guardar `password_hash` para el login de v2.
En su lugar:

1. Se agrega la columna `auth_user_id uuid references auth.users(id)` (ver
   migración `0001_v2_auth_setup.sql`).
2. Se agrega `email` a `usuarios_central`.
3. **RESUELTO** (ver `docs/DESIGN_LOG.md`, sección "Editar Usuario — cambio de
   contraseña unificado..."): no es un script de una sola corrida — es un
   botón por usuario en el Panel de Gestión ("Enviar link de acceso"), donde
   el admin/superadmin escribe o confirma el email antes de enviarlo:
   - Si el usuario no tiene `auth_user_id` todavía (viene de v1, sin migrar):
     `supabase.auth.admin.inviteUserByEmail(email)`, y al volver se guarda
     `auth_user_id` + `email`.
   - Si ya tiene `auth_user_id` (ya migrado): `resetPasswordForEmail(email)`,
     sin tocar `usuarios_central`.
   Mismo mecanismo sirve para migrar usuarios viejos Y para resetear la
   contraseña de usuarios ya migrados — unificado en un solo Server Action
   con `service_role`, protegido por rol.
4. v1 sigue funcionando durante toda la transición porque no se toca
   `password_hash` ni el resto del esquema — v1 y v2 conviven hasta el corte
   definitivo, que puede hacerse empresa por empresa o usuario por usuario,
   sin fecha límite forzada.

## 6. Cómo correr en local

```bash
npm install
cp .env.local.example .env.local   # completar credenciales
npm run dev
```

## 7. Versionado

Igual que v1: cada entrega sube el número de versión. Se define en
`lib/version.ts` (`APP_VERSION = "v2.000"`) y se muestra en el pie del Sidebar,
igual que el sello `v1.149` de `app.py`.
