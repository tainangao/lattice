from __future__ import annotations

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

    def search(self, query: str, limit: int = 5) -> list[RetrievalHit]:
        statement = """
        MATCH (source)-[rel]->(target)
        WHERE toLower(coalesce(source.name, '')) CONTAINS $query
           OR toLower(type(rel)) CONTAINS $query
           OR toLower(coalesce(target.name, '')) CONTAINS $query
           OR toLower(coalesce(rel.evidence, '')) CONTAINS $query
        RETURN
          coalesce(source.name, toString(id(source))) AS source_name,
          type(rel) AS relationship,
          coalesce(target.name, toString(id(target))) AS target_name,
          coalesce(rel.evidence, '') AS evidence
        LIMIT $limit
        """

        with self._driver.session(database=self._settings.database) as session:
            result = session.run(statement, query=query.lower(), limit=limit)
            rows = [record.data() for record in result]

        hits: list[RetrievalHit] = []
        for index, row in enumerate(rows, start=1):
            source_name = row.get("source_name")
            relationship = row.get("relationship")
            target_name = row.get("target_name")
            evidence = row.get("evidence")
            if not all(
                isinstance(value, str)
                for value in (source_name, relationship, target_name, evidence)
            ):
                continue
            content = (
                f"{source_name} {relationship} {target_name}. Evidence: {evidence}"
            )
            hits.append(
                RetrievalHit(
                    source_id=f"neo4j-edge-{index}",
                    score=1.0 - (index * 0.01),
                    content=content,
                    source_type="shared_graph",
                    location=f"{source_name}-{relationship}-{target_name}",
                )
            )
        return hits
