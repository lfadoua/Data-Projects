# Refonte premium de l'interface Data Job Market Intelligence

> Historical UI redesign report. Current test counts and separately sourced Docker evidence are in [the validation summary](PROJECT_VALIDATION_SUMMARY.md); the original measurements below are retained.

Date du compte rendu : **15 octobre 2026**. Le redesign est implémenté dans l'application Streamlit existante. FastAPI conserve les calculs métier, les accès PostgreSQL/pgvector et le routage Analytics/RAG. Ce document décrit les changements présents dans le code et distingue les vérifications exécutées des limites de validation.

## 1. Résultat et périmètre

L'application adopte une interface claire inspirée de la référence fournie : barre latérale DataJob, navigation sur six pages, barre de recherche, sélection du pays, héros illustré, quatre cartes KPI, graphiques coordonnés, statut V2 et aperçu de l'assistant connecté au backend. Les pages Market Overview, Job Explorer et AI Assistant partagent désormais les mêmes composants et le même thème. Validation et Settings sont de nouvelles pages fonctionnelles.

Les changements métier nécessaires au parcours sont limités à une route de diagnostic en lecture seule et à une recherche textuelle paginée. L'architecture Python/Streamlit/FastAPI est conservée. Aucune migration, ingestion ou réindexation n'a été exécutée pour cette refonte.

Le contrôle HTTP/SQL enregistré le **15 octobre 2026 à 00:16:36 UTC** confirme l'état suivant :

| Élément | État mesuré |
| --- | --- |
| Base utilisée | PostgreSQL |
| Annonces avant et après les contrôles | 12 217 |
| Chunks V2 avant et après les contrôles | 30 955 |
| Embeddings V2 avant et après les contrôles | 30 955 |
| Version active | V2 |
| Dimensions | 384 |
| Index prêt / partiel | `true` / `false` |
| Comparaison des volumes avant/après | Réussie |

Ces mesures établissent la conservation des volumes pendant les contrôles. Elles ne constituent pas une nouvelle comparaison exhaustive du contenu de chaque vecteur avec les checkpoints : cette validation appartient au rapport V2 du 11 octobre.

## 2. Pages et parcours implémentés

| Page | Comportement implémenté |
| --- | --- |
| Home | Héros illustré en SVG, trois repères fonctionnels, quatre KPI, compétences, carte mondiale/liste, villes, ancienneté, rôles, état V2 et aperçu RAG réel. |
| Market Overview | Filtres partagés, KPI filtrés, compétences, rôles, ancienneté, géographie, type de lieu de travail, matrice compétence × rôle et explications des données manquantes. |
| Job Explorer | Recherche textuelle, filtres, nombre de correspondances, cartes d'annonces en deux colonnes, badges de compétences, extraits, détails et liens originaux ; pagination précédente/suivante et sélection de page. |
| AI Assistant | Questions d'exemple, saisie de question, conversation en session, badge de route réel, réponse complète, statistiques SQL ou panneau de preuves RAG avec sources développables et liens. |
| Validation | Résultats datés de la validation V2, tableau des 20 critères, export CSV, provenance du snapshot, diagnostic d'index actuel et limites Docker/CI/fournisseurs. |
| Settings | Nombre d'annonces par page, cartes compactes, visibilité des détails techniques disponibles, informations sur le jeu historique et rafraîchissement des caches de lecture. |

### Navigation, recherche et filtres

La navigation repose sur `st.page_link` et `st.switch_page`. L'élément actif de la barre latérale correspond à la page affichée. La carte promotionnelle ouvre Job Explorer et le bas de la barre affiche un espace local générique.

La recherche du bandeau a deux parcours. Une expression ordinaire ouvre Job Explorer ; une saisie se terminant par `?`, ou commençant par certaines formulations anglaises reconnues, ouvre AI Assistant avec la question préremplie et soumise. Cette distinction est une heuristique d'interface ; le routage métier Analytics/RAG reste effectué par le backend.

Le pays est fourni par les facettes de l'API, avec **All countries** par défaut. Les filtres persistent dans l'état de session entre les pages : rôle, pays, ville, ancienneté, type de lieu de travail, entreprise et compétence. Un changement de filtre réinitialise la pagination. Market Overview, Job Explorer et les questions adressées à l'assistant réutilisent ce contexte ; Home réutilise également les filtres actifs.

