# Rapport détaillé — Data Job Market Intelligence

**État mesuré : 25 septembre 2026, 20 h 52 UTC.** Ce document décrit ce qui a été construit et vérifié dans le projet local. **La validation finale V2 n'est pas terminée** : les vecteurs V2 sont encore calculés, et leur publication atomique dans PostgreSQL n'a pas eu lieu. Les résultats ci-dessous sont donc explicitement séparés entre V1 validé, V2 préparé/en cours et contrôles restants. Les chiffres d'avancement sont un instantané, pas une promesse de résultat final.

## 1. Où se trouve le projet et comment lire son histoire

- Racine Git : `C:\Users\HP\Documents\ChatGPT\Data Job Market Intelligence`.
- Application : `C:\Users\HP\Documents\ChatGPT\Data Job Market Intelligence\data-job-market-intelligence`.
- Code et documentation suivis par Git : 105 fichiers avant l'ajout du présent rapport.
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

Le dernier commit de code vérifié au moment de cet instantané est `f216ba112eb8a5cc498de6e0f823ff8301ab942f`. Le hash changera si le présent rapport est commité, et pourra encore changer après les corrections éventuelles de la validation V2.

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

Le dernier point est une limite **mesurée**, et non masquée : deux embeddings LSA V1 n'ont pas de direction utilisable pour une similarité cosinus. Le rapport `evaluation/results/final-v1-index-audit.json` marque donc son contrôle global comme échoué sur ce critère, même si les comptes, dimensions et liens aux jobs passent. V2 vise à remplacer l'index de recherche actif tout en gardant V1 disponible pour revenir en arrière.

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

## 6. FastAPI, Streamlit et interface créée

`api/main.py`, `api/dependencies.py` et `api/routes/health.py` exposent l'application HTTP. Les six routes explicitement demandées ont déjà renvoyé **HTTP 200 avec V1 actif** : `GET /health`, `GET /api/analytics/overview`, `GET /api/analytics/skills`, `GET /api/analytics/jobs`, `POST /api/assistant/query` et `POST /api/rag/query`. Ce contrôle sera répété une fois V2 activé. Des routes supplémentaires fournissent filtres, matrice rôle-compétence, rapport qualité et réindexation protégée par jeton administrateur.

`app/Home.py` est l'accueil Streamlit. `app/pages/1_Market_Overview.py` présente les KPI, graphiques Plotly et la matrice rôle-compétence. `2_Job_Explorer.py` contient les filtres, les cartes d'annonces paginées, descriptions et liens source. `3_AI_Assistant.py` est l'interface de questions-réponses ; `app/components/design.py` et `ui.py` fournissent l'apparence et les composants communs.

Vérification manuelle déjà effectuée dans le navigateur **sur V1** :

- **Market Overview** : graphiques et carte de chaleur chargés ; le filtre Canada a mis les KPI à 625 jobs et a changé les graphiques.
- **Job Explorer** : 12 217 jobs sans filtre ; 625 avec Canada ; douze cartes paginées visibles ; une description réelle et le lien de l'annonce d'origine ont pu être ouverts.
- **AI Assistant** : la question France a affiché la route `ANALYTICS` et la réponse `0`. Une question sur les responsabilités de Senior Data Engineers a affiché `RAG`, six annonces récupérées, les références `[S1]` à `[S6]`, un compteur de preuves, une qualité d'évidence et des extraits avec liens originaux.
- Recherche statique de `placeholder`, `coming soon`, `lorem ipsum`, `fake response` et `TODO` dans les dossiers applicatifs : aucun contenu correspondant trouvé au moment du contrôle.

Cette observation prouve que l'interface V1 fonctionne, **pas** encore que l'interface utilisera V2 après bascule. FastAPI et Streamlit ont été arrêtés temporairement pour libérer de la mémoire pendant le calcul V2 ; ils devront être relancés pour la validation finale.

## 7. V2 : conception, calcul et état réel

V2 utilise le modèle local `BAAI/bge-small-en-v1.5` via FastEmbed/ONNX. Les chunks sont ciblés à 320 mots avec 40 mots de chevauchement et les embeddings à 384 dimensions. Le calcul se fait avant une transaction unique qui doit insérer les lignes de `job_chunks_v2` et créer `index_state` ligne 2. Tant que cette transaction n'a pas réussi, l'API continue à utiliser V1. Le modèle, le texte des chunks et la taille des lots entrent dans l'identité des checkpoints ; une reprise n'utilise donc pas silencieusement des lots incompatibles.

