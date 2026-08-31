# baseline — per JD

Every case, failures included.

| JD | outcome | fabricated | softened | supported | tokens | s | note |
| -- | ------- | ---------- | -------- | --------- | ------ | - | ---- |
| jd_01 | less_matched | 4 | 0 | 21 | 6746 | 43.23 |  |
| jd_02 | skip | 2 | 0 | 18 | 7287 | 31.73 |  |
| jd_03 | less_matched | 2 | 0 | 22 | 7287 | 43.66 |  |
| jd_04 | less_matched | 0 | 0 | 22 | 7398 | 36.51 |  |
| jd_05 | less_matched | 1 | 0 | 24 | 7157 | 39.07 |  |
| jd_06 | less_matched | 1 | 0 | 19 | 7479 | 39.3 |  |
| jd_07 | skip | 1 | 0 | 18 | 7795 | 35.64 |  |
| jd_08 | less_matched | 1 | 0 | 20 | 6308 | 34.3 |  |
| jd_09 | most_matched | 3 | 0 | 20 | 8173 | 37.49 |  |
| jd_10 | most_matched | 1 | 0 | 21 | 6818 | 38.38 |  |
| jd_11 | less_matched | 3 | 0 | 19 | 6962 | 45.31 |  |
| jd_12 | most_matched | 1 | 0 | 21 | 6675 | 41 |  |
| jd_13 | less_matched | 2 | 0 | 19 | 6891 | 35.47 |  |
| jd_14 | less_matched | 1 | 0 | 21 | 7081 | 42.48 |  |
| jd_15 | less_matched | 1 | 0 | 21 | 7047 | 37.04 |  |

## Rejected claims

- **jd_01** u01: Backend engineer with 2+ years building public-facing web services at scale — 99.99%-availability REST APIs, sub-100ms database queries, 500K-event/day pipelines. Python (FastAPI, Django, Flask) and Java/Spring Boot, PostgreSQL and ORM-backed data models, Docker/Linux from development through production deployment. Comfortable owning problems end to end on a distributed team, with strong habits around automated testing, CI gates, and code review. M.S. in Computer Science.
  - tool 'Flask' [unsupported] -- no tool_evidence entry
- **jd_01** u06: Containerized backend services with Docker and deployed on Ubuntu EC2 hosts behind Nginx load balancing for production traffic.
  - tool 'Ubuntu' [unsupported] -- no tool_evidence entry
- **jd_01** u10: Modeled relational data in MySQL/PostgreSQL-compatible RDS with read replicas and ORM mappings (Hibernate/MyBatis), sustaining sub-100ms queries at peak; used DynamoDB with GSIs for high-volume metadata.
  - tool 'PostgreSQL' [misplaced] -- evidence points at proj_1, not exp_2
  - tool 'Hibernate' [unplaced] -- evidence is a skills-line mention with no role or project behind it; a gap answer must supply one before it can sit in a bullet
  - tool 'MyBatis' [unplaced] -- evidence is a skills-line mention with no role or project behind it; a gap answer must supply one before it can sit in a bullet
- **jd_01** u24: **Languages:** Python, Java, TypeScript, JavaScript, Golang, SQL, C/C++ **Web & APIs:** FastAPI, Django, Flask, Spring Boot, Node.js, Express.js, REST, GraphQL, React **Databases & ORMs:** PostgreSQL, MySQL, Hibernate, MyBatis, SQLAlchemy, Redis, MongoDB, DynamoDB **Platform & Tooling:** Ubuntu/Linux, Docker, Kubernetes, Nginx, GitHub Actions, Jenkins, CI/CD, Git, Kafka **Cloud:** AWS (EC2, Lambda, API Gateway, SQS, RDS), GCP (Cloud Run, Cloud SQL)
  - tool 'Flask' [unsupported] -- no tool_evidence entry
  - tool 'SQLAlchemy' [unsupported] -- no tool_evidence entry
