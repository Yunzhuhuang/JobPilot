# Clara Huang

clarahuang11111@gmail.com | linkedin.com/in/yunzhu-huang | Software & AI Engineer | Seattle, WA (open to relocation)

## Summary

Software & AI engineer with 2 years building high-availability distributed systems at Amazon (Alexa) — 99.99% uptime APIs, 500K-event/day pipelines — plus hands-on AI engineering across production RAG pipelines, multi-agent systems (Google ADK, LangChain/LangGraph), and an AI-assisted solo product shipped to production; AI-startup internship and M.S. in Computer Science.

## Work Experience

### AIPetique LLC | Software Development Engineer Intern | May 2025 – Aug 2025

- Built and deployed an AI customer-service chatbot for a Shopify Hydrogen pet e-commerce platform using FastAPI, LangChain, and React, covering pet care Q&A, order tracking, store policy, and account management.
- Designed a RAG pipeline with GTE-Qwen2-7B-instruct embeddings, Qdrant vector storage, and hybrid semantic + keyword retrieval, improving answer relevance by 30% across a 10K-prompt evaluation set.
- Cached embeddings in Redis and optimized asynchronous request handling, reducing end-to-end query latency by 45% under concurrent load.
- Containerized backend services with Docker and deployed on AWS EC2 behind Nginx load balancing for production traffic.

### Amazon.com Services LLC | Software Development Engineer – Alexa Kitchen | Jul 2022 – Apr 2024

- Designed and launched a Spring Boot backend end to end, consolidating Alexa-owned, third-party, and user-generated recipes, serving 10K+ daily active users within one week of launch.
- Modeled recipe metadata in DynamoDB with GSI-based query acceleration and relational preference mappings in MySQL (RDS) with read replicas, sustaining sub-100ms queries at peak load.
- Implemented RESTful APIs with idempotent endpoint design and pagination, cutting response payloads and connection overhead and improving p99 latency by 30%.
- Configured SQS ingestion pipelines with dead-letter queues and exponential backoff, processing 500K daily events at 99.9% delivery reliability.
- Developed event-driven Lambda functions behind API Gateway with rate limiting and circuit-breaker middleware, maintaining 99.99% availability across Alexa Kitchen APIs.
- Integrated Meepo, a centralized preference repository, to deliver personalized recipe recommendations; built GraphQL APIs with DataLoader batching, achieving sub-50ms preference-sync latency.
- Implemented JWT authentication and AWS Cognito-based identity federation with role-based access control to secure preference APIs and synchronize user sessions across services.
- Deployed distributed caching with Redis Cluster for preference graphs and recipe embeddings, using Bloom-filter pre-checks to block queries for nonexistent keys and prevent cache penetration, cutting backend read load by 45%.
- Automated CI/CD pipelines with Docker, AWS EKS, and GitHub Actions for blue-green deployments, ensuring zero-downtime rollouts and environment parity across staging and production.
- Migrated manual operational alarms to infrastructure-as-code with CloudWatch and CDK, reducing false-positive alerts by 40%.

## Projects

### NextRound | Creator & Sole Full-Stack Engineer – React, TypeScript, FastAPI, PostgreSQL | Feb 2026 – Present

- Building an end-to-end interview-prep platform with a companion Chrome extension that captures LeetCode submissions in real time and generates personalized spaced-repetition review schedules.
- Developed a responsive React/TypeScript frontend and a containerized FastAPI backend with PostgreSQL managing attempt histories and review plans; automated CI/CD with GitHub Actions deploying to Google Cloud Run, Cloud SQL, and Cloudflare Pages.
- Shipped from zero to production in two months as a solo engineer using an AI-assisted development workflow (Cursor and Claude Code), with automated test suites and CI gates enforcing quality on every AI-generated change.

### AI Talent Match Agent | Google Cloud ADK Hackathon – Python, Gemini, FastAPI | May 2025 – Jun 2025

- Built an automated resume-screening system with Google Agent Development Kit and Gemini 1.5 Flash for semantic scoring and entity extraction from PDF resumes.
- Engineered a multi-agent architecture with a coordinator agent orchestrating specialized sub-agents over A2A protocols and shared tool-context state.
- Deployed to Google Cloud Agent Engine with OpenTelemetry observability, and evaluated agent performance against benchmark thresholds within the ADK framework.

## Technical Skills

**Languages:** Java, Python, C/C++, TypeScript, JavaScript, Golang, SQL
**Backend & Frontend:** Spring Boot, FastAPI, Django, Node.js, React, Redux, Angular, MyBatis, Hibernate, Express.js
**AI & Agents:** LangChain, LangGraph, RAG, Qdrant, Google ADK, Gemini/LLM integration
**Cloud & Data:** AWS (Lambda, DynamoDB, SQS, EC2, API Gateway), GCP (Cloud Run), MySQL, PostgreSQL, MongoDB, Redis, Kafka
**Tools:** Docker, Kubernetes, GitHub Actions, CI/CD, Git, Linux, Jenkins

## Education

**Northeastern University** — M.S. in Computer Science | Sept 2024 – May 2026
**University of Minnesota–Twin Cities** — B.A. in Computer Science | Aug 2019 – May 2022
