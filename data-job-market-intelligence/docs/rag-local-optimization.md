# Assistant RAG local : modes, mesures et vérification

> Current status: [31 October validation summary](PROJECT_VALIDATION_SUMMARY.md). The earlier Docker-unavailable statements below are dated observations, superseded by the owner-reported external-Supabase runtime. For safe startup, use [Setup](SETUP_AND_RUN.md).

État initial validé le 29 octobre 2026, puis corrections ciblées le 30 octobre.
Le [rapport hors Docker du 30 octobre](final-nondocker-completion-report.md) est
la référence des corrections du 30 octobre ; les mesures du 28–29 octobre restent conservées.
Les résultats reproductibles initiaux sont dans
`evaluation/results/rag-local-optimization/`. Les tableaux de mesures sont dans
`performance-report.md` ; l'état des validations est dans `validation-report.md`.

Contrôles du 29 octobre : 176 tests réussis, dont les 3 tests PostgreSQL ; Ruff et
formatage réussis. Les six routes API répondent avec le code actuel. Market
Overview, Job Explorer et AI Assistant ont été manipulés dans le navigateur.
Le mode extractif fonctionne ; Ollama sélectionne des citations dans le chemin
configuré, mais les reformulations naturelles du benchmark ont toutes utilisé un
fallback. Deux des cinq questions RAG HTTP signalent des preuves insuffisantes.
Les 48 contrôles Docker statiques réussissent ; aucun conteneur n'a été lancé.
Le renouvellement du mot de passe PostgreSQL précédemment exposé reste à réaliser.

Le 30 octobre, le prompt compact a été séparé dans
`src/prompts/selected_summary.py`. La sélection des sources utilise toujours la
question, mais la tâche de formulation reçoit uniquement les phrases sélectionnées,
afin d'éviter de copier une généralisation sur le rôle depuis la question.
Le contrôle conserve ses règles et tolère seulement un point final ajouté à une
ligne source qui n'avait pas de ponctuation terminale. La citation exacte reste
inchangée. Les taux et latences mesurés après correction sont dans le nouveau
rapport, sans compter une abstention ou un fallback comme génération acceptée.

Rapports locaux détaillés :

- Mesures locales : `evaluation/results/rag-local-optimization/performance-report.md`
- Validation locale : `evaluation/results/rag-local-optimization/validation-report.md`
- Interface : `evaluation/results/rag-local-optimization/ui-manual-validation.json`

Ces artefacts sont volontairement ignorés par Git et restent disponibles sur ce PC.

## Architecture conservée

CSV historiques → ETL existant → PostgreSQL/pgvector → SQL analytics ou RAG V2 →
FastAPI → Streamlit. Aucun ETL, réindexage, déplacement de tables ou changement de
vecteurs n'est nécessaire pour modifier la génération. Le dernier audit du
21 octobre a mesuré 12 217 offres, 30 955 chunks/embeddings V2 de 384 dimensions,
23 638 chunks V1 conservés et aucun chunk V2 orphelin.

Le paramètre de schéma est `djmi`, mais cet audit a trouvé les cinq tables
applicatives dans `public`. Cette mission ne migre pas les données. Le dataset
représente la collecte du 12 au 17 janvier 2024, pas le marché actuel.

La recherche utilise BAAI/bge-small-en-v1.5 local, puis un reranker cross-encoder
MiniLM ou hybrid. Les scores de classement ne sont ni des probabilités ni une
validation de vérité. Le modèle BGE est désormais réutilisé dans le processus ;
son espace et ses dimensions restent contrôlés face à l'état de l'index à chaque
requête. Aucun cache de réponses ou de résultats SQL n'a été ajouté.

## Choix explicite du mode

Le champ optionnel `response_mode` est commun aux deux endpoints de questions.
Le corps et les autres champs de réponse restent compatibles.

| Demande | Comportement |
| --- | --- |
| Champ absent ou `null` | Chemin configuré conservé. Avec Ollama, le strict expérimental sélectionne des citations et le code les remet en contexte complet. Avec le fournisseur extractif, la synthèse historique est conservée. |
| `extractive` | Sélection déterministe de phrases pertinentes complètes, au plus deux annonces. Toutes les affirmations vérifient `text == quote`. Aucun appel LLM. |
| `generative` | Ollama reçoit uniquement des phrases déjà sélectionnées. Il produit `text` et `source_id`, sans recopier le champ de citation. Le code rattache les citations et contrôle la reformulation. Sinon, fallback extractif explicite. |

