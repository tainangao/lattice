from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass

from lattice.app.retrieval.contracts import RetrievalHit


@dataclass(frozen=True)
class Neo4jSettings:
    uri: str
    username: str
    password: str
    database: str


class Neo4jGraphStore:
    def __init__(self, settings: Neo4jSettings) -> None:
        try:
            from neo4j import GraphDatabase
        except Exception as exc:  # pragma: no cover - optional dependency path
            raise RuntimeError("neo4j driver is required for graph retrieval") from exc

        self._settings = settings
        self._driver = GraphDatabase.driver(
            settings.uri,
            auth=(settings.username, settings.password),
        )

    def close(self) -> None:
        self._driver.close()

    @staticmethod
    def _query_terms(query: str) -> list[str]:
        terms = re.findall(r"[a-z0-9]+", query.lower())
        return [term for term in terms if len(term) >= 2]

    @staticmethod
    def _slug(value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
        return normalized or "unknown"

    def _run(self, statement: str, **params: object) -> list[dict[str, object]]:
        with self._driver.session(database=self._settings.database) as session:
            result = session.run(statement, **params)
            return [record.data() for record in result]

    def _title_profile_hits(self, terms: list[str], limit: int) -> list[RetrievalHit]:
        statement = """
        MATCH (t:Title)
        WITH t, $terms AS terms
        WITH t,
          reduce(score = 0.0, term IN terms |
            score +
            CASE WHEN toLower(coalesce(t.title, '')) CONTAINS term THEN 2.0 ELSE 0.0 END +
            CASE WHEN toLower(coalesce(t.description, '')) CONTAINS term THEN 0.4 ELSE 0.0 END
          ) AS score
        WHERE score > 0
        OPTIONAL MATCH (d:Person)-[:DIRECTED]->(t)
        OPTIONAL MATCH (a:Person)-[:ACTED_IN]->(t)
        OPTIONAL MATCH (t)-[:IN_GENRE]->(g:Genre)
        OPTIONAL MATCH (t)-[:IN_COUNTRY]->(c:Country)
        OPTIONAL MATCH (t)-[:HAS_RATING]->(r:Rating)
        RETURN
          t.show_id AS show_id,
          t.title AS title,
          t.type AS type,
          t.release_year AS release_year,
          coalesce(t.description, '') AS description,
          collect(DISTINCT d.name)[0..3] AS directors,
          collect(DISTINCT a.name)[0..4] AS actors,
          collect(DISTINCT g.name)[0..4] AS genres,
          collect(DISTINCT c.name)[0..3] AS countries,
          head(collect(DISTINCT r.code)) AS rating,
          score AS relevance
        ORDER BY relevance DESC, t.release_year DESC
        LIMIT $limit
        """
        rows = self._run(statement, terms=terms, limit=limit)

        hits: list[RetrievalHit] = []
        for row in rows:
            show_id = row.get("show_id")
            title = row.get("title")
            title_type = row.get("type")
            release_year = row.get("release_year")
            description = row.get("description")
            directors = row.get("directors")
            actors = row.get("actors")
            genres = row.get("genres")
            countries = row.get("countries")
            rating = row.get("rating")
            relevance = row.get("relevance")

            if not isinstance(title, str):
                continue
            if not isinstance(show_id, str):
                show_id = title
            if not isinstance(title_type, str):
                title_type = "Title"
            if not isinstance(release_year, int):
                release_year = 0
            if not isinstance(description, str):
                description = ""

            director_names = [
                name for name in (directors or []) if isinstance(name, str)
            ]
            actor_names = [name for name in (actors or []) if isinstance(name, str)]
            genre_names = [name for name in (genres or []) if isinstance(name, str)]
            country_names = [
                name for name in (countries or []) if isinstance(name, str)
            ]
            rating_code = rating if isinstance(rating, str) and rating else "unknown"
            score = float(relevance) if isinstance(relevance, (int, float)) else 1.0

            details = [f"{title} ({title_type}, {release_year})"]
            if director_names:
                details.append(f"directors: {', '.join(director_names)}")
            if actor_names:
                details.append(f"cast: {', '.join(actor_names)}")
            if genre_names:
                details.append(f"genres: {', '.join(genre_names)}")
            if country_names:
                details.append(f"countries: {', '.join(country_names)}")
            details.append(f"rating: {rating_code}")
            if description:
                details.append(f"description: {description}")

            hits.append(
                RetrievalHit(
                    source_id=f"title:{self._slug(show_id)}",
                    score=score,
                    content="; ".join(details),
                    source_type="shared_graph",
                    location=f"neo4j://title/{self._slug(show_id)}",
                )
            )
        return hits

    def _person_relation_hits(self, terms: list[str], limit: int) -> list[RetrievalHit]:
        statement = """
        MATCH (p:Person)-[rel:DIRECTED|ACTED_IN]->(t:Title)
        WITH p, rel, t, $terms AS terms
        WITH p, rel, t,
          reduce(score = 0.0, term IN terms |
            score +
            CASE WHEN toLower(coalesce(p.name, '')) CONTAINS term THEN 2.0 ELSE 0.0 END +
            CASE WHEN toLower(coalesce(t.title, '')) CONTAINS term THEN 1.0 ELSE 0.0 END
          ) AS score
        WHERE score > 0
        RETURN
          p.name AS person_name,
          type(rel) AS relationship,
          t.show_id AS show_id,
          t.title AS title,
          t.type AS type,
          t.release_year AS release_year,
          score + 0.2 AS relevance
        ORDER BY relevance DESC, t.release_year DESC
        LIMIT $limit
        """
        rows = self._run(statement, terms=terms, limit=limit)

        hits: list[RetrievalHit] = []
        for row in rows:
            person_name = row.get("person_name")
            relationship = row.get("relationship")
            show_id = row.get("show_id")
            title = row.get("title")
            title_type = row.get("type")
            release_year = row.get("release_year")
            relevance = row.get("relevance")

            if not all(
                isinstance(value, str)
                for value in (person_name, relationship, title, title_type)
            ):
                continue
            if not isinstance(show_id, str):
                show_id = title
            if not isinstance(release_year, int):
                release_year = 0
            score = float(relevance) if isinstance(relevance, (int, float)) else 1.0

            relation_id = (
                f"person:{self._slug(person_name)}:{self._slug(relationship)}:"
                f"{self._slug(show_id)}"
            )
            hits.append(
                RetrievalHit(
                    source_id=relation_id,
                    score=score,
                    content=(
                        f"{person_name} {relationship} {title} "
                        f"({title_type}, {release_year})."
                    ),
                    source_type="shared_graph",
                    location=f"neo4j://relation/{relation_id}",
                )
            )
        return hits

    def _genre_relation_hits(self, terms: list[str], limit: int) -> list[RetrievalHit]:
        statement = """
        MATCH (t:Title)-[:IN_GENRE]->(g:Genre)
        WITH t, g, $terms AS terms
        WITH t, g,
          reduce(score = 0.0, term IN terms |
            score +
            CASE WHEN toLower(coalesce(g.name, '')) CONTAINS term THEN 2.0 ELSE 0.0 END +
            CASE WHEN toLower(coalesce(t.title, '')) CONTAINS term THEN 1.0 ELSE 0.0 END
          ) AS score
        WHERE score > 0
        RETURN
          g.name AS genre,
          t.show_id AS show_id,
          t.title AS title,
          t.type AS type,
          t.release_year AS release_year,
          score + 0.1 AS relevance
        ORDER BY relevance DESC, t.release_year DESC
        LIMIT $limit
        """
        rows = self._run(statement, terms=terms, limit=limit)

        hits: list[RetrievalHit] = []
        for row in rows:
            genre_name = row.get("genre")
            show_id = row.get("show_id")
            title = row.get("title")
            title_type = row.get("type")
            release_year = row.get("release_year")
            relevance = row.get("relevance")

            if not all(
                isinstance(value, str) for value in (genre_name, title, title_type)
            ):
                continue
            if not isinstance(show_id, str):
                show_id = title
            if not isinstance(release_year, int):
                release_year = 0
            score = float(relevance) if isinstance(relevance, (int, float)) else 1.0

            relation_id = f"genre:{self._slug(genre_name)}:{self._slug(show_id)}"
            hits.append(
                RetrievalHit(
                    source_id=relation_id,
                    score=score,
                    content=(
                        f"{title} ({title_type}, {release_year}) IN_GENRE {genre_name}."
                    ),
                    source_type="shared_graph",
                    location=f"neo4j://relation/{relation_id}",
                )
            )
        return hits

    def _country_relation_hits(
        self, terms: list[str], limit: int
    ) -> list[RetrievalHit]:
        statement = """
        MATCH (t:Title)-[:IN_COUNTRY]->(c:Country)
        WITH t, c, $terms AS terms
        WITH t, c,
          reduce(score = 0.0, term IN terms |
            score +
            CASE WHEN toLower(coalesce(c.name, '')) CONTAINS term THEN 2.0 ELSE 0.0 END +
            CASE WHEN toLower(coalesce(t.title, '')) CONTAINS term THEN 1.0 ELSE 0.0 END
          ) AS score
        WHERE score > 0
        RETURN
          c.name AS country,
          t.show_id AS show_id,
          t.title AS title,
          t.type AS type,
          t.release_year AS release_year,
          score + 0.1 AS relevance
        ORDER BY relevance DESC, t.release_year DESC
        LIMIT $limit
        """
        rows = self._run(statement, terms=terms, limit=limit)

        hits: list[RetrievalHit] = []
        for row in rows:
            country_name = row.get("country")
            show_id = row.get("show_id")
            title = row.get("title")
            title_type = row.get("type")
            release_year = row.get("release_year")
            relevance = row.get("relevance")

            if not all(
                isinstance(value, str) for value in (country_name, title, title_type)
            ):
                continue
            if not isinstance(show_id, str):
                show_id = title
            if not isinstance(release_year, int):
                release_year = 0
            score = float(relevance) if isinstance(relevance, (int, float)) else 1.0

            relation_id = f"country:{self._slug(country_name)}:{self._slug(show_id)}"
            hits.append(
                RetrievalHit(
                    source_id=relation_id,
                    score=score,
                    content=(
                        f"{title} ({title_type}, {release_year}) "
                        f"IN_COUNTRY {country_name}."
                    ),
                    source_type="shared_graph",
                    location=f"neo4j://relation/{relation_id}",
                )
            )
        return hits

    def _rating_relation_hits(self, terms: list[str], limit: int) -> list[RetrievalHit]:
        statement = """
        MATCH (t:Title)-[:HAS_RATING]->(r:Rating)
        WITH t, r, $terms AS terms
        WITH t, r,
          reduce(score = 0.0, term IN terms |
            score +
            CASE WHEN toLower(coalesce(r.code, '')) CONTAINS term THEN 2.0 ELSE 0.0 END +
            CASE WHEN toLower(coalesce(t.title, '')) CONTAINS term THEN 1.0 ELSE 0.0 END
          ) AS score
        WHERE score > 0
        RETURN
          r.code AS rating,
          t.show_id AS show_id,
          t.title AS title,
          t.type AS type,
          t.release_year AS release_year,
          score + 0.1 AS relevance
        ORDER BY relevance DESC, t.release_year DESC
        LIMIT $limit
        """
        rows = self._run(statement, terms=terms, limit=limit)

        hits: list[RetrievalHit] = []
        for row in rows:
            rating_code = row.get("rating")
            show_id = row.get("show_id")
            title = row.get("title")
            title_type = row.get("type")
            release_year = row.get("release_year")
            relevance = row.get("relevance")

            if not all(
                isinstance(value, str) for value in (rating_code, title, title_type)
            ):
                continue
            if not isinstance(show_id, str):
                show_id = title
            if not isinstance(release_year, int):
                release_year = 0
            score = float(relevance) if isinstance(relevance, (int, float)) else 1.0

            relation_id = f"rating:{self._slug(rating_code)}:{self._slug(show_id)}"
            hits.append(
                RetrievalHit(
                    source_id=relation_id,
                    score=score,
                    content=(
                        f"{title} ({title_type}, {release_year}) "
                        f"HAS_RATING {rating_code}."
                    ),
                    source_type="shared_graph",
                    location=f"neo4j://relation/{relation_id}",
                )
            )
        return hits

    def _fallback_relation_hits(self, query: str, limit: int) -> list[RetrievalHit]:
        statement = """
        MATCH (source)-[rel]->(target)
        WHERE toLower(coalesce(source.name, source.title, '')) CONTAINS $query
           OR toLower(type(rel)) CONTAINS $query
           OR toLower(coalesce(target.name, target.title, '')) CONTAINS $query
           OR toLower(coalesce(rel.evidence, '')) CONTAINS $query
        RETURN
          coalesce(source.name, source.title, toString(id(source))) AS source_name,
          type(rel) AS relationship,
          coalesce(target.name, target.title, toString(id(target))) AS target_name,
          coalesce(rel.evidence, '') AS evidence
        LIMIT $limit
        """
        rows = self._run(statement, query=query.lower(), limit=limit)

        hits: list[RetrievalHit] = []
        for row in rows:
            source_name = row.get("source_name")
            relationship = row.get("relationship")
            target_name = row.get("target_name")
            evidence = row.get("evidence")
            if not all(
                isinstance(value, str)
                for value in (source_name, relationship, target_name, evidence)
            ):
                continue
            relation_id = (
                f"fallback:{self._slug(source_name)}:{self._slug(relationship)}:"
                f"{self._slug(target_name)}"
            )
            hits.append(
                RetrievalHit(
                    source_id=relation_id,
                    score=0.6,
                    content=(
                        f"{source_name} {relationship} {target_name}. "
                        f"Evidence: {evidence}"
                    ),
                    source_type="shared_graph",
                    location=f"neo4j://relation/{relation_id}",
                )
            )
        return hits

    @staticmethod
    def _normalize_scores(hits: list[RetrievalHit]) -> list[RetrievalHit]:
        if not hits:
            return []
        values = [hit.score for hit in hits]
        minimum = min(values)
        maximum = max(values)
        if maximum <= minimum:
            return [
                RetrievalHit(
                    source_id=hit.source_id,
                    score=1.0,
                    content=hit.content,
                    source_type=hit.source_type,
                    location=hit.location,
                )
                for hit in hits
            ]

        normalized: list[RetrievalHit] = []
        for hit in hits:
            score = (hit.score - minimum) / (maximum - minimum)
            normalized.append(
                RetrievalHit(
                    source_id=hit.source_id,
                    score=round(score, 6),
                    content=hit.content,
                    source_type=hit.source_type,
                    location=hit.location,
                )
            )
        return normalized

    def search(self, query: str, limit: int = 5) -> list[RetrievalHit]:
        normalized_query = query.lower().strip()
        terms = self._query_terms(normalized_query)
        if not terms:
            return []

        asks_person = any(
            token in normalized_query
            for token in ("director", "directed", "actor", "actors", "cast", "starring")
        )
        asks_genre = any(token in normalized_query for token in ("genre", "category"))
        asks_country = any(token in normalized_query for token in ("country", "where"))
        asks_rating = any(
            token in normalized_query
            for token in (
                "rating",
                "tv-ma",
                "tv-14",
                "tv-pg",
                "pg-13",
                "pg",
                "g",
                "r",
            )
        )

        candidate_hits: list[RetrievalHit] = []
        candidate_hits.extend(
            self._title_profile_hits(terms=terms, limit=max(6, limit * 2))
        )
        if asks_person or not any((asks_genre, asks_country, asks_rating)):
            candidate_hits.extend(
                self._person_relation_hits(terms=terms, limit=max(6, limit * 2))
            )
        if asks_genre or not any((asks_person, asks_country, asks_rating)):
            candidate_hits.extend(
                self._genre_relation_hits(terms=terms, limit=max(5, limit * 2))
            )
        if asks_country or not any((asks_person, asks_genre, asks_rating)):
            candidate_hits.extend(
                self._country_relation_hits(terms=terms, limit=max(5, limit * 2))
            )
        if asks_rating or not any((asks_person, asks_genre, asks_country)):
            candidate_hits.extend(
                self._rating_relation_hits(terms=terms, limit=max(5, limit * 2))
            )

        if not candidate_hits:
            candidate_hits = self._fallback_relation_hits(query=query, limit=limit)

        deduped: OrderedDict[str, RetrievalHit] = OrderedDict()
        for hit in sorted(candidate_hits, key=lambda item: item.score, reverse=True):
            deduped.setdefault(hit.source_id, hit)

        ranked = self._normalize_scores(list(deduped.values()))
        return ranked[:limit]

    def count_edges(self) -> int:
        statement = "MATCH ()-[rel]->() RETURN count(rel) AS edge_count"
        with self._driver.session(database=self._settings.database) as session:
            result = session.run(statement)
            row = result.single()
        if not row:
            return 0
        count = row.get("edge_count")
        return int(count) if isinstance(count, int) else 0
