# Finalisation des tâches restantes hors Docker

> Dated 30 October 2026 record. The [31 October validation summary](PROJECT_VALIDATION_SUMMARY.md) adds fresh checks and the owner-reported Docker runtime; the non-Docker scope and measurements below describe that earlier mission.

Date : **30 octobre 2026**. Projet : Data Job Market Intelligence.

Répertoire : `C:\Users\HP\Documents\ChatGPT\Data Job Market Intelligence\data-job-market-intelligence`.

**Résultat : corrections ciblées réalisées et validées localement.** Les quatre
tentatives mesurées du mode génératif restreint donnent désormais une réponse
acceptée, sans fallback. Cela ne valide ni les paraphrases libres ni une qualité
générale sur d'autres questions. Les 193 tests passent, PostgreSQL inclus.
La rotation du mot de passe reste une action de l'utilisateur et la CI hébergée
reste non vérifiée. Aucun commit, push ou déploiement n'a été effectué.

Les artefacts de cette mission sont dans
[`evaluation/results/nondocker-finalization-2026-10-30/`](../evaluation/results/nondocker-finalization-2026-10-30/).
Ils restent locaux et sont ignorés par Git. Les rapports antérieurs ont été conservés.

## A. État initial

Statut de l'audit : **Terminée et validée**.

Les trois références demandées ont été lues :

- [validation-report.md, état du 29 octobre](../evaluation/results/rag-local-optimization/validation-report.md) ;
- [performance-report.md, mesures du 28 octobre](../evaluation/results/rag-local-optimization/performance-report.md) ;
- [guide local](rag-local-optimization.md), actualisé à la suite de cette mission.

L'état initial comportait 176 tests réussis, dont trois tests PostgreSQL, six
routes HTTP validées, un mode extractif fonctionnel, une interface déjà contrôlée
et une synthèse naturelle qui revenait systématiquement à des citations
extractives sur les tentatives Senior Data Engineer et AWS.

Les comptes étaient de 12 217 offres, 23 638 chunks V1 et 30 955 chunks/embeddings
V2 de dimension 384. Le corpus a été collecté du **12 au 17 janvier 2024** ; ce
n'est ni une collecte actuelle ni une série temporelle des publications.

Le dépôt avait déjà des changements non commités : code LLM/RAG, documentation,
tests et fichiers SQL pédagogiques. Ces éléments ont été préservés. Au début de
cette reprise, Ollama était accessible, mais FastAPI et Streamlit étaient arrêtés.
Ils ont été redémarrés après le benchmark séquentiel.

Les tâches reprises sont limitées au prompt/contrôle génératif, aux protections
des diagnostics, aux tests pertinents, à la CI Python et à la documentation.
La campagne complète historique de stockage, les dix questions et la comparaison
V1/V2 n'ont pas été relancées inutilement.

## B. Modifications effectuées

Statut : **Terminée et validée**, dans les limites précisées ci-dessous.