Les questions numériques restent routées vers SQL quel que soit le mode demandé.
La page AI Assistant propose le choix et affiche le mode réellement retourné,
pas une déduction à partir du fournisseur choisi. Une nouvelle session choisit
désormais « Extractive fast », recommandé sur ce PC sans coût de génération.
Le choix explicite « Configured default » et le champ API absent conservent le
comportement serveur existant. Les préférences de session existantes sont gardées. La
prévisualisation automatique de Home utilise toujours ce chemin sans Ollama.

`metadata.mode` décrit la provenance effective : `extractive`, `ollama` ou
`extractive_fallback`. `output_mode` distingue citations exactes, citations
sélectionnées par LLM, synthèse contrainte et preuves insuffisantes.
`generation_attempted`, `generation_used`, `fallback_reason` et les rejets sont
séparés. Une absence de documents ou de phrases pertinentes n'appelle pas le LLM.
Un refus d'Ollama n'est pas transformé en affirmation factuelle.

## Trois niveaux de garantie

1. **Identité de source** : les identifiants S1, S2, etc. viennent du code et des
   documents récupérés, jamais d'URLs inventées par le modèle.
2. **Citation exacte** : la citation normalisée doit être présente littéralement
   dans le chunk correspondant. Les citations avec ID inconnu, fausses ou ambiguës
   sont rejetées. Les phrases sont conservées avec négation, acteur et modalités.
3. **Support et pertinence** : l'extraction utilise des ancres de technologies et
   des indices de tâches. La génération naturelle applique une politique fermée
   et conservatrice ; elle n'est pas une preuve générale d'entailment sémantique.

La génération accepte une phrase complète, une attribution neutre à l'annonce,
ou la transformation initiale impératif → gérondif. Un préfixe de rôle est
réécrit vers « This posting describes … » seulement si le titre de la source
correspond et si le prédicat reste intégralement identique à la phrase d'origine
(ou son gérondif). Cela évite d'adopter une généralisation sur tous les emplois.
Les nombres, négations, technologies, modalités et responsabilités ajoutées ne
sont pas autorisés par un simple recouvrement de mots. L'exemple « Managers work
with engineers who build pipelines » ne permet pas « Managers build pipelines ».

Cette politique rejette aussi des reformulations pourtant correctes et ne valide
ni la véracité de l'annonce ni le contexte absent du chunk. Les traductions et
paraphrases libres ne sont pas prises en charge par cette garde. Les labels de
qualité des preuves décrivent la couverture, pas une probabilité de vérité.
`semantic_entailment_verified` reste donc faux. La tolérance du point final ne
supprime aucun mot ni aucune ponctuation de la source ; elle ne transforme pas
une question en affirmation et n'autorise pas de paraphrase libre.

## Profilage

`metadata.timings_ms` mesure : réécriture, recherche, reranking, construction du
contexte, synthèse locale, préparation de génération, appel LLM, vérification,
construction de réponse et total du pipeline. Une étape non exécutée est `null`,
notamment `llm_generation` en mode extractif ; ce n'est pas une durée inventée.

`retrieval_timings_ms` sépare l'état d'index, l'acquisition du modèle, l'embedding
de requête et la recherche/matérialisation PostgreSQL. Ces sous-durées sont incluses
dans la recherche : il ne faut pas additionner les niveaux.

Ollama expose les tokens et, lorsqu'il les fournit, `usage.ollama_timings_ms` :
chargement, traitement du prompt, génération et total. Les nanosecondes du serveur
sont converties en millisecondes. Une réponse tronquée ou un JSON invalide est
rejeté ; la consommation mesurée reste disponible pour diagnostiquer le fallback.

Le total RAG exclut le routage initial et la sérialisation HTTP. La conversion de
réponse est mesurée dans `api_timings_ms`. La sérialisation JSON réelle, effectuée
une seule fois, est renvoyée dans `X-Serialization-Time-Ms` et `Server-Timing` :
l'inclure après coup dans son propre corps obligerait à sérialiser deux fois.
`X-Response-Time` mesure le traitement HTTP avant émission au client.

`X-App-Instance` change à chaque démarrage ; `X-Code-Revision` identifie les fichiers
chargés au démarrage. Ils permettent de vérifier qu'un ancien Uvicorn n'a pas
répondu à la place du serveur testé. Ils ne contiennent aucune configuration secrète.

## Configuration locale