Le paramètre de recherche textuelle porte sur le titre, l'entreprise et la description nettoyée. Il est combiné aux filtres existants. Les caractères `%`, `_` et `\` sont traités littéralement, les valeurs restent des paramètres SQL liés et la longueur maximale est de 200 caractères.

### Assistant et traçabilité

L'aperçu de Home appelle réellement `POST /api/assistant/query` avec la question « What responsibilities are expected from Senior Data Engineers? ». Son texte est un extrait de la réponse reçue. Le badge de route, la qualité des preuves, le nombre d'annonces récupérées et les puces de sources proviennent de cette réponse. Le bouton d'ouverture transfère la question et la réponse dans la conversation de la page AI Assistant.

Une réponse Analytics présente un résultat calculé et, lorsqu'elles existent, ses statistiques structurées. Une réponse RAG conserve le texte et les identifiants de citations retournés. Le panneau de preuves expose les extraits, les entreprises, les lieux connus et les URL originales. L'interface rappelle que les observations sur les annonces sélectionnées ne mesurent pas une fréquence dans l'ensemble du marché.

Les états vides, questions trop courtes, erreurs de validation HTTP, indisponibilités du backend et erreurs de chargement de l'aperçu disposent de messages dédiés. Des indicateurs de chargement accompagnent les appels de l'assistant. Une requête d'assistant peut attendre jusqu'à 150 secondes ; cette limite est un délai client, pas une promesse de temps de réponse.

## 3. Composants et thème réutilisables

| Fichier | Responsabilité |
| --- | --- |
| `app/components/design.py` | Coquille globale, barre latérale, héros, cartes KPI, anneau de progression, badges, panneaux, titres, puces, états vides et liens de sources. Échappement HTML des valeurs affichées. |
| `app/components/ui.py` | Client HTTP, caches de lecture, bandeau, recherche, état des filtres, rendu des réponses et détails des sources. |
| `app/components/charts.py` | Barres de compétences, rôles, donut d'ancienneté, carte/liste géographique et matrice compétence × rôle. |
| `app/components/dashboard.py` | Lecture de la preuve historique, KPI de Home, état actuel de l'index et aperçu de l'assistant. |
| `app/components/icons.py` | Logo, illustration du héros et icônes SVG locales, sans bibliothèque JavaScript ajoutée. |
| `app/components/preferences.py` | Préférences en session indépendantes des clés temporaires des widgets. |
| `app/assets/theme.css` | Couleurs, typographie, espacements, cartes, focus, survols et règles de mise en page responsive. |
| `.streamlit/config.toml` | Thème clair, couleurs Streamlit cohérentes et service des fichiers statiques locaux. |

Les tokens centraux reprennent le bleu `#2563EB`, le cyan `#0EA5E9`, le fond `#F6F9FE`, les cartes blanches, les bordures `#E6ECF5`, le texte `#111827`, le vert `#10B981` et le violet `#8B5CF6`. La barre latérale cible 240 px et la zone principale limite sa largeur à 1 680 px. La police préfère Inter, puis Segoe UI et Arial ; Inter n'est pas téléchargée ni intégrée comme fichier de police.

Les graphiques de rôles, d'ancienneté et la matrice utilisent Plotly. Les compétences utilisent des barres HTML/CSS avec un fond de piste et des valeurs calculées. Les cartes de compétences et les graphiques conservent des libellés et des informations de survol plutôt que de dépendre uniquement des couleurs.

La carte géographique emploie les codes pays et les effectifs renvoyés par l'API. Les marqueurs représentent les pays ; ils ne sont pas des coordonnées inférées pour chaque poste. Le fichier `app/static/geo/world_110m.json` permet de servir localement le fond cartographique de Plotly. La vue List conserve les pays connus ou inconnus ; la vue Map indique les effectifs dont le pays est inconnu. Les villes affichées sont issues des agrégats de l'API.

Les règles CSS ajustent les colonnes de Home sur tablette et le bandeau sur mobile. L'illustration décorative disparaît sur les petits écrans. Le focus clavier est visible et `prefers-reduced-motion` désactive les transitions. La présence de ces règles dans le code ne suffit pas à attester la conformité de toutes les pages sur tous les appareils : les observations navigateur sont consignées séparément ci-dessous.

## 4. Intégrations API conservées et extensions

