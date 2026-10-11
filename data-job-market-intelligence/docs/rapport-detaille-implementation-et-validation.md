# Rapport détaillé — Data Job Market Intelligence

**Bilan final fonctionnel V2 — 11 octobre 2026.** Rapport assemblé à partir des contrôles réellement exécutés ; les dates précises des mesures sont enregistrées dans les JSON. Les horodatages techniques ci-dessous sont en UTC. La validation locale utilise PostgreSQL Supabase, FastAPI et Streamlit. **Les composants critiques fonctionnent avec V2. Docker reste partiellement validé**, car son exécutable est absent sur cet ordinateur. Aucun déploiement Docker effectif ni succès GitHub Actions hébergé n’est affirmé.

| Résultat final | Mesure vérifiée |
| --- | --- |
| Index de recherche actif | **V2**, `index_state.id=2`, version `v2`, `partial=false` |
| Offres conservées | **12 217** |
| Chunks V2 | **30 955** |
| Embeddings pgvector V2 | **30 955**, dimension **384** |
| Checkpoints comparés au stockage | **484 lots**, **30 955 vecteurs**, écart maximal **0,0** |
| Couverture / intégrité | 12 217 jobs couverts, zéro chunk orphelin, zéro vecteur nul |
| V1 conservé | 23 638 chunks / embeddings ; limite historique : deux vecteurs nuls |
| Tests, PostgreSQL inclus | **61 réussis**, zéro échec, zéro ignoré, deux avertissements |
| Tests PostgreSQL | **3 réussis**, inclus dans la suite complète |
| Lint et format | Ruff passe ; 94 fichiers conformes |
| API | **6 routes HTTP 200** |
| Questions réelles | **10/10** routes et preuves vérifiées ; **25 sources**, **67 claims** cités vérifiés |
| Interface | Trois pages vérifiées dans le navigateur sur V2 |
| Docker | 16 contrôles statiques passent ; aucune exécution Compose locale |
| Definition of Done | **19 critères validés, 1 partiellement validé, 0 manquant ou échoué** |

**Dernier commit de code Python validé : `f216ba112eb8a5cc498de6e0f823ff8301ab942f`.** Le commit final de documentation est communiqué avec la livraison ; il ne modifie pas l’architecture.

Les résultats analytiques portent sur un instantané historique collecté en janvier 2024. Une réponse France = 0 signifie que cet échantillon ne contient pas d’offre correspondante ; elle ne décrit pas le marché français actuel.

## 1. Où se trouve le projet et comment lire son histoire

- Racine Git : `C:\Users\HP\Documents\ChatGPT\Data Job Market Intelligence`.
- Application : `C:\Users\HP\Documents\ChatGPT\Data Job Market Intelligence\data-job-market-intelligence`.
- Code et documentation suivis par Git : 106 fichiers lors de l’inspection finale.
- Fichiers volumineux ou privés exclus de Git : environnement `.venv/`, configuration locale `.env`, CSV bruts, données traitées, modèles, checkpoints d'embeddings, journaux et résultats de validation JSON.
- Le dossier voisin nommé **Data Job Market Intelligence Pipeline** est un ancien projet distinct. Ses chiffres de nettoyage ne doivent pas être substitués aux chiffres de la présente application. Ici, la base `djmi` contient 12 217 jobs.

Le premier commit Git de ce dépôt, `ee9b7c84aaec2da254ea7783ea9a96a9cbf7113d` du 24 septembre 2026 à 21 h 04 UTC, regroupe déjà l'application fonctionnelle. Il **ne donne pas la date individuelle de création de chaque fichier** ni l'ordre exact des modifications faites avant ce commit. Les commits suivants documentent précisément les corrections et outils de validation ajoutés ensuite. Cette distinction évite de présenter une chronologie reconstituée comme une preuve Git.

## 2. Chronologie vérifiable des commits

| Date UTC | Commit | Changement enregistré |
| --- | --- | --- |
| 24/09 21 h 04 | `ee9b7c8` | Code applicatif initialement versionné : ingestion, PostgreSQL, index V1, code V2, FastAPI, Streamlit, tests, Docker, CI et documentation. L'activation complète de V2 restait à faire. |
| 24/09 21 h 27 | `b36830b` | Script des dix questions finales et corrections des réponses : dix compétences, distribution complète, responsabilités AWS mieux ancrées dans les phrases sources, rôle Data Analyst non renommé à tort. |
| 24/09 21 h 38 | `349d640` | Audit d'intégrité pgvector et comparaison V1/V2 fondée sur des mesures. |
| 25/09 14 h 08 | `cc39f80` | Vérification indépendante en SQL des cinq réponses quantitatives. |
| 25/09 14 h 10 | `029845e` | Indicateur explicite de réponse ancrée dans la base et exigence de claims reliés au texte. |
| 25/09 14 h 12 | `28eb3ef` | Vérification prévue de chaque vecteur V2 publié contre son checkpoint calculé. |
| 25/09 14 h 14 | `8639d61` | Commandes reproductibles de validation dans `evaluation/README.md`. |
| 25/09 20 h 38 | `f216ba1` | Lecture PostgreSQL paginée et reprise après coupure SSL pendant l'indexation. |
| 25/09 | `8e01177` | Création du premier rapport détaillé, explicitement provisoire. |
| 05/10 | `0be58a5` | Connexion PostgreSQL rétablie, reprise V2 et rapport actualisé. |
| 11/10 15 h 25 min 48 s | Journal d’exécution | Activation complète des 30 955 chunks V2 dans PostgreSQL. |

Le dernier commit ayant modifié le code Python est `f216ba112eb8a5cc498de6e0f823ff8301ab942f`. Ce code a été validé avec V2 actif le 11 octobre. Les commits suivants portent sur la documentation ; le hash du commit final de livraison est donné dans le bilan de livraison et dans `evaluation/results/final-v2-release.json`.

## 3. Source des données et préparation

La source utilisée est le jeu Kaggle `asaniczka/data-science-job-postings-and-skills`, repris depuis les CSV locaux existants. L'application n'invente pas de données et ne télécharge pas automatiquement un nouvel échantillon. Les trois fichiers réels se trouvent dans `data/raw/` :

