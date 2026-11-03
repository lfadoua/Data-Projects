-- Exercice 3 : DENSE_RANK ajoute un classement par metier.
-- PARTITION BY recommence le classement pour chaque metier.
-- Les ex aequo sont conserves : rang <= 3 peut retourner plus de 3 lignes.
-- Le nom de competence est trie seulement a la fin, pas dans la fenetre.
-- Emplacement physique actuel : public, pas djmi.

BEGIN READ ONLY;
SET LOCAL statement_timeout = '30s';

WITH offres_par_metier_competence AS (
    SELECT
        j.normalized_job_title AS metier,
        js.skill,
        COUNT(DISTINCT j.id) AS nb_offres
    FROM public.jobs AS j
    INNER JOIN public.job_skills AS js
        ON js.job_id = j.id
    GROUP BY j.normalized_job_title, js.skill
),
competences_classees AS (
    SELECT
        metier,
        skill,
        nb_offres,
        DENSE_RANK() OVER (
            PARTITION BY metier
            ORDER BY nb_offres DESC
        ) AS rang
    FROM offres_par_metier_competence
)
SELECT
    metier,
    skill,
    nb_offres,
    rang
FROM competences_classees
WHERE rang <= 3
ORDER BY metier, rang, skill;

ROLLBACK;