| Endpoint | Usage dans l'interface |
| --- | --- |
| `GET /health` | Connectivité et présence d'index ; indicateur Connected/Unavailable. |
| `GET /api/system/status` | Nouvelle lecture de l'état enregistré de l'index, du nombre de chunks/vecteurs, de la dimension, de l'état partiel et du type de base. |
| `GET /api/analytics/overview` | Nombre d'annonces et distributions réelles, avec filtres. |
| `GET /api/analytics/skills` | Contrat existant conservé et vérifié ; Home et Market Overview utilisent les compétences de la réponse overview pour éviter un appel supplémentaire. |
| `GET /api/analytics/jobs` | Résultats filtrés et paginés ; paramètre optionnel `search` ajouté sans retirer les paramètres précédents. |
| `GET /api/analytics/filters` | Choix réels des contrôles. |
| `GET /api/analytics/skill-role` | Matrice des occurrences de compétences par famille de rôle. |
| `POST /api/assistant/query` | Routage existant Analytics/RAG, réponses, citations et métadonnées. |

Les autres routes existantes, notamment RAG et qualité, sont préservées. La nouvelle route de statut ne déclenche aucune construction d'index et ne renvoie aucune configuration de connexion. Son état Ready décrit les informations d'index et les effectifs disponibles ; ce n'est pas un test exhaustif des fournisseurs de modèles.

L'URL de l'API est lue depuis `STREAMLIT_API_URL`, puis depuis le fichier `.env` local si nécessaire, avec `http://127.0.0.1:8000` comme valeur par défaut. Les identifiants de base ne sont pas affichés dans l'interface.

Pour limiter les appels lors des reruns, les données analytiques sont mises en cache 45 secondes, la santé 15 secondes et les facettes 300 secondes. L'aperçu de l'assistant est mis en cache 600 secondes par URL, filtres et identité d'index. Les résultats de validation sont lus avec un cache de 60 secondes. Settings permet de vider les caches de lecture et de l'aperçu ; cela ne recharge pas les données et ne reconstruit pas l'index.

## 5. Données historiques et différences justifiées

La référence guide la composition, la palette et les proportions. Certains éléments sont adaptés pour que le produit reste fidèle aux données :

| Élément de la demande/référence | Choix implémenté et raison |
| --- | --- |
| Filtre de période récente | Indicateur **Historical dataset** : collecte du 12 au 17 janvier 2024, dates de publication indisponibles. |
| « Role Demand Trend » | **Job Distribution by Role** avec effectifs réels ; aucune série mensuelle fabriquée. |
| Croissance des KPI | Descriptions et statuts pertinents ; aucun taux de croissance inventé. |
| Notifications | Indicateur de santé API réel, sans notification fictive. |
| Carte centrée sur un seul pays | Vue mondiale des pays enregistrés, avec bascule Map/List et catégorie inconnue conservée. |
| Carte de profil/abonnement | **Local workspace** et action vers Job Explorer, sans compte ni paiement inventés. |
| Assistant illustratif | Réponse réelle du backend, sources et qualité de preuve réelles ; extrait compact sur Home. |
| Validation « 61 » et « 19/20 » | Snapshot de version daté, clairement distinct du diagnostic en direct et des nouvelles commandes de test. |
| Illustration du héros | Composition SVG locale adaptée à la grille Streamlit. |
| Mise en page exacte au pixel | Grille native Streamlit et composants Plotly/HTML/CSS ; les différences visuelles mesurées doivent être documentées avec les captures. |

Les catégories d'ancienneté ne sont pas regroupées arbitrairement. Les rôles **Other / Unclassified** restent présents dans les analyses. Les lieux absents ne sont pas complétés par supposition. Une annonce historique et son lien d'origine ne garantissent pas qu'un recrutement est encore ouvert.

Les KPI de validation lisent `app/assets/validation_snapshot.json`, daté du 11 octobre 2026. Si le fichier local `evaluation/results/final-v2-release.json` existe et correspond au commit source attendu, quelques résultats sont complétés depuis cet artefact. Les **19/20 critères et 95 %** décrivent donc la validation V2 historique ; ils ne mesurent pas le pourcentage d'acceptation du redesign.

## 6. Vérifications exécutées

### Suite Python et analyse statique

