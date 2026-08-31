# _synthetic — per JD

Every case, failures included.

| JD | outcome | fabricated | softened | supported | tokens | s | note |
| -- | ------- | ---------- | -------- | --------- | ------ | - | ---- |
| jd_01 | most_matched | - | - | - | 6100 | 11.4 | no resume produced |
| jd_02 | less_matched | - | - | - | 6100 | 11.4 | no resume produced |
| jd_03 | most_matched | 0 | 0 | 12 | 6100 | 11.4 |  |
| jd_04 | less_matched | - | - | - | 6100 | 11.4 | no resume produced |
| jd_05 | most_matched | 5 | 2 | 2 | 6100 | 11.4 |  |
| jd_06 | less_matched | - | - | - | 6100 | 11.4 | no resume produced |
| jd_07 | skip | - | - | - | 6100 | 11.4 | no resume produced |
| jd_08 | less_matched | - | - | - | 6100 | 11.4 | no resume produced |
| jd_09 | error | - | - | - | 6100 | 11.4 | fetch failed: simulated packet failure |
| jd_10 | most_matched | - | - | - | 6100 | 11.4 | no resume produced |
| jd_11 | less_matched | - | - | - | 6100 | 11.4 | no resume produced |
| jd_12 | most_matched | - | - | - | 6100 | 11.4 | no resume produced |
| jd_13 | most_matched | - | - | - | 6100 | 11.4 | no resume produced |
| jd_14 | dropped (H-1B) | - | - | - | 6100 | 11.4 | no resume produced |
| jd_15 | less_matched | - | - | - | 6100 | 11.4 | no resume produced |

## Rejected claims

- **jd_05** u03: Configured Kafka ingestion pipelines with dead-letter queues, processing 500K daily events at 99.9% delivery reliability.
  - tool 'Kafka' [unplaced] -- evidence is a skills-line mention with no role or project behind it; a gap answer must supply one before it can sit in a bullet
- **jd_05** u04: Developed event-driven Lambda functions behind API Gateway, maintaining 99.999% availability across Alexa Kitchen APIs.
  - metric '99.999% availability': 99.999 is not in the profile
- **jd_05** u05: Built a Qdrant vector store for recipe embeddings, improving recommendation relevance by 30%.
  - tool 'Qdrant' [misplaced] -- evidence points at exp_1, not exp_2
- **jd_05** u06: Stripe — Senior Software Engineer
  - company 'Stripe' matches no profile entry
  - title 'Senior Software Engineer' matches no profile entry
- **jd_05** u09: Trained and served retrieval models on a Kubeflow pipeline running on AWS EC2, cutting inference latency by 45%.
  - tool 'Kubeflow' [unsupported] -- no tool_evidence entry
