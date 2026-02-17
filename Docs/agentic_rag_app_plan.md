# Agentic RAG Web Application Design Plan

## Overview

This document outlines the design and user journey for an agentic RAG (Retrieval Augmented Generation) web application. The application will leverage FastAPI for the backend, Streamlit for the frontend, Supabase for relational data and vector embeddings, and Neo4j for graph data. Gemini will be used for both embeddings and chat functionalities.

## Core Features & Technologies

*   **Application Type:** Web Application
*   **Frontend:** Streamlit
*   **Backend:** FastAPI
*   **Databases:**
    *   **Supabase (SQL):** For storing relational data and vector embeddings (both user-specific and shared).
    *   **Neo4j:** For storing and querying graph-structured data.
*   **LLM & Embeddings:** Gemini (user-provided API key)
*   **Orchestration:** LangGraph for agentic workflow management.
*   **Key Features:**
    *   User Authentication
    *   Data Management (CRUD)
    *   Real-time Interactions (WebSockets via FastAPI)
    *   Integrations (Neo4j, Supabase, Gemini API)
    *   User Interface (UI)
    *   Background Processing (for file ingestion)
    *   File Upload/Download (PDF, TXT, Microsoft Word)

## Critique and Supplementation of Initial Ideas

### 1. Agentic RAG App

*   **Supplement:** The "agentic" nature will be realized through a LangGraph-based orchestration of specialized agents:
    *   **Router Agent:** Directs queries to the appropriate data source (user-specific files, shared documents, Neo4j graphs).
    *   **Vector Retrieval Agent:** Handles embedding queries and searches Supabase for relevant document chunks (both private and shared).
    *   **Graph Query Agent:** Translates natural language into Cypher queries and executes them against Neo4j.
    *   **Summarization/Synthesis Agent:** Combines information from various sources and generates a coherent response.
    *   **Memory Agent:** Manages conversation history and context for multi-turn interactions.
*   **Critique:** The primary design challenge will be the robust orchestration and interaction logic between these agents.

### 2. Conversation Start (File Upload / Chat Box)

*   **Supplement:**
    *   **File Upload Feedback:** Implement clear visual feedback (progress bar, status messages) during file upload and processing.
    *   **Initial Prompts:** Offer example prompts in the chat box to guide users and showcase capabilities.
*   **Critique:** Covers essential user entry points.

### 3. User-Uploaded Files (Private)

*   **Supplement:**
    *   **Security & Authorization:** Implement robust user authentication (Supabase Auth) to ensure strict access control. Embeddings and raw files in Supabase Storage will be tied to `user_id` and `file_id`.
    *   **File Storage:** Raw files (PDF, TXT, Word) will be stored in Supabase Storage with user-specific access.
    *   **File Management:** A "My Files" section will allow users to view, manage, and delete their uploaded documents and associated embeddings.
*   **Critique:** This feature provides significant personalization.

### 4. Pre-Ingested Files (Shared)

*   **Supplement:**
    *   **Content Management:** An administrative interface or separate ingestion pipeline will be needed for managing shared content.
    *   **Categorization:** Consider categorizing shared documents for more targeted RAG.
*   **Critique:** Essential for a common knowledge base.

### 5. Neo4j Graphs

*   **Supplement:**
    *   **Graph Schema Awareness:** The Graph Query Agent will need to understand the Neo4j schema (node labels, relationship types, properties) to generate accurate Cypher queries. This can be achieved by providing schema context to Gemini or using schema introspection tools.
    *   **Hybrid Retrieval:** The Router Agent will determine when to use graph queries versus vector search based on query patterns.
*   **Critique:** A powerful differentiator for complex relational queries.

### 6. LangGraph

*   **Supplement:**
    *   **State Management:** LangGraph's state management will be crucial for maintaining conversation context and managing intermediate agent outputs.
    *   **Error Handling:** Design robust error handling within the LangGraph flow.
*   **Critique:** An excellent choice for complex, multi-step reasoning.

### 7. User API Key (Gemini)

*   **Supplement:**
    *   **Client-Side Storage:** API keys will be stored securely client-side (e.g., in browser local storage) and used directly for API calls, or passed with each request. The application backend will NOT store user API keys, addressing user privacy concerns.
    *   **Validation:** Implement client-side and server-side validation.
    *   **Usage Monitoring:** Consider providing basic usage statistics to users.
*   **Critique:** Smart for cost management and user control.

### 8. Gemini (Embedding & Chat)

*   **Supplement:**
    *   **Model Selection:** Specify appropriate Gemini models (e.g., `text-embedding-004`, `gemini-pro`).
    *   **Rate Limits:** Inform users about rate limits and how the app handles them.
*   **Critique:** Powerful and versatile for core LLM functionalities.

---

## User Journey Design: Agentic RAG Web App

### Phase 1: Onboarding & Setup (First-time User)

1.  **Landing Page:**
    *   **User Action:** Navigates to the app URL.
    *   **System:** Displays an overview of the app's capabilities: "Your Personal & Shared Knowledge Assistant," highlighting agentic RAG, private document analysis, shared knowledge base, and graph insights.
    *   **Call to Action:** "Get Started" or "Sign Up."