Pendant cette session de refonte, la commande avec intégration PostgreSQL a terminé avec **61 tests réussis, dont 3 tests PostgreSQL, en 25,32 secondes**. Les tests de l'API existants ont été étendus pour couvrir le statut d'index et la recherche : casse, combinaison avec pays, caractères littéraux, entrée ressemblant à une injection et rejet au-delà de 200 caractères.

Les contrôles finaux `ruff check .`, `ruff format --check .` et `compileall` sur `app`, `api` et `src` réussissent. Le snapshot historique affiché par l'interface conserve son propre horodatage et ne prétend pas refléter automatiquement ce nouveau lancement de pytest.

### Contrôles HTTP et rapprochement SQL

L'artefact local `evaluation/results/ui-redesign-api-validation.json` enregistre **14 contrôles réussis sur 14**. Il utilise de vraies requêtes HTTP et des rapprochements SQL indépendants en lecture seule. Les latences suivantes sont celles de ce passage local ; ce ne sont pas des moyennes ni des garanties de performance.

| Contrôle | HTTP attendu/observé | Résultat mesuré | Durée |
| --- | --- | --- | --- |
| Santé | 200 / 200 | Base connectée, 12 217 annonces, 30 955 chunks, index présent | 0,515 s |
| Statut système | 200 / 200 | V2, 30 955 vecteurs/chunks, 384 dimensions, prêt et non partiel | 0,367 s |
| Overview | 200 / 200 | Total SQL identique ; 625 annonces au Canada | 4,435 s |
| Compétences | 200 / 200 | Top 20 identique au calcul SQL indépendant | 0,532 s |
| Recherche Python | 200 / 200 | 4 851 correspondances textuelles ; contenu retourné vérifié | 6,343 s |
| Filtre Canada | 200 / 200 | 625 correspondances ; annonces retournées canadiennes | 0,545 s |
| Pagination offset 0 | 200 / 200 | 20 identifiants identiques à l'ordre SQL | 0,506 s |
| Pagination offset 20 | 200 / 200 | 20 identifiants identiques à l'ordre SQL, aucun chevauchement | 0,427 s |
| Recherche littérale `%` | 200 / 200 | 2 263 correspondances, identiques au SQL | 1,267 s |
| Recherche littérale `_` | 200 / 200 | 309 correspondances, identiques au SQL | 1,170 s |
| Recherche littérale de barres obliques inverses | 200 / 200 | 49 correspondances, identiques au SQL pour la chaîne envoyée | 1,083 s |
| Recherche de 201 caractères | 422 / 422 | Entrée rejetée conformément au contrat | 0,016 s |
| Question analytique | 200 / 200 | Route Analytics, 5 121/12 217 annonces mentionnent Python : 41,92 % | 2,182 s |
| Question descriptive | 200 / 200 | Route RAG V2, sources et citations vérifiées | 5,850 s |

Les cinq premières compétences vérifiées sont SQL **5 592**, Python **5 121**, Machine Learning **3 324**, AWS **2 816** et Azure **2 156**. La recherche textuelle Python à 4 851 résultats et la fréquence de compétence Python à 5 121 utilisent des définitions différentes : l'une recherche du texte dans les champs d'annonce, l'autre agrège les compétences normalisées. Cette différence ne doit pas être présentée comme une incohérence de comptage.

Pour la question descriptive sur les responsabilités des Senior Data Engineers, le backend a renvoyé six annonces et la qualité **Strong evidence**. Le contrôle a rapproché **6 sources, 6 chunks et 14 citations/extraits de claims** avec les enregistrements de la base. La réponse évoque les pipelines, SQL/modélisation/entrepôts et l'infrastructure cloud, en précisant qu'il s'agit d'observations sur les sources sélectionnées. Cette vérification de traçabilité n'est pas une mesure complète de la qualité sémantique de toute réponse possible.

L'artefact JSON et son script de contrôle se trouvent dans `evaluation/results/`, répertoire de résultats locaux ignoré par Git. Ils ne sont pas nécessairement présents dans un nouveau clone. Le résumé mesuré ci-dessus permet de conserver les faits du passage dans le rapport versionné.

### Contrôles navigateur et captures

Les six pages ont été ouvertes et inspectées dans le navigateur local. Les contrôles ci-dessous ont été effectués par interaction avec les widgets, puis lecture du résultat affiché.

