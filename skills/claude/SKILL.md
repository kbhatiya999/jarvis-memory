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
Tell the user what will happen, then:
1. **Import the release** (one write-cypher call):
```cypher
CALL apoc.load.json('https://raw.githubusercontent.com/kbhatiya999/jarvis-memory/main/release.json') YIELD value
MERGE (c:JarvisConfig {version: value.version}) ON CREATE SET c.schema_version = value.schema_version, c.instructions = value.instructions, c.notes = value.notes, c.active = false, c.created_at = datetime()
WITH value, c UNWIND value.migrations AS x
MERGE (m:Migration {id: x.id}) ON CREATE SET m.to_schema = x.to_schema, m.seq = x.seq, m.statement = x.statement, m.expected_delta = x.expected_delta, m.note = x.note, m.created_at = datetime()
WITH value, c, count(m) AS migrations
RETURN c.version, value.schema_version AS schema, migrations, apoc.util.md5([c.instructions]) = value.md5 AS md5_ok
```
   If `md5_ok` is false, stop and say the download was corrupted.
2. **Run the migrations**: for each `Migration` with `applied_at IS NULL` and `to_schema` > the current schema (0 if there is no Person yet), ordered by `to_schema, seq`, run its `statement` exactly as stored (one write-cypher call each), then `MATCH (m:Migration {id:$id}) SET m.applied_at = datetime()`. Stop at the first error and report it.
3. **Profile**: ask the user, in one message, for the name to call them, their pronouns, their time zone (IANA, e.g. Asia/Kolkata) and language. Then `MATCH (p:Person {id:'me'}) SET p.name = $name, p.pronoun_subject = $s, p.pronoun_object = $o, p.pronoun_possessive = $poss, p.timezone = $tz, p.language = $lang, p.schema_version = $schema, p.updated_at = datetime()`.
4. **Activate**: `MATCH (c:JarvisConfig) SET c.active = (c.version = $version)`.
5. **Verify**: `RETURN COUNT { (:Person) } AS person, COUNT { (:Sphere) } AS spheres, COUNT { ()-[:TRUSTS]->() } AS trusts` — expect 1 person and one TRUSTS per sphere. Then greet the user with `jarvis help`.

## Recovery (works even if the stored instructions are broken)
- `jarvis version` — `MATCH (c:JarvisConfig) RETURN c.version, c.schema_version, c.active, c.notes ORDER BY c.version DESC LIMIT 5`.
- `jarvis rollback` — activate the highest version below the live one whose schema_version ≤ p.schema_version: `MATCH (c:JarvisConfig) SET c.active = (c.version = $prev)`.
