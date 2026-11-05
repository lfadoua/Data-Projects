# Rotation manuelle du mot de passe PostgreSQL / Supabase

Statut : **Action manuelle requise**. La rotation distante n'a pas été effectuée
par l'agent. Aucun identifiant ni fichier `.env` existant n'a été modifié.

Un ancien mot de passe a été visible dans un diagnostic. Une connexion qui
fonctionne ou un scan propre des fichiers ne prouve pas que ce mot de passe a
été renouvelé. Ne pas envoyer sa valeur dans le chat, un rapport ou une capture.

## Procédure sur ce projet Windows

1. Arrêter les processus FastAPI/Streamlit du projet pour éviter les connexions
   utilisant l'ancien secret. Dans leurs terminaux, utiliser `Ctrl+C`.
2. Ouvrir le bon projet dans le tableau de bord Supabase, puis **Database
   Settings**. Utiliser l'action de réinitialisation du mot de passe de la base.
   Il s'agit du mot de passe PostgreSQL, pas du mot de passe de connexion au compte.
   Générer et conserver la nouvelle valeur dans un gestionnaire de mots de passe.
3. Ouvrir localement `.env` dans un éditeur, sans afficher son contenu au terminal :

   ```powershell
   Set-Location 'C:\Users\HP\Documents\Data Projects\Data Job Market Intelligence\data-job-market-intelligence'
   notepad .env
   ```

4. Mettre à jour le secret effectivement utilisé. Dans ce code, **DATABASE_URL
   non vide est prioritaire** sur les paramètres `DB_*`. Si cette URL est renseignée,
   remplacer son mot de passe en encodant les caractères réservés. Sinon, mettre
   à jour uniquement `DB_PASSWORD` avec la valeur littérale selon la syntaxe `.env`.
   Ne pas changer les hôte, port, utilisateur, schéma ou paramètres SSL existants.
   Les variables déjà définies dans le processus Windows ont priorité sur `.env` :
   mettre également à jour une éventuelle surcharge locale, sans l'imprimer.
5. Pour confirmer les paramètres de connexion, utiliser le bouton **Connect**
   du projet Supabase. Copier les paramètres du bon mode ; le nom d'utilisateur
   du pooler diffère de celui d'une connexion directe. Ne pas reconstruire l'hôte
   du pooler à partir de sa seule région.
6. Enregistrer `.env`, puis redémarrer FastAPI et Streamlit avec les commandes du
   [guide local](rag-local-optimization.md). Les paramètres et connexions sont
   mis en cache par processus ; redémarrer évite de conserver l'ancienne valeur.
7. Vérifier `/health` et, si souhaité, les trois tests PostgreSQL en lecture seule
   avec le lanceur qui masque les diagnostics :

   ```powershell
   .\.venv\Scripts\python.exe -m evaluation.safe_checks --live --output evaluation/results/after-manual-rotation.json tests/test_live_database.py
   ```

   Ce contrôle ne recharge aucune donnée et ne reconstruit aucun index. Une erreur
   « tenant or user not found » demande de revérifier les paramètres du pooler ;
   elle ne prouve pas à elle seule un mauvais mot de passe.
8. Vérifier que `.env` reste ignoré par Git, sans afficher son contenu :

   ```powershell
   git check-ignore .env
   git ls-files -- .env
   ```

   La première commande doit identifier `.env` ; la seconde ne doit rien retourner.
   Ne jamais commiter le nouveau secret, même pour réparer la CI.

## Contrôles et limites

Le chargement du projet utilise `dotenv_values(..., interpolate=False)` et la
priorité de l'environnement du processus. Les champs secrets utilisent
`SecretStr` ; les erreurs de validation n'affichent plus les valeurs d'entrée.
Le moteur SQL masque les paramètres liés, et les journaux configurés par
l'application masquent les secrets connus, leurs formes encodées, les URI
PostgreSQL et les jetons Bearer dans les messages et tracebacks formatés.

Ces protections ne garantissent pas l'absence d'une valeur inconnue dans tout
l'historique Git, les captures d'écran, les terminaux ou des services externes.
La sortie brute d'un outil tiers peut encore contenir des données sensibles :
privilégier `evaluation.safe_checks` et ne pas partager des traces intégrales.
La procédure ne crée aucun nouvel utilisateur, privilège ou schéma.

Sources officielles consultées le 30 octobre 2026 :
[gestion du mot de passe du projet Supabase](https://supabase.com/docs/guides/database/postgres/roles#changing-your-project-password),
[connexion PostgreSQL et encodage de l'URL](https://supabase.com/docs/guides/database/connecting-to-postgres).