| Problème constaté | Fichier modifié ou ajouté | Correction / justification | Validation associée |
|---|---|---|---|
| Le modèle reprend le titre de métier de la question et généralise la phrase. | `src/prompts/selected_summary.py` ; `src/rag/service.py` | Prompt compact séparé ; demande explicite d'attribution à une annonce. Le modèle reçoit les phrases sélectionnées, sans la question complète. La sélection et le contrôle de pertinence utilisent toujours la question. Le chemin legacy conserve son contrat. | Diagnostic réel avant, benchmark réel après, tests API/runtime. |
| Une ligne source sans point final est rejetée si Qwen ajoute seulement un point. | `src/rag/grounding.py` | Autoriser exclusivement ce point de présentation. La citation originale reste exacte. Aucun mot, acteur, nombre, modalité ou technologie supplémentaire n'est autorisé ; les virgules internes et ponctuations de la source ne sont pas supprimées. | Cinq tests sur ce cas : attribution valide, ajout de contenu, généralisation, point d'interrogation/exclamation ; régression existante question → affirmation. |
| Une nouvelle session commence dans le chemin configuré, potentiellement lent. | `app/components/ui.py` ; `tests/test_assistant_ui.py` | **Extractive fast** devient le choix initial d'une nouvelle session. Une préférence existante et le choix explicite Configured default restent possibles. L'API sans champ conserve son comportement. | Tests de persistance/contrat UI et observation du choix initial dans le navigateur. |
| Les diagnostics tiers peuvent interpoler des paramètres ou des secrets dans une erreur. | `src/config/security.py` ; `src/config/logging_config.py` | Masquage des valeurs configurées et encodées, URI PostgreSQL et Bearer après formatage, traceback inclus. Les formatters spécialisés du serveur sont conservés. | Tests avec secrets synthétiques, messages interpolés, exception et formatter Uvicorn. |
| Des erreurs Pydantic ou SQLAlchemy peuvent afficher des valeurs d'entrée/paramètres. | `src/config/settings.py` ; `src/database/connection.py` | `hide_input_in_errors=True` et `hide_parameters=True`. Le chargement `.env` littéral et la priorité de l'environnement restent inchangés. | Tests de chargement, représentation, erreur de validation et option moteur ; tests PostgreSQL. |
| Une mesure générative peut être confondue avec un fallback ou une abstention. | `evaluation/generative_validation.py` | Évaluation ciblée 1.5B uniquement, séquentielle, avec échauffement, deux répétitions, compteurs conditionnés aux vraies tentatives, citations SQL et empreintes. Refus d'écraser une mesure existante. Aucun téléchargement. | Deux tests de calcul des taux, dont exclusion des échauffements et abstentions ; benchmark réel de neuf cas. |
| Les nouveaux prompts doivent être traçables. | `evaluation/local_benchmark.py` ; `api/main.py` | Ajouter le prompt séparé aux empreintes des sources de benchmark et de l'API chargée. | Aucune dérive d'empreinte du benchmark final ; en-tête HTTP comparé aux fichiers actuels. |
| Les commandes ordinaires peuvent produire une trace brute sensible. | `evaluation/safe_checks.py` | Pytest/Ruff en sous-processus avec sortie masquée avant sauvegarde/affichage. Surcharges limitées au processus, opt-in PostgreSQL explicite. | Exécution ciblée puis campagne finale ; aucun changement de `.env`. |
| Le scan doit inclure les journaux et anciens rapports locaux. | `evaluation/security_inspection.py` | Inspection des fichiers suivis/non ignorés et diagnostics locaux, sans imprimer les correspondances secrètes. Contrôle des exemples fictifs et du suivi Git de `.env`. | Résultat consigné dans `security-final.json`, avec périmètre et limites. |
| La séparation CI entre tests locaux et base externe est implicite ; le formatage n'est pas contrôlé. | `../.github/workflows/ci.yml` | Ajout du contrôle de formatage ; commande Python explicite `pytest -q -m "not live" --tb=short`, `RUN_DB_INTEGRATION=0`, `LLM_PROVIDER=extractive`. | YAML lu localement, commandes et dépendances vérifiées, 190 tests hors live et 3 live collectés séparément. |
| Le caractère historique doit rester visible et les résultats récents distingués des anciens. | `README.md` ; `app/Home.py` ; `docs/rag-local-optimization.md` | Introduction explicitement historique, lien vers ce rapport, remplacement d'un libellé « Live charts » par « Charts », guide des évaluations ciblées. Pas de refonte du design. | Relecture ciblée ; notice historique observée dans Streamlit. |
| La rotation doit être réalisable sans partager la valeur. | `docs/rotation-secrets.md` | Procédure manuelle Supabase/Windows, priorité DATABASE_URL/DB_PASSWORD, encodage, redémarrage et contrôle sans affichage de `.env`. | Source du chargement inspectée, tests synthétiques et documentation officielle consultée. La rotation distante n'a pas été réalisée. |

Les tests ajoutés ou adaptés pour cette reprise sont dans
`tests/test_grounding.py`, `tests/test_rag_runtime.py`,
`tests/test_generative_validation.py`, `tests/test_secret_handling.py` et
`tests/test_assistant_ui.py`. Le total augmente de **176 à 193**, soit 17 cas
supplémentaires. Les régressions existantes couvrent aussi les sources absentes,
fausses citations, technologies ajoutées, négations, acteurs, réponses tronquées,
timeouts, refus et réponses structurées des deux endpoints.

## C. Validation technique

Statut : **Terminée et validée** pour les contrôles locaux exécutés.