Conserver les identifiants existants dans `.env` ; ne jamais remplacer ce fichier
par l'exemple s'il existe déjà. Les valeurs suivantes concernent uniquement le LLM :

```dotenv
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:1.5b
OLLAMA_URL=http://localhost:11434
OLLAMA_NUM_GPU=0
OLLAMA_NUM_PREDICT=512
OLLAMA_TIMEOUT_SECONDS=120
PROMPT_VERSION=v2
RAG_RETRIEVAL_K=20
RAG_RERANK_K=8
RAG_CONTEXT_K=2
RAG_RERANKER=hybrid
```

`OLLAMA_NUM_PREDICT` vide conserve la limite du serveur ; le budget 512 est explicite
pour les benchmarks optimisés. Il borne la génération mais peut provoquer un
fallback si le JSON est coupé : ce n'est pas une garantie de réponse complète.
Laisser `OLLAMA_NUM_GPU` vide permet la sélection automatique ; 0 utilise le CPU,
qui contourne le plantage Vulkan observé sur ce PC. Ces paramètres n'affectent pas
les embeddings déjà stockés. Aucun compte ni clé d'API n'est requis par Ollama local.

## Démarrage Windows

Dans PowerShell, depuis le dossier du projet :

```powershell
Set-Location 'C:\Users\HP\Documents\ChatGPT\Data Job Market Intelligence\data-job-market-intelligence'
ollama pull qwen2.5:1.5b
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Dans une seconde fenêtre, depuis le même dossier :

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/Home.py --server.address 127.0.0.1 --server.port 8501
```

Ouvrir http://127.0.0.1:8501. La configuration du frontend cible le port 8000 par
défaut. Un démarrage expérimental sur 8001 ne modifie pas automatiquement cette
adresse. Avant de libérer un port, vérifier l'identité du processus ; ne pas
terminer tous les processus Python. Ne pas exécuter `--load` ou `indexing --v2`
pour un simple redémarrage.

## Tests et benchmark reproductible

```powershell
.\.venv\Scripts\python.exe -m evaluation.safe_checks --output evaluation/results/offline-checks.json
.\.venv\Scripts\python.exe -m evaluation.safe_checks --live --output evaluation/results/live-checks.json
```

Ce sont deux options, sans obligation de les exécuter toutes les deux. Les
surcharges sont limitées au sous-processus, sans réécrire `.env`. Les tests
unitaires mockent Ollama et utilisent SQLite en mémoire.
Les trois tests PostgreSQL sont des lectures seules. Les échecs doivent rester
visibles, mais leurs traces doivent être filtrées avant partage : certains drivers
incluent des arguments de connexion dans les tracebacks complets.

```powershell
.\.venv\Scripts\python.exe -m evaluation.generative_validation --repetitions 2 --output evaluation/results/generative-validation-new.json
```

Cette évaluation ciblée du 1.5B évite de refaire les configurations déjà validées
et refuse d'écraser un résultat existant. Elle ne lance pas le 3B. Le benchmark
est séquentiel, utilise les mêmes quatre questions et filtres, un
échauffement exclu des statistiques, deux répétitions et un contexte de deux
annonces. Il vérifie la traçabilité dans PostgreSQL et les comptes avant/après.
Il ne charge pas plusieurs modèles Ollama à la fois. Le 3B est mesuré seulement
si la mémoire physique disponible après déchargement atteint le seuil de 3 Gio ;
sinon il figure comme `not measured`. Les erreurs et fallbacks ne sont pas retirés
des tableaux. Les durées des sorties de tailles différentes ne prouvent pas
qu'un reranker est intrinsèquement meilleur.

Un ancien code préservé peut être relancé avec `--phase baseline --source-snapshot`
pour obtenir une comparaison contemporaine, sans remplacer les fichiers du dépôt.
La nouvelle extraction et l'ancien assemblage de thèmes n'ont pas exactement la
même forme de sortie. Le mode génératif compact a une variante de prompt propre ;
il est identifié comme tel et ne doit pas être confondu avec le chemin legacy.

## Sécurité et limites

`.env` est ignoré par Git. Aucun secret ne doit apparaître dans les rapports,
commits ou captures. Un mot de passe PostgreSQL ayant été visible dans une trace
doit être renouvelé chez le fournisseur puis mis à jour localement. Cette mission
ne réalise aucune rotation distante ni migration de données.

Les chiffres vérifiés, les erreurs de connexion transitoires et les validations
encore non exécutées sont distingués dans le rapport. OpenAI et Docker runtime
restent hors des validations locales de cette optimisation.
