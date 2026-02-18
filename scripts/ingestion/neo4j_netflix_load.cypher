// Netflix titles CSV ingestion for Neo4j
//
// Usage:
//   :param csvUrl => 'https://<public-url>/netflix_titles.csv';
//   // For Neo4j Desktop/local import folder only:
//   // :param csvUrl => 'file:///netflix_titles.csv';
//
// Then run this script section-by-section in Neo4j Browser.

CREATE CONSTRAINT title_show_id_unique IF NOT EXISTS
FOR (t:Title) REQUIRE t.show_id IS UNIQUE;

CREATE CONSTRAINT person_name_unique IF NOT EXISTS
FOR (p:Person) REQUIRE p.name IS UNIQUE;

CREATE CONSTRAINT country_name_unique IF NOT EXISTS
FOR (c:Country) REQUIRE c.name IS UNIQUE;

CREATE CONSTRAINT genre_name_unique IF NOT EXISTS
FOR (g:Genre) REQUIRE g.name IS UNIQUE;

CREATE CONSTRAINT rating_code_unique IF NOT EXISTS
FOR (r:Rating) REQUIRE r.code IS UNIQUE;

CREATE INDEX title_name_idx IF NOT EXISTS
FOR (t:Title) ON (t.title);

CREATE INDEX title_type_idx IF NOT EXISTS
FOR (t:Title) ON (t.type);

CREATE INDEX title_release_year_idx IF NOT EXISTS
FOR (t:Title) ON (t.release_year);

CALL {
  LOAD CSV WITH HEADERS FROM $csvUrl AS row
  WITH row
  WHERE row.show_id IS NOT NULL AND trim(row.show_id) <> ''
  MERGE (t:Title {show_id: trim(row.show_id)})
  SET t.title = trim(coalesce(row.title, '')),
      t.type = trim(coalesce(row.type, '')),
      t.release_year = CASE
        WHEN row.release_year IS NULL OR trim(row.release_year) = '' THEN NULL
        ELSE toInteger(row.release_year)
      END,
      t.date_added_raw = trim(coalesce(row.date_added, '')),
      t.duration_raw = trim(coalesce(row.duration, '')),
      t.description = trim(coalesce(row.description, ''))
} IN TRANSACTIONS OF 500 ROWS;

CALL {
  LOAD CSV WITH HEADERS FROM $csvUrl AS row
  WITH row
  WHERE row.show_id IS NOT NULL AND trim(row.show_id) <> ''
    AND row.rating IS NOT NULL AND trim(row.rating) <> ''
  MATCH (t:Title {show_id: trim(row.show_id)})
  MERGE (r:Rating {code: trim(row.rating)})
  MERGE (t)-[:HAS_RATING]->(r)
} IN TRANSACTIONS OF 500 ROWS;

CALL {
  LOAD CSV WITH HEADERS FROM $csvUrl AS row
  WITH row
  WHERE row.show_id IS NOT NULL AND trim(row.show_id) <> ''
    AND row.director IS NOT NULL AND trim(row.director) <> ''
  MATCH (t:Title {show_id: trim(row.show_id)})
  UNWIND [x IN split(row.director, ',') | trim(x)] AS directorName
  WITH t, directorName
  WHERE directorName <> ''
  MERGE (p:Person {name: directorName})
  MERGE (p)-[:DIRECTED]->(t)
} IN TRANSACTIONS OF 500 ROWS;

CALL {
  LOAD CSV WITH HEADERS FROM $csvUrl AS row
  WITH row
  WHERE row.show_id IS NOT NULL AND trim(row.show_id) <> ''
    AND row.cast IS NOT NULL AND trim(row.cast) <> ''
  MATCH (t:Title {show_id: trim(row.show_id)})
  UNWIND [x IN split(row.cast, ',') | trim(x)] AS actorName
  WITH t, actorName
  WHERE actorName <> ''
  MERGE (p:Person {name: actorName})
  MERGE (p)-[:ACTED_IN]->(t)
} IN TRANSACTIONS OF 500 ROWS;

CALL {
  LOAD CSV WITH HEADERS FROM $csvUrl AS row
  WITH row
  WHERE row.show_id IS NOT NULL AND trim(row.show_id) <> ''
    AND row.country IS NOT NULL AND trim(row.country) <> ''
  MATCH (t:Title {show_id: trim(row.show_id)})
  UNWIND [x IN split(row.country, ',') | trim(x)] AS countryName
  WITH t, countryName
  WHERE countryName <> ''
  MERGE (c:Country {name: countryName})
  MERGE (t)-[:IN_COUNTRY]->(c)
} IN TRANSACTIONS OF 500 ROWS;

CALL {
  LOAD CSV WITH HEADERS FROM $csvUrl AS row
  WITH row
  WHERE row.show_id IS NOT NULL AND trim(row.show_id) <> ''
    AND row.listed_in IS NOT NULL AND trim(row.listed_in) <> ''
  MATCH (t:Title {show_id: trim(row.show_id)})
  UNWIND [x IN split(row.listed_in, ',') | trim(x)] AS genreName
  WITH t, genreName
  WHERE genreName <> ''
  MERGE (g:Genre {name: genreName})
  MERGE (t)-[:IN_GENRE]->(g)
} IN TRANSACTIONS OF 500 ROWS;

// Verification
MATCH (t:Title) RETURN count(t) AS titles;
MATCH (p:Person) RETURN count(p) AS people;
MATCH (g:Genre) RETURN count(g) AS genres;
MATCH (c:Country) RETURN count(c) AS countries;
MATCH (r:Rating) RETURN count(r) AS ratings;
