# Fase 2 — Docker Swarm: Clúster d'Alta Disponibilitat

> **Objectiu**: convertir l'entorn local de la Fase 1 en un clúster Docker Swarm format per 3 màquines virtuals (1 manager + 2 workers), desplegar tots els microserveis amb rèpliques i demostrar la tolerància a fallades i l'escalat en calent.

## Índex

1. [Infraestructura](#1-infraestructura)
2. [Pujar imatges a Docker Hub](#2-pujar-imatges-a-docker-hub)
3. [Inicialitzar el clúster Swarm](#3-inicialitzar-el-clúster-swarm)
4. [Adaptació del docker-stack.yml](#4-adaptació-del-docker-stackyml)
5. [Desplegament al clúster](#5-desplegament-al-clúster)
6. [Tolerància a fallades](#6-tolerància-a-fallades)
7. [Escalat en calent](#7-escalat-en-calent)
8. [Conclusions](#8-conclusions)

---

## 1. Infraestructura

Per a aquesta fase s'han preparat **3 màquines virtuals** a VirtualBox amb Ubuntu Server 24 i Docker Engine instal·lat:

| Nom | Rol | IP xarxa interna | IP host-only |
|---|---|---|---|
| `manager` | Manager Swarm | 192.168.0.1 | 192.168.56.2 |
| `worker1` | Worker Swarm | 192.168.0.2 | 192.168.56.3 |
| `worker2` | Worker Swarm | 192.168.0.3 | 192.168.56.4 |

> 💡 **Configuració de xarxa**: cada VM té dos adaptadors. La **xarxa interna** (`192.168.0.0/24`) és la que utilitzen els nodes per comunicar-se entre ells durant el funcionament del clúster Swarm. La **xarxa host-only** (`192.168.56.0/24`) és la que utilitza el meu Windows per connectar-me per SSH a les VMs.

> 📸 **CAPTURA 2.1** — Captura mostrant les tres VMs encesses al VirtualBox amb els seus noms i adreces IP.

---

## 2. Pujar imatges a Docker Hub

A diferència de la Fase 1, on les imatges es construïen i s'utilitzaven localment, en un clúster Swarm multi-node **les imatges han d'estar disponibles a un registry accessible per tots els nodes**. Sense això, els workers no podrien executar contenidors basats en imatges que només existeixen al manager.

Per a aquest projecte s'ha utilitzat **Docker Hub** amb l'usuari `arodriguez5`.

### Comandes utilitzades

```bash
# Login a Docker Hub (un sol cop)
docker login

# Construïm les imatges amb tags adequats
docker build -t arodriguez5/shopmicro-frontend:1.0 ./frontend
docker build -t arodriguez5/shopmicro-api-gateway:1.0 ./api-gateway
docker build -t arodriguez5/shopmicro-product-service:1.0 ./product-service
docker build -t arodriguez5/shopmicro-order-service:1.0 ./order-service
docker build -t arodriguez5/shopmicro-user-service:1.0 ./user-service
docker build -t arodriguez5/shopmicro-notification-service:1.0 ./notification-service

# Pugem les imatges a Docker Hub
docker push arodriguez5/shopmicro-frontend:1.0
docker push arodriguez5/shopmicro-api-gateway:1.0
docker push arodriguez5/shopmicro-product-service:1.0
docker push arodriguez5/shopmicro-order-service:1.0
docker push arodriguez5/shopmicro-user-service:1.0
docker push arodriguez5/shopmicro-notification-service:1.0
```

> 📸 **CAPTURA 2.2** — Sortida del `docker compose up -d --build` mostrant la construcció de les 6 imatges localment.

> 📸 **CAPTURA 2.3** — Sortida dels `docker push` mostrant les imatges pujades a Docker Hub.

> 📸 **CAPTURA 2.4** — Captura de la pàgina de Docker Hub a `https://hub.docker.com/u/arodriguez5` mostrant els 6 repositoris.

---

## 3. Inicialitzar el clúster Swarm

### Inicialització al manager

```bash
docker swarm init --advertise-addr 192.168.0.1
```

Aquesta comanda retorna un token que cal copiar per fer servir als workers:

```
docker swarm join --token SWMTKN-1-xxxxx 192.168.0.1:2377
```

### Unió dels workers

A `worker1` i `worker2`, executem la comanda `docker swarm join` amb el token rebut.

### Verificació de l'estat del clúster

```bash
docker node ls
```

> 📸 **CAPTURA 2.5** — Sortida de `docker node ls` mostrant els 3 nodes en estat `Ready` i `Active`, amb el manager com a `Leader`.

```
ID                            HOSTNAME   STATUS    AVAILABILITY   MANAGER STATUS
n29jmdhodb5t6wuz5ktn2sd6b *   manager    Ready     Active         Leader
xciydcayxgoavr96qb8oaviin     worker1    Ready     Active         
8j5zj4tb6ej7lcian6s24gbz7     worker2    Ready     Active
```

---

## 4. Adaptació del docker-stack.yml

El fitxer `docker-compose.yml` de la Fase 1 no es pot utilitzar directament en Swarm. Cal crear un nou fitxer `docker-stack.yml` amb les següents diferències:

### Canvis principals respecte a Compose

| Concepte | Compose (Fase 1) | Swarm (Fase 2) |
|---|---|---|
| `build:` | Sí, construeix localment | **No suportat** — cal `image:` apuntant a Docker Hub |
| `depends_on` | Espera healthchecks | **Ignorat** — Swarm no garanteix ordre |
| `container_name` | Personalitzat | **Ignorat** |
| `deploy:` | Ignorat per Compose | **Aquí és on es configura tot** |
| Xarxes | `bridge` per defecte | `overlay` (multi-node) |

### Configuració dels `deploy:` aplicada

Cada servei té un bloc `deploy:` amb:

- **`replicas`**: nombre de rèpliques (2 per als microserveis d'API, 1 per a les BD).
- **`placement.constraints`**: les BDs i la cua estan forçades al manager (`node.role == manager`) perquè tenen volums locals.
- **`restart_policy`**: reinici automàtic si un contenidor cau.
- **`update_config`**: rolling update amb `parallelism: 1` i `order: start-first` (zero downtime).

> 📸 **CAPTURA 2.6** — Captura del fitxer `docker-stack.yml` complet (pot ser en diverses parts).

### Exemple de bloc `deploy:` per a un microservei

```yaml
product-service:
  image: arodriguez5/shopmicro-product-service:1.0
  environment:
    DB_HOST: db-products
    DB_USER: appuser
    DB_PASSWORD: apppass123
    DB_NAME: products_db
    REDIS_HOST: cache
  networks:
    - backend-net
    - data-net
  deploy:
    replicas: 2
    restart_policy:
      condition: on-failure
      delay: 5s
    update_config:
      parallelism: 1
      delay: 10s
      order: start-first
```

### Exemple de bloc `deploy:` per a una BD

```yaml
db-products:
  image: mysql:8.0
  # ... resta de configuració ...
  deploy:
    replicas: 1
    placement:
      constraints:
        - node.role == manager
    restart_policy:
      condition: on-failure
```

---

## 5. Desplegament al clúster

### Còpia de fitxers al manager

Des de Windows amb PowerShell:

```bash
scp docker-stack.yml arodriguez@192.168.56.2:~/shopmicro/
scp -r secrets arodriguez@192.168.56.2:~/shopmicro/
```

> 📸 **CAPTURA 2.7** — Sortida de l'`scp` mostrant la transferència dels fitxers al manager.

> 📸 **CAPTURA 2.8** — Sortida de `ls -la` al manager mostrant `docker-stack.yml` i la carpeta `secrets/`.

### Desplegament

```bash
docker stack deploy -c docker-stack.yml shopmicro
```

> 📸 **CAPTURA 2.9** — Sortida del `docker stack deploy` mostrant la creació de xarxes, secrets i serveis.

### Verificació de l'estat dels serveis

```bash
docker stack services shopmicro
```

> 📸 **CAPTURA 2.10** — Sortida de `docker stack services shopmicro` mostrant tots els serveis amb les rèpliques desitjades.

### Distribució de rèpliques per node

```bash
docker stack ps shopmicro
```

> 📸 **CAPTURA 2.11** — Sortida de `docker stack ps shopmicro` mostrant on s'executa cada rèplica (manager, worker1 o worker2).

### Demostració del routing mesh

Una característica clau de Swarm és el **routing mesh**: el port 8080 està disponible des de **qualsevol IP del clúster**, encara que el contenidor del frontend només s'executi físicament en un dels nodes. Swarm enruta automàticament la petició al node correcte.

```bash
curl -I http://192.168.0.1:8080    # via manager
curl -I http://192.168.0.2:8080    # via worker1
curl -I http://192.168.0.3:8080    # via worker2
```

Les tres comandes han de retornar `HTTP/1.1 200 OK`.

> 📸 **CAPTURA 2.12** — Sortida dels tres `curl` a les diferents IPs del clúster, totes responent amb 200 OK.

### Logs del notification-service durant l'ús

```bash
docker service logs shopmicro_notification-service --tail 10
```

> 📸 **CAPTURA 2.13** — Logs del `notification-service` mostrant els missatges `[NOTIFICACIÓ] Comanda #X creada...` i confirmant que el flux 2 funciona en el clúster.

### Resolució de problemes detectats

Durant el primer desplegament a Swarm es va observar que els microserveis no podien crear les taules a les BDs degut a una **race condition**: les rèpliques arrencaven abans que MySQL hagués acabat la inicialització completa (creació de databases i usuaris). En un entorn multi-node amb xarxes overlay aquest procés és sensiblement més lent que amb Docker Compose.

**Solució aplicada**: incrementar el nombre de reintents de la funció `init_db()` als microserveis Python de 10 a 30, i augmentar l'interval de 3 a 5 segons (oferint així una finestra de fins a 150 segons per esperar que MySQL estigui plenament operatiu).

Després s'han reconstruït les imatges com a `:1.1` i s'han pujat de nou a Docker Hub. Finalment s'ha forçat l'actualització dels serveis al clúster:

```bash
docker service update --force --image arodriguez5/shopmicro-product-service:1.1 shopmicro_product-service
```

Aquesta solució il·lustra una de les **diferències clau entre Compose i Swarm**: en un entorn de producció orquestrat, els temps d'inicialització i les dependències entre serveis requereixen un disseny més robust del codi de l'aplicació.

---

## 6. Tolerància a fallades

### Aturada manual del worker2

Per simular una fallada de hardware, atura el servei Docker al `worker2`:

```bash
# Al worker2:
sudo systemctl stop docker
```

> 📸 **CAPTURA 2.14** — Sortida del `systemctl stop docker` al worker2.

### Verificació al manager

Després d'esperar uns 30 segons, des del manager:

```bash
docker node ls
```

> 📸 **CAPTURA 2.15** — Sortida de `docker node ls` mostrant `worker2` amb `STATUS: Down`.

### Redistribució automàtica de rèpliques

```bash
docker stack ps shopmicro
```

> 📸 **CAPTURA 2.16** — Sortida de `docker stack ps shopmicro` mostrant com Swarm ha llançat noves rèpliques al manager i worker1 per substituir les que estaven a worker2 (apareixen com `Shutdown` les antigues i `Running` les noves).

### Verificació que el servei segueix funcionant

```bash
curl http://192.168.0.1:8080/api/products
```

La web continua responent normalment a `http://192.168.56.2:8080`.

> 📸 **CAPTURA 2.17** — Captura de la web carregant correctament tot i tenir worker2 caigut.

### Reincorporació del worker2

```bash
# Al worker2:
sudo systemctl start docker
```

Després d'un minut:

```bash
# Al manager:
docker node ls
```

> 📸 **CAPTURA 2.18** — Sortida de `systemctl start docker` al worker2 i, després, sortida de `docker node ls` al manager mostrant worker2 de nou en estat `Ready`.

---

## 7. Escalat en calent

Una de les funcionalitats més potents de Swarm és la possibilitat d'**escalar serveis sense aturar-los**. Per exemple, augmentar les rèpliques de `product-service` de 2 a 4:

```bash
docker service scale shopmicro_product-service=4
```

> 📸 **CAPTURA 2.19** — Sortida de la comanda `docker service scale` mostrant `4/4 running`.

### Verificació de la distribució

```bash
docker stack services shopmicro
docker stack ps shopmicro --filter desired-state=running | grep product
```

> 📸 **CAPTURA 2.20** — Sortida de `docker stack services shopmicro` amb `product-service: 4/4` i la distribució de les 4 rèpliques entre els 3 nodes (manager, worker1, worker2).

L'escalat ha estat **transparent per als usuaris**: la web ha seguit funcionant durant tota l'operació.

---

## 8. Conclusions

### Què s'ha aconseguit

- Clúster Swarm format per 3 nodes operatiu.
- 6 imatges pròpies pujades a Docker Hub i utilitzades pels nodes del clúster.
- Tots els serveis desplegats amb rèpliques i polítiques de reinici.
- Demostració pràctica del **routing mesh** (port 8080 accessible des de qualsevol node).
- Demostració de la **tolerància a fallades** parant un worker.
- Demostració d'**escalat en calent** sense interrupció del servei.

### Què s'ha après

- **Diferència entre orquestració local (Compose) i orquestració de clúster (Swarm)**: Compose és per a desenvolupament, Swarm afegeix concurrència multi-node, alta disponibilitat i routing mesh.
- **Per què cal un registry**: en Swarm multi-node, les imatges s'han de poder descarregar des de qualsevol node.
- **Race conditions entre serveis**: en entorns distribuïts, no es pot assumir que les BDs estiguin llestes immediatament; cal codi de retry robust als microserveis.
- **Constraints de placement**: serveis amb estat (BD, cua) s'han de fixar a un node concret per consistència de volums.
- **Rolling updates**: amb `parallelism: 1` i `order: start-first` es poden actualitzar els serveis sense downtime.

### Limitacions detectades

- Les **credencials encara estan en clar** al `docker-stack.yml`. Aquest és el problema que es resol a la Fase 3.
- Totes les xarxes overlay són "obertes" entre serveis. La segmentació de seguretat es fa també a la Fase 3.
- Sense escaneig de vulnerabilitats: les imatges utilitzades poden tenir CVEs conegudes.

Aquestes limitacions es tracten a la fase següent.

---

*⬅️ Tornar a la [Fase 1](./FASE1.md) | Anar a la [Fase 3 — Seguretat](./FASE3.md) ➡️*