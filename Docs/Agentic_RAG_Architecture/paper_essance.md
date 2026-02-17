## 5.6 Graph-Based Agentic RAG

### 5.6.1 Agent-G: Agentic Framework for Graph RAG

**Agent-G [8]** introduces a novel agentic architecture that integrates graph knowledge bases with unstructured document retrieval. By combining structured and unstructured data sources, this framework enhances retrieval-augmented generation (RAG) systems with improved reasoning and retrieval accuracy. It employs modular retriever banks, dynamic agent interaction, and feedback loops to ensure high-quality outputs.

> **Figure 21:** An Overview of Agent-G: Agentic Framework for Graph RAG [8]

---

### Key Idea of Agent-G

The core principle of Agent-G lies in its ability to dynamically assign retrieval tasks to specialized agents, leveraging both graph knowledge bases and textual documents. Agent-G adjusts its retrieval strategy as follows:

* **Graph Knowledge Bases:** Structured data is used to extract relationships, hierarchies, and connections (e.g., disease-to-symptom mappings in healthcare).
* **Unstructured Documents:** Traditional text retrieval systems provide contextual information to complement graph data.
* **Critic Module:** Evaluates the relevance and quality of retrieved information, ensuring alignment with the query.
* **Feedback Loops:** Refines retrieval and synthesis through iterative validation and re-querying.

### Workflow

The Agent-G system is built on four primary components:

1. **Retriever Bank:**
* A modular set of agents specializes in retrieving graph-based or unstructured data.
* Agents dynamically select relevant sources based on the query’s requirements.


2. **Critic Module:**
* Validates retrieved data for relevance and quality.
* Flags low-confidence results for re-retrieval or refinement.


3. **Dynamic Agent Interaction:**
* Task-specific agents collaborate to integrate diverse data types.
* Ensures cohesive retrieval and synthesis across graph and text sources.


4. **LLM Integration:**
* Synthesizes validated data into a coherent response.
* Iterative feedback from the critic ensures alignment with the query’s intent.



### Key Features and Advantages

* **Enhanced Reasoning:** Combines structured relationships from graphs with contextual information from unstructured documents.
* **Dynamic Adaptability:** Adjusts retrieval strategies dynamically based on query requirements.
* **Improved Accuracy:** Critic module reduces the risk of irrelevant or low-quality data in responses.
* **Scalable Modularity:** Supports the addition of new agents for specialized tasks, enhancing scalability.

---

### Use Case: Healthcare Diagnostics

**Prompt:** *What are the common symptoms of Type 2 Diabetes, and how are they related to heart disease?*

**System Process (Agent-G Workflow):**

1. **Query Reception and Assignment:** The system receives the query and identifies the need for both graph-structured and unstructured data.
2. **Graph Retriever:** * Extracts relationships between Type 2 Diabetes and heart disease from a medical knowledge graph.
* Identifies shared risk factors such as obesity and high blood pressure.


3. **Document Retriever:** * Retrieves descriptions of symptoms (e.g., thirst, fatigue) from medical literature.
* Adds contextual information to complement graph insights.


4. **Critic Module:** * Evaluates quality and flags low-confidence results for refinement.
5. **Response Synthesis:** The LLM integrates validated data into a coherent response.

**Integrated Response:** > “Type 2 Diabetes symptoms include increased thirst, frequent urination, and fatigue. Studies show a 50% correlation between diabetes and heart disease, primarily through shared risk factors such as obesity and high blood pressure.”

---

### 5.6.2 GeAR: Graph-Enhanced Agent for Retrieval-Augmented Generation

**GeAR [35]** introduces an agentic framework that enhances traditional RAG systems by incorporating graph-based retrieval mechanisms. By leveraging graph expansion techniques and an agent-based architecture, GeAR addresses challenges in multi-hop retrieval scenarios.

> **Figure 22:** An Overview of GeAR: Graph-Enhanced Agent for Retrieval-Augmented Generation [35]

### Key Idea of GeAR

GeAR advances RAG performance through two primary innovations:

* **Graph Expansion:** Enhances conventional base retrievers (e.g., BM25) by expanding the retrieval process to include graph-structured data.
* **Agent Framework:** Utilizes an agent-based architecture to manage retrieval tasks more effectively, allowing for autonomous decision-making.

### Workflow

1. **Graph Expansion Module:** * Integrates graph-based data to consider relationships between entities.
* Enhances the ability to handle multi-hop queries by expanding the search space.


2. **Agent-Based Retrieval:** * Employs an agent framework to manage the retrieval process.
* Autonomously decides to utilize graph-expanded paths to improve relevance.


3. **LLM Integration:** * Combines retrieved information with LLM capabilities.
* Ensures the generative process is informed by both unstructured and structured data.



### Key Features and Advantages

* **Enhanced Multi-Hop Retrieval:** Handles complex queries requiring reasoning over interconnected information.
* **Agentic Decision-Making:** Enables dynamic selection of retrieval strategies.
* **Improved Accuracy:** Increases precision via structured graph data.
* **Scalability:** Modular nature allows for the integration of new data sources.

---

### Use Case: Multi-Hop Question Answering

**Prompt:** *Which author influenced the mentor of J.K. Rowling?*

**System Process (GeAR Workflow):**

1. **Top-Tier Agent:** Evaluates the multi-hop nature of the query.
2. **Graph Expansion Module:** Identifies J.K. Rowling’s mentor and traces literary influences through graph-structured relationships.
3. **Agent-Based Retrieval:** Autonomously selects the graph-expanded path and integrates textual context for details.
4. **Response Synthesis:** Combines insights from both sources to generate the final answer.

**Integrated Response:** > “J.K. Rowling’s mentor, [Mentor Name], was heavily influenced by [Author Name], known for their [notable works or genre]. This connection highlights the layered relationships in literary history...”
