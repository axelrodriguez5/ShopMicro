# ShopMicro — Plataforma e-Commerce de Microserveis

> **Projecte de 2 ASIR** — Containerització, orquestració i seguretat amb Docker

## Sobre el projecte

ShopMicro és una plataforma fictícia de comerç electrònic que ven productes tecnològics. Aquest projecte simula la migració d'una aplicació monolítica a una arquitectura de **microserveis containeritzats**, passant per quatre fases progressives de complexitat: desenvolupament local, alta disponibilitat, seguretat i producció amb Kubernetes.

## Autor

- **Nom**: Axel Rodríguez
- **Curs**: 2 ASIR
- **Centre**: [Nom del centre]
- **Data**: Maig 2026

## Arquitectura general

La plataforma es compon de **9 serveis** containeritzats:

| Servei | Tecnologia | Funció |
|---|---|---|
| `frontend` | Nginx + HTML/JS | Interfície web |
| `api-gateway` | Nginx (reverse proxy) | Punt d'entrada únic |
| `product-service` | Python Flask | CRUD de productes |
| `order-service` | Python Flask | Gestió de comandes |
| `user-service` | Python Flask | Autenticació amb JWT |
| `notification-service` | Python Flask | Consumidor de RabbitMQ |
| `db-products` | MySQL 8.0 | BD de productes |
| `db-orders` | MySQL 8.0 | BD de comandes/usuaris |
| `cache` | Redis 7 | Cache (TTL 60s) |
| `message-queue` | RabbitMQ 3 | Cua de missatges |

## Estructura de la documentació

Aquest repositori conté la documentació completa del projecte dividida en quatre fases:

### [Fase 1 — Docker Compose (Desenvolupament)](./fase1.md)

Containerització de tots els serveis i orquestració amb Docker Compose en un entorn de desenvolupament local. S'inclou la configuració de xarxes internes, volums persistents, healthchecks i el desenvolupament del frontend amb tres fluxos funcionals demostrables.

### [Fase 2 — Docker Swarm (Alta disponibilitat)](./fase2.md)

Migració de Docker Compose a un clúster Docker Swarm format per 3 nodes (1 manager + 2 workers). S'aplica l'arquitectura de rèpliques, restart policies i rolling updates. S'inclouen proves de tolerància a fallades i escalat en calent.

### [Fase 3 — Seguretat](./fase3.md)

Aplicació de mesures de seguretat al clúster Swarm: migració de credencials a Docker Secrets, aïllament de xarxes overlay seguint el principi de mínim privilegi, anàlisi del TLS automàtic entre nodes amb CA interna, i escaneig de vulnerabilitats amb Docker Scout.

### [Fase 4 — Kubernetes (Producció)](./fase4.md)

Migració de l'arquitectura a Kubernetes per a l'entorn de producció. *(Pendent d'execució)*

## Fluxos funcionals demostrats

Tots els fluxos s'han verificat a les Fases 1, 2 i 3:

1. **Flux de consulta de productes** — frontend → api-gateway → product-service → Redis (cache) o db-products → resposta.
2. **Flux de creació de comanda** — frontend → order-service → descompta stock + crea comanda + publica missatge a RabbitMQ → notification-service registra al log.
3. **Flux de tolerància a fallades (Swarm)** — aturada manual de worker-2 i comprovació de redistribució de rèpliques.

## Tecnologies utilitzades

- **Containerització**: Docker Engine 24+, Docker Compose v2, Docker Swarm
- **Microserveis**: Python 3.11, Flask, mysql-connector-python, pika (RabbitMQ), redis-py, PyJWT
- **Infraestructura**: Ubuntu Server 24, VirtualBox (3 VMs)
- **Registry**: Docker Hub (usuari `arodriguez5`)
- **Seguretat**: Docker Secrets, mTLS automàtic de Swarm, Docker Scout
- **Eines de desenvolupament**: VS Code amb Remote-SSH, Git

## Conclusions globals

El projecte ha permès:

- Comprendre les diferències entre containerització (Docker), orquestració local (Compose) i orquestració de clúster (Swarm/Kubernetes).
- Aplicar el **principi de mínim privilegi** a les xarxes i secrets.
- Aprendre a gestionar **race conditions** entre serveis dependents (BD vs microserveis).
- Comprendre els avantatges del **TLS mutu automàtic** de Swarm per a la comunicació entre nodes.
- Identificar i mitigar **vulnerabilitats reals** (CVE) a les imatges utilitzades.
- Adaptar-se a canvis d'API en imatges oficials (cas de la deprecació de `RABBITMQ_DEFAULT_USER_FILE` en versions recents de RabbitMQ).

---

*Aquesta documentació segueix la lògica progressiva de les fases del projecte. Es recomana llegir-la en ordre per entendre l'evolució de l'arquitectura.*