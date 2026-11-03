-- Exercice 2 : WITH nomme deux resultats intermediaires.
-- Denominateur : toutes les offres, meme sans competence extraite.
-- Une offre peut mentionner plusieurs competences : les pourcentages
-- ne forment pas une repartition dont la somme doit etre 100 pour cent.
-- Emplacement physique actuel : public, pas djmi.

BEGIN READ ONLY;
SET LOCAL statement_timeout = '30s';

WITH total_offres AS (
    SELECT COUNT(*) AS nb_total
    FROM public.jobs
),
offres_par_competence AS (
    SELECT
        js.skill,
        COUNT(DISTINCT j.id) AS nb_offres
    FROM public.jobs AS j
    INNER JOIN public.job_skills AS js
        ON js.job_id = j.id
    GROUP BY js.skill
)
SELECT
    c.skill,
    c.nb_offres,
    t.nb_total AS total_offres,
    ROUND(
        100.0 * c.nb_offres / NULLIF(t.nb_total, 0),
        2
    ) AS pourcentage_offres
FROM offres_par_competence AS c
CROSS JOIN total_offres AS t
ORDER BY c.nb_offres DESC, c.skill
LIMIT 10;

ROLLBACK;
