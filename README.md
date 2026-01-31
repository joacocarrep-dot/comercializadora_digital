# Comercializadora Digital - Backend

## 🚀 Setup rápido (desarrollo local)

```bash
# 1. Configurar entorno
cp .env.example .env
# (opcional) editar .env con tus credenciales personalizadas

# 2. Levantar el stack con Docker
docker-compose up --build

# 3. Verificar que el API está funcionando
curl http://localhost:8000/api/v1/health
# Respuesta esperada: {"status":"ok","environment":"development","database":"connected"}
```

## 📋 Prerrequisitos

- Docker y Docker Compose instalados
- (Opcional) Python 3.11+ para desarrollo local fuera de contenedores

## 🐳 Comandos Docker útiles

```bash
# Iniciar servicios en primer plano (con logs)
docker-compose up

# Iniciar servicios en segundo plano (detached)
docker-compose up -d

# Detener servicios
docker-compose down

# Reconstruir contenedores (después de cambios en Dockerfile)
docker-compose up --build

# Ver logs de la aplicación
docker-compose logs -f app

# Ver logs de PostgreSQL
docker-compose logs -f postgres

# Ejecutar migraciones de base de datos
docker-compose exec app alembic upgrade head

# Crear nueva migración (cuando se agregan modelos en Fase 1+)
docker-compose exec app alembic revision --autogenerate -m "descripcion"

# Acceder a shell dentro del contenedor de la app
docker-compose exec app bash
```

## 🗄️ Base de datos

- **PostgreSQL 15** ejecutándose en el contenedor `postgres`
- Puerto expuesto: `5432` (solo accesible desde otros contenedores)
- Volumen persistente: `./postgres-data` (fuera del contenedor)
- Healthcheck configurado con `pg_isready` cada 30 segundos
- Credenciales por defecto (modificables en `.env`):
  - Base de datos: `comercializadora`
  - Usuario: `user`
  - Contraseña: `password`

## 🔌 Endpoints disponibles

- `GET /api/v1/health` - Health check del API
- `GET /docs` - Documentación Swagger UI
- `GET /redoc` - Documentación ReDoc

## 📁 Estructura del proyecto

```
backend/
├── app/
│   ├── config/          # Configuración con Pydantic Settings
│   ├── core/            # Middleware, seguridad (futuro)
│   ├── models/          # Modelos SQLAlchemy (Fase 1+)
│   ├── schemas/         # Schemas Pydantic (Fase 1+)
│   ├── api/
│   │   └── v1/          # Endpoints API v1
│   ├── services/        # Lógica de negocio (Fase 1+)
│   ├── repositories/    # Acceso a datos (Fase 1+)
│   └── utils/           # Utilidades (Fase 1+)
├── migrations/          # Migraciones Alembic (configuradas para async)
└── tests/              # Tests (estructura vacía por ahora)
```

## 🛠️ Desarrollo

### Hot-reload
La aplicación está configurada con hot-reload usando Uvicorn. Cualquier cambio en los archivos `.py` dentro de `backend/app/` se reflejará automáticamente sin necesidad de reiniciar el contenedor.

### Variables de entorno
- **`.env.example`**: Template con variables requeridas
- **`.env`**: Archivo local (NO versionado, agregado a .gitignore)
- Las variables se cargan automáticamente via `pydantic-settings`

### Migraciones (Alembic)
El proyecto está configurado para migraciones asíncronas usando SQLAlchemy 2.0 + asyncpg. Para usar migraciones:

```bash
# Ejecutar migraciones pendientes
docker-compose exec app alembic upgrade head

# Crear nueva migración (después de cambios en modelos)
docker-compose exec app alembic revision --autogenerate -m "descripcion"

# Revertir última migración
docker-compose exec app alembic downgrade -1
```

## 🔐 Seguridad (desarrollo)

- CORS configurado para permitir todos los orígenes (`allow_origins=["*"]`) en desarrollo
- En producción se restringirán los orígenes permitidos
- Las variables sensibles (SECRET_KEY) deben cambiarse en producción

## 🧪 Testing (Futuro)

La carpeta `backend/tests/` está preparada para futuras implementaciones de tests unitarios y de integración.

## ⚙️ Inicialización de repositorio Git (opcional)

Si deseas versionar el proyecto:

```bash
# Inicializar repositorio Git (si aún no está inicializado)
git init

# Configurar usuario (si es necesario)
git config user.name "Tu Nombre"
git config user.email "tu.email@ejemplo.com"

# Primer commit
git add .
git commit -m "Initial commit: Fase 0 completada"
```

## 📄 Documentación adicional

- Ver `docs/` para documentación técnica detallada
- `docs/desarrollo.md` contiene el seguimiento completo de la implementación

## ❓ Problemas comunes

### Puerto 8000 ya en uso
Si el puerto 8000 está ocupado, modifica `docker-compose.yml` cambiando `"8000:8000"` a `"8080:8000"` (o cualquier puerto libre).

### Error de conexión a PostgreSQL
Asegúrate de que:
1. El servicio `postgres` esté ejecutándose (`docker-compose ps`)
2. El healthcheck haya pasado (puede tardar unos segundos en el primer inicio)
3. Las credenciales en `.env` coincidan con las de `docker-compose.yml`

### Permisos de volumen PostgreSQL
En algunos sistemas puede ser necesario ajustar permisos del directorio `postgres-data/`:
```bash
sudo chown -R 999:999 postgres-data/
```

## 📞 Soporte

Para problemas técnicos o consultas, revisa primero la documentación en `docs/`. Si el problema persiste, contacta al equipo de desarrollo.