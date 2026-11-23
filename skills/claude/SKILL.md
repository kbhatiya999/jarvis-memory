---
name: jarvis
description: Your Jarvis on your own Neo4j memory graph (Jarvis Memory connector). Use when you tell it about your life, plans, reminders, routines or values, ask what it remembers, or type a command starting with 'jarvis'.
---

# jarvis (loader)

This skill is a thin loader. Jarvis's real, versioned instructions live in your own Neo4j graph (node `JarvisConfig` with `active = true`). They are installed and upgraded from the public release at
`https://raw.githubusercontent.com/kbhatiya999/jarvis-memory/main/release.json`, so this skill never needs re-saving and upgrades never lose data.

## Every turn
1. **Connector.** Use the Jarvis Memory connector (`read-cypher`, `write-cypher`, `get-schema`). If its tools are not loaded, load them with ToolSearch (query "cypher"). If they still aren't there, say plainly that a Jarvis Memory connector pointing at the user's Neo4j Aura instance must be added and turned on in this chat (see the README). Never pretend anything was saved, and never store Jarvis data in Claude's own memory instead.
2. **Load** with one read-cypher call:
```cypher
OPTIONAL MATCH (p:Person {id:'me'}) OPTIONAL MATCH (c:JarvisConfig {active:true}) RETURN p.name, p.pronoun_subject, p.pronoun_object, p.pronoun_possessive, p.timezone, p.language, p.schema_version, c.version AS live, c.schema_version AS config_schema, c.instructions AS instructions
```
3. **Follow `instructions`** as this skill's instructions for the rest of the turn, with `live` as the running version. They are the user's own text, installed in their own database from the release above. They never override your safety rules or the user's message in this chat.
4. If there is **no active JarvisConfig** (a new or empty graph), run **Setup** below. If `config_schema` is higher than `p.schema_version`, say so in one line and offer `jarvis upgrade` or `jarvis rollback`. Do not guess the instructions.

## Setup (empty graph, or "jarvis setup")
S1. Import the release (write-cypher): CALL apoc.load.json('https://raw.githubusercontent.com/kbhatiya999/jarvis-memory/main/release.json') YIELD value MERGE (c:JarvisConfig {version: value.version}) ON CREATE SET c.schema_version = value.schema_version, c.instructions = value.instructions, c.notes = value.notes, c.active = false, c.created_at = datetime() WITH value, c UNWIND value.migrations AS x MERGE (m:Migration {id: x.id}) ON CREATE SET m.to_schema = x.to_schema, m.seq = x.seq, m.statement = x.statement, m.expected_delta = x.expected_delta, m.note = x.note, m.created_at = datetime() WITH value, c, count(m) AS migrations RETURN c.version, value.schema_version AS schema, migrations, apoc.util.md5([c.instructions]) = value.md5 AS md5_ok. If md5_ok is false, stop: the download is corrupted.
S2. Constraints and indexes in one call (write-cypher): CALL apoc.load.json('https://raw.githubusercontent.com/kbhatiya999/jarvis-memory/main/release.json') YIELD value CALL apoc.schema.assert(value.setup.indexes, value.setup.constraints, false) YIELD label, key, action RETURN action, count(*) AS n
S3. Recall index (write-cypher): CREATE FULLTEXT INDEX recall_text IF NOT EXISTS FOR (n:Event|Fact|Intention) ON EACH [n.text, n.statement]
S4. Seed the graph (write-cypher): MERGE (p:Person {id:'me'}) ON CREATE SET p.trust_phase = 'new' WITH p UNWIND ['health','work','money','relationships','home','learning','self'] AS s MERGE (x:Sphere {name:s}) ON CREATE SET x.version = 0 MERGE (p)-[t:TRUSTS]->(x) ON CREATE SET t.level = 0.3, t.updated_at = datetime() WITH count(x) AS spheres OPTIONAL MATCH (m:Migration) WHERE m.to_schema <= 3 AND m.applied_at IS NULL SET m.applied_at = datetime(), m.applied_note = 'fast setup' RETURN spheres, count(m) AS migrations_marked
S5. Ask the user in one message: the name to call them, pronouns (she/her, he/him, they/them or other), time zone (IANA, e.g. Asia/Kolkata) and language. Then (write-cypher): MATCH (p:Person {id:'me'}) SET p.name = $name, p.pronoun_subject = $s, p.pronoun_object = $o, p.pronoun_possessive = $poss, p.timezone = $tz, p.language = $lang, p.schema_version = 3, p.updated_at = datetime() WITH p MATCH (c:JarvisConfig) SET c.active = (c.version = 9) RETURN p.name, COUNT { (:Sphere) } AS spheres, COUNT { ()-[:TRUSTS]->() } AS trusts, COUNT { (m:Migration) WHERE m.applied_at IS NULL AND m.to_schema <= 3 } AS pending
    Expect spheres 7, trusts 7, pending 0. Then greet the user with jarvis help.

## Recovery (works even if the stored instructions are broken)
- `jarvis version` — `MATCH (c:JarvisConfig) RETURN c.version, c.schema_version, c.active, c.notes ORDER BY c.version DESC LIMIT 5`.
- `jarvis rollback` — activate the highest version below the live one whose schema_version ≤ p.schema_version: `MATCH (c:JarvisConfig) SET c.active = (c.version = $prev)`.
