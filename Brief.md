# Contexte du projet

Vous êtes ingénieur en intelligence artificielle au sein d’une entreprise spécialisée dans la distribution d’équipements biomédicaux. Les laboratoires clients rencontrent régulièrement des difficultés techniques avec leurs équipements. L’accès aux manuels techniques, souvent volumineux et dispersés en plusieurs PDF, est chronophage, et l’intervention du service technique engendre des délais coûteux, impactant la continuité des analyses et la remise des résultats aux cliniciens.

**Votre mission consiste à concevoir et déployer une architecture RAG (Retrieval-Augmented Generation) optimisée**, capable d’indexer les manuels techniques et les bases de connaissances internes afin de fournir aux techniciens de laboratoire des réponses précises, actionnables et sourcées, en langage naturel, avant même l’ouverture d’un ticket support.

---

## Étapes de réalisation

### 1. Prétraitement et Chunking
*   Importer le manuel technique ou les documents PDF de référence.
*   Choisir une méthode de chunking qui préserve le maximum de contexte dans chaque chunk.
*   Chaque chunk doit être accompagné de métadonnées utiles.

### 2. Indexation et persistance des embeddings
*   Choisir une base de données vectorielle adaptée (ChromaDB, FAISS, Qdrant).
*   Sélectionner un modèle d’embeddings (Hugging Face, Ollama).
*   Persister les embeddings dans un store vectoriel.

### 3. Retrieval (Récupération des informations)
*   Configurer un retriever qui permet de rechercher les chunks pertinents selon la requête de l’utilisateur.
*   Intégrer des techniques d’amélioration de la recherche (Query expansion, Reranking).

### 4. Génération de réponse (RAG)
*   Définir un prompt centralisé et bien formulé.
*   Utiliser un LLM pour générer des réponses à partir des chunks récupérés.
*   S’assurer que les réponses soient précises.

---

## Architecture des données

### Tables principales
*   **users** : `id`, `username`, `email`, `hashed_password`, `role`
*   **Query** : `id`, `query`, `reponse`, `created_at`

---

## Stack Technique (Back-end)

*   **Framework** : FastAPI (API REST asynchrone)
*   **Validation** : Pydantic
*   **ORM** : SQLAlchemy
*   **Pipeline RAG** : LangChain
*   **Authentification** : JWT
*   **Base de données** : PostgreSQL
*   **Configuration** : pydantic-settings + fichiers `.env`
*   **Conteneurisation** : Docker + Docker Compose
*   **Qualité de code** : Gestion centralisée des exceptions & Tests unitaires

# LLMOps

## MLflow

### Logger la configuration RAG
- **Chunking** : taille, overlap et stratégie de segmentation des documents sources  
- **Embedding** : choix du modèle d’embedding, dimensionnalité et normalisation  
- **Retrieval** : algorithme de similarité (cosine, L2), nombre de chunks retournés (`k`) et re-ranking  

### Logger la configuration du LLM
- Hyperparamètres du LLM :
  - Template de prompt  
  - Température  
  - Modèle sélectionné  
  - `max_tokens`  
  - `top_p`  
  - `top_k`  

### Observabilité et évaluation
- Logger les réponses et les contextes  
- Logger les métriques RAG avec **DeepEval** :
  - Answer Relevance  
  - Faithfulness  
  - Precision@k  
  - Recall@k  
- Logger le pipeline RAG (modèle) avec **LangChain**

---

## Pipeline CI/CD → Kubernetes

- Exécuter les tests (code + RAG)  
- Construire l’image Docker  
- Publier l’image sur Docker Hub  
- Déployer l’image dans Kubernetes (un seul pod)  
- Superviser et gérer le pod via **Minikube**

---

## Monitoring avec Prometheus & Grafana

### Supervision
- Surveiller les métriques du RAG et du pod  

### Collecte des métriques
- **Infrastructure** :
  - CPU  
  - RAM  
  - Statut du pod  
- **Applicatives (RAG)** :
  - Latence  
  - Qualité des réponses  
  - Erreurs  
  - Nombre de requêtes  

### Alerting
- Configurer des alertes basées sur les métriques du RAG :
  - Seuils de latence  
  - Taux d’erreurs  
  - Dégradation de la qualité des réponses  