- **jd_02** u01: Full-stack software engineer with 2+ years of industry experience shipping and operating live, player-facing services at Amazon (Alexa), plus solo end-to-end product development across frontend (React/TypeScript), backend, and tooling. Strong foundation in data structures, algorithms, and performance profiling; fast learner across languages (Java, C/C++, C#-adjacent, Python, TypeScript) and eager to move into game development with Unity and C#.
  - tool 'C#' [unsupported] -- no tool_evidence entry
  - tool 'Unity' [unsupported] -- no tool_evidence entry
- **jd_02** u19: **Languages:** C/C++, Java, C# (learning), Python, TypeScript, JavaScript, Golang, SQL **Client & UI:** React, Redux, Angular, TypeScript, responsive UI/UX, Chrome extensions **Backend:** Spring Boot, FastAPI, Node.js, Express.js, Django, REST, GraphQL **Tools & Practice:** Git, Docker, Kubernetes, GitHub Actions, Jenkins, Linux, CI/CD, performance profiling, unit/integration testing **Data & Cloud:** MySQL, PostgreSQL, DynamoDB, MongoDB, Redis, Kafka, AWS, GCP
  - tool 'C#' [unsupported] -- no tool_evidence entry
  - tool 'GCP' [unsupported] -- no tool_evidence entry
- **jd_03** u01: Full-stack engineer who ships end-to-end: React/TypeScript front ends, Python (FastAPI) and Java (Spring Boot) back ends, and PostgreSQL/DynamoDB data layers. Took a 0→1 product from idea to production solo in two months using an AI-assisted workflow (Cursor, Claude Code) with CI gates on every change, and operated 99.99%-availability APIs serving 10K+ daily users at Amazon. Comfortable owning ideation, technical design, launch, and the on-call life that follows.
  - metric '0→1 product to production solo in two months': 0, 1 is not in the profile
- **jd_03** u23: **Frontend:** React, TypeScript, JavaScript, Redux, Angular, Chrome extensions, responsive UI **Backend:** Python (FastAPI, Django), Java (Spring Boot), Go, Node.js/Express, C/C++, REST, GraphQL **Data:** PostgreSQL, MySQL, DynamoDB, MongoDB, Redis, Kafka, SQL **Cloud & Infra:** AWS (Lambda, API Gateway, EC2, SQS, DynamoDB, EKS, Cognito, CloudWatch/CDK), GCP (Cloud Run, Cloud SQL), Cloudflare Pages, Docker, Kubernetes, GitHub Actions, CI/CD, Linux **AI-Assisted Development & AI Systems:** Cursor, Claude Code, GitHub Copilot; LangChain, LangGraph, RAG, Qdrant, Google ADK, Gemini/LLM integration, OpenTelemetry
  - tool 'GCP' [unsupported] -- no tool_evidence entry
  - tool 'GitHub Copilot' [unsupported] -- no tool_evidence entry
- **jd_05** u24: **Languages:** Java, Python, TypeScript, JavaScript, SQL, Golang, C/C++ (Ruby: actively learning) **Backend & Frontend:** Spring Boot, FastAPI, Node.js, Express.js, Django, React, Redux, Angular, Hibernate **Data & Messaging:** PostgreSQL, MySQL, DynamoDB, MongoDB, Redis, SQS, Kafka **Testing & Delivery:** Automated test suites, CI gates, GitHub Actions, Jenkins, blue-green deployment, Docker, Kubernetes **Cloud:** AWS (Lambda, DynamoDB, SQS, EC2, API Gateway, EKS, Cognito, CloudWatch/CDK), GCP (Cloud Run, Cloud SQL) **AI & Agents:** LangChain, LangGraph, RAG, Qdrant, Google ADK, LLM integration
  - tool 'Ruby' [unsupported] -- no tool_evidence entry
- **jd_06** u19: **Languages:** C/C++, Python, Java, Golang, TypeScript, JavaScript, SQL **Systems & Networking:** Linux, REST/GraphQL APIs, TCP/UDP service design, message queues (SQS, Kafka), distributed caching (Redis Cluster), idempotency & retry/backoff, circuit breakers **Reliability & Tooling:** Unit/integration testing, CI/CD (GitHub Actions, Jenkins), Docker, Kubernetes, infrastructure-as-code (CDK), CloudWatch observability, OpenTelemetry, debugging & performance profiling **Backend & Frontend:** Spring Boot, FastAPI, Django, Node.js, React, Redux **Cloud & Data:** AWS (Lambda, DynamoDB, SQS, EC2, API Gateway, EKS), GCP (Cloud Run), PostgreSQL, MySQL, MongoDB
  - tool 'TCP/UDP' [unsupported] -- no tool_evidence entry
- **jd_07** u18: **Languages:** Java, TypeScript, JavaScript, Python, C/C++, Golang, SQL (Swift: currently learning) **Client & UI:** React, Redux, Angular, Chrome Extensions, responsive UI, REST/GraphQL client integration **Systems & OOP:** object-oriented design, concurrency, caching, networking, storage, unit/integration testing **Backend:** Spring Boot, FastAPI, Node.js, Express.js, Django, Hibernate, MyBatis **Cloud & Data:** AWS (Lambda, DynamoDB, SQS, EC2, API Gateway, Cognito), GCP (Cloud Run), MySQL, PostgreSQL, MongoDB, Redis, Kafka **Tools:** Docker, Kubernetes, GitHub Actions, CI/CD, Git, Linux, Jenkins
  - tool 'Swift' [unsupported] -- no tool_evidence entry
  - tool 'GCP' [unsupported] -- no tool_evidence entry
- **jd_08** u20: **Languages:** Java, Python, SQL, TypeScript, JavaScript, C/C++, Golang **Backend & Data:** Spring Boot, FastAPI, Django, Node.js, PostgreSQL, MySQL, DynamoDB, MongoDB, Redis, Kafka, SQS, REST/GraphQL APIs, ETL & data pipelines **Frontend & Visualization:** React, Redux, TypeScript, Angular **Infrastructure:** Docker, Kubernetes (EKS), AWS (Lambda, API Gateway, EC2, RDS, CloudWatch, CDK), GCP (Cloud Run, Cloud SQL), GitHub Actions, Jenkins, Linux **Analytics & AI:** LangChain/LangGraph, RAG, vector search (Qdrant), LLM integration, OpenTelemetry
  - tool 'ETL & data pipelines' [unsupported] -- no tool_evidence entry
  - tool 'LLM integration' [unsupported] -- no tool_evidence entry
- **jd_09** u10: Developed event-driven Lambda functions behind API Gateway with rate limiting and circuit breakers, maintaining 99.99% availability; ran SQS ingestion with DLQs and exponential backoff at 500K events/day and 99.9% delivery reliability.
  - tool 'DLQs' [unsupported] -- no tool_evidence entry
- **jd_09** u14: Collaborated daily across product, data, and partner teams in a healthcare-adjacent consumer domain with strict reliability and privacy requirements (JWT auth, AWS Cognito federation, RBAC).
  - tool 'RBAC' [unsupported] -- no tool_evidence entry
- **jd_09** u17: Deployed to Google Cloud Agent Engine with OpenTelemetry tracing and evaluated agent output against benchmark thresholds inside the ADK eval framework — including where a human reviewer had to stay in the loop.
  - tool 'ADK eval framework' [unsupported] -- no tool_evidence entry
- **jd_10** u21: **Languages:** Java, Python, Golang, TypeScript, JavaScript, C/C++, SQL **Backend:** Spring Boot, FastAPI, Django, Node.js/Express, REST, GraphQL, gRPC-style service design, MyBatis, Hibernate **Identity & Security:** JWT, OAuth/OIDC via AWS Cognito, role-based access control, API rate limiting, idempotency **Cloud & Data:** AWS (Lambda, API Gateway, DynamoDB, SQS, RDS/MySQL, EC2, EKS, Cognito, CloudWatch, CDK), GCP (Cloud Run, Cloud SQL), PostgreSQL, MongoDB, Redis, Kafka **Infra & Tooling:** Docker, Kubernetes, GitHub Actions, Jenkins, CI/CD, Linux, Git **AI:** LangChain, LangGraph, RAG, Qdrant, Google ADK, LLM integration
  - tool 'gRPC-style service design' [unsupported] -- no tool_evidence entry
  - tool 'OAuth/OIDC' [unsupported] -- no tool_evidence entry
  - tool 'GCP' [unsupported] -- no tool_evidence entry
  - tool 'LLM integration' [unsupported] -- no tool_evidence entry
- **jd_11** u01: Backend and applied AI engineer who ships end-to-end: production LLM systems (RAG pipelines, multi-agent architectures, benchmark-driven evaluation) on top of 2 years of high-scale distributed systems work at Amazon Alexa — 99.99%-availability APIs and 500K-event/day data pipelines. Comfortable with ambiguous, customer-facing problems: built and shipped a production product solo in two months, and prototyped a multi-agent evaluation system in six weeks. Python/Java/Go, AWS + GCP. M.S. in Computer Science (May 2026).
  - tool 'GCP' [unsupported] -- no tool_evidence entry
- **jd_11** u15: **Evaluated agent performance against benchmark thresholds** inside the ADK evaluation framework, with OpenTelemetry tracing for per-agent latency and failure analysis.
  - tool 'ADK evaluation framework' [unsupported] -- no tool_evidence entry
- **jd_11** u21: **Languages:** Python, Java, Golang, TypeScript, C/C++, SQL **AI & LLM:** RAG, embeddings & vector search (Qdrant), LangChain, LangGraph, Google ADK, multi-agent orchestration, Gemini/OpenAI API integration, prompt and retrieval evaluation, OpenTelemetry tracing **Data & Pipelines:** SQS, Kafka, event-driven pipelines, PostgreSQL, MySQL, DynamoDB, MongoDB, Redis **Backend:** FastAPI, Spring Boot, Django, Node.js, REST, GraphQL; React/TypeScript on the frontend **Cloud & Infra:** AWS (Lambda, API Gateway, DynamoDB, SQS, EC2, EKS, Cognito, CloudWatch/CDK), GCP (Cloud Run, Cloud SQL, Agent Engine), Docker, Kubernetes, GitHub Actions, Linux
  - tool 'GCP' [unsupported] -- no tool_evidence entry
- **jd_12** u21: **Core for this role:** SQL (PostgreSQL, MySQL, DynamoDB), REST APIs & third-party API integration, TypeScript/JavaScript, Node.js, AWS (Lambda, API Gateway, SQS, EC2, DynamoDB, RDS, Cognito, CloudWatch), Bash/Linux shell scripting **Languages:** TypeScript, JavaScript, Java, Python, Golang, SQL, C/C++ **Backend & Frontend:** Node.js, Express.js, Spring Boot, FastAPI, Django, React, Redux **AI & Automation:** LangChain, LangGraph, RAG, Qdrant, Google ADK, Gemini/LLM integration, Cursor / Claude Code workflows **Data & Infra:** MySQL, PostgreSQL, MongoDB, Redis, Kafka, Docker, Kubernetes, GitHub Actions, Jenkins, Git
  - tool 'Bash/Linux shell scripting' [unsupported] -- no tool_evidence entry
- **jd_13** u02: NextRound | Creator & Sole Full-Stack Engineer — React, TypeScript, Vite-style SPA, Chrome Extension, FastAPI, PostgreSQL | Feb 2026 – Present
  - tool 'Vite' [unsupported] -- no tool_evidence entry
- **jd_13** u20: **Frontend:** TypeScript, JavaScript, React, Redux, Angular, HTML/CSS, Chrome Extensions, responsive UI, component design systems **Languages:** TypeScript, JavaScript, Java, Python, Go, C/C++, SQL **Backend:** FastAPI, Node.js, Express.js, Spring Boot, Django, GraphQL, REST **Cloud & Data:** AWS (Lambda, API Gateway, DynamoDB, SQS, EC2), GCP (Cloud Run, Cloud SQL), Cloudflare Pages, PostgreSQL, MySQL, Redis, Kafka **AI & Agents:** LangChain, LangGraph, RAG, Qdrant, Google ADK, Gemini/LLM integration; AI-assisted development (Cursor, Claude Code) **Tools:** Docker, Kubernetes, GitHub Actions, CI/CD, Git, Linux
  - tool 'HTML/CSS' [unsupported] -- no tool_evidence entry
- **jd_14** u21: **Frontend:** TypeScript, JavaScript, React, Redux, Angular, HTML/CSS, responsive UI **Backend:** Python (FastAPI, Django), Node.js/Express, Golang, Java (Spring Boot), REST, GraphQL **Databases:** PostgreSQL, MySQL, DynamoDB, MongoDB, Redis **Cloud & Infra:** AWS (EC2, Lambda, API Gateway, SQS, RDS, DynamoDB, Cognito, CloudWatch, EKS, CDK), GCP (Cloud Run, Cloud SQL) **DevOps & Security:** Docker, Kubernetes, GitHub Actions, Jenkins, CI/CD, blue-green deploys, JWT/OAuth, RBAC, Git, Linux **Data & Messaging:** Kafka, SQS, event-driven pipelines, telemetry/observability (CloudWatch, OpenTelemetry)
  - tool 'HTML/CSS' [unsupported] -- no tool_evidence entry
  - tool 'GCP' [unsupported] -- no tool_evidence entry
  - tool 'RBAC' [unsupported] -- no tool_evidence entry
- **jd_15** u02: **Languages:** Python, Java, Golang, SQL, C/C++, TypeScript, JavaScript **Data & Storage:** S3/EC2 object storage, DynamoDB (GSI design), PostgreSQL, MySQL (RDS, read replicas), MongoDB, Redis Cluster, Qdrant vector storage, Kafka, SQS pipelines with DLQs and backoff **Infrastructure:** Kubernetes (AWS EKS), Docker, GitHub Actions, Jenkins, CI/CD, blue-green deploys, AWS CDK / infrastructure-as-code, CloudWatch, OpenTelemetry, Nginx, Linux **AI & Agents:** RAG pipeline design, embedding generation and caching, LangChain, LangGraph, Google ADK, Gemini/LLM integration **Backend:** FastAPI, Spring Boot, Django, Node.js, GraphQL (DataLoader batching), REST, React
  - tool 'S3' [unsupported] -- no tool_evidence entry