L'indexation complète a déterminé **30 955 chunks pour 12 217 jobs**. Ce nombre est confirmé par plusieurs reprises de la préparation ; ce n'est **pas encore** un compte V2 publié dans pgvector. Au point de mesure de 20 h 52 UTC :

| Élément V2 | Mesure |
| --- | ---: |
| Chunks attendus après découpage | 30 955 |
| Lots `.npy` complets sauvegardés | 233 |
| Vecteurs V2 sauvegardés dans ces lots | 14 912 |
| Chunks V2 présents dans PostgreSQL | **0** |
| Embeddings V2 présents dans pgvector | **0** |
| Ligne `index_state` V2 | **Absente** |
| Index actif vérifié | **V1** |

Un contrôle intermédiaire sur 5 888 vecteurs sauvegardés a trouvé des tableaux 384 dimensions contigus, finis, sans norme nulle et de norme proche de 1. Il ne constitue pas la vérification des 30 955 vecteurs ni de leur stockage final. Le processus V2 était actif lors de l'instantané ; le compteur local peut continuer à augmenter.

Le calcul a été interrompu par une mise en veille Windows le 25 septembre (journal système : sommeil de 14 h 38 à 20 h 23 UTC). Après le réveil, deux tentatives de lecture de **toutes** les descriptions en une seule requête ont échoué avec une connexion SSL PostgreSQL fermée. Le correctif `f216ba1` lit désormais les jobs par pages ordonnées et réessaie une page en cas de coupure. Le nouvel indexeur a relu les 12 217 jobs, reproduit les mêmes 30 955 chunks et réutilisé les checkpoints, sans modifier les données ni l'architecture V1/V2. Un petit processus local, non suivi par Git, demande temporairement à Windows d'éviter la veille automatique **seulement tant que l'indexeur actuel tourne** ; il libère cette demande quand l'indexeur sort. Une veille volontaire ou l'arrêt de l'ordinateur reste hors du contrôle de l'application.

## 8. Dix questions réelles : résultats V1 mesurés

Les dix questions exactes de la demande finale ont été envoyées par HTTP à `/api/assistant/query` avec V1 actif. `evaluation/final_validation.py` a enregistré les filtres, routes, réponses, documents récupérés, sources et latences dans `evaluation/results/final-v1-baseline.json`. Les cinq réponses d'analytics ont été comparées avec des requêtes SQL indépendantes ; chaque source et citation RAG a été reliée au job/chunk PostgreSQL et ses extraits vérifiés. **Aucun écart de route, SQL ou traçabilité n'a été trouvé sur ce lot V1.** Les latences incluent la charge de calcul V2 présente lors de la mesure et ne sont pas un benchmark matériel isolé.