| Fichier | Lignes mesurées | Rôle |
| --- | ---: | --- |
| `job_postings.csv` | 12 217 | Titres, entreprises, lieux, niveau et champs de collecte. |
| `job_summary.csv` | 12 217 | Descriptions utilisées pour le nettoyage, le découpage et le RAG. |
| `job_skills.csv` | 12 217 | Compétences source à joindre et normaliser. |

`src/preprocessing/pipeline.py` découvre les colonnes présentes, joint les fichiers par `job_link`, conserve une identité de job stable, écrit les données traitées et produit le rapport qualité. `cleaner.py` enlève notamment le bruit HTML et nettoie les descriptions. `normalizer.py` normalise titre, séniorité, pays, ville, mode de travail, type d'emploi et salaires exploitables. `skill_extractor.py` extrait les compétences à partir de la taxonomie configurable `config/skills.json`. Les tests correspondants sont dans `tests/test_preprocessing.py`.

Le rapport qualité actuellement enregistré dans `data/processed/quality_report.json` indique :

| Mesure | Résultat |
| --- | ---: |
| Lignes brutes | 12 217 |
| Jobs traités | 12 217 |
| Doublons supprimés | 0 |
| Titres absents supprimés | 0 |
| Descriptions nettoyées absentes | 0 % |
| Pays manquant | 2,04 % |
| Lieu manquant | 0,008 % |
| Couverture des titres normalisés | 51,34 % |
| Couverture de l'extraction de compétences | 75,23 % |
| Date réelle de publication manquante | 100 % |

La plage du 12 au 17 janvier 2024 correspond à `first_seen`, c'est-à-dire à la **collecte**, pas à une tendance de recrutement. Les rôles non classables restent dans les données ; le projet ne transforme pas artificiellement toutes les annonces en métiers Data/IA. Les lieux de recherche du crawler ne sont pas considérés comme des lieux d'emploi vérifiés. Les publications sans localisation fiable gardent une valeur inconnue. Les salaires absents ne sont pas estimés.

Le fichier généré `data/processed/jobs.jsonl` est présent et contient les jobs traités. Les CSV et JSONL sont ignorés par Git pour éviter un dépôt volumineux et une redistribution non contrôlée des données source.

## 4. Base PostgreSQL et index V1

`src/database/connection.py` construit la connexion à PostgreSQL à partir de `.env`, avec SSL pour l'instance distante, schéma applicatif `djmi` et vérification des connexions du pool. **Aucun mot de passe n'est reproduit dans ce rapport.** `init_db.py` initialise l'extension pgvector et les tables. `models.py` définit `jobs`, `job_skills`, `job_chunks` (V1), `job_chunks_v2` (V2) et `index_state`. `repositories.py` charge les jobs en transaction et applique les filtres métier. Le rechargement des jobs invalide les deux index de recherche, ce qui oblige à réindexer.

Mesures directement obtenues dans PostgreSQL à l'instantané :

| Élément | Valeur vérifiée |
| --- | ---: |
| Jobs dans `djmi.jobs` | 12 217 |
| Chunks V1 dans `djmi.job_chunks` | 23 638 |
| Embeddings V1 présents | 23 638 |
| Jobs possédant au moins un chunk V1 | 12 217 |
| Chunks V1 orphelins | 0 |
| Dimension V1 | 128 |
| Extension pgvector | 0.8.2 |
| Index HNSW cosinus V1 | Présent |
| Vecteurs V1 de norme nulle | **2** |

Le dernier point est une limite **mesurée**, et non masquée : deux embeddings LSA V1 n'ont pas de direction utilisable pour une similarité cosinus. Le rapport `evaluation/results/final-v1-index-audit.json` marque donc son contrôle global comme échoué sur ce critère, même si les comptes, dimensions et liens aux jobs passent. V2 remplace désormais l'index de recherche actif ; V1 reste disponible pour revenir en arrière, avec cette limite connue.

## 5. Analyse SQL, routage et RAG

`src/analytics/service.py` calcule les comptes, pourcentages, classements de compétences, répartitions par rôle/pays/ville/séniorité, données de salaires comparables et pagination des jobs. Chaque compétence est comptée au plus une fois par annonce. Les requêtes sont construites par SQLAlchemy ; le programme ne lance pas de SQL produit librement par un modèle. Les filtres pris en charge sont notamment rôle, pays, ville, séniorité, mode de travail, entreprise et compétence.

`src/routing/classifier.py`, `metadata.py` et `service.py` séparent les demandes quantitatives, traitées par SQL, des demandes descriptives, traitées par RAG. Les demandes ambiguës ou non prises en charge donnent une clarification plutôt qu'un résultat inventé. Pendant la validation des dix questions, une correction a rendu visibles les **dix** compétences demandées, et non seulement cinq, ainsi que toutes les catégories de séniorité.

Le RAG se trouve dans `src/rag/` :

1. `chunking.py` découpe les descriptions par phrases avec taille et chevauchement configurables.
2. `embeddings.py` définit l'interface des fournisseurs, V1 TF-IDF/SVD 128 dimensions, V2 BGE local 384 dimensions et fournisseur OpenAI optionnel.
3. `indexing.py` calcule les vecteurs et prépare un remplacement atomique de l'index choisi.
4. `retriever.py` interroge pgvector avec similarité cosinus et filtres de métadonnées.
5. `reranker.py` reclasse les résultats avec un cross-encoder local, ou un repli hybride, puis sélectionne des jobs distincts.
6. `context_builder.py`, `service.py` et `synthesis.py` bâtissent une réponse à partir d'extraits de vrais jobs et y attachent des IDs de sources.

Les modules `src/prompts/` encadrent le routage, la réécriture, l'extraction de métadonnées, la synthèse et la vérification. `src/llm/` contient les fournisseurs de génération optionnels. Le mode local par défaut est une **synthèse ancrée et non générative** ; il ne se présente pas comme une réponse LLM. Les fournisseurs OpenAI/Ollama optionnels n'ont pas fait l'objet d'un essai réel dans cette validation. Les descriptions d'emplois sont traitées comme des preuves non fiables : une citation doit renvoyer à une source récupérée et une citation textuelle doit apparaître dans le chunk correspondant. Cela prouve la traçabilité, mais pas automatiquement la justesse de toute paraphrase.


## 6. FastAPI, Streamlit et contrôles de l’interface