| Scénario | Résultat observé |
| --- | --- |
| Home | Logo, icônes, illustration locale, quatre KPI, barres de compétences, carte mondiale, donut, rôles, statut V2 et aperçu IA chargés |
| Carte / liste | Les deux vues fonctionnent ; la liste conserve les comptes réels, dont les lieux inconnus |
| Filtre pays | Canada affiche 625 annonces ; la sélection persiste avec « View all » vers Market Overview |
| Recherche globale | Python ouvre Job Explorer ; avec Canada, 302 correspondances textuelles sont affichées |
| Pagination | Six cartes par page après changement dans Settings ; la page suivante affiche six autres enregistrements |
| Préférences | Six cartes et aperçus longs restent appliqués après navigation ; retour dans Settings : valeurs conservées |
| Recherche conservée | Revenir dans Job Explorer réaffiche Python dans le champ et dans le filtre de recherche |
| Recherche vide | `no-such-posting-zzvalidation` affiche zéro résultat et un message utile ; Clear search restitue 12 217 annonces |
| Filtre de rôle | Data Engineer affiche 1 751 annonces ; Reset filters restitue 12 217 annonces |
| Question Analytics | Python au Canada : 313 / 625, soit 50,08 % ; route et filtres affichés |
| Question RAG | Senior Data Engineers : route RAG, Strong evidence, six annonces, citations et panneau de sources ; première source développée avec extrait et lien réels |
| Aperçu Home | Open AI Assistant reprend sa vraie réponse avec les six sources ; l'historique précédent reste présent |
| Validation | 20 critères, date du 11 octobre, limite Docker et statut live distinct affichés |
| Settings | Préférences fonctionnelles et rafraîchissement des caches sans chargement ni réindexation |
| Responsive | Largeurs 1440, 1024, 768 et 375 px inspectées ; largeur du document égale à celle du viewport, sans débordement horizontal global |
| Menu mobile | Ouverture, navigation et fermeture vérifiées ; cartes empilées et recherche utilisable |

L'inspection a permis de corriger les SVG supprimés par le sanitiseur HTML, un en-tête transparent qui interceptait les clics, la grille tablette, l'espace réservé au menu replié, la pagination mobile et les clés de widgets qui perdaient des préférences. Le logo et les icônes sont désormais des images SVG locales encodées ; aucun script n'a été ajouté.

Les captures sont enregistrées dans `evaluation/results/ui-redesign/` : `home-1440.png`, `home-1024.png`, `home-768.png`, `home-375.png`, `market-overview-canada-1440.png`, `job-explorer-python-canada-1440.png`, `job-cards-375.png`, `job-explorer-empty-375.png`, `job-explorer-data-engineer-768.png`, `assistant-analytics-canada-1440.png`, `assistant-rag-sources-1440.png`, `validation-1440.png`, `settings-1440.png` et `mobile-menu-375.png`. `responsive-measurements.json` conserve les mesures de largeur. Ces preuves locales sont ignorées par Git. Les essais responsive n'équivalent pas à une certification d'accessibilité ni à des essais sur tous les appareils physiques.

### Préservation, secrets et Docker

Le contrôle final en lecture seule confirme **12 217 annonces**, **23 638 chunks/vecteurs V1**, **30 955 chunks/vecteurs V2**, les deux lignes d'état et la disponibilité V2 en 384 dimensions, non partielle. Les endpoints de santé FastAPI, statut système et santé Streamlit répondent HTTP 200. Le rapport est `evaluation/results/ui-redesign-final-system-check.json`.

L'inspection finale des 24 fichiers modifiés ou créés utilise 11 familles de motifs : **zéro secret détecté**. `.env` reste ignoré et non versionné ; son contenu n'a pas été affiché. Le rapport est `evaluation/results/ui-redesign-secrets-inspection.json`.

La nouvelle validation Docker compte **48 contrôles statiques réussis sur 48**, dont le schéma Compose officiel mis en cache, les entrées COPY, les ressources de carte, le snapshot de validation, les dépendances de santé et les références d'environnement. `Dockerfile.frontend` copie maintenant `.streamlit`, nécessaire au thème et au service des fonds de carte locaux. Rapport : `evaluation/results/ui-redesign-docker-static-validation.json`. Docker est absent : `docker compose config`, les builds, `docker compose up --build` et la santé réelle des conteneurs n'ont pas été exécutés.

