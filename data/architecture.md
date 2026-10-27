# Document Assistant — Architecture

The frontend is built using Next.js, and the backend is built using FastAPI.

The backend extracts text from PDF files, chunks the text, and creates embeddings using a local Sentence Transformers model.

Qdrant stores and retrieves document vectors. The backend combines retrieved text with task instructions and calls a Groq-hosted language model to generate an answer.

The initial implementation runs locally. Cloud deployment and user authentication are not included in this prototype.

The backend uses Redis to cache frequently requested document responses.