FastAPI possède la logique métier et Streamlit appelle ses endpoints HTTP. Les deux services ont été relancés après la publication de V2. Le `/health` indique `status=ok`, `database=connected`, `jobs=12217`, `chunks=30955`, `index_ready=true`.

| Route vérifiée | HTTP | Latence observée | Contrôle |
| --- | ---: | ---: | --- |
| `GET /health` | 200 | 0.434 s | 12 217 jobs, 30 955 chunks, index prêt |
| `GET /api/analytics/overview` | 200 | 3.097 s | Réponse réelle de PostgreSQL |
| `GET /api/analytics/skills` | 200 | 0.540 s | Réponse réelle de PostgreSQL |
| `GET /api/analytics/jobs` | 200 | 0.698 s | Réponse réelle de PostgreSQL |
| `POST /api/assistant/query` | 200 | 2.068 s | Route analytics, filtre Data Engineer / France, réponse 0 |
| `POST /api/rag/query` | 200 | 7.678 s | Route RAG, index v2, sources/chunks PostgreSQL vérifiés |

### Vérification manuelle Streamlit sur V2

- **Market Overview** : KPI 12 217, graphiques de compétences/rôles/séniorité/localisation/mode de travail et matrice rôle-compétence chargés. Le filtre `Country=Canada` ramène le total à **625**, la première ville à Toronto et actualise les graphiques.
- **Job Explorer** : 12 217 offres sans filtre, **625** avec Canada, douze cartes paginées, badges de compétences et liens originaux visibles. La description réelle de **Machine Learning Engineer — MobSquad** a été ouverte.
- **AI Assistant / analytics** : question exacte sur Data Engineer en France, réponse **0** et badge **ANALYTICS** visibles.
- **AI Assistant / RAG** : question exacte sur Senior Data Engineers, badge **RAG**, réponse citée `[S1]` à `[S6]`, compteur **6 retrieved job postings**, label d’évidence et six sources affichés. La première source a été ouverte : extrait réel et lien original visibles. Les détails techniques indiquent `fastembed-bge-small-en-v1.5-384`, les filtres Data Engineer / Senior, les vrais IDs des chunks et le reclassement `cross_encoder`.
- **Contenu provisoire** : aucun placeholder de contenu constaté sur ces pages ; l’inspection statique des dossiers `app`, `api`, `src` ne trouve aucun `TODO`, `lorem ipsum`, `coming soon`, `fake response` ou `placeholder`. Le texte indicatif normal du champ de saisie est une aide de l’interface.

Preuves locales :

![Market Overview filtré sur Canada](../evaluation/results/ui-v2/market-overview-canada.png)

![Réponse RAG, citations et compteur de preuves](../evaluation/results/ui-v2/assistant-rag-v2.png)

Le bilan manuel et les autres captures sont dans `evaluation/results/ui-v2/`. La vérification couvre les interactions décrites ; elle n’est pas un test exhaustif de toutes les combinaisons de filtres.

## 7. V2 : calcul, activation et pgvector

Le modèle local est `BAAI/bge-small-en-v1.5` via FastEmbed/ONNX ; la dimension est 384. Les descriptions sont découpées par phrases, avec une cible de 320 mots et un chevauchement de 40 mots. Le contenu, le modèle et les paramètres déterminent l’identité des checkpoints. L’indexeur réutilise uniquement des lots compatibles, finis et de la forme attendue.

Le calcul a connu des interruptions. Le 25 septembre, une veille Windows et des erreurs SSL sur une grande lecture ont conduit au correctif de pagination `f216ba1`. Le 5 octobre, Supabase renvoyait `tenant/user not found` ; les paramètres affichés dans le tableau de bord correspondaient au fichier local, et une nouvelle connexion a ensuite retrouvé les 12 217 offres. La reprise a réutilisé 23 936 vecteurs. Le 11 octobre, l’indexeur arrêté a été relancé, a réutilisé **26 816** vecteurs, puis a terminé les **30 955**. Le journal confirme **Index activated: 30955 chunks** le **11 octobre 2026 à 15:25:48 UTC**.

Une transaction unique publie les chunks V2 et la ligne d’état 2. Les tables de jobs et de V1 sont conservées. Le helper local non suivi `keep-awake-v2.py` empêchait temporairement la veille automatique pendant l’indexation et libère sa demande lorsque le processus sort.

| Contrôle V2 dans PostgreSQL | Résultat |
| --- | --- |
| Jobs | 12217 |
| Chunks | 30955 |
| Embeddings | 30955 |
| Jobs ayant des chunks | 12217 |
| Chunks orphelins | 0 |
| Vecteurs de norme nulle | 0 |
| Dimension | 384 |
| Extension pgvector | 0.8.2 |
| Index HNSW cosinus V2 | True |
| Norme minimale | 0.999999793984225 |
| Norme maximale | 1.00000022091416 |
| Audit global | True |
| Lots comparés au stockage | 484 |
| Vecteurs comparés au stockage | 30955 |
| Écart maximal de composante | 0.0 |

**V2 est réellement utilisé.** Toutes les réponses RAG du lot de dix questions déclarent V2 ; tous leurs chunks et citations ont été vérifiés contre `job_chunks_v2` et `jobs`. Le retriever préfère la ligne d’état 2 lorsqu’elle existe. Un `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)` de la recherche cosinus non filtrée, avec un vecteur V2 sauvegardé, a mesuré une utilisation de **`ix_chunks_v2_embedding_cosine` sur `job_chunks_v2`** : 20 lignes retournées, temps d’exécution PostgreSQL **820,537 ms** pour cette requête précise. Ce temps SQL n’est pas la latence HTTP de l’assistant.

Les recherches avec filtres de métadonnées utilisent volontairement un classement cosinus exact sur le sous-ensemble filtré, pour éviter la perte de résultats d’un index approximatif sur une petite sélection. Elles interrogent toujours la table V2. Le plan SQL enregistré ne prétend donc pas que toutes les questions filtrées utilisent le HNSW.

## 8. Les dix questions exactes : résultats finaux V2