## 7. Lancer l'application sous Windows PowerShell

Utiliser l'environnement virtuel et le `.env` déjà configurés dans ce checkout. Le lancement de l'interface ne nécessite pas de relancer l'ingestion ni l'indexation de la base existante.

Dans un premier terminal :

```powershell
Set-Location 'C:\Users\HP\Documents\ChatGPT\Data Job Market Intelligence\data-job-market-intelligence'
.\.venv\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Dans un second terminal :

```powershell
Set-Location 'C:\Users\HP\Documents\ChatGPT\Data Job Market Intelligence\data-job-market-intelligence'
.\.venv\Scripts\python.exe -m streamlit run app/Home.py --server.address 127.0.0.1 --server.port 8501
```

Ouvrir [l'application Streamlit](http://127.0.0.1:8501), [la documentation de l'API](http://127.0.0.1:8000/docs) ou [la santé de l'API](http://127.0.0.1:8000/health). Si un de ces services fonctionne déjà sur son port, réutiliser ce service au lieu de lancer une seconde instance.

Si l'environnement virtuel manque sur une nouvelle installation, créer l'environnement puis installer les dépendances avant de lancer les services :

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Configurer ensuite les variables documentées dans `.env.example` pour la base existante, sans écraser un `.env` déjà présent. La refonte ne requiert aucun nouveau secret.

Pour relancer les contrôles du projet :

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -q
```

Pour inclure les trois tests PostgreSQL avec la connexion locale configurée :

```powershell
$env:RUN_DB_INTEGRATION = '1'
.\.venv\Scripts\python.exe -m pytest -q
```

Les préférences Settings restent limitées à la session de navigateur. Le bouton Refresh system and cached data vide les caches d'interface et relit les endpoints ; il ne modifie ni les tables métier ni les embeddings.

## 8. Fichiers créés et modifiés

Fichiers créés pour la refonte :

- `.streamlit/config.toml`
- `app/assets/theme.css`
- `app/assets/validation_snapshot.json`
- `app/components/charts.py`
- `app/components/dashboard.py`
- `app/components/icons.py`
- `app/components/preferences.py`
- `app/pages/4_Validation.py`
- `app/pages/5_Settings.py`
- `app/static/geo/world_110m.json`
- `app/static/geo/README.md`
- `docs/premium-ui-redesign.md`

Fichiers modifiés :

- `app/Home.py`
- `app/components/design.py`
- `app/components/ui.py`
- `app/pages/1_Market_Overview.py`
- `app/pages/2_Job_Explorer.py`
- `app/pages/3_AI_Assistant.py`
- `api/main.py`
- `src/analytics/service.py`
- `tests/test_api.py`
- `Dockerfile.frontend`
- `README.md`
- `docs/api-contract.md`

Les résultats de contrôle et les captures locales constituent des preuves d'exécution distinctes du code versionné.

## 9. Limites de validation et maintenance

Docker reste indisponible sur cette machine. Aucune construction d'image, exécution de conteneur ou validation runtime Compose n'est revendiquée pour cette refonte. Le snapshot V2 conserve les 16 contrôles historiques ; les 48 contrôles statiques de la refonte sont documentés séparément ci-dessus.

Aucune exécution hébergée de GitHub Actions n'a été vérifiée ici. Les fournisseurs optionnels OpenAI et Ollama n'ont pas été exécutés dans cette validation. La réponse descriptive mesurée utilise le chemin local existant ; elle ne prouve pas le fonctionnement d'un fournisseur distant.

Les contrôles HTTP/SQL attestent les scénarios explicitement listés, pas toutes les combinaisons de facettes. Les résultats datés de Validation ne constituent pas une surveillance continue. La santé de la connexion et le statut d'index peuvent être mis en cache brièvement.

La mise en page conserve les widgets natifs Streamlit et applique une feuille CSS centralisée. Certains sélecteurs de présentation s'appuient sur les attributs structurels de Streamlit ; une mise à jour de Streamlit doit donc être accompagnée d'une vérification visuelle des six pages, de la navigation et des petits écrans. Aucune manipulation JavaScript du DOM n'a été ajoutée.

Les données restent un échantillon historique à couverture géographique inégale. Les champs manquants, les catégories non classées, l'absence de dates de publication et l'éventuelle expiration des liens source restent visibles dans l'expérience et dans l'interprétation des résultats.
