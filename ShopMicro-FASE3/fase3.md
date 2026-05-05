# Fase 3 — Seguretat a Docker Swarm

> **Objectiu**: aplicar mesures de seguretat al clúster Swarm de la Fase 2: migració de credencials a Docker Secrets, aïllament de xarxes overlay, anàlisi del TLS automàtic i escaneig de vulnerabilitats.

## Índex

1. [Tasca 1 — Anàlisi de vulnerabilitats](#1-tasca-1--anàlisi-de-vulnerabilitats)
2. [Tasca 2 — Migració a Docker Secrets](#2-tasca-2--migració-a-docker-secrets)
3. [Tasca 3 — Aïllament de xarxes overlay](#3-tasca-3--aïllament-de-xarxes-overlay)
4. [Tasca 4 — TLS i certificats al clúster](#4-tasca-4--tls-i-certificats-al-clúster)
5. [Tasca 5 — Escaneig de vulnerabilitats amb Docker Scout](#5-tasca-5--escaneig-de-vulnerabilitats-amb-docker-scout)
6. [Conclusions](#6-conclusions)

---

## 1. Tasca 1 — Anàlisi de vulnerabilitats

L'objectiu d'aquesta tasca és identificar i documentar totes les credencials que estan en clar al `docker-stack.yml` de la Fase 2.

### Comanda d'auditoria

```bash
grep -E "PASSWORD|PASS|SECRET|USER" docker-stack.yml
```

> 📸 **CAPTURA 3.1** — Sortida del `grep` mostrant totes les línies amb credencials en clar.

### Vulnerabilitats identificades

|  | Vulnerabilitat | Servei afectat | Risc |
|---|---|---|---|
| **V1** | Contrasenya MySQL `apppass123` en clar a `DB_PASSWORD` | product-service, order-service, user-service | **Alt** — qualsevol amb accés al fitxer pot accedir a totes les BD |
| **V2** | Credencials RabbitMQ `admin / admin123` en clar | message-queue, order-service, notification-service | **Mitjà-Alt** — accés al broker permet veure/manipular missatges |
| **V3** | Clau JWT `clausecreta_2asix` en clar | user-service | **Alt** — qualsevol amb la clau pot generar tokens vàlids i suplantar usuaris |
| **V4** | Usuari de BD `appuser` en clar a `DB_USER` | Tots els microserveis | **Baix** — informació útil per a atacants però no és el problema crític |

### Riscos generals

- Si el repositori Git es filtra → **totes les credencials queden exposades**.
- En entorn multi-equip, qualsevol desenvolupador amb accés al fitxer veu les contrasenyes de producció.
- Les variables d'entorn són visibles des de dins del contenidor (`env`) i via `docker inspect` per a qualsevol amb accés al socket Docker.
- Les contrasenyes a `environment:` queden als logs si algun procés bolca l'entorn.

---

## 2. Tasca 2 — Migració a Docker Secrets

### 2.1 Per què Docker Secrets

Els **Docker Secrets** són un mecanisme nadiu de Swarm per gestionar dades sensibles. Es caracteritzen per:

- **Xifrats en repòs** dins del clúster (Raft).
- **Xifrats en trànsit** entre nodes (mTLS).
- **Muntats com a fitxers** (no com a variables d'entorn) a `/run/secrets/<nom>`, evitant aparèixer a `docker inspect` i `env`.
- **Inmutables**: per canviar el valor cal crear un secret nou amb un altre nom.
- **Mínim privilegi**: cada servei només té accés als secrets que declara explícitament.

### 2.2 Crear els secrets a Swarm

Primer s'esborren els secrets antics que existien per la Fase 2:

```bash
docker secret ls
docker secret rm db_root_password shopmicro_db_root_password shopmicro_db_user_password
```

> 📸 **CAPTURA 3.2** — Sortida de `docker secret ls` abans de la neteja, i després mostrant llista buida.

A continuació es creen els 5 secrets nous, un per credencial:

```bash
echo -n 'rootpass123'        | docker secret create db_root_password -
echo -n 'apppass123'         | docker secret create db_user_password -
echo -n 'admin'              | docker secret create mq_user -
echo -n 'admin123'           | docker secret create mq_password -
echo -n 'clausecreta_2asix'  | docker secret create jwt_secret -
```

> 💡 **Important**: el `-n` de `echo` evita afegir un caràcter `\n` final, problema clàssic que ja vam patir a la Fase 1 amb els fitxers de secrets.

> 📸 **CAPTURA 3.3** — Sortida de les 5 comandes `docker secret create` i, després, `docker secret ls` mostrant els 5 secrets creats.

### 2.3 Adaptar el codi Python

Els secrets en Swarm es munten com a fitxers a `/run/secrets/<nom>`. Els microserveis Python han de llegir-los d'allà. Per fer-ho, s'ha afegit una funció helper a cada microservei:

```python
def read_secret(name, fallback_env=None):
    """Llegeix un secret de /run/secrets/<name>.
    Si no existeix, llegeix de la variable d'entorn (per compatibilitat amb Compose)."""
    secret_path = f'/run/secrets/{name}'
    if os.path.exists(secret_path):
        with open(secret_path, 'r') as f:
            return f.read().strip()
    if fallback_env and fallback_env in os.environ:
        return os.environ[fallback_env]
    raise RuntimeError(f"Secret '{name}' no trobat ni a /run/secrets/ ni com a variable {fallback_env}")
```

> 📸 **CAPTURA 3.4** — Captura del codi de la funció `read_secret` al fitxer `app.py` d'un dels microserveis.

El paràmetre `fallback_env` permet que el mateix codi funcioni tant en Swarm (amb secrets) com en Docker Compose (amb variables d'entorn), facilitant el desenvolupament local i la migració entre entorns.

### Resum de variables migrades a secrets per microservei

| Microservei | Variables que ara venen de secrets |
|---|---|
| `product-service` | `DB_PASSWORD` |
| `user-service` | `DB_PASSWORD`, `JWT_SECRET` |
| `order-service` | `DB_PASSWORD`, `MQ_USER`, `MQ_PASS` |
| `notification-service` | `MQ_USER`, `MQ_PASS` |

> 📸 **CAPTURA 3.5** — Captura de les línies `read_secret(...)` als 4 fitxers `app.py`.

### 2.4 Reconstruir i pujar les imatges

S'han reconstruït les imatges amb tag `:1.1` i s'han pujat a Docker Hub:

```bash
docker build -t arodriguez5/shopmicro-product-service:1.1 ./product-service
docker build -t arodriguez5/shopmicro-order-service:1.1 ./order-service
docker build -t arodriguez5/shopmicro-user-service:1.1 ./user-service
docker build -t arodriguez5/shopmicro-notification-service:1.1 ./notification-service

docker push arodriguez5/shopmicro-product-service:1.1
docker push arodriguez5/shopmicro-order-service:1.1
docker push arodriguez5/shopmicro-user-service:1.1
docker push arodriguez5/shopmicro-notification-service:1.1
```

> 📸 **CAPTURA 3.6** — Sortida del `docker build` per a una imatge.

> 📸 **CAPTURA 3.7** — Sortida del `docker push` mostrant les 4 imatges pujades a Docker Hub amb el tag `:1.1`.

### 2.5 Cas especial: RabbitMQ i la deprecació de `_FILE`

Durant el desplegament es va detectar que la imatge oficial `rabbitmq:3-management` (versió 3.13+) **ha eliminat el suport** per a les variables d'entorn `RABBITMQ_DEFAULT_USER_FILE` i `RABBITMQ_DEFAULT_PASS_FILE`, fent que el contenidor sortís immediatament amb codi d'error:

```
error: RABBITMQ_DEFAULT_PASS_FILE is set but deprecated
error: RABBITMQ_DEFAULT_USER_FILE is set but deprecated
Please use a configuration file instead
```

> 📸 **CAPTURA 3.8** — Logs del contenidor de RabbitMQ amb els missatges d'error de deprecació.

#### Solució aplicada: fitxer de definicions JSON

Seguint la documentació oficial de RabbitMQ, s'ha migrat a l'enfocament basat en un **fitxer de definicions JSON** que conté usuaris, permisos i virtual hosts. Aquest fitxer es carrega a l'arrencada mitjançant la directiva `load_definitions` del `rabbitmq.conf`.

El fitxer JSON conté el hash SHA-256 de la contrasenya (RabbitMQ no permet emmagatzemar contrasenyes en clar):

```json
{
  "rabbit_version": "3.13.0",
  "users": [{
    "name": "admin",
    "password_hash": "Rl+QdrxlCXCho4h2TgizyKTmUbcSWslY0BHK5L1lykIkh3sb",
    "hashing_algorithm": "rabbit_password_hashing_sha256",
    "tags": ["administrator"]
  }],
  "vhosts": [{"name": "/"}],
  "permissions": [{
    "user": "admin", "vhost": "/",
    "configure": ".*", "write": ".*", "read": ".*"
  }]
}
```

El hash s'ha generat amb un script Python:

```python
import hashlib, base64, os
password = 'admin123'
salt = os.urandom(4)
hashed = salt + hashlib.sha256(salt + password.encode('utf-8')).digest()
print(base64.b64encode(hashed).decode('utf-8'))
```

> 📸 **CAPTURA 3.9** — Sortida del script Python generant el hash.

> 📸 **CAPTURA 3.10** — Captura del fitxer `rabbitmq-definitions.json` complet amb el hash incrustat.

Tant el `rabbitmq-definitions.json` com el `rabbitmq.conf` s'han pujat com a Docker Secrets:

```bash
docker secret create rabbitmq_definitions ./rabbitmq-definitions.json
docker secret create rabbitmq_config ./rabbitmq.conf
```

> 📸 **CAPTURA 3.11** — Sortida de `docker secret ls` mostrant els 7 secrets totals (5 originals + `rabbitmq_definitions` + `rabbitmq_config`).

Aquesta solució té tres avantatges:

1. Compleix amb les recomanacions oficials de RabbitMQ.
2. Manté el principi de la Fase 3 que cap credencial estigui en clar al `docker-stack.yml`.
3. Permet definir polítiques, vhosts i queues de manera declarativa, facilitant futures ampliacions.

### 2.6 Nou docker-stack.yml amb secrets

> 📸 **CAPTURA 3.12** — Captura del fitxer `docker-stack.yml` complet amb els canvis (en diverses parts si cal).

#### Canvis principals respecte a la Fase 2

- Cap valor de contrasenya en clar a `environment:`.
- Cada servei declara explícitament quins secrets necessita amb `secrets:`.
- El bloc final `secrets:` declara tots els secrets com a `external: true`.
- El servei `message-queue` ara munta `rabbitmq_config` a `/etc/rabbitmq/rabbitmq.conf` amb la sintaxi extensa `source/target`.

```yaml
secrets:
  db_root_password:    { external: true }
  db_user_password:    { external: true }
  mq_user:             { external: true }
  mq_password:         { external: true }
  jwt_secret:          { external: true }
  rabbitmq_config:     { external: true }
  rabbitmq_definitions: { external: true }
```

`external: true` significa que aquests secrets ja existeixen al clúster (creats manualment) i Docker no els tornarà a crear ni a sobreescriure. Això **desacobla el cicle de vida dels secrets del cicle de vida del stack**, una bona pràctica de seguretat.

### 2.7 Redesplegament i verificació

```bash
docker stack rm shopmicro
sleep 20
docker volume rm shopmicro_db_products_data shopmicro_db_orders_data shopmicro_cache_data shopmicro_mq_data
docker stack deploy -c docker-stack.yml shopmicro
```

> 📸 **CAPTURA 3.13** — Sortida del `docker stack deploy` mostrant la creació dels serveis amb les noves imatges `:1.1`.

> 📸 **CAPTURA 3.14** — Sortida de `docker stack services shopmicro` mostrant tots els serveis amb rèpliques `X/X`, incloent `message-queue 1/1`.

> 📸 **CAPTURA 3.15** — Logs de RabbitMQ mostrant el missatge `Importing concurrently 1 users... Started RabbitMQ broker` confirmant que ha carregat les definicions del JSON.

### 2.8 Verificació funcional

Tota la web segueix funcionant amb els secrets, però ara cap credencial està en clar enlloc.

> 📸 **CAPTURA 3.16** — Captura de la web mostrant el login funcional amb token JWT, la càrrega de productes amb badge de Redis, i la creació de comandes.

> 📸 **CAPTURA 3.17** — Logs de `notification-service` mostrant els missatges de notificació rebuts (`[NOTIFICACIÓ] Comanda #X creada...`), demostrant que el flux 2 funciona en mode segur.

---

## 3. Tasca 3 — Aïllament de xarxes overlay

### 3.1 Disseny basat en mínim privilegi

A diferència de la Fase 2, on s'utilitzaven 3 xarxes overlay genèriques, ara s'han creat **6 xarxes overlay especialitzades** seguint el principi de mínim privilegi. Cada servei només pot pertànyer a les xarxes que realment necessita per a la seva funció.

```yaml
networks:
  frontend-net:    { driver: overlay }   # frontend ↔ api-gateway
  backend-net:     { driver: overlay }   # api-gateway ↔ microserveis
  products-net:    { driver: overlay }   # product/order-service ↔ db-products
  orders-net:      { driver: overlay }   # order/user-service ↔ db-orders
  cache-net:       { driver: overlay }   # product-service ↔ cache
  mq-net:          { driver: overlay }   # order/notification-service ↔ rabbitmq
```

> 📸 **CAPTURA 3.18** — Captura de la secció `networks:` del `docker-stack.yml`.

### 3.2 Matriu de comunicació

| Origen ↓ / Destí → | frontend | api-gw | product | order | user | notif | db-prod | db-ord | cache | rabbitmq |
|---|---|---|---|---|---|---|---|---|---|---|
| **Usuari (port 8080)** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **frontend** | – | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **api-gateway** | ❌ | – | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **product-service** | ❌ | ❌ | – | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ |
| **order-service** | ❌ | ❌ | ❌ | – | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ |
| **user-service** | ❌ | ❌ | ❌ | ❌ | – | ❌ | ❌ | ✅ | ❌ | ❌ |
| **notif-service** | ❌ | ❌ | ❌ | ❌ | ❌ | – | ❌ | ❌ | ❌ | ✅ |

### 3.3 Verificació de les xarxes creades

```bash
docker network ls | grep shopmicro
```

> 📸 **CAPTURA 3.19** — Sortida del `docker network ls` mostrant les 6 xarxes overlay del stack.

### 3.4 Inspecció dels serveis a cada xarxa

```bash
for net in frontend-net backend-net products-net orders-net cache-net mq-net; do
    echo "===== shopmicro_$net ====="
    docker network inspect shopmicro_$net \
        --format '{{range .Containers}}{{.Name}}{{println}}{{end}}'
    echo ""
done
```

> 📸 **CAPTURA 3.20** — Sortida del bucle mostrant els contenidors connectats a cada xarxa.

### 3.5 Prova pràctica d'aïllament

La prova definitiva consisteix a intentar resoldre noms DNS des de dins d'un contenidor que **no hauria de poder veure** altres serveis.

#### Setup: identificar un contenidor del frontend

```bash
# Al worker on s'executi el frontend:
docker ps --filter "name=shopmicro_frontend"
FRONTEND_ID=f448b1d1e401
```

> 📸 **CAPTURA 3.21** — Sortida del `docker ps` identificant el contenidor del frontend.

#### Test 1: el frontend POT parlar amb l'api-gateway (mateixa xarxa)

```bash
docker exec $FRONTEND_ID getent hosts api-gateway
```

Resultat esperat: una IP, exemple `10.0.6.2`.

> 📸 **CAPTURA 3.22** — Sortida del `getent hosts api-gateway` retornant una IP.

#### Test 2: el frontend NO POT parlar amb les BDs (diferent xarxa)

```bash
docker exec $FRONTEND_ID getent hosts db-products
docker exec $FRONTEND_ID getent hosts db-orders
docker exec $FRONTEND_ID getent hosts product-service
docker exec $FRONTEND_ID getent hosts user-service
docker exec $FRONTEND_ID getent hosts cache
```

Resultat esperat: cap sortida (silenci) i exit code != 0.

> 📸 **CAPTURA 3.23** — Sortida dels `getent` retornant buit, demostrant l'aïllament. **Aquesta és la captura clau de la Tasca 3.**

### 3.6 Anàlisi dels avantatges

L'aïllament implementat segueix el principi de mínim privilegi i ofereix tres beneficis clars:

1. **Limitació de la superfície d'atac**: si un atacant comprometés el frontend (per exemple, mitjançant una vulnerabilitat al servidor Nginx o al codi JavaScript del client), no podria saltar directament a les bases de dades, ja que aquestes ni tan sols són resolubles per DNS des del seu contenidor. L'única ruta possible passa pel `api-gateway`, que pot aplicar autenticació i altres controls.

2. **Aïllament de dominis funcionals**: el `product-service` no pot parlar amb `db-orders`, ni el `user-service` amb `db-products`. Això evita que una vulnerabilitat en un microservei comprometi dades d'un altre domini funcional.

3. **Reducció del risc del notification-service**: aquest servei només té accés a `mq-net` (RabbitMQ). Encara que un atacant aconseguís executar codi dins el seu contenidor, no podria escalar a cap base de dades ni a la resta de microserveis.

---

## 4. Tasca 4 — TLS i certificats al clúster

### 4.1 Què passa per dins de Swarm

Quan es va executar `docker swarm init` a la Fase 2, internament Swarm va realitzar tres operacions criptogràfiques que normalment no es veuen:

1. **Va crear una CA (Certificate Authority) arrel** dins del manager. Funciona com un "notari" intern del clúster.
2. **Va generar un certificat TLS per al manager**, signat per aquesta CA.
3. Cada vegada que un worker s'unia amb `docker swarm join`, **la CA li emetia el seu propi certificat TLS únic**.

A partir d'aquest moment, tota comunicació de control entre nodes es xifra amb **TLS mutu (mTLS)**: el manager verifica el certificat del worker, i el worker verifica el del manager. Si algú intentés connectar-se sense un certificat vàlid signat per la CA del clúster, seria rebutjat immediatament.

Això és el que fa que **Swarm sigui segur per defecte**, sense que l'administrador hagi de tocar res d'OpenSSL.

### 4.2 Verificar l'estat de la CA

```bash
docker info | grep -A 25 "Swarm:"
```

> 📸 **CAPTURA 3.24** — Sortida de `docker info | grep -A 25 "Swarm:"` mostrant la secció `CA Configuration: Expiry Duration: 3 months`.

Punts destacables de la sortida:

- **`CA Configuration: Expiry Duration: 3 months`**: validesa dels certificats dels nodes.
- **`Force Rotate: 0`**: cap rotació forçada en marxa.
- **`Root Rotation In Progress: false`**: la CA arrel no està rotant ara mateix.
- **`Manager Addresses: 192.168.0.1:2377`**: endpoint mTLS del manager.

### 4.3 Inspeccionar el certificat arrel de la CA

```bash
sudo openssl x509 -in /var/lib/docker/swarm/certificates/swarm-root-ca.crt -text -noout | head -25
```

> 📸 **CAPTURA 3.25** — Sortida de l'`openssl x509` mostrant el certificat arrel.

#### Punts destacables del certificat arrel

- **`Issuer: CN=swarm-ca`** i **`Subject: CN=swarm-ca`**: l'emissor i el subjecte són el mateix → és una **CA autofirmada (self-signed)**, normal per a una CA arrel.
- **`Validity 10 anys`**: la CA arrel dura 10 anys. Els certificats dels nodes (managers/workers) que firma aquesta CA només duren 3 mesos i es renoven automàticament.
- **`ecdsa-with-SHA256`** i **`Public-Key: (256 bit)`**: utilitza criptografia de **corba el·líptica (ECDSA)**, més moderna i eficient que RSA.
- **`X509v3 Key Usage: Certificate Sign`** i **`CA:TRUE`**: aquest certificat sí pot signar altres certificats, com tota CA.

### 4.4 Inspeccionar el certificat del propi node manager

```bash
sudo openssl x509 -in /var/lib/docker/swarm/certificates/swarm-node.crt -text -noout | head -30
```

> 📸 **CAPTURA 3.26** — Sortida del certificat del node manager.

#### Punts destacables del certificat del node

- **`Issuer: CN=swarm-ca`** → aquest certificat l'ha signat la CA del clúster (la de la secció anterior). No és autofirmat.
- **`Subject: O=ClusterID, OU=swarm-manager, CN=NodeID`** → cada node té la seva identitat incrustada al certificat:
  - `O` = ID del clúster (tots els nodes del mateix clúster comparteixen aquest valor).
  - `OU` = rol del node (`swarm-manager` o `swarm-worker`).
  - `CN` = identificador únic del node.

Això és el que permet el **mTLS amb autenticació mútua i d'identitat**: quan un worker es connecta al manager, el manager verifica que el certificat del worker té el mateix `O` (mateix clúster) i un `CN` vàlid (un node conegut).

### 4.5 Tràfic de control vs. tràfic de dades

És important diferenciar dos tipus de tràfic en un clúster Swarm:

| Tipus | Característiques |
|---|---|
| **Tràfic de control** (entre managers i workers) | Sempre xifrat amb mTLS. No es pot desactivar. |
| **Tràfic de dades** (entre contenidors via xarxes overlay) | Per defecte NO xifrat. Es pot activar amb `--opt encrypted` (xifrat IPSEC). |

En aquesta pràctica, com que les VMs es troben en una xarxa interna aïllada (192.168.0.0/24) i amb baixos requeriments de confidencialitat, no s'ha activat el xifrat de dades a les xarxes overlay. En un entorn de producció amb nodes a diferents centres de dades o en cloud públic, seria una mesura imprescindible.

### 4.6 Rotació automàtica de certificats

Una de les avantatges principals d'aquest sistema és que la rotació de certificats és **completament automàtica i transparent** per a l'administrador. Swarm renova els certificats dels nodes abans que expirin sense interrompre el servei. Si calgués, també es pot forçar una rotació manual amb:

```bash
docker swarm update --cert-expiry <durada>
docker swarm ca --rotate    # rotar la CA arrel completa
```

---

## 5. Tasca 5 — Escaneig de vulnerabilitats amb Docker Scout

### 5.1 Instal·lació de Docker Scout

```bash
curl -fsSL https://raw.githubusercontent.com/docker/scout-cli/main/install.sh -o install-scout.sh
sh install-scout.sh
docker scout version
```

> 📸 **CAPTURA 3.27** — Sortida de `docker scout version` confirmant la instal·lació (v1.20.4).

### 5.2 Vista ràpida de cada imatge

```bash
docker scout quickview mysql:8.0
docker scout quickview redis:7-alpine
docker scout quickview rabbitmq:3-management
docker scout quickview nginx:alpine
docker scout quickview arodriguez5/shopmicro-product-service:1.1
docker scout quickview arodriguez5/shopmicro-order-service:1.1
docker scout quickview arodriguez5/shopmicro-user-service:1.1
docker scout quickview arodriguez5/shopmicro-notification-service:1.1
docker scout quickview arodriguez5/shopmicro-frontend:1.0
docker scout quickview arodriguez5/shopmicro-api-gateway:1.0
```

> 📸 **CAPTURA 3.28** — Sortida del `quickview` per a les imatges base (mysql, redis, rabbitmq, nginx).

> 📸 **CAPTURA 3.29** — Sortida del `quickview` per a les imatges pròpies (product, order, user, notification, frontend, api-gateway).

### 5.3 Anàlisi detallat de cada imatge

S'han generat informes complets amb `docker scout cves`:

```bash
mkdir -p ~/shopmicro/scout-reports
cd ~/shopmicro/scout-reports

docker scout cves mysql:8.0 > mysql.txt
docker scout cves redis:7-alpine > redis.txt
docker scout cves rabbitmq:3-management > rabbitmq.txt
docker scout cves nginx:alpine > nginx.txt
docker scout cves arodriguez5/shopmicro-product-service:1.1 > product-service.txt
# ... resta d'imatges
```

> 📸 **CAPTURA 3.30** — Sortida del `ls -la` a `scout-reports/` mostrant tots els fitxers d'informes generats.

### 5.4 Resum de vulnerabilitats detectades

| Imatge | Mida | Crítiques | Altes | Mitges | Baixes | Total |
|---|---|---|---|---|---|---|
| `mysql:8.0` | 234 MB | **1** | 12 | 15 | 4 | **32** |
| `redis:7-alpine` | ~40 MB | 5 | 45 | 38 | 3 | **91** |
| `rabbitmq:3-management` | ~250 MB | 3 | 15 | 50 | 17 | **85** |
| `nginx:alpine` | ~50 MB | 0 | 2 | 10 | 2 | **15** |
| `arodriguez5/shopmicro-product-service:1.1` | 86 MB | 0 | 5 | 0 | 0 | **5** |
| `arodriguez5/shopmicro-order-service:1.1` | 86 MB | 0 | 9 | 0 | 24 | **33** |
| `arodriguez5/shopmicro-user-service:1.1` | 86 MB | 0 | 10 | 0 | 24 | **34** |
| `arodriguez5/shopmicro-notification-service:1.1` | ~80 MB | 0 | 5 | 0 | 24 | **29** |
| `arodriguez5/shopmicro-frontend:1.0` | ~50 MB | 0 | 2 | 10 | 2 | **15** |
| `arodriguez5/shopmicro-api-gateway:1.0` | ~50 MB | 0 | 2 | 10 | 2 | **15** |
| **TOTAL** | | **9** | **107** | **133** | **104** | **~353** |

### 5.5 Conclusions del resum

- **Total de vulnerabilitats trobades**: aproximadament **353** repartides entre les 10 imatges.
- **Vulnerabilitats CRITICAL**: només n'hi ha **9** en total (1 a MySQL, 3 a RabbitMQ, 5 a Redis).
- La imatge amb més vulnerabilitats és `redis:7-alpine` (91), tot i la seva mida petita. Això és contraintuïtiu però lògic: Alpine s'actualitza lentament i el Redis utilitza biblioteques antigues.
- **Les meves imatges Python són les més netes** (5-34 vulnerabilitats), demostrant que `python:3.11-slim` és una bona elecció de base.
- `notification-service` (que no té API web) també té poques vulnerabilitats, perquè té menys dependències.

### 5.6 Anàlisi detallada de les CVEs més greus

#### 🔴 CVE-2025-68121 — La única vulnerabilitat CRITICAL

| Camp | Valor |
|---|---|
| **Severitat** | 🔴 **CRITICAL** |
| **Component afectat** | `stdlib` (Go standard library) v1.24.6 |
| **Versió vulnerable** | < 1.24.13 |
| **Versió corregida** | 1.24.13 |
| **Imatge afectada** | `mysql:8.0` (entrypoint utilitza Go) |

**Descripció**: Vulnerabilitat crítica a la biblioteca estàndard de Go que afecta el binari `docker-entrypoint.sh` de MySQL (compilat amb Go).

**Mitigació en el meu cas**: **Risc real BAIX**. La vulnerabilitat afecta el procés d'arrencada del contenidor, no el motor de MySQL en si. Els meus contenidors de BD no estan exposats a Internet (només a les xarxes overlay `products-net` i `orders-net`), només arrenquen un cop, i estan al manager amb accés restringit per SSH.

> 📸 **CAPTURA 3.31** — Sortida de `docker scout cves --only-severity critical,high mysql:8.0` mostrant la CVE-2025-68121 i les altres altes.

#### 🟠 CVE-2024-21272 — SQL Injection (afecta directament l'app)

| Camp | Valor |
|---|---|
| **Severitat** | 🟠 **HIGH** (CVSS 7.7) |
| **Component afectat** | `mysql-connector-python` v8.2.0 |
| **Versió vulnerable** | < 9.1.0 |
| **Versió corregida** | 9.1.0 |
| **Imatges afectades** | product-service, order-service, user-service |

**Descripció**: Improper Neutralization of Special Elements used in an SQL Command (CWE-89). El connector de Python a MySQL no escapa correctament certs caràcters especials en consultes preparades.

**Risc real per a la meva app**: **MITJÀ**. La meva app utilitza `mysql.connector` directament amb consultes parametritzades (`%s`). Tot i que l'ús correcte de paràmetres mitiga la majoria d'injeccions SQL, una vulnerabilitat al propi connector podria ser explotada en certs camps controlats per l'usuari.

**Mitigació immediata recomanada**: actualitzar `requirements.txt` dels microserveis a `mysql-connector-python==9.1.0` i tornar a construir les imatges com a `:1.2`.

> 📸 **CAPTURA 3.32** — Sortida de `docker scout cves --only-severity critical,high arodriguez5/shopmicro-product-service:1.1` mostrant la CVE-2024-21272 i les altres altes.

#### 🟠 CVE-2026-24049 — Path Traversal a Wheel

| Camp | Valor |
|---|---|
| **Severitat** | 🟠 **HIGH** (CVSS 7.1) |
| **Component afectat** | `wheel` v0.45.1 (eina de packaging Python) |
| **Versió corregida** | 0.46.2 |

**Descripció**: Improper Limitation of a Pathname to a Restricted Directory (CWE-22). L'eina `wheel` que `pip` utilitza per instal·lar paquets tenia una vulnerabilitat en la gestió de paths.

**Risc real**: **MOLT BAIX**. L'eina `wheel` només s'utilitza durant la **construcció** de la imatge Docker, no en runtime. Un cop la imatge està construïda, el binari ja no s'executa.

### 5.7 Defensa en profunditat aplicada

L'escaneig ha revelat 353 vulnerabilitats totals. Eliminar-les TOTES és pràcticament impossible: cada actualització d'una imatge introdueix noves dependències amb les seves pròpies CVEs. La filosofia correcta no és "zero vulnerabilitats" sinó **fer que les vulnerabilitats existents siguin difícils d'explotar**.

| Vulnerabilitat tipus | Mitigació aplicada en aquest projecte |
|---|---|
| SQL Injection a `user-service` | Aïllament de xarxes: només pot accedir a `db-orders`, no a `db-products`. Si un atacant injecta SQL, no pot saltar entre BDs. |
| Compromís d'una imatge | Docker Secrets: les credencials no estan a `docker inspect` ni a `env`. |
| RCE en notification-service | El servei NO té accés a cap BD. El dany màxim és parar les notificacions. |
| Atac MITM al clúster | mTLS automàtic entre nodes amb CA interna i certificats rotats cada 3 mesos. |
| Filtració del codi font | Cap credencial en clar al `docker-stack.yml`. |
| Compromís d'un worker | Constraints `node.role == manager` als serveis crítics: les BDs mai s'executen al worker compromès. |

L'objectiu d'aquesta arquitectura és garantir que cap vulnerabilitat individual sigui suficient per comprometre tot el sistema. Aquest és el principi de **"defense in depth"** recomanat per OWASP i CISA.

### 5.8 Mesures de mitigació proposades a llarg termini

1. **Imatges base mínimes**: substituir imatges grans com `python:3.11` per versions `slim` o `alpine`. Ja s'ha fet en aquest projecte; es podria considerar fins i tot **distroless** per a producció.
2. **Multi-stage builds**: construir les imatges en dues etapes per reduir mida i superfície d'atac.
3. **Usuari no-root als contenidors**: afegir `USER appuser` als Dockerfiles per limitar danys en cas de compromís.
4. **Actualització regular d'imatges**: refer i pujar les imatges almenys un cop al mes.
5. **Pinning per digest**: utilitzar `mysql:8.0@sha256:abc123...` en lloc de `mysql:8.0` per garantir reproducibilitat.
6. **Escaneig automàtic en CI/CD**: integrar `docker scout cves` com a etapa obligatòria abans de publicar imatges.
7. **Signatura d'imatges** (Docker Content Trust o Cosign): garantir que no han estat manipulades.

---

## 6. Conclusions

### Què s'ha aconseguit

- Migració completa de credencials a Docker Secrets (5 secrets per a credencials + 2 secrets per a la configuració de RabbitMQ).
- Aïllament de xarxes overlay segons el principi de mínim privilegi (6 xarxes especialitzades).
- Documentació del funcionament del TLS automàtic de Swarm i la seva CA interna.
- Escaneig de vulnerabilitats de totes les imatges amb Docker Scout, identificant 353 CVEs i analitzant les més crítiques.
- Tot el sistema continua funcionant igual que a la Fase 2 però ara amb seguretat en profunditat.

### Què s'ha après

- **Diferència entre seguretat per defecte i seguretat aplicada**: Swarm ofereix mTLS gratuït, però Docker Secrets i l'aïllament de xarxes són responsabilitat de qui dissenya l'stack.
- **Comportament dels secrets en Swarm**: són immutables, externs al stack i es munten com a fitxers (no com a variables d'entorn).
- **Adaptació a canvis d'API**: la deprecació de `RABBITMQ_DEFAULT_USER_FILE` requereix migrar a un fitxer de definicions JSON. Saber llegir documentació oficial i adaptar-se és part de la feina.
- **Defensa en profunditat**: les vulnerabilitats no s'eliminen, es **mitiguen** mitjançant capes de seguretat. Una sola CVE no ha de ser suficient per comprometre el sistema.
- **Gestió de certificats automàtica**: Swarm gestiona la CA i els certificats dels nodes sense intervenció manual, però cal entendre què passa per dins.

### Limitacions detectades

- **Duplicació de credencials de RabbitMQ**: el JSON i els secrets `mq_user`/`mq_password` han de coincidir manualment. En producció es resoldria amb scripts de provisioning.
- **No s'ha activat el xifrat de xarxes overlay** (`--opt encrypted`). En aquest entorn (xarxa interna aïllada) no és crític, però en cloud públic seria imprescindible.
- **CVEs no resoltes**: tot i identificades, no s'han eliminat totes per limitacions de temps. Caldria un cicle d'actualització mensual de les imatges.

---

*⬅️ Tornar a la [Fase 2](./FASE2.md) | Anar a la [Fase 4 — Kubernetes](./FASE4.md) ➡️*