Mesure HTTP commencée le `2026-10-11T16:11:00.613823+00:00`. Chaque question est passée par `POST /api/assistant/query`. Les cinq réponses analytics ont été réconciliées avec des requêtes SQL indépendantes. Les cinq réponses RAG utilisent V2 ; leurs sources, liens, IDs de jobs, IDs de chunks et citations textuelles ont été vérifiés dans PostgreSQL. **Dix réponses ancrées, zéro problème de route, SQL ou traçabilité.**

| Nº | Question | Route / filtres extraits | Réponse exacte enregistrée | Documents / IDs de sources | Latence HTTP | Ancrage |
| ---: | --- | --- | --- | --- | ---: | --- |
| 1 | How many Data Engineer jobs are in France? | `analytics` ; `{"job_title": "Data Engineer", "country": "France"}` | 0 postings in this historical dataset match Data Engineer, France. | SQL ; aucune source RAG | 2.209 s | Oui — SQL over PostgreSQL |
| 2 | What are the top 10 most requested skills? | `analytics` ; `{}` | Most requested skills in this historical dataset: SQL (5,592); Python (5,121); Machine Learning (3,324); AWS (2,816); Azure (2,156); Spark (2,076); Excel (1,956); Tableau (1,828); Power BI (1,664); GCP (1,466). Each job counts once per skill. | SQL ; aucune source RAG | 2.389 s | Oui — SQL over PostgreSQL |
| 3 | What percentage of jobs mention Python? | `analytics` ; `{"skill": "Python"}` | 5,121 of 12,217 matching jobs (41.92%) mention Python. | SQL ; aucune source RAG | 2.443 s | Oui — SQL over PostgreSQL |
| 4 | Which cities contain the most job postings? | `analytics` ; `{}` | Top recorded cities among all roles and locations: New York (357); London (239); Chicago (232); San Francisco (199); Washington (184). 296 postings are unknown. | SQL ; aucune source RAG | 2.077 s | Oui — SQL over PostgreSQL |
| 5 | What is the distribution of seniority levels? | `analytics` ; `{}` | Distribution of seniority values among all roles and locations: Mid/Senior (source) (4,769); Lead (3,015); Senior (2,985); Unspecified (927); Junior (335); Executive (153); Intern (33). | SQL ; aucune source RAG | 2.101 s | Oui — SQL over PostgreSQL |
| 6 | What responsibilities are expected from Senior Data Engineers? | `rag` ; `{"job_title": "Data Engineer", "seniority": "Senior"}` | The selected postings describe these responsibilities:<br><br>• Data pipelines or ingestion [S1], [S2], [S5], [S6]<br>• SQL, data modeling, or warehousing [S1], [S2], [S4], [S5], [S6]<br>• Cloud infrastructure or deployment [S1], [S2], [S3], [S5], [S6]<br><br>These are observations from the selected postings, not market-wide frequencies. | 6 jobs / 6 chunks ; S1, S2, S3, S4, S5, S6 | 9.552 s | Oui — verified chunks |
| 7 | What skills are commonly associated with Kubernetes? | `rag` ; `{"skill": "Kubernetes"}` | In the retrieved postings that mention Kubernetes, these other tracked technologies appear:<br><br>• Docker — present in 4 selected posting(s) [S3], [S4], [S5], [S6]<br>• AWS — present in 3 selected posting(s) [S1], [S3], [S4]<br>• Azure — present in 3 selected posting(s) [S2], [S3], [S4]<br>• Machine Learning — present in 3 selected posting(s) [S3], [S5], [S6]<br>• Python — present in 3 selected posting(s) [S3], [S5], [S6]<br><br>These are observations from the selected postings, not market-wide frequencies. | 6 jobs / 6 chunks ; S1, S2, S3, S4, S5, S6 | 7.439 s | Oui — verified chunks |
| 8 | What AWS-related responsibilities appear in Data Engineer roles? | `rag` ; `{"job_title": "Data Engineer", "skill": "AWS"}` | In the selected postings, AWS appears in responsibilities involving:<br><br>• SQL, data modeling, or warehousing [S1], [S3], [S6]<br>• Cloud infrastructure or deployment [S1], [S2], [S3], [S4], [S5], [S6]<br><br>These are observations from the selected postings, not market-wide frequencies. | 6 jobs / 6 chunks ; S1, S2, S3, S4, S5, S6 | 8.718 s | Oui — verified chunks |
| 9 | What are common requirements for Machine Learning Engineer positions? | `rag` ; `{"job_title": "Machine Learning Engineer", "skill": "Machine Learning"}` | Across the retrieved postings, these tracked skills appear:<br><br>• Machine Learning — present in 6 selected posting(s) [S1], [S2], [S3], [S4], [S5], [S6]<br>• Python — present in 4 selected posting(s) [S3], [S4], [S5], [S6]<br>• TensorFlow — present in 3 selected posting(s) [S3], [S5], [S6]<br>• AWS — present in 2 selected posting(s) [S3], [S4]<br>• Deep Learning — present in 2 selected posting(s) [S1], [S3]<br>• Data pipelines or ingestion [S2], [S3], [S4]<br>• Cloud infrastructure or deployment [S3], [S4], [S6]<br><br>These are observations from the selected postings, not market-wide frequencies. | 6 jobs / 6 chunks ; S1, S2, S3, S4, S5, S6 | 8.243 s | Oui — verified chunks |
| 10 | What responsibilities appear in remote Data Analyst roles? | `rag` ; `{"job_title": "Data Analyst", "workplace_type": "Remote"}` | The selected postings describe these responsibilities:<br><br>• Reliability, monitoring, or quality [S1]<br><br>These are observations from the selected postings, not market-wide frequencies. | 1 jobs / 1 chunks ; S1 | 3.186 s | Oui — verified chunks |

### Correspondance précise des sources RAG avec les jobs

Les IDs `S1` à `S6` sont locaux à chaque réponse. Le même libellé S1 dans deux questions ne représente pas le même job. Les IDs PostgreSQL ci-dessous sont les identités stables des enregistrements. Les URLs sont les liens de la source conservés en base ; la disponibilité actuelle de la page LinkedIn externe n’a pas été testée.

#### Question 6 — What responsibilities are expected from Senior Data Engineers?

Qualité d’évidence affichée : **Strong evidence**. 14 claims avec citations textuelles vérifiées. Réponse fondée sur 6 jobs sélectionnés, sans extrapolation de leurs fréquences à tout le marché.

