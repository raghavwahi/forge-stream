# ForgeStream

Full-stack application built with **Next.js** (frontend) and **FastAPI** (backend), containerised with Docker and deployable to Kubernetes.

---

## Quick Start

### Prerequisites

| Tool | Version |
|------|---------|
| [Docker](https://docs.docker.com/get-docker/) | 20.10+ |
| [Docker Compose](https://docs.docker.com/compose/install/) | v2+ |

### 1. Clone the repository

```bash
git clone https://github.com/raghavwahi/forge-stream.git
cd forge-stream
```

### 2. Start all services

```bash
docker compose -f infra/docker/docker-compose.yml up --build
```

This builds and starts:

| Service | URL | Description |
|---------|-----|-------------|
| **web** | <http://localhost:3000> | Next.js frontend |
| **api** | <http://localhost:8000> | FastAPI backend |
| **API docs (Swagger UI)** | <http://localhost:8000/docs> | Swagger UI |
| **API docs (ReDoc)** | <http://localhost:8000/redoc> | ReDoc |

### 3. Verify the stack is running

```bash
curl http://localhost:8000/health
# → {"status":"ok"}
```

### 4. Stop all services

```bash
docker compose -f infra/docker/docker-compose.yml down
```

---

## Local Development (without Docker)

```bash
# Install root workspace dependencies
npm install

# Start the API (Python ≥ 3.11 required)
cd api && pip install -e ".[dev]" && cd ..
npm run api:dev          # → http://localhost:8000

# Start the frontend
npm run web:dev          # → http://localhost:3000
```

---

## Project Structure

```
forge-stream/
├── api/                 # FastAPI backend
│   ├── app/
│   │   └── main.py      # Application entry point
│   └── pyproject.toml    # Python dependencies
├── web/                 # Next.js frontend
│   ├── src/app/          # App Router pages
│   └── package.json
├── infra/
│   ├── docker/           # Docker Compose & Dockerfiles
│   └── k8s/              # Kubernetes manifests
├── docs/                 # Technical documentation
└── .workflows/           # AI-assisted review workflows
```

---

## Documentation

- **[Technical Specification](docs/technical_spec.md)** — DB ERD, API endpoints, and LLM provider class hierarchy.

---

## License

This project is licensed under the [MIT License](LICENSE).