2.  **Sign Up / Login:**
    *   **User Action:** Clicks "Sign Up," provides email/password (or uses social login via Supabase Auth).
    *   **System:** Creates a new user account and authenticates.
3.  **Gemini API Key Configuration:**
    *   **User Action:** Presented with a clear prompt: "Connect Your Gemini API Key." Instructions are provided on how to obtain a key from Google AI Studio, with a direct link. User inputs their key.
    *   **System:** Validates the API key (e.g., by making a small test call to Gemini). The key is then securely stored client-side (e.g., in browser local storage) and used for direct calls to the Gemini API. The backend will not store the user's API key.
    *   **Feedback:** Success/failure message. If successful, redirects to the main chat interface.
4.  **Welcome & Quick Tour (Optional):**
    *   **System:** A brief, interactive overlay tour highlighting the chat box, file upload button, and a mention of shared knowledge/graph capabilities.

### Phase 2: Core Interaction - The Chat Interface

This is the central hub for all interactions.

**Scenario A: Querying Shared Knowledge Base or Neo4j Graphs**

1.  **Chat Input:**
    *   **User Action:** Types a question in the chat box (e.g., "What are the company's vacation policies?" or "Show me the relationships between the 'Project X' and its key stakeholders.").
    *   **System (LangGraph - Router Agent):**
        *   Analyzes the query's intent.
        *   *If related to shared documents:* Routes to the Vector Retrieval Agent (shared).
        *   *If related to relationships/entities:* Routes to the Graph Query Agent.
    *   **System (Vector Retrieval Agent - Shared):**
        *   Embeds the user query (Gemini).
        *   Searches shared document embeddings in Supabase.
        *   Retrieves relevant text chunks.
    *   **System (Graph Query Agent):**
        *   Translates the natural language query into a Cypher query (using Gemini with graph schema context).
        *   Executes the Cypher query against Neo4j.
        *   Retrieves relevant graph data.
    *   **System (Synthesis Agent):**
        *   Combines retrieved information.
        *   Generates a concise, accurate answer (Gemini).
    *   **Feedback:** Displays the answer in the chat.

**Scenario B: Uploading and Querying a Private File**

1.  **File Upload:**
    *   **User Action:** Clicks the "Upload File" button (prominently displayed near the chat input). Selects a PDF, TXT, or Word file from their device.
    *   **System:**
        *   Displays upload progress.
        *   Stores the raw file in Supabase Storage (private, user-specific).
        *   Initiates a background process:
            *   Extracts text from the file.
            *   Chunks the text.
            *   Embeds chunks (Gemini).
            *   Stores embeddings in Supabase SQL, tagged with `user_id` and `file_id`.
    *   **Feedback:** "Uploading [filename]... (50%)" -> "Processing [filename]..." -> "File [filename] ready for questions!"
2.  **Querying Private File:**
    *   **User Action:** Types a question related to the newly uploaded file (e.g., "Summarize the key recommendations in the 'Project Proposal.pdf' I just uploaded.").
    *   **System (LangGraph - Router Agent):**
        *   Identifies the query's intent to target a user-specific document.
        *   Routes to the Vector Retrieval Agent (private).
    *   **System (Vector Retrieval Agent - Private):**
        *   Embeds the user query (Gemini).
        *   Searches *only* the user's private document embeddings in Supabase.
        *   Retrieves relevant text chunks.
    *   **System (Synthesis Agent):**
        *   Generates an answer based on the private document (Gemini).
    *   **Feedback:** Displays the answer in the chat.

**Scenario C: Multi-Source / Hybrid Query**

1.  **Complex Question:**
    *   **User Action:** Asks a question requiring information from multiple sources (e.g., "Based on my uploaded 'Market Analysis.docx', how do its findings align with the shared 'Company Strategy' document, and what are the related market trends identified in the Neo4j graph?").
    *   **System (LangGraph - Orchestration Agent):**
        *   Breaks down the complex query into sub-tasks.
        *   Delegates to multiple agents concurrently:
            *   Vector Retrieval Agent (private) for 'Market Analysis.docx'.
            *   Vector Retrieval Agent (shared) for 'Company Strategy'.
            *   Graph Query Agent for market trends in Neo4j.
        *   Collects and synthesizes results from all agents, performing multi-hop reasoning if necessary.
    *   **Feedback:** Provides a comprehensive, integrated answer in the chat.

### Phase 3: User Management & Settings

1.  **Navigation:**
    *   **User Action:** Clicks on a "Settings" or "My Account" icon/link.
2.  **Settings Page:**
    *   **System:** Displays options for:
        *   **API Key Management:** View current Gemini API key (masked), option to update/replace.
        *   **My Uploaded Files:** A list of all user-uploaded files, their status (processing/ready), and options to view details or delete.
        *   **Usage Statistics (Optional):** Basic metrics on queries, token usage.
        *   **Account Settings:** Change password, email, etc.
        *   **Logout.**