| Source locale | ID de job PostgreSQL | Titre / entreprise | Lien original |
| --- | --- | --- | --- |
| S1 | `fe62ee62d0f9756ad8242a141dccecd1` | Sr. Data Engineer — Latitude Inc | [Annonce source](https://www.linkedin.com/jobs/view/sr-data-engineer-at-latitude-inc-3787730196) |
| S2 | `316531af66c6bfc865f735921cb7e1b6` | Senior Data Engineer — Ascendo Resources | [Annonce source](https://www.linkedin.com/jobs/view/senior-data-engineer-at-ascendo-resources-3792135667) |
| S3 | `fdb4382efaff3190f134df501f3031dc` | Senior Data Engineer, Enterprise Data and Analytics — First Command Financial Services, Inc. | [Annonce source](https://www.linkedin.com/jobs/view/senior-data-engineer-enterprise-data-and-analytics-at-first-command-financial-services-inc-3773358880) |
| S4 | `9f1444d8d6b654045ad5bf7072a86753` | Senior Data Engineer — Kforce Inc | [Annonce source](https://www.linkedin.com/jobs/view/senior-data-engineer-at-kforce-inc-3800584417) |
| S5 | `7bc62b9b5cba5f6eab724bafe292aff1` | Sr. Data Engineer — Tential Solutions | [Annonce source](https://www.linkedin.com/jobs/view/sr-data-engineer-at-tential-solutions-3783160018) |
| S6 | `03990263a15693671d8eae8364b3723c` | Senior Data Engineer — Kforce Inc | [Annonce source](https://www.linkedin.com/jobs/view/senior-data-engineer-at-kforce-inc-3796399527) |

#### Question 7 — What skills are commonly associated with Kubernetes?

Qualité d’évidence affichée : **Strong evidence**. 16 claims avec citations textuelles vérifiées. Réponse fondée sur 6 jobs sélectionnés, sans extrapolation de leurs fréquences à tout le marché.

| Source locale | ID de job PostgreSQL | Titre / entreprise | Lien original |
| --- | --- | --- | --- |
| S1 | `90147700107ba03b43fd3ca8811ad09c` | Data Engineer — Merit321, Launching Careers | [Annonce source](https://www.linkedin.com/jobs/view/data-engineer-at-merit321-launching-careers-3713419751) |
| S2 | `8de45b6a6c5cdf148f1cc536b69d1fe4` | Staff, Software Engineer - Big Data — Walmart | [Annonce source](https://www.linkedin.com/jobs/view/staff-software-engineer-big-data-at-walmart-3791513877) |
| S3 | `e79f627e0294e4471bd76784ab8b4ef4` | Data Scientist — Apex Systems | [Annonce source](https://www.linkedin.com/jobs/view/data-scientist-at-apex-systems-3803344385) |
| S4 | `b8fd1610a5dd6db18a3fef34bfab8809` | Lead Data Engineer — Jarvis Consulting Group | [Annonce source](https://www.linkedin.com/jobs/view/lead-data-engineer-at-jarvis-consulting-group-3772374932) |
| S5 | `57552675af801c496fa78b49a0ba5bf5` | Senior Backend and Cloud Engineer - Machine Learning Infrastructure (Python) — Scandit | [Annonce source](https://uk.linkedin.com/jobs/view/senior-backend-and-cloud-engineer-machine-learning-infrastructure-python-at-scandit-3779591028) |
| S6 | `712aacb4cfa41e3d6e6c8a88ad8cb7af` | Senior Backend and Cloud Engineer - Machine Learning Infrastructure (Python) — Scandit | [Annonce source](https://uk.linkedin.com/jobs/view/senior-backend-and-cloud-engineer-machine-learning-infrastructure-python-at-scandit-3779590087) |

#### Question 8 — What AWS-related responsibilities appear in Data Engineer roles?

Qualité d’évidence affichée : **Strong evidence**. 9 claims avec citations textuelles vérifiées. Réponse fondée sur 6 jobs sélectionnés, sans extrapolation de leurs fréquences à tout le marché.

| Source locale | ID de job PostgreSQL | Titre / entreprise | Lien original |
| --- | --- | --- | --- |
| S1 | `efdaef0fd9ef49fecf375e50c11467e8` | Data Engineer — NR Consulting | [Annonce source](https://www.linkedin.com/jobs/view/data-engineer-at-nr-consulting-3768019176) |
| S2 | `e448a4c390e607aa590a163bc885a267` | AWS DATA ENGINEER \| BEAVERTON, OR – HYBRID \| Industry: Retail / Wholesale — Vodastra Technologies | [Annonce source](https://www.linkedin.com/jobs/view/aws-data-engineer-beaverton-or-%E2%80%93-hybrid-industry-retail-wholesale-at-vodastra-technologies-3787735460) |
| S3 | `40abd6a020f7bec2142877dcfb78fc4a` | Data Engineer (AWS, Python, Apache Spark, Jenkins/Terraform, SQL, Agile) — Diversity Nexus | [Annonce source](https://www.linkedin.com/jobs/view/data-engineer-aws-python-apache-spark-jenkins-terraform-sql-agile-at-diversity-nexus-3800557593) |
| S4 | `8267b8c4c4251f07dc21d6b2c71bb305` | Data Engineer — QinetiQ US | [Annonce source](https://www.linkedin.com/jobs/view/data-engineer-at-qinetiq-us-3799970634) |
| S5 | `c820f117423345b275903ca85a6a36bc` | Data Engineer — Robert Half | [Annonce source](https://www.linkedin.com/jobs/view/data-engineer-at-robert-half-3797531408) |
| S6 | `7bc6a80f6f19f9193b4722b2ddc29d96` | Senior AWS Data Engineer - 6-Month Contract — Hour Consulting | [Annonce source](https://ca.linkedin.com/jobs/view/senior-aws-data-engineer-6-month-contract-at-hour-consulting-3770141485) |

#### Question 9 — What are common requirements for Machine Learning Engineer positions?

Qualité d’évidence affichée : **Strong evidence**. 27 claims avec citations textuelles vérifiées. Réponse fondée sur 6 jobs sélectionnés, sans extrapolation de leurs fréquences à tout le marché.

| Source locale | ID de job PostgreSQL | Titre / entreprise | Lien original |
| --- | --- | --- | --- |
| S1 | `cdae132709cc81e8f3804b7102dd9dfa` | Senior Machine Learning Engineer — Lirio | [Annonce source](https://www.linkedin.com/jobs/view/senior-machine-learning-engineer-at-lirio-3770480493) |
| S2 | `237662fc11276bbbe2940cc011199750` | Machine Learning Engineer — Brooksource | [Annonce source](https://www.linkedin.com/jobs/view/machine-learning-engineer-at-brooksource-3794037620) |
| S3 | `2b04010c6813ae0127a5a02c15049310` | Machine Learning Engineer — HummingBirds Consulting LLC - now doing Business as HummingBirds Innovation | [Annonce source](https://www.linkedin.com/jobs/view/machine-learning-engineer-at-hummingbirds-consulting-llc-now-doing-business-as-hummingbirds-innovation-3799484968) |
| S4 | `a662eabb9dc2d5ca103fa8db73d84603` | Machine Learning Engineer — InfoVision Inc. | [Annonce source](https://www.linkedin.com/jobs/view/machine-learning-engineer-at-infovision-inc-3798657627) |
| S5 | `b99c6a9fd982119cc262a113f72d2fcf` | Senior Full-Stack Machine Learning Engineer- OPTIX — GA-CCRi | [Annonce source](https://www.linkedin.com/jobs/view/senior-full-stack-machine-learning-engineer-optix-at-ga-ccri-3657308448) |
| S6 | `2b0b65fa03f791c5162d47e1b8b6c23f` | Machine Learning (Advanced) — microTECH Global LTD | [Annonce source](https://uk.linkedin.com/jobs/view/machine-learning-advanced-at-microtech-global-ltd-3792282264) |

#### Question 10 — What responsibilities appear in remote Data Analyst roles?

Qualité d’évidence affichée : **Limited evidence**. 1 claims avec citations textuelles vérifiées. Réponse fondée sur 1 jobs sélectionnés, sans extrapolation de leurs fréquences à tout le marché.

| Source locale | ID de job PostgreSQL | Titre / entreprise | Lien original |
| --- | --- | --- | --- |
| S1 | `322135f6e2a8de0759a992a2e64321f8` | Medical Data Analyst (Medical Coder) (Remote) — NewYork-Presbyterian Hospital | [Annonce source](https://www.linkedin.com/jobs/view/medical-data-analyst-medical-coder-remote-at-newyork-presbyterian-hospital-3772287984) |

La question sur les Data Analysts à distance ne fournit qu’**un job** et porte le label **Limited evidence**. Ce résultat ne permet pas de généraliser les responsabilités de tous les Data Analysts à distance. La synthèse locale reprend les catégories présentes dans les preuves ; elle ne constitue pas une évaluation humaine exhaustive de la justesse de chaque formulation.

## 9. Tests, lint, inspection des secrets, Docker et CI

- **Suite complète** : `RUN_DB_INTEGRATION=1 pytest -q` → **61 passed**, zéro échec, zéro test ignoré, **44,04 s**, deux avertissements de dépréciation FastAPI/Starlette/AnyIO.
- **PostgreSQL** : les trois tests `test_postgresql_vector_and_source_linkage`, `test_live_api_counts_and_real_citations`, `test_v2_index_is_complete_when_active` passent dans cette suite. Le dernier n’est plus ignoré : V2 est actif et complet.
- **Ruff** : `ruff check .` passe ; `ruff format --check .` passe avec **94 files already formatted**.
- **Traçabilité** : **25 références de sources**, **25 jobs cités distincts**, **67 claims** et leurs citations vérifiés sur les cinq questions RAG. Le POST direct `/api/rag/query` a aussi été vérifié : six sources réelles, zéro problème.
- **Secrets** : inspection de tous les fichiers suivis et de l’historique Git, recherche de motifs de clés privées/tokens/identifiants dans les URLs et comparaison avec les valeurs sensibles du `.env` local. Zéro résultat confirmé ; `.env` est ignoré et n’a pas été versionné. Le résultat exact et le commit scanné sont enregistrés dans `evaluation/results/secrets-inspection.json`. Cette inspection est une vérification par motifs et comparaison de valeurs, pas une preuve mathématique d’absence de tout secret possible.
- **Docker** : YAML Compose parsé ; validation JSON Schema réussie contre le [schéma officiel Compose](https://raw.githubusercontent.com/compose-spec/compose-spec/main/schema/compose-spec.json), dont une copie et le SHA-256 sont conservés avec les résultats ; **16 contrôles statiques passent** (quatre services, image pgvector, volumes, dépendances de santé, bootstrap, Dockerfiles, ports locaux, mot de passe local configuré, étapes CI). L’exécutable Docker est absent. **Non exécutés** : `docker compose config`, `docker compose up --build`, construction locale des images, démarrage effectif des services Compose et test HTTP dans les conteneurs.
- **CI** : `.github/workflows/ci.yml` existe dans la racine Git parente, installe les dépendances, lance Ruff/pytest, valide Compose et construit les images. Aucun lancement GitHub Actions hébergé n’a été observé dans cette validation.

## 10. Répertoire : quels fichiers ont été créés et à quoi ils servent

Le tableau liste les fichiers fonctionnels et d'évaluation ; les fichiers `__init__.py` déclarent les paquets Python et les `README.md` des sous-dossiers documentent leurs contrats. La liste exacte de tous les fichiers suivis s'obtient par `git ls-files` depuis la racine Git.

| Dossier / fichier | Fonction concrète |
| --- | --- |
| `.env.example`, `src/config/settings.py`, `config/skills.json` | Variables documentées, validation des réglages, taxonomie des compétences. Le vrai `.env` reste local. |
| `src/preprocessing/{pipeline,cleaner,normalizer,skill_extractor}.py` | CSV réels → jointure, nettoyage, champs normalisés, compétences et rapport qualité. |
| `src/database/{connection,init_db,models,repositories}.py` | Connexion, extension pgvector, tables, chargement transactionnel et filtres. |
| `src/analytics/{service,schemas}.py` | Statistiques SQL, filtres et schémas de réponse. |
| `src/routing/{classifier,metadata,service}.py` | Classification de la question, extraction des filtres, choix analytics/RAG et formulation analytique. |
| `src/rag/{chunking,embeddings,indexing,retriever,reranker,context_builder,service,synthesis}.py` | Découpage, vecteurs V1/V2, stockage, recherche, reclassement, contexte et réponse citée. |
| `src/prompts/{router,metadata_extraction,query_rewrite,grounded_answer,synthesis,verification}.py` | Instructions versionnées et contrôles d'une réponse fondée sur des sources. |
| `src/llm/{client,structured_output}.py` | Fournisseurs de génération optionnels et structure de claims. |
| `api/{main,dependencies}.py`, `api/routes/health.py` | API HTTP et dépendances partagées. |
| `app/Home.py`, `app/pages/1_Market_Overview.py`, `2_Job_Explorer.py`, `3_AI_Assistant.py` | Trois vues métier et accueil Streamlit. |
| `app/components/{design,ui}.py` | Styles et composants réutilisés. |
| `src/evaluation/evaluator.py`, `evaluation/questions.json`, `evaluation/review_v2.py` | Évaluation générale et questions révisées. |
| `evaluation/{final_validation,check_index,verify_v2_storage,compare_indexes}.py` | Dix questions exactes, audit pgvector, comparaison de tous les vecteurs sauvegardés/publiés et comparaison V1/V2 sans score fabriqué. |
| `tests/{conftest,test_preprocessing,test_analytics,test_retrieval,test_router,test_api,test_llm,test_v2_quality,test_live_database}.py` | Fixtures et tests unitaires, API, RAG et PostgreSQL opt-in. |
| `Dockerfile.api`, `Dockerfile.frontend`, `docker-compose.yml`, `.dockerignore` | Conteneurs API/UI, base pgvector, setup et réseau local. |
| `.github/workflows/ci.yml` | Workflow CI à la racine Git parente. |
| `README.md`, `docs/{implementation-plan,api-contract,v2-index-migration}.md`, `evaluation/README.md` | Lancement, contrats, migration/retour V1, commandes de validation. |
| `notebooks/01_data_exploration.ipynb` à `04_market_analysis.ipynb` | Exploration, nettoyage, compétences et analyses reproductibles. |

Les fichiers créés **pendant l'exécution**, et non dans Git, sont notamment `data/processed/jobs.jsonl`, `data/processed/quality_report.json`, le modèle LSA V1, les modèles FastEmbed, les lots `data/models/v2-checkpoints/.../batch-*.npy`, les journaux d'indexation et `evaluation/results/*.json`. Le petit `data/models/keep-awake-v2.py` est lui aussi local/ignoré : il n'appartient pas à l'architecture de l'application et disparaîtra avec les fichiers de travail locaux.


## 11. Definition of Done — les vingt critères originaux

Les critères sont repris dans leur ordre et leur formulation d’origine. Les statuts utilisent exactement les trois libellés demandés. Le périmètre des preuves est la validation locale du 11 octobre 2026, complétée par les artefacts de préparation déjà produits.

| Nº | Critère original | Statut final | Preuve / limite |
| ---: | --- | --- | --- |
| 1 | preprocessing works | ✅ implemented and validated | CSV réels, 12 217 jobs traités, rapport qualité et tests de prétraitement. |
| 2 | processed data can be stored in PostgreSQL | ✅ implemented and validated | 12 217 enregistrements jobs interrogés dans PostgreSQL. |
| 3 | descriptions are chunked | ✅ implemented and validated | 30 955 chunks V2 publiés, identité texte/chunk vérifiée. |
| 4 | embeddings can be created | ✅ implemented and validated | 30 955 vecteurs calculés dans 484 lots valides. |
| 5 | embeddings can be stored in pgvector | ✅ implemented and validated | Tous les vecteurs stockés comparés à tous les checkpoints, écart maximal zéro. |
| 6 | semantic retrieval works | ✅ implemented and validated | Cinq questions RAG sur V2 ; recherche cosinus et plan HNSW mesurés. |
| 7 | metadata filtering works | ✅ implemented and validated | Rôle, séniorité, compétences et Remote extraits ; filtres pays de l’interface vérifiés. |
| 8 | analytics works | ✅ implemented and validated | Cinq réponses réconciliées avec SQL indépendant. |
| 9 | Analytics/RAG routing works | ✅ implemented and validated | Cinq routes analytics et cinq routes RAG conformes. |
| 10 | grounded RAG works | ✅ implemented and validated | 67 claims reliés à des citations exactes dans les chunks V2. |
| 11 | sources are returned | ✅ implemented and validated | 25 références aux jobs réels retournées ; sources visibles dans Streamlit. |
| 12 | FastAPI exposes real endpoints | ✅ implemented and validated | Six routes demandées HTTP 200 sur V2. |
| 13 | Streamlit uses those endpoints | ✅ implemented and validated | Trois pages vérifiées dans le navigateur avec données et réponses réelles. |
| 14 | Docker configuration is usable | ⚠️ implemented but not fully validated | Schéma officiel et 16 contrôles statiques passent ; Docker/Compose non exécutés car indisponibles. |
| 15 | meaningful tests exist | ✅ implemented and validated | 61 tests réussis, dont trois tests PostgreSQL réels. |
| 16 | CI exists | ✅ implemented and validated | Workflow présent et inspecté ; exécution hébergée non observée. |
| 17 | README documents the real implementation | ✅ implemented and validated | Architecture, commandes, V2, modèle local et limites documentés. |
| 18 | no secrets are committed | ✅ implemented and validated | Inspection des fichiers suivis et de l’historique, zéro résultat ; .env ignoré. |
| 19 | no fake metrics are reported | ✅ implemented and validated | Comptes et latences mesurés ; aucun score de pertinence inventé. |
| 20 | no fake citations are generated | ✅ implemented and validated | Toutes les citations des questions et du POST RAG direct correspondent à PostgreSQL. |

Bilan : **19 ✅, 1 ⚠️, 0 ❌**. Les composants critiques de l’application locale fonctionnent avec V2. La livraison n’est pas déclarée entièrement validée sous Docker tant que le critère 14 n’a pas été exécuté sur une machine disposant de Docker.

## 12. Comparaison V1 / V2 : uniquement des mesures

Baseline V1 : `2026-09-25T14:04:42.666141+00:00`. Validation V2 : `2026-10-11T16:11:00.613823+00:00`. Les cinq questions sont identiques.

| Question RAG | Jobs / chunks V1 | Jobs / chunks V2 | Jobs cités communs | Latence V1 | Latence V2 |
| --- | --- | --- | ---: | ---: | ---: |
| What responsibilities are expected from Senior Data Engineers? | 6 / 6 | 6 / 6 | 1 | 15.165 s | 9.552 s |
| What skills are commonly associated with Kubernetes? | 6 / 6 | 6 / 6 | 1 | 15.078 s | 7.439 s |
| What AWS-related responsibilities appear in Data Engineer roles? | 6 / 6 | 6 / 6 | 2 | 9.643 s | 8.718 s |
| What are common requirements for Machine Learning Engineer positions? | 6 / 6 | 6 / 6 | 2 | 10.368 s | 8.243 s |
| What responsibilities appear in remote Data Analyst roles? | 1 / 1 | 1 / 1 | 1 | 6.646 s | 3.186 s |

La récupération garde le même nombre de jobs dans ces cinq cas (6, 6, 6, 6, 1) ; les sources choisies changent en partie. Les latences observées V2 sont plus faibles dans ce lot, **sans permettre d’attribuer à V2 un gain causal de performance** : les mesures ont été effectuées à des dates différentes, avec une charge et des caches différents, et la baseline V1 coexistait avec le calcul V2. Aucun Recall@K, MRR, NDCG, score humain de pertinence ni gain de qualité chiffré n’a été inventé. La traçabilité passe pour les deux versions ; elle n’est pas une mesure complète de pertinence.

## 13. Limites restantes et portée de la livraison

1. **Docker absent** : validation statique uniquement ; les commandes de construction et de lancement doivent être exécutées sur un environnement équipé.
2. **CI hébergée** : configuration inspectée, aucun résultat de run GitHub Actions confirmé.
3. **Génération optionnelle** : la validation utilise la synthèse locale extractive. Les fournisseurs OpenAI/Ollama optionnels n’ont pas été testés en conditions réelles.
4. **Données historiques** : collecte en janvier 2024 ; dates de publication absentes, géographie et taxonomie incomplètes, salaires non estimés. L’absence de France dans l’échantillon ne décrit pas le marché actuel.
5. **Évidence limitée** : un seul job pour Remote Data Analyst ; les décomptes RAG concernent les postings sélectionnés.
6. **Benchmark** : pas de jugements de pertinence annotés ; comparaison à des moments différents, sans benchmark matériel isolé.
7. **V1 conservé** : deux vecteurs nuls mesurés dans le baseline V1. Ils ne concernent pas l’index actif V2, qui contient zéro vecteur nul.
8. **Dépendances** : deux avertissements de dépréciation dans les tests, sans échec.
9. **Exploitation locale** : PostgreSQL distant requiert la disponibilité du projet Supabase et du réseau. FastAPI/Streamlit doivent fonctionner pour utiliser l’interface.

Aucun changement d’architecture n’a été nécessaire pendant les contrôles finaux du 11 octobre. Le correctif de lecture paginée antérieur résolvait l’échec SSL et conservait V1, les jobs et les checkpoints.

## 14. Artefacts finaux vérifiables

| Artefact local | Contenu |
| --- | --- |
| [`final-v2-index-audit.json`](../evaluation/results/final-v2-index-audit.json) | Comptes, état V2, dimensions, normes, extension, HNSW et liens aux jobs. |
| [`final-v2-storage-verification.json`](../evaluation/results/final-v2-storage-verification.json) | Comparaison exhaustive des 30 955 embeddings aux 484 checkpoints. |
| [`final-v2-query-plan.json`](../evaluation/results/final-v2-query-plan.json) | EXPLAIN ANALYZE réel de la recherche cosinus non filtrée V2. |
| [`final-v2-api-routes.json`](../evaluation/results/final-v2-api-routes.json) | Requêtes, réponses HTTP et latences des six routes. |
| [`final-v2-validation.json`](../evaluation/results/final-v2-validation.json) | Dix questions exactes, réponses, filtres, sources, claims, SQL et latences. |
| [`final-v2-traceability.json`](../evaluation/results/final-v2-traceability.json) | Bilan des 25 références, 67 claims et sources du POST RAG direct. |
| [`final-v1-baseline.json`](../evaluation/results/final-v1-baseline.json) | Mesures historiques V1 des mêmes questions. |
| [`final-v1-v2-comparison.json`](../evaluation/results/final-v1-v2-comparison.json) | Comparaison mesurée des cinq questions RAG. |
| [`final-v2-checks.json`](../evaluation/results/final-v2-checks.json) | Résultats des tests, PostgreSQL, Ruff et recherche de placeholders. |
| [`secrets-inspection.json`](../evaluation/results/secrets-inspection.json) | Inspection finale sans reproduction de valeurs sensibles. |
| [`docker-static-validation.json`](../evaluation/results/docker-static-validation.json) | Seize contrôles statiques et commandes Docker explicitement non exécutées. |
| [`ui-v2/ui-validation.json`](../evaluation/results/ui-v2/ui-validation.json) | Bilan manuel des trois pages ; captures et texte de l’assistant dans le même dossier. |
| [`final-v2-release.json`](../evaluation/results/final-v2-release.json) | Hash de livraison, commit Python validé, comptes et limites de la livraison. |

Ces artefacts sont enregistrés localement dans `evaluation/results/` et ignorés par Git. Le code et le présent rapport sont versionnés ; les CSV, modèles, checkpoints, journaux et secrets restent locaux.

## 15. Utilisation et reproduction des contrôles

Pour utiliser l’application déjà chargée, démarrer les services suivants depuis le dossier de l’application, chacun dans son terminal :

```powershell
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
.\.venv\Scripts\python.exe -m streamlit run app/Home.py --server.address 127.0.0.1 --server.port 8501
```

Interface : `http://127.0.0.1:8501`. Documentation API : `http://127.0.0.1:8000/docs`. Le chargement de données et l’indexation sont déjà effectués ; un rechargement volontaire invalide les index et impose une nouvelle indexation.

Les commandes d’audit, de vérification de stockage, des dix questions, de comparaison, des tests PostgreSQL et de Ruff figurent dans `evaluation/README.md`. Les relancer suppose une base accessible et, pour les questions HTTP, FastAPI démarré.
