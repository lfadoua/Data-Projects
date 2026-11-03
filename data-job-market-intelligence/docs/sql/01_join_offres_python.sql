-- Exercice 1 : relier les offres et leurs competences avec INNER JOIN.
-- Emplacement physique verifie le 19 octobre 2026 : public.
-- Le schema djmi existe, mais ses tables applicatives sont absentes.
-- Execution complete en lecture seule, puis fermeture par ROLLBACK.

BEGIN READ ONLY;
SET LOCAL statement_timeout = '30s';

SELECT
    j.id,
    j.job_title,
    j.company,
    j.country,
    js.skill
FROM public.jobs AS j
INNER JOIN public.job_skills AS js
    ON js.job_id = j.id
WHERE j.normalized_job_title = 'Data Engineer'
  AND js.skill = 'Python'
ORDER BY j.company NULLS LAST, j.job_title, j.id
LIMIT 20;

ROLLBACK;