| Question | Route, filtres extraits | Réponse mesurée, résumée sans changer les chiffres | Documents / sources | Latence HTTP | Ancrage vérifié |
| --- | --- | --- | --- | ---: | --- |
| How many Data Engineer jobs are in France? | analytics ; `job_title=Data Engineer`, `country=France` | 0 job dans cet instantané. | SQL ; sans source RAG | 4,325 s | Oui, compte SQL indépendant. |
| What are the top 10 most requested skills? | analytics ; aucun filtre | SQL 5 592 ; Python 5 121 ; Machine Learning 3 324 ; AWS 2 816 ; Azure 2 156 ; Spark 2 076 ; Excel 1 956 ; Tableau 1 828 ; Power BI 1 664 ; GCP 1 466. | SQL ; sans source RAG | 3,916 s | Oui, classement SQL indépendant. |
| What percentage of jobs mention Python? | analytics ; `skill=Python` | 5 121 / 12 217, soit 41,92 %. | SQL ; sans source RAG | 3,774 s | Oui, numérateur et dénominateur SQL. |
| Which cities contain the most job postings? | analytics ; aucun filtre | New York 357 ; London 239 ; Chicago 232 ; San Francisco 199 ; Washington 184 ; 296 villes inconnues. | SQL ; sans source RAG | 3,452 s | Oui, regroupement SQL indépendant. |
| What is the distribution of seniority levels? | analytics ; aucun filtre | Mid/Senior (source) 4 769 ; Lead 3 015 ; Senior 2 985 ; Unspecified 927 ; Junior 335 ; Executive 153 ; Intern 33. | SQL ; sans source RAG | 3,103 s | Oui, regroupement SQL indépendant. |
| What responsibilities are expected from Senior Data Engineers? | RAG ; `job_title=Data Engineer`, `seniority=Senior` | Pipelines/ingestion, SQL-modélisation-entrepôt, infrastructure cloud dans les annonces retenues. | 6 jobs ; `S1`–`S6` | 15,165 s | Oui, sources et citations V1 vérifiées. |
| What skills are commonly associated with Kubernetes? | RAG ; `skill=Kubernetes` | Parmi les six annonces récupérées : AWS 4, Docker 4, SQL 4, Azure 3, Python 3. Ce ne sont pas des fréquences du marché entier. | 6 jobs ; `S1`–`S6` | 15,078 s | Oui, sources et citations V1 vérifiées. |
| What AWS-related responsibilities appear in Data Engineer roles? | RAG ; `job_title=Data Engineer`, `skill=AWS` | Pipelines/ingestion et infrastructure/déploiement cloud dans des phrases où AWS apparaît avec la responsabilité. | 6 jobs ; `S1`–`S6` | 9,643 s | Oui, extraits AWS et sources V1 vérifiés. |
| What are common requirements for Machine Learning Engineer positions? | RAG ; `job_title=Machine Learning Engineer`, `skill=Machine Learning` | Dans six annonces sélectionnées : Machine Learning 6, Python 5, Deep Learning 4, PyTorch 3, TensorFlow 3 ; des responsabilités pipelines/cloud sont aussi citées. | 6 jobs ; `S1`–`S6` | 10,368 s | Oui, sources et citations V1 vérifiées. |
| What responsibilities appear in remote Data Analyst roles? | RAG ; `job_title=Data Analyst`, `workplace_type=Remote` | Une seule annonce pertinente sélectionnée soutient un thème fiabilité/surveillance/qualité. Généralisation limitée. | 1 job ; `S1` | 6,646 s | Oui pour cet extrait V1 ; preuve limitée. |

Les identifiants `S1` à `S6` sont locaux à chaque réponse et **ne sont pas des identifiants de jobs globaux**. Le JSON de validation contient pour chacun l'ID de job, l'URL originale, l'extrait et les claims. L'inspection montre que chaque référence RAG de ces dix tests V1 correspond à un vrai enregistrement ou chunk PostgreSQL. Il n'existe pas encore de tableau analogue V2 : **aucun score ni gain de V2 n'est inventé ici**.

## 9. Tests, lint, secrets, Docker et CI

- Suite complète exécutée avant le dernier correctif de pagination, avec `RUN_DB_INTEGRATION=1` : **59 tests réussis, 1 test V2 reporté**, deux avertissements de dépréciation de dépendances. Ce test V2 est reporté parce que l'index n'est pas actif, pas déclaré réussi.
- Après le correctif de lecture paginée, `tests/test_v2_quality.py` : **9 tests réussis**. Il couvre notamment l'ordre et la limite des pages, la qualité de synthèse et les garde-fous V2. La suite complète sera **relancée sur le code actuel une fois V2 actif**.
- Dernier lint sur le code actuel : `ruff check .` réussi ; `ruff format --check .` réussi pour **93 fichiers**.
- Inspection des secrets enregistrée dans `evaluation/results/secrets-inspection.json` : **104 fichiers Git suivis** au moment du scan, zéro motif sensible trouvé et `.env` non suivi. Ce scan doit être répété après le dernier commit, car le nombre de fichiers a augmenté depuis.
- Docker : exécutable indisponible sur cet ordinateur. Seize vérifications **statiques** de `docker-compose.yml`, Dockerfiles, dépendances, ports locaux, volumes, santé des services et présence de la configuration ont réussi. **Non exécutés** : `docker compose config`, `docker compose up --build`, construction locale des images et démarrage effectif des quatre services.
- CI : le fichier parent `.github/workflows/ci.yml` existe ; il installe les dépendances, lance Ruff/pytest, vérifie Compose et construit les images dans GitHub Actions. Aucun résultat d'exécution hébergée n'a été confirmé ici.

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

## 11. Définition de terminé : 20 critères, état provisoire

Les libellés de statut ci-dessous sont ceux demandés pour l'évaluation finale. Le tableau est **provisoire** tant que V2 n'est pas actif ; il ne vaut pas acceptation finale du projet.