| Contrôle | Résultat réellement observé |
|---|---|
| Tests ciblés avant finalisation | 127 réussis, deux avertissements, 18,54 s. |
| Suite complète avec PostgreSQL activé | **193 réussis**, deux avertissements, 32,53 s ; aucune erreur ni test sauté. |
| Tests PostgreSQL | Les trois tests `live` ont été exécutés dans cette suite ; lectures de la base, linkage, index et citations. |
| Ruff | Tous les contrôles réussis. |
| Formatage | **118 fichiers déjà formatés** après correction d'un repli de ligne dans `app/Home.py`. |
| Dépendances installées | `pip check` : aucune incompatibilité déclarée. |
| API actuelle | Six routes distinctes requises : statut 200 ; sept appels incluant un cas supplémentaire d'abstention. |
| Identité du serveur | `X-Code-Revision` identique à l'empreinte attendue ; instance de ce démarrage identifiée. |
| SQL | Pourcentage Python confronté à une requête indépendante PostgreSQL ; résultat conservé : 5 121 / 12 217, soit 41,92 %. |
| RAG HTTP | Réponse extractive Senior Data Engineer avec sources contrôlées en PostgreSQL ; société inexistante : abstention sans génération. |
| Streamlit | Santé 200 ; mode initial Extractive fast ; mode génératif réellement utilisé dans AI Assistant, deux sources et compte de preuves visibles. |
| Données | 12 217 offres, 23 638 chunks V1, 30 955 chunks/embeddings V2 ; état complet V2, 384 dimensions ; comptes/empreinte d'état inchangés avant et après. |

Le premier passage de formatage a identifié une seule mise en forme de ligne
dans Home. Elle a été corrigée puis Ruff et le contrôle complet de formatage ont
été rejoués. La suite de tests déjà réussie n'a pas été répétée pour cette seule
modification de mise en forme. L'historique de ce contrôle reste dans
`final-quality-checks.json`.

### Avertissements examinés

Le code installé est FastAPI 0.141.1, Starlette 1.6.0, HTTPX 0.28.1 et AnyIO 4.15.1.
Deux avertissements proviennent de `starlette.testclient` : compatibilité HTTPX
dépréciée au profit de HTTPX2, et utilisation de l'alias déprécié
`anyio.abc.BlockingPortal`.

Le code applicatif n'utilise pas directement cet alias. Aucune modification de
`site-packages`, aucun filtre qui cache ces avertissements et aucune migration de
dépendances n'ont été effectués pour les supprimer artificiellement. Les tests
restent réussis et `pip check` reste propre. La migration du client de test ou de
Starlette doit être traitée comme une mise à jour de dépendances distincte, avec
sa propre validation de compatibilité. Statut du diagnostic : **Terminée et
validée**. Les deux avertissements restent visibles ; aucune correction de
dépendance n'est revendiquée.

