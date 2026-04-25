# ShopMicro — Plataforma e-Commerce de Microserveis
## Fase 1: Docker Compose (Entorn de Desenvolupament)
 
---
 
## Descripció del Projecte
 
**ShopMicro** és una plataforma fictícia de comerç electrònic que demostra:
- Arquitectura de microserveis amb contenidors Docker
- Orquestració amb Docker Compose
- Comunicació inter-serveis (API REST)
- Cua de missatges (RabbitMQ)
- Caché (Redis)
- Múltiples bases de dades (MySQL)
---
 
## Arquitectura
 
```
┌─────────────────────────────────────────────────────┐
│         FRONTEND LAYER (frontend-net)                │
├──────────────────┬──────────────────────────────────┤
│ Frontend (Nginx) │  API Gateway (Nginx reverse-proxy)│
│ Puerto 80        │  Puerto 8080                      │
└────────────┬─────┴────────────────┬──────────────────┘
             │                      │
┌────────────┴──────────────────────┴──────────────────┐
│       MICROSERVICES LAYER (backend-net)              │
├────────────────┬────────────────┬────────────────────┤
│ product-       │ order-         │ user-service      │
│ service:5001   │ service:5002   │ :5003             │
├────────┬───────┴────────┬───────┴─────────┬─────────┤
│ Redis  │                │                 │         │
│ Cache  │           RabbitMQ               │         │
└────────┴─────────┬──────┴─────────────────┼─────────┘
                   │                        │
┌──────────────────┴────────────────────────┴─────────┐
│    DATABASE & STORAGE LAYER (db-net, mq-net)      │
├──────────────────┬─────────────────┬────────────────┤
│ db-products      │ db-orders       │ notification-  │
│ (MySQL 8.0)      │ (MySQL 8.0)     │ service        │
└──────────────────┴─────────────────┴────────────────┘
<img width="827" height="1169" alt="shopmicro_arquitectura" src="https://github.com/user-attachments/assets/5a941395-a40f-4091-bcd9-9fd9639d42c8" />

```
 
---
 
## Estructura de Carpetes
 
```
shopmicro/
├── docker-compose.yml          ← FITXER PRINCIPAL
├── secrets/
│   └── db_root_password.txt
├── frontend/
│   ├── Dockerfile
│   └── index.html
├── api-gateway/
│   ├── Dockerfile
│   └── nginx.conf
├── product-service/
│   ├── Dockerfile
│   ├── app.py
│   └── requirements.txt
├── order-service/
│   ├── Dockerfile
│   ├── app.py
│   └── requirements.txt
├── user-service/
│   ├── Dockerfile
│   ├── app.py
│   └── requirements.txt
└── notification-service/
    ├── Dockerfile
    ├── app.py
    └── requirements.txt
```
 
---
 
## Com Executar el Projecte
 
### Requisits
- **Docker** (v20.10+)
- **Docker Compose** (v1.29+)
- Terminal/CLI
### Passos
 
#### 1 Clonar o Descarregar el Projecte
```bash
# Si tens el projecte en ZIP, descomprimeix-lo
unzip shopmicro.zip
cd shopmicro
```
 
#### 2 Construir les Imatges
```bash
docker compose build
```
Això construirà les imatges Docker per a tots els serveis (espera 2-3 minuts).
 
#### 3 Iniciar els Contenidors
```bash
docker compose up -d
```
 
Paciència! Els serveis triguen 20-30 segons en estar totalment operatius. Els contenidors esperen a que les BDs estiguin sanes.
 
#### 4 Verificar que tot Funciona
```bash
# Veure el status de tots els contenidors
docker compose ps
 
# Hauries de veure tots amb status "Up" i "healthy"
```
 
#### 5 Accedir a la Plataforma
Obri el navegador i aneu a:
```
http://localhost:8080
```
 
---
 
## Provar els Fluxos Funcionals
 
### Flux 1: Consulta de Productes (amb Redis Cache)
 
1. Aneu a **http://localhost:8080**
2. Es carregarà una llista de productes
3. Observeu al **log** (baix de la pàgina):
   ```
   Productes carregats des de product-service (via Redis cache)
   ```
4. Recarregueu la pàgina (F5):
   - **Primera vegada**: Consulta BD, guarda a Redis
   - **Segones vegades (30s)**: Servit des de Redis (més ràpid)
**Verificar logs**:
```bash
docker compose logs product-service | grep -i "cache"
```
 
### Flux 2: Creació de Comanda (amb RabbitMQ)
 
1. Cliqueu el botó **"Afegir i comprar"** en qualsevol producte
2. Al modal:
   - Deixeu `user1` com a usuari
   - Introduïu quantitat (p.e., 2)
   - Cliqueu **"Comprar"**
3. Hauries de veure el missatge: `Comanda creada! ID: 1`
**Verificar que la comanda es va publicar a RabbitMQ**:
```bash
docker compose logs order-service | grep "Missatge publicat"
```
 
**Verificar que notification-service va processar el missatge**:
```bash
docker compose logs notification-service | grep "NOVA NOTIFICACIÓ"
```
 
### Flux 3: Consultar Comandes
 
```bash
# Per API directa
curl http://localhost:8080/api/orders/
 
# Hauries de veure la comanda que creares
```
 
