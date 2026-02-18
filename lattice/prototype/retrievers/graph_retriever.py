from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from neo4j import GraphDatabase

from lattice.prototype.models import SourceSnippet
from lattice.prototype.retrievers.scoring import overlap_score, tokenize


class SeedGraphRetriever:
    def __init__(self, graph_path: str) -> None:
        self._graph_path = graph_path

    async def retrieve(self, question: str, limit: int = 3) -> list[SourceSnippet]:
        edges = _load_graph_edges(self._graph_path)
        ranked = sorted(
            edges,
            key=lambda edge: overlap_score(question, _edge_text(edge)),
            reverse=True,
        )
        top_edges = [
            edge for edge in ranked if overlap_score(question, _edge_text(edge)) > 0
        ][:limit]
        return [
            SourceSnippet(
                source_type="graph",
                source_id=f"{edge['source']}->{edge['target']}",
                text=_edge_summary(edge),
                score=overlap_score(question, _edge_text(edge)),
            )
            for edge in top_edges
        ]


class Neo4jGraphRetriever:
    def __init__(
        self,
        uri: str,
        username: str,
        password: str,
        database: str,
        scan_limit: int,
    ) -> None:
        self._database = database
        self._scan_limit = scan_limit
        self._driver = GraphDatabase.driver(uri, auth=(username, password))

    async def retrieve(self, question: str, limit: int = 3) -> list[SourceSnippet]:
        return await asyncio.to_thread(self._retrieve_sync, question, limit)

    def _retrieve_sync(self, question: str, limit: int) -> list[SourceSnippet]:
        tokens = _query_tokens(question)
        if not tokens:
            edges = self._fetch_candidate_edges()
            ranked = sorted(
                edges,
                key=lambda edge: overlap_score(question, _edge_text(edge)),
                reverse=True,
            )
            top_edges = [
                edge for edge in ranked if overlap_score(question, _edge_text(edge)) > 0
            ][:limit]
            return [
                SourceSnippet(
                    source_type="graph",
                    source_id=f"{edge['source']}->{edge['target']}",
                    text=_edge_summary(edge),
                    score=overlap_score(question, _edge_text(edge)),
                )
                for edge in top_edges
            ]

        flags = _query_flags(question)
        genre_phrases = _genre_phrases(question)
        results = self._fetch_ranked_netflix_results(
            tokens=tokens,
            tv_signal=flags["tv_signal"],
            movie_signal=flags["movie_signal"],
            genre_phrases=genre_phrases,
            limit=limit,
        )
        return [_result_to_snippet(result) for result in results]

    def _fetch_candidate_edges(self) -> list[dict[str, str]]:
        cypher = (
            "MATCH (source)-[rel]->(target) "
            "RETURN "
            "coalesce(source.name, toString(id(source))) AS source, "
            "type(rel) AS relationship, "
            "coalesce(target.name, toString(id(target))) AS target, "
            "coalesce(rel.evidence, rel.description, '') AS evidence "
            "LIMIT $limit"
        )
        with self._driver.session(database=self._database) as session:
            records = session.run(cypher, limit=self._scan_limit)
            return [_record_to_edge(record) for record in records]

    def _fetch_ranked_netflix_results(
        self,
        tokens: list[str],
        tv_signal: bool,
        movie_signal: bool,
        genre_phrases: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        cypher = (
            "MATCH (t:Title) "
            "OPTIONAL MATCH (t)<-[:DIRECTED|ACTED_IN]-(p:Person) "
            "WITH t, collect(distinct p.name) AS people "
            "OPTIONAL MATCH (t)-[:IN_GENRE]->(g:Genre) "
            "WITH t, people, collect(distinct g.name) AS genres "
            "WITH t, people, genres, "
            "toLower(coalesce(t.title, '')) AS title_lower, "
            "toLower(coalesce(t.type, '')) AS type_lower, "
            "[token IN $tokens WHERE title_lower CONTAINS token] AS title_hits, "
            "[token IN $tokens WHERE any(name IN people WHERE toLower(name) CONTAINS token)] AS person_hits, "
            "[token IN $tokens WHERE any(name IN genres WHERE toLower(name) CONTAINS token)] AS genre_hits, "
            "[phrase IN $genre_phrases WHERE any(name IN genres WHERE toLower(name) CONTAINS phrase)] AS genre_phrase_hits "
            "WITH t, type_lower, people, genres, title_hits, person_hits, genre_hits, genre_phrase_hits, "
            "size(title_hits) AS title_score, "
            "size(person_hits) AS person_score, "
            "size(genre_hits) AS genre_score "
            "WITH t, type_lower, people, genres, title_hits, person_hits, genre_hits, genre_phrase_hits, "
            "title_score, person_score, genre_score, "
            "size(genre_phrase_hits) AS genre_phrase_score, "
            "CASE WHEN $tv_signal AND type_lower = 'tv show' THEN 1 ELSE 0 END AS tv_bonus, "
            "CASE WHEN $movie_signal AND type_lower = 'movie' THEN 1 ELSE 0 END AS movie_bonus "
            "WHERE title_score + person_score + genre_score + genre_phrase_score + tv_bonus + movie_bonus > 0 "
            "RETURN "
            "t.show_id AS show_id, "
            "t.title AS title, "
            "t.type AS title_type, "
            "t.release_year AS release_year, "
            "people[0..5] AS people, "
            "genres[0..5] AS genres, "
            "title_hits AS title_hits, "
            "person_hits AS person_hits, "
            "genre_hits AS genre_hits, "
            "genre_phrase_hits AS genre_phrase_hits, "
            "(title_score * 3.0 + person_score * 2.0 + genre_score * 2.0 + genre_phrase_score * 4.0 + tv_bonus * 1.0 + movie_bonus * 1.0) "
            "/ toFloat($token_count) AS score "
            "ORDER BY score DESC, title_score DESC, person_score DESC, genre_score DESC "
            "LIMIT $limit"
        )
        with self._driver.session(database=self._database) as session:
            records = session.run(
                cypher,
                tokens=tokens,
                tv_signal=tv_signal,
                movie_signal=movie_signal,
                genre_phrases=genre_phrases,
                token_count=max(len(tokens), 1),
                limit=min(limit, self._scan_limit),
            )
            return [_record_to_result(record) for record in records]


def _edge_text(edge: dict[str, str]) -> str:
    return " ".join(
        [
            edge.get("source", ""),
            edge.get("relationship", ""),
            edge.get("target", ""),
            edge.get("evidence", ""),
        ]
    )


def _edge_summary(edge: dict[str, str]) -> str:
    return (
        f"{edge.get('source', 'Unknown')} {edge.get('relationship', 'RELATED_TO')} "
        f"{edge.get('target', 'Unknown')}. Evidence: {edge.get('evidence', 'n/a')}"
    )


def _load_graph_edges(path: str) -> list[dict[str, str]]:
    graph_file = Path(path)
    if not graph_file.exists():
        return []
    raw = json.loads(graph_file.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        edges = raw.get("edges", [])
    else:
        edges = raw
    return [
        item for item in edges if {"source", "relationship", "target"}.issubset(item)
    ]


def _query_tokens(question: str) -> list[str]:
    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "what",
        "which",
        "titles",
        "title",
        "involve",
        "involves",
        "involving",
        "show",
        "movie",
        "movies",
        "series",
        "about",
    }
    return [
        token
        for token in tokenize(question)
        if len(token) > 2 and token not in stop_words
    ]


def _query_flags(question: str) -> dict[str, bool]:
    tokens = tokenize(question)
    return {
        "tv_signal": "tv" in tokens,
        "movie_signal": "movie" in tokens,
    }


def _genre_phrases(question: str) -> list[str]:
    normalized = question.strip().lower()
    phrases: list[str] = []
    for phrase in ["tv thrillers", "tv dramas", "tv comedies", "docuseries"]:
        if phrase in normalized:
            phrases.append(phrase)
    return phrases


def _record_to_result(record: Any) -> dict[str, Any]:
    return {
        "show_id": record.get("show_id"),
        "title": record.get("title"),
        "title_type": record.get("title_type"),
        "release_year": record.get("release_year"),
        "people": _coerce_str_list(record.get("people")),
        "genres": _coerce_str_list(record.get("genres")),
        "title_hits": _coerce_str_list(record.get("title_hits")),
        "person_hits": _coerce_str_list(record.get("person_hits")),
        "genre_hits": _coerce_str_list(record.get("genre_hits")),
        "genre_phrase_hits": _coerce_str_list(record.get("genre_phrase_hits")),
        "score": _coerce_float(record.get("score")),
    }


def _coerce_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _coerce_float(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    return 0.0


def _result_to_snippet(result: dict[str, Any]) -> SourceSnippet:
    title = result.get("title") or "Unknown title"
    title_type = result.get("title_type") or "Unknown type"
    release_year = result.get("release_year")
    year_text = f", {release_year}" if isinstance(release_year, int) else ""
    people = ", ".join(result.get("people", [])) or "n/a"
    genres = ", ".join(result.get("genres", [])) or "n/a"
    title_hits = ", ".join(result.get("title_hits", [])) or "none"
    person_hits = ", ".join(result.get("person_hits", [])) or "none"
    genre_hits = ", ".join(result.get("genre_hits", [])) or "none"
    genre_phrase_hits = ", ".join(result.get("genre_phrase_hits", [])) or "none"
    source_id = result.get("show_id") or title
    return SourceSnippet(
        source_type="graph",
        source_id=f"Title:{source_id}",
        text=(
            f"{title} ({title_type}{year_text}) | genres: {genres} | people: {people}. "
            f"Matched tokens -> title: {title_hits}; people: {person_hits}; genres: {genre_hits}; genre_phrases: {genre_phrase_hits}."
        ),
        score=min(max(_coerce_float(result.get("score")), 0.0), 1.0),
    )


def _record_to_edge(record: Any) -> dict[str, str]:
    source = record.get("source", "")
    relationship = record.get("relationship", "RELATED_TO")
    target = record.get("target", "")
    evidence = record.get("evidence", "")
    return {
        "source": source if isinstance(source, str) else str(source),
        "relationship": relationship
        if isinstance(relationship, str)
        else str(relationship),
        "target": target if isinstance(target, str) else str(target),
        "evidence": evidence if isinstance(evidence, str) else str(evidence),
    }