| Nº | Critère original | Statut provisoire | Preuve ou manque |
| ---: | --- | --- | --- |
| 1 | Prétraitement opérationnel | ✅ implemented and validated | Trois CSV lus ; 12 217 jobs traités ; rapport qualité généré. |
| 2 | Stockage des données traitées dans PostgreSQL | ✅ implemented and validated | 12 217 lignes `jobs` interrogées. |
| 3 | Descriptions découpées en chunks | ⚠️ implemented but not fully validated | 23 638 V1 présents ; 30 955 V2 préparés mais non publiés. |
| 4 | Embeddings créés | ⚠️ implemented but not fully validated | 23 638 V1 ; V2 encore en calcul. |
| 5 | Embeddings stockés dans pgvector | ⚠️ implemented but not fully validated | V1 stocké ; V2 = 0 ligne publiée. |
| 6 | Recherche sémantique | ⚠️ implemented but not fully validated | V1 testé ; V2 actif non testé. |
| 7 | Filtrage par métadonnées | ⚠️ implemented but not fully validated | V1 et filtres UI vérifiés ; reprise V2 à contrôler. |
| 8 | Analytics | ✅ implemented and validated | Cinq questions SQL réconciliées indépendamment. |
| 9 | Routage analytics/RAG | ⚠️ implemented but not fully validated | Dix routes V1 correctes ; réexécution V2 en attente. |
| 10 | RAG fondé sur des preuves | ⚠️ implemented but not fully validated | Claims V1 reliés aux chunks ; V2 en attente. |
| 11 | Sources retournées | ⚠️ implemented but not fully validated | Sources V1 réelles ; sources V2 à vérifier. |
| 12 | Endpoints FastAPI réels | ⚠️ implemented but not fully validated | Six routes HTTP 200 sur V1 ; test V2 en attente. |
| 13 | Streamlit appelle les endpoints | ⚠️ implemented but not fully validated | Interface V1 inspectée ; interface V2 à reprendre. |
| 14 | Configuration Docker utilisable | ⚠️ implemented but not fully validated | 16 contrôles statiques ; Docker absent, aucune exécution Compose. |
| 15 | Tests significatifs | ✅ implemented and validated | Suite réelle et tests ciblés exécutés ; le résultat final V2 viendra en plus. |
| 16 | CI présente | ✅ implemented and validated | Workflow GitHub Actions présent ; exécution hébergée non observée. |
| 17 | README décrit l'implémentation réelle | ✅ implemented and validated | Commandes, architecture, limites et sécurité documentées. |
| 18 | Aucun secret commité | ⚠️ implemented but not fully validated | Scan de 104 fichiers négatif ; à répéter après le commit final. |
| 19 | Aucune métrique fabriquée | ✅ implemented and validated | Résultats rapportés avec mesures, origine et limites ; pas de score de pertinence inventé. |
| 20 | Aucune citation fabriquée | ⚠️ implemented but not fully validated | Traçabilité V1 vérifiée ; toutes les citations V2 restent à contrôler. |

## 12. Ce qu'il faut encore faire pour obtenir de vrais résultats finaux V2

1. Laisser le calcul local terminer ses **30 955** vecteurs prévus et vérifier que la transaction publie `job_chunks_v2` et `index_state` ligne 2, sans modifier les 12 217 jobs ni V1.
2. Exécuter `evaluation.check_index` pour confirmer les comptes exacts, la dimension 384, l'absence de vecteur nul/orphelin, la couverture des jobs et l'index cosinus.
3. Exécuter `evaluation.verify_v2_storage` pour comparer **chaque** vecteur pgvector à son lot calculé, pas seulement un échantillon.
4. Relancer FastAPI et Streamlit, puis vérifier les six routes et les trois pages sur **V2 actif**.
5. Exécuter `evaluation.final_validation` sur les dix questions exactes, avec route, filtres, réponse, documents, sources, latence et preuve réelle en base.
6. Exécuter `evaluation.compare_indexes` sur les cinq questions RAG, en indiquant les nombres de documents, chevauchements de jobs et latences réellement mesurés. Sans labels de pertinence humains, ne pas inventer un score de qualité.
7. Relancer la suite complète avec PostgreSQL, Ruff, l'inspection des secrets et les vérifications Docker possibles ; indiquer précisément que `docker compose up --build` n'est pas exécutable sur cette machine.
8. Mettre à jour ce rapport, les vingt statuts et le hash du **dernier** commit seulement après les contrôles ci-dessus. Ne pas appeler le projet « terminé » avant l'utilisation confirmée de l'index V2 par la recherche et l'interface.

Les commandes reproductibles correspondantes se trouvent dans `evaluation/README.md`. Une automatisation Codex attachée à cette tâche surveille la reprise de l'indexation et doit lancer les contrôles finaux quand V2 sera réellement actif.