---
 
## Commands Útils
 
### Ver logs d'un servei específic
```bash
docker compose logs product-service -f        # -f = follow (en temps real)
docker compose logs order-service
docker compose logs notification-service
docker compose logs message-queue
```
 
### Accedir a una BD
```bash
# MySQL db-products
docker exec -it db-products mysql -u shopuser -pshoppass products_db
SELECT * FROM products;
 
# MySQL db-orders
docker exec -it db-orders mysql -u shopuser -pshoppass orders_db
SELECT * FROM orders;
```
 
### Accedir a Redis
```bash
docker exec -it cache redis-cli
KEYS *                 # Veure totes les claus cacheades
GET products:all       # Veure el contingut del cache de productes
```
 
### Accedir a RabbitMQ Web UI
```
http://localhost:15672
Usuari: shopuser
Contrasenya: shoppass
```
Aquí podeu veure la cua `orders` i els missatges.
 
### Aturar els contenidors
```bash
docker compose down
```
 
### Eliminar volums (ATENCIÓ: es perdran les dades!)
```bash
docker compose down -v
```
 
---
 
## Verificació del Desplegament
 
### Checklist
```
✓ docker compose ps → tots els contenidors "healthy"
✓ Accediu a http://localhost:8080 → veu el frontend
✓ La llista de productes es carrega → product-service funciona
✓ Creeu una comanda → order-service funciona
✓ docker compose logs notification-service | grep "NOVA NOTIFICACIÓ" → RabbitMQ funciona
✓ docker exec -it db-products mysql... → BD funciona
```
 
---
 
## Troubleshooting
 
### "Port 8080 is already in use"
```bash
# Canviar el port al docker-compose.yml
# Canviar línea: ports: - "8080:80"  →  ports: - "8081:80"
docker compose up -d
```
 
### Contenidors que no estan "healthy"
```bash
# Esperar més temps (30-60 segons)
docker compose ps
 
# Veure els logs per a errors
docker compose logs db-products
docker compose logs product-service
```
 
### "Cannot connect to RabbitMQ"
```bash
# Assegurar-se que RabbitMQ està healthy
docker compose ps message-queue
 
# Si no, reiniciar
docker compose restart message-queue
```
 
### "Connection refused: db-products"
```bash
# Els serveis es connecten entre ells per nom (definit a docker-compose)
# Si canvies `docker run` en comptes de `docker-compose`, no funcionarà
# Usa sempre: docker compose up -d
```
 
---
 
## Endpoints de l'API
 
### Product Service (http://localhost:8080/api/products/)
```
GET /api/products/         → Llista tots els productes
GET /api/products/1        → Obté producte amb ID 1
POST /api/products/        → Crea un producte nou
POST /api/products/update-stock  → Descomptar stock (intern)
```
 
### Order Service (http://localhost:8080/api/orders/)
```
GET /api/orders/           → Llista totes les comandes
GET /api/orders/1          → Obté comanda amb ID 1
POST /api/orders/          → Crea una nova comanda
```
 
### User Service (http://localhost:8080/api/users/)
```
GET /api/users             → Llista tots els usuaris
POST /api/users/register   → Registrar usuari nou
POST /api/users/login      → Login (retorna JWT token)
```
 
---
 
## Documentació de Docker Compose
 
### Fitxer docker-compose.yml - Explained
 
**Services**: Cada contenidor és un servei
- `db-products`: Base de dades MySQL de productes
- `product-service`: API Flask de productes
- ... (etc per a tots els altres)
**Networks**: Aïllament de tràfic
- `frontend-net`: Només frontend + api-gateway
- `backend-net`: Microserveis + cache
- `db-net`: Bases de dades
- `mq-net`: RabbitMQ + notification-service
**Volumes**: Persistència de dades
- `db_products_data`: /var/lib/mysql de db-products
- `redis_data`: /data de Redis
- `rabbitmq_data`: /var/lib/rabbitmq de RabbitMQ
**Healthchecks**: Proves de salut per sincronitzar arrencades
```yaml
healthcheck:
  test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
  interval: 10s      # Comprovar cada 10 segons
  timeout: 5s        # Timeout de 5 segons
  retries: 10        # Fallar després de 10 intents fallats
  start_period: 30s  # Esperar 30s abans de comprovar
```
 
**depends_on**: Ordenar l'arrencada dels serveis
```yaml
depends_on:
  db-products:
    condition: service_healthy  # Esperar a que db-products sigui healthy
```
 
---
 
## Fase Següent: Docker Swarm
 
Un cop comprenguis la Fase 1 (Docker Compose), la Fase 2 escalarà aquest mateix `docker-compose.yml` a un clúster Docker Swarm amb:
- Replicació de serveis (3 rèpliques per a alta disponibilitat)
- Balanceig de càrrega automàtic
- Orquestració en múltiples nodes
- Simulació de fallada de nodes
---
 
## Contacte / Suport
 
Si tens problemes:
1. Revisa els logs: `docker compose logs <servei>`
2. Verifica els ports: `docker compose ps`
3. Reinicia els contenidors: `docker compose restart`
4. Revisa la secció Troubleshooting arriba
---
