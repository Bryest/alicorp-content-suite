# Content Suite

> Plataforma para generación de contenido alineado a marca, con RAG y validación multimodal vía AI.
> Construida para **Alicorp**.

---

## El problema que resuelve

Alicorp tiene **+12 marcas** (Don Vittorio, Inka Chips, Bolívar, AlaCena, Marsella, Plusbelle…). Cada una produce **miles de piezas de contenido al año**: descripciones de producto, posts de redes sociales, guiones de video, taglines.

Hoy, ese contenido se escribe a mano, se manda a revisión a marca + legal, y se itera 2-3 veces antes de publicarse. **Tiempo promedio: 4-8 horas por pieza. 3+ personas involucradas.**

Content Suite reduce eso a **5-10 minutos por pieza**. Automatiza el 80% del trabajo de revisión, pero el aprobador humano tiene la última palabra.

---

## Stack tecnológico

| Capa | Tecnología | Por qué |
|---|---|---|
| Backend | **FastAPI** + Python 3.11 | Async nativo, OpenAPI auto-generado, type hints estrictos |
| Frontend | **Next.js 14** (App Router) + TypeScript | UI moderna, SSR opcional, ecosistema React |
| Base de datos | **Supabase** (Postgres + pgvector) | Managed Postgres con búsqueda vectorial nativa, Auth incluido, free tier generoso |
| LLM texto | **Groq Llama 3.3 70B** | Inferencia 5-10× más rápida que GPUs gracias a chips LPU custom |
| Embeddings | **Gemini text-embedding-001** (768-dim MRL) | Top score MTEB en español/inglés, soporta truncación con MRL |
| Visión | **Gemini 2.5 Flash** | Único multimodal con free tier viable; acepta imagen + texto en un prompt |
| Observability | **Langfuse Cloud** | Trazas estructuradas, free tier 50K eventos/mes |
| Hosting | **Render** (backend) + **Vercel** (frontend) | Free tier, deploy desde GitHub |

---

## Demo en vivo

La aplicación web está desplegada en Vercel. La URL está visible en el panel derecho del repositorio. Las trazas de observabilidad viven en Langfuse Cloud (invitación enviada al email del recruiter).

### Credenciales para probar

| Rol | Correo | Contraseña |
|---|---|---|
| Creator (genera contenido) | `creator@test.com` | `Test1234!` |
| Aprobador A (revisa texto) | `approver.a@test.com` | `Test1234!` |
| Aprobador B (valida imagen) | `approver.b@test.com` | `Test1234!` |

---

## Qué hace, en una línea por módulo

| Módulo | Qué hace |
|---|---|
| **I · Brand DNA Architect** | Toma 7 inputs simples (nombre, tono, audiencia, reglas visuales, palabras prohibidas…) y genera un manual de marca estructurado, indexado en una base de datos vectorial. |
| **II · Creative Engine** | Genera contenido (descripciones, posts, guiones, taglines) consultando primero el manual vía RAG, garantizando que cada pieza esté alineada a marca. Bloquea palabras prohibidas automáticamente. |
| **III · Governance & Multimodal Audit** | 3 roles (creator, aprobador A, aprobador B) + máquina de estados inviolable. El aprobador B sube una imagen, Gemini Vision la audita contra las reglas visuales de la marca y devuelve un check estructurado. |
| **IV · Observability** | Cada llamada a IA queda trazada en Langfuse: qué se recuperó del RAG, qué prompt se envió, cuánto tardó la auditoría multimodal. |

---

## Cómo funciona el flujo end-to-end

```
Creator define la marca (1 vez)
   └──► Manual estructurado (5 secciones)
        └──► Indexado en pgvector
             └──► El sistema "conoce" la marca

Creator pide contenido
   └──► RAG retrieve top-3 chunks de marca
        └──► Si no hay contexto suficiente → BLOQUEADO
        └──► Si hay contexto → Groq genera grounded
              └──► Doble check de palabras prohibidas
                   └──► PENDIENTE de revisión

Aprobador A revisa texto
   └──► Aprueba → TEXTO APROBADO
   └──► Rechaza → REJECTED (con razón)

Aprobador B sube imagen
   └──► Gemini Vision audita vs reglas visuales
        └──► Compliant + checks individuales
              └──► Aprueba → PUBLICACIÓN APROBADA
              └──► Rechaza → REJECTED
```
---

## Arquitectura: hexagonal / DDD

```
backend/
├── domain/              # Lógica pura. Cero dependencias externas.
│   ├── brand/           #   BrandManual, BrandChunk, BrandSection, ForbiddenWords
│   ├── content/         #   ContentItem, ApprovalStatus, StateMachine
│   └── audit/           #   AuditResult, CheckItem
├── application/         # Casos de uso. Orquestan domain + ports.
│   ├── brand_service.py     # Módulo I
│   ├── content_service.py   # Módulo II
│   └── audit_service.py     # Módulo III
├── infrastructure/      # Adapters de proveedores externos.
│   ├── supabase_client.py   # BrandRepository + ContentRepository
│   ├── groq_client.py       # LLM texto
│   ├── gemini_client.py     # Visión multimodal
│   ├── embedding_service.py # Embeddings
│   └── langfuse_client.py   # Tracing
└── api/                 # FastAPI routes + middleware (auth, RBAC, rate limit, errors)

frontend/
└── src/app/             # creator/, approver-a/, approver-b/ + login
```
---

## Decisiones de arquitectura

