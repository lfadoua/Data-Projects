"""All counts and distributions come from SQL over the filtered dataset."""

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from src.analytics.schemas import Filters
from src.database.models import Job, JobSkill
from src.database.repositories import FILTER_COLUMNS, apply_filters, job_dict


class AnalyticsService:
    def __init__(self, engine):
        self.engine = engine

    def count(self, filters=None):
        with Session(self.engine) as session:
            return session.scalar(
                apply_filters(select(func.count()).select_from(Job), filters or {})
            )

    def published_count(self, filters=None, date_prefix=""):
        statement = select(func.count()).select_from(Job).where(Job.published_date.is_not(None))
        if date_prefix:
            statement = statement.where(Job.published_date.like(date_prefix + "%"))
        with Session(self.engine) as session:
            return session.scalar(apply_filters(statement, filters or {}))

    def groups(self, field, filters=None, limit=20):
        column = FILTER_COLUMNS.get(field)
        if column is None:
            column = {"employment_type": Job.employment_type}.get(field)
        if column is None:
            raise ValueError("Unsupported grouping")
        statement = apply_filters(select(column, func.count()).select_from(Job), filters or {})
        statement = statement.group_by(column).order_by(func.count().desc(), column).limit(limit)
        with Session(self.engine) as session:
            return [
                {"name": name or "Unknown", "count": count}
                for name, count in session.execute(statement)
            ]

    def skills(self, filters=None, limit=20):
        total = self.count(filters)
        statement = select(JobSkill.skill, func.count()).join(Job, Job.id == JobSkill.job_id)
        statement = apply_filters(statement, filters or {}).group_by(JobSkill.skill)
        statement = statement.order_by(func.count().desc(), JobSkill.skill).limit(limit)
        with Session(self.engine) as session:
            return {
                "total_jobs": total,
                "items": [
                    {
                        "name": name,
                        "count": count,
                        "percentage": round(count / total * 100, 2) if total else 0,
                    }
                    for name, count in session.execute(statement)
                ],
            }

    def salary(self, filters=None, group_by=None):
        extra = {
            "seniority": Job.seniority,
            "job_title": Job.normalized_job_title,
            "country": Job.country,
        }.get(group_by)
        dimensions = [Job.salary_currency, Job.salary_period]
        if extra is not None:
            dimensions.append(extra)
        statement = select(
            *dimensions,
            func.count(),
            func.min(Job.salary_min),
            func.avg(Job.salary_min),
            func.avg(Job.salary_max),
            func.max(Job.salary_max),
        ).where(
            Job.salary_min.is_not(None),
            Job.salary_currency.is_not(None),
            Job.salary_period.is_not(None),
        )
        statement = apply_filters(statement, filters or {}).group_by(*dimensions)
        with Session(self.engine) as session:
            rows = []
            for record in session.execute(statement):
                c, p = record[0], record[1]
                group = record[2] if extra is not None else None
                n, low, a, b, high = record[3:] if extra is not None else record[2:]
                row = {
                    "currency": c,
                    "period": p,
                    "jobs": n,
                    "min": low,
                    "mean_min": a,
                    "mean_max": b,
                    "max": high,
                }
                if extra is not None:
                    row[group_by] = group
                rows.append(row)
        return {
            "groups": rows,
            "group_by": group_by,
            "note": (
                "Only explicit salary fields with known currency and period; no "
                "currency conversion."
            ),
        }

    def trends(self, filters=None):
        month = func.substr(Job.published_date, 1, 7)
        statement = apply_filters(
            select(month, func.count()).where(Job.published_date.is_not(None)), filters or {}
        )
        with Session(self.engine) as session:
            rows = [
                {"month": m, "count": n}
                for m, n in session.execute(statement.group_by(month).order_by(month))
            ]
        return {
            "items": rows,
            "note": "Publication dates only. Collection dates are not hiring trends.",
        }

    def overview(self, filters=None):
        return {
            "total_jobs": self.count(filters),
            "top_skills": self.skills(filters, 10)["items"],
            **{f"by_{field}": self.groups(field, filters) for field in FILTER_COLUMNS},
            "by_employment_type": self.groups("employment_type", filters),
            "salary": self.salary(filters),
            "publication_trends": self.trends(filters),
        }

    def skill_role(self, filters=None, roles=None, skills=None):
        """SQL counts for a small, interpretable role-by-skill heatmap."""
        roles = list(roles or [])[:8]
        skills = list(skills or [])[:12]
        if not roles or not skills:
            return []
        statement = (
            select(Job.normalized_job_title, JobSkill.skill, func.count())
            .join(JobSkill, JobSkill.job_id == Job.id)
            .where(Job.normalized_job_title.in_(roles), JobSkill.skill.in_(skills))
        )
        statement = apply_filters(statement, filters or {}).group_by(
            Job.normalized_job_title, JobSkill.skill
        )
        with Session(self.engine) as session:
            return [
                {"role": role, "skill": skill, "count": count}
                for role, skill, count in session.execute(statement)
            ]

    def jobs(self, filters=None, limit=20, offset=0, search=None):
        statement = apply_filters(select(Job), filters or {})
        if search and search.strip():
            # Treat user-entered wildcards literally; values remain bound parameters.
            literal = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{literal}%"
            statement = statement.where(
                or_(
                    Job.job_title.ilike(pattern, escape="\\"),
                    Job.company.ilike(pattern, escape="\\"),
                    Job.cleaned_description.ilike(pattern, escape="\\"),
                )
            )
        with Session(self.engine) as session:
            total = session.scalar(select(func.count()).select_from(statement.subquery()))
            return {
                "total": total,
                "limit": limit,
                "offset": offset,
                "items": [
                    job_dict(job)
                    for job in session.scalars(
                        statement.order_by(Job.id).offset(offset).limit(limit)
                    )
                ],
            }

    def facets(self):
        with Session(self.engine) as session:
            result = {
                name: list(
                    session.scalars(
                        select(column).where(column.is_not(None)).distinct().order_by(column)
                    )
                )
                for name, column in FILTER_COLUMNS.items()
            }
            result["skill"] = list(
                session.scalars(select(JobSkill.skill).distinct().order_by(JobSkill.skill))
            )
            return result

    def skill_frequency(self, skill, filters=None):
        base = (
            filters.model_dump(exclude_none=True)
            if isinstance(filters, Filters)
            else dict(filters or {})
        )
        total = self.count(base)
        target_exists = exists(
            select(JobSkill.job_id).where(
                JobSkill.job_id == Job.id,
                func.lower(JobSkill.skill) == skill.lower(),
            )
        )
        statement = apply_filters(select(func.count()).select_from(Job).where(target_exists), base)
        with Session(self.engine) as session:
            count = session.scalar(statement)
        return {
            "skill": skill,
            "count": count,
            "total_jobs": total,
            "percentage": round(100 * count / total, 2) if total else 0,
        }