Références primaires : [TestClient Starlette](https://starlette.dev/testclient/),
[signalement de l'alias AnyIO dans Starlette](https://github.com/Kludex/starlette/issues/3497),
[BlockingPortal AnyIO](https://anyio.readthedocs.io/en/stable/threads.html).

### Contrôle manuel de l'assistant

Une nouvelle session affiche Extractive fast. Après sélection volontaire de
Generative Ollama, la question Senior Data Engineer donne :

- route **RAG** ;
- libellé **Ollama · Natural synthesis · 23.9 s** ;
- deux affirmations attribuées à leurs annonces, références **S1/S2** ;
- **2 retrieved job postings** et leurs liens ;
- notice rappelant que le support sémantique n'est pas vérifié indépendamment.

Cette durée est celle affichée par l'interface, distincte du protocole de
benchmark après échauffement. Le test n'a pas été assimilé à une mesure de débit.
La [capture du contrôle](assets/assistant-verified-2026-10-30.png)
et `ui-validation.json` conservent la preuve. Les autres pages et le design déjà
validés n'ont pas subi une nouvelle campagne exhaustive.

## D. Résultats du RAG génératif

Statut du mode restreint sur les cas mesurés : **Terminée et validée**.

### Diagnostic des rejets

Les sorties réelles de l'ancien prompt ont été capturées avant le contrôle, sur
les deux questions problématiques, avec les mêmes phrases sources sélectionnées :

1. **Senior Data Engineer** : Qwen ajoute « Senior Data Engineers are expected to »,
   retire une virgule et transforme notamment « Mentors » en « mentor ». Le
   diagnostic `unsupported_entity` identifie ici un titre ajouté à la phrase,
   pas une organisation inventée. Le sens peut être plausible, mais la portée
   générale et la transformation grammaticale dépassent la politique fermée.
2. **AWS** : Qwen ajoute un sujet général sur les rôles, supprime un intitulé de
   tâche et remplace plusieurs expressions. Ce n'est pas un échec de parsing JSON
   ou de source_id : la reformulation sort des formes autorisées et reste rejetée.
3. **Après correction du prompt** : l'attribution devient correcte, mais le modèle
   ajoute un point à une ligne source non ponctuée. Ce seul écart de présentation
   a reçu la correction ciblée. Une suppression d'intitulé dans la phrase AWS
   reste rejetée, même si elle peut être une reformulation raisonnable.

Les références aux sources restent attribuées par Python. La vérification exige
une citation exacte dans le chunk et un ID connu. Aucun seuil lexical général
n'a été abaissé et aucun modèle lourd d'inférence sémantique n'a été ajouté.

### Protocole comparable et limites

Benchmark final : neuf cas, comprenant **un échauffement exclu** puis deux
répétitions des quatre questions/filtres du rapport précédent. Modèle installé
**Qwen 2.5 1.5B**, CPU (`num_gpu=0`), budget 512 tokens, température 0,
20 candidats, reranking hybrid de 8 et contexte de 2. Les phrases fournies pour
Senior/AWS sont identiques à celles du diagnostic avant correction.

Ollama est maintenant en **0.40.13**, contre 0.40.11 dans les mesures du 28 octobre.
Un diagnostic de l'ancien prompt effectué ce 30 octobre en 0.40.13 reproduit les
deux rejets. Les médianes historiques restent affichées pour transparence ; la
différence de runtime, le prompt et la charge du PC empêchent d'attribuer un petit
écart de durée à une optimisation précise. Aucun gain de vitesse général n'est
revendiqué. Les empreintes du code du benchmark final correspondent aux fichiers
validés. Le 3B n'a pas été lancé : seulement 1,899 Gio de RAM physique étaient
libres avant cette mesure.

### Taux observés

| Mesure, hors échauffement | Ancien benchmark naturel | Benchmark final |
|---|---:|---:|
| Cas totaux | 8 | 8 |
| Vraies tentatives de génération | 4 | 4 |
| Réponses génératives acceptées | 0 / 4 | **4 / 4** |
| Taux accepté parmi les tentatives | 0 % | **100 %** |
| Fallbacks parmi les tentatives | 4 / 4, soit 100 % | **0 / 4, soit 0 %** |
| Cas sans appel LLM | 4 | 4 |
| Réponses acceptées après rejet d'une affirmation | 0 | **2 / 4** |
| Affirmations finales contrôlées dans les cas génératifs | Sortie de secours | **6** |
| Erreurs de traçabilité SQL des sorties finales | 0 | **0** |

Ce taux de 100 % porte sur **quatre tentatives seulement**, pas sur toutes les
questions possibles. Deux réponses AWS ne conservent qu'une affirmation après
rejet de l'autre. Sur les six affirmations acceptées, **quatre utilisent une
attribution à l'annonce et deux restent verbatim**. Il ne s'agit pas de six
paraphrases libres ou de six nouveaux faits. Les quatre autres cas sont des
abstentions sans génération : Kubernetes faute de phrase admissible dans le
contexte retenu, et la société inexistante.

### Latences mesurées

Temps du service, secondes, après échauffement ; deux répétitions par ligne.
La validation SQL du benchmark est mesurée séparément.

| Question | Avant, médiane | Final, médiane [min–max] | Appel LLM final, médiane | Sortie finale |
|---|---:|---:|---:|---|
| Senior Data Engineer | 11,394 | **11,553 [11,363–11,743]** | 10,531 | 2 affirmations par réponse, 2 sources |
| Responsabilités AWS | 16,625 | **16,535 [16,165–16,905]** | 14,168 | 1 affirmation par réponse, 1 source |
| Compétences Kubernetes | 0,751 | **0,777 [0,514–1,039]** | Non exécuté | Preuves insuffisantes |
| Société inexistante | 0,435 | **0,847 [0,370–1,324]** | Non exécuté | Preuves insuffisantes |

Tokens mesurés dans chaque répétition : Senior **333 entrée / 91 sortie** ; AWS
**366 entrée / 113 sortie**. Aucune valeur de tokens n'est attribuée aux cas sans
appel LLM. Aucun score de pertinence, d'hallucination ou d'entailment n'est inventé.

### Garanties et limites du grounding

**Extractive fast reste recommandé.** SQL produit des statistiques exactes sur
le corpus filtré. Le RAG présente des observations tirées des seules annonces
sélectionnées. Une abstention signifie que ce contexte ne justifie pas une réponse,
pas que le corpus entier ou le marché ne contient aucune réponse.

La présence littérale d'une citation garantit sa traçabilité, pas la vérité de
l'annonce ni toute son implication sémantique. Le contrôle accepte uniquement des
formes bornées : phrase complète, attribution neutre, inflexion initiale prévue,
et point final de présentation. Il préserve les contrôles de source, texte,
nombres, technologies, négation, modalité, acteurs et portée. Une relation
« les managers travaillent avec les ingénieurs qui construisent » ne permet pas
de dire « les managers construisent ». Les traductions et reformulations libres
restent hors validation. `semantic_entailment_verified` reste faux.

## E. Sécurité

| Tâche | Statut | Résultat |
|---|---|---|
| Secrets dans les fichiers suivis | **Terminée et validée** | Aucun secret configuré détecté dans le périmètre inspecté. |
| Chargement des variables | **Terminée et validée** | `.env` littéral, environnement prioritaire, champs SecretStr ; tests synthétiques réussis. |
| `.env` et `.env.example` | **Terminée et validée** | `.env` ignoré et non suivi, inchangé ; champs sensibles de l'exemple fictifs/vides. |
| Diagnostics, journaux et rapports locaux | **Terminée et validée** | Scan de valeurs connues/formes encodées et motifs d'URI/jetons ; aucun résultat. Protections de formatage testées. |
| Procédure de rotation | **Terminée et validée** | [Instructions Windows/Supabase](rotation-secrets.md) avec le bon secret effectif et les contrôles après rotation. |
| Rotation réelle du mot de passe | **Action manuelle requise** | Réalisée uniquement par l'utilisateur, puis mise à jour locale de `.env` et redémarrage des services. |

Le périmètre et le nombre final de fichiers inspectés figurent dans
`security-final.json`. Ce scan ne certifie pas tout l'historique Git, des valeurs
inconnues, les captures, l'historique des terminaux ou des services externes.
Un scan propre ne remplace jamais la rotation du mot de passe anciennement exposé.
Aucune valeur sensible n'est copiée dans ce rapport et aucune rotation distante
ou modification du fichier `.env` n'a été réalisée.

## F. Tâches non réalisées et prochaines actions

| Tâche | Statut | Raison exacte / prochaine action |
|---|---|---|
| CI Python, configuration locale | **Terminée et validée** | Installation des dépendances, Ruff et sélection de tests contrôlés ; 190 tests hors live, 3 live. Aucun secret externe nécessaire au job Python. |
| Exécution de GitHub Actions sur GitHub | **Implémentée mais non validée** | Aucun push ni dispatch hébergé réalisé ; un fichier YAML local n'est pas une preuve d'exécution hébergée. À vérifier sur GitHub lors d'une publication autorisée. |
| Mot de passe exposé | **Action manuelle requise** | Suivre la procédure de rotation ; l'agent ne modifie ni Supabase ni `.env`. |
| Généralisation des reformulations libres | **Bloquée** | La politique actuelle ne prouve pas l'entailment général. Étendre les cas annotés et l'évaluation humaine avant toute ouverture des règles. |
| Modèle Qwen 3B | **Bloquée** | Mémoire disponible insuffisante pour justifier ce lancement ; aucun téléchargement ni lancement effectué. |

Les deux avertissements de dépendances restent visibles et documentés ; aucune
fausse correction n'est annoncée. Une mise à jour contrôlée des dépendances peut
être envisagée séparément. Les deux abstentions du corpus n'ont pas été masquées
par une réponse générée. Aucun déploiement ni publication d'image n'a été ajouté.

**Docker et Docker Compose sont réservés intégralement à l'utilisateur. Aucune
commande, construction, exécution ou tâche de validation Docker n'a été effectuée
dans cette mission.** Les quatre fichiers protégés sont inchangés.

### Commandes reproductibles

Depuis le répertoire du projet, choisir les contrôles nécessaires, sans obligation
de tous les répéter. Les résultats de génération existants ne sont pas écrasés :

```powershell
# Tests hors base externe et qualité, sortie masquée
.\.venv\Scripts\python.exe -m evaluation.safe_checks --output evaluation/results/checks-new.json

# Inclure les trois tests PostgreSQL en lecture seule
.\.venv\Scripts\python.exe -m evaluation.safe_checks --live --output evaluation/results/checks-live-new.json

# Évaluation ciblée Qwen 1.5B local, deux répétitions, pas de 3B
.\.venv\Scripts\python.exe -m evaluation.generative_validation --repetitions 2 --output evaluation/results/generative-new.json

# Inspection locale sans affichage des valeurs secrètes
.\.venv\Scripts\python.exe -m evaluation.security_inspection --output evaluation/results/security-new.json
```

Pour démarrer FastAPI/Streamlit sans rechargement de données, suivre le
[guide local](rag-local-optimization.md). La procédure de rotation est distincte
et doit être effectuée manuellement, sans partager la nouvelle valeur.

## G. État final du dépôt et protection des données

HEAD de référence : **32ac590d4e800532182676e7a6aee723ae48a4c1**, branche
`codex/prise-en-main`. Le travail reste local et non commité ; ce hash ne contient
pas à lui seul les nouvelles corrections. Aucun commit, push ou déploiement.

Les fichiers modifiés/ajoutés par cette reprise sont ceux de la table B, ainsi
que les tests et ce rapport. L'inventaire complet est conservé dans
`git-status-final.txt` ; il distingue par ses chemins les changements locaux,
sans les attribuer tous à cette mission. Des modifications antérieures restent
présentes dans `.env.example`, les modules LLM/API/routage, les tests et les guides.
Les fichiers pédagogiques `docs/atelier-sql-offres-competences.md` et `docs/sql/`
sont conservés.

Vérifications de protection :

- `Dockerfile.api`, `Dockerfile.frontend`, `docker-compose.yml`, `.dockerignore` et
  `.env` sont identiques à leur état du début de mission, vérifié par empreinte.
- Aucune modification des identifiants Supabase, schémas, tables ou privilèges.
- Aucun ETL, chargement du corpus, migration, suppression de chunks ou
  réindexage de production. Aucun embedding **du corpus** recalculé. Le RAG
  calcule normalement les vecteurs des questions ; les tests créent leurs
  fixtures isolées SQLite comme auparavant, sans modifier PostgreSQL.
- Les lectures de benchmark sont marquées en lecture seule ; les contrôles HTTP
  utilisent uniquement des routes de lecture/question. Les comptes et l'état
  d'index sont identiques avant/après. Ce n'est pas un nouvel audit bit à bit de
  tous les vecteurs ; l'audit de stockage antérieur est préservé.

### Preuves locales conservées

| Artefact | Contenu |
|---|---|
| `initial-file-snapshot.json` ; `protected-file-verification.json` | État initial et confirmation des fichiers protégés inchangés. |
| `generation-diagnosis-before.json` | Sorties réelles de l'ancien prompt et raisons des rejets. |
| `generative-after.json` | Mesure intermédiaire du prompt corrigé, avant tolérance du point final ; préservée. |
| `generative-final.json` ; `generative-final-source/` | Protocole final, neuf cas, taux, citations, tokens, durées et empreintes. |
| `focused-checks.json` ; `final-quality-checks.json` | Tests ciblés, suite complète, Ruff et suivi de la correction de formatage. |
| `live-api-checks.json` | Identité API, routes, SQL indépendant, RAG, abstention et état de base. |
| `ui-validation.json` ; `ollama-accepted-ui.png` | Manipulation réelle de Streamlit et réponse Ollama acceptée. |
| `ci-inspection.json` | Workflow local, sélection de tests et cohérence des dépendances ; pas une exécution GitHub. |
| `security-final.json` ; `git-status-final.txt` | Périmètre du scan final et état local du dépôt. |

La conclusion reste limitée aux preuves recueillies : le chemin génératif borné
fonctionne sur les cas testés, l'extractif demeure le choix recommandé sur ce PC,
et la rotation des identifiants comme la vérification CI hébergée ne sont pas
présentées comme terminées.