### Hexagonal / DDD
4 módulos, 3 roles, máquina de estados y 5 proveedores externos no entran prolijos en un archivo único. Separar el dominio (entidades de marca, transiciones de aprobación, value objects) de la infraestructura (SDKs externos) hace que cambiar Groq por OpenAI mañana sea editar un archivo, no buscar referencias por todo el repo. El precio fue más scaffolding al inicio.

### Supabase Auth en lugar de JWT hardcodeado
El reto pide 3 roles. Lo simple era firmar un HS256 con una clave en el `.env`. En vez de eso, el login es un proxy a `/auth/v1/token` de Supabase, los tokens son ES256 asimétricos firmados por Supabase, y el backend los valida contra el JWKS público.

### RAG con threshold
La búsqueda vectorial filtra por similitud server-side. Si ningún chunk del manual de marca pasa el umbral, el endpoint devuelve `BLOCKED` y ni siquiera llama al LLM. Es la forma de evitar que el modelo invente cosas que no están en el manual.

### Embeddings de 768-dim (no 3072)
Gemini Embedding 001 retorna 3072 por default. Truncamos a 768 con MRL (Matryoshka Representation Learning): 4× menos storage en pgvector, score MTEB ~68.0 vs ~68.2 (la diferencia es invisible en la práctica), y matchea el `vector(768)` del schema.

### Errores upstream mapeados en un solo lugar
`api/middleware/exception_handlers.py` traduce cada excepción de SDK al HTTP status que corresponde: `groq.RateLimitError` → 429, `google.api_core.exceptions.ResourceExhausted` → 429, `httpx.TimeoutException` → 408, etc. El frontend agarra el status y muestra el mensaje al usuario en español. El backend no expone tracebacks.

---

## Capacidad operativa (free tier)

Para una marca como **Inka Chips** (papas nativas, multi-SKU, comunicación frecuente), el sistema permite **20 piezas completas por día** (crear manual de marca → generar copy → validar imagen).

El límite lo pone Gemini 2.5 Flash Vision (20 imágenes/día en cuenta gratuita). El cupo se reinicia diariamente.

Texto y embeddings tienen muchísima más holgura (Groq 14,400 calls/día, Gemini Embedding 1,000 calls/día). Pasando a tier pagado los límites desaparecen y el costo queda en el orden de **~$50/mes para 1,000 piezas de contenido**, alrededor de 1 hora del salario de un marketer.

---

## Endpoints principales

| Método | Path | Rol | Descripción |
|---|---|---|---|
| `POST` | `/api/v1/auth/login` | público | Login vía Supabase Auth |
| `POST` | `/api/v1/brand-dna` | creator | Crear manual de marca + indexar en RAG |
| `GET` | `/api/v1/brands` | creator | Listar marcas del usuario |
| `GET` | `/api/v1/brands/{brand_id}` | creator | Detalle del manual con secciones parseadas |
| `POST` | `/api/v1/generate` | creator | Generar contenido grounded en RAG |
| `GET` | `/api/v1/content` | cualquiera | Listar items (con filtros) |
| `GET` | `/api/v1/content/{id}` | cualquiera | Detalle de un item |
| `PATCH` | `/api/v1/audit/text/{id}` | approver_a | Aprobar/rechazar texto |
| `POST` | `/api/v1/audit/image/{id}` | approver_b | Auditar imagen (multimodal) |
| `GET` | `/api/v1/health` | público | Health check |

OpenAPI completo en `/docs` (Swagger UI interactivo).

---

## Seguridad

- **JWT-protected endpoints**: toda ruta excepto `/health` y `/auth/login` requiere Bearer token. Cross-role calls retornan 403.
- **Verificación JWT con JWKS**: los tokens de Supabase son ES256 asimétricos; el backend fetcha el JWKS público para verificar (no compartimos secret).
- **Per-IP rate limiting** (slowapi):
  - `/auth/login`: 5/min, previene credential stuffing
  - `/brand-dna`, `/generate`, `/audit/image`: 5/min, capa el costo de LLM
  - `/audit/text`: 20/min, solo DB sin LLM
  - resto: 60/min
- **Security headers**: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `X-XSS-Protection` en cada response.
- **CORS allowlist**: solo los dominios de Vercel autorizados pueden llamar al backend.
- **Access log** estructurado por request: `METHOD path status latency_ms ip`.

---

## Limitaciones

- **Free tier de Gemini Vision = 20 audits/día.** En tier pagado el límite desaparece (~$0.04 por audit).
- **Render free tier duerme** después de 15 min de inactividad. El primer request post-sleep tarda ~30s en arrancar (cold start).
- **El sistema es human-in-the-loop**, no automatización end-to-end. Los aprobadores siempre tienen veto final. Fue una decisión, no una limitación técnica.
- **RAG depende de la calidad del input al Brand DNA.** Manual pobre → recuperación pobre → contenido pobre.

---

## Roadmap

- **Q3** Fine-tuning con feedback de aprobadores (rejections → training data).
- **Q4** Generación de imagen integrada (Imagen 3 conditioned al Brand DNA).
- **2027** Integración con DAM corporativo + workflows en Slack/Teams.
- **Multi-ambiente** (dev/staging/prod): separación de Supabase + Render + Vercel para release safety.
- **Módulo de admin**: gestión granular de roles y permisos vía UI.

---

## Despliegue

- **Backend** → Render (`render.yaml` incluido).
- **Frontend** → Vercel (root directory `frontend/`).
- **DB** → Supabase project con `db/schema.sql` ejecutado.

Variables de entorno requeridas en Render:
`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `GROQ_API_KEY`, `GOOGLE_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `CORS_ORIGINS`, `ENVIRONMENT=production`.
