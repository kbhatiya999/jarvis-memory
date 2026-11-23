"""Build release.json for Jarvis memory. Usage: python3 build.py <raw release.json URL> <instructions file>"""
import hashlib, json, sys

url, src = sys.argv[1], sys.argv[2]
ins = open(src, encoding="utf-8").read().replace("{{RELEASE_URL}}", url)

def m(id, to, seq, st, d, note):
    return {"id": id, "to_schema": to, "seq": seq, "statement": st, "expected_delta": d, "note": note}

C = lambda name, label, prop: f"CREATE CONSTRAINT {name} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
s1 = [
    ("person_id", "Person", "id"), ("sphere_name", "Sphere", "name"), ("intention_id", "Intention", "id"),
    ("event_id", "Event", "id"), ("event_key", "Event", "key"), ("fact_id", "Fact", "id"),
    ("contact_name", "Contact", "name"), ("topic_name", "Topic", "name"),
    ("jarvisconfig_version", "JarvisConfig", "version"), ("migration_id", "Migration", "id"),
]
migrations = [m(f"s1-{i+1:03d}", 1, i + 1, C(*c), "0", f"constraint {c[0]}") for i, c in enumerate(s1)]
n = len(migrations)
migrations += [
    m(f"s1-{n+1:03d}", 1, n + 1, "CREATE FULLTEXT INDEX recall_text IF NOT EXISTS FOR (n:Event|Fact|Intention) ON EACH [n.text, n.statement]", "0", "full-text recall index"),
    m(f"s1-{n+2:03d}", 1, n + 2, "CREATE INDEX event_type_at IF NOT EXISTS FOR (n:Event) ON (n.type, n.at)", "0", "event lookup index"),
    m(f"s1-{n+3:03d}", 1, n + 3, "MERGE (p:Person {id:'me'}) ON CREATE SET p.trust_phase = 'new' RETURN p.id", "nodes +1 on a fresh graph", "the user's Person node"),
    m(f"s1-{n+4:03d}", 1, n + 4, "UNWIND ['health','work','money','relationships','home','learning'] AS s MERGE (x:Sphere {name:s}) ON CREATE SET x.version = 0 RETURN count(x)", "nodes +6 on a fresh graph", "six base spheres"),
    m(f"s1-{n+5:03d}", 1, n + 5, "MATCH (p:Person {id:'me'}), (s:Sphere) MERGE (p)-[t:TRUSTS]->(s) ON CREATE SET t.level = 0.3, t.updated_at = datetime() RETURN count(t)", "rels +6 on a fresh graph", "trust per sphere starts at 0.3"),
    m("s2-001", 2, 1, "MATCH (e:Event)-[:ABOUT]->(i:Intention)-[:IN_SPHERE]->(s:Sphere) WHERE e.type IN ['action','attempt'] AND NOT (e)-[:IN_SPHERE]->(:Sphere) MERGE (e)-[:IN_SPHERE]->(s) RETURN count(*) AS added", "rels +N (backfill)", "action/attempt Events get their Intention's sphere"),
    m("s3-001", 3, 1, "MERGE (s:Sphere {name:'self'}) ON CREATE SET s.version = 0 WITH s MATCH (p:Person {id:'me'}) MERGE (p)-[t:TRUSTS]->(s) ON CREATE SET t.level = 0.3, t.updated_at = datetime() RETURN s.name, t.level", "nodes +1, rels +1", "sphere self"),
    m("s3-002", 3, 2, C("resolution_id", "Resolution", "id"), "0", "Resolution id unique"),
    m("s3-003", 3, 3, C("item_id", "Item", "id"), "0", "Item id unique"),
    m("s3-004", 3, 4, C("store_name", "Store", "name"), "0", "Store name unique"),
]

URL = url
SETUP_TEXT = f"""SETUP (empty graph, or "jarvis setup"; exempt from the 4-call limit; about 5 calls). Tell the user what will happen, then:
S1. Import the release (write-cypher): CALL apoc.load.json('{url}') YIELD value MERGE (c:JarvisConfig {{version: value.version}}) ON CREATE SET c.schema_version = value.schema_version, c.instructions = value.instructions, c.notes = value.notes, c.active = false, c.created_at = datetime() WITH value, c UNWIND value.migrations AS x MERGE (m:Migration {{id: x.id}}) ON CREATE SET m.to_schema = x.to_schema, m.seq = x.seq, m.statement = x.statement, m.expected_delta = x.expected_delta, m.note = x.note, m.created_at = datetime() WITH value, c, count(m) AS migrations RETURN c.version, value.schema_version AS schema, migrations, apoc.util.md5([c.instructions]) = value.md5 AS md5_ok. If md5_ok is false, stop: the download is corrupted.
S2. Constraints and indexes in one call (write-cypher): CALL apoc.load.json('{url}') YIELD value CALL apoc.schema.assert(value.setup.indexes, value.setup.constraints, false) YIELD label, key, action RETURN action, count(*) AS n
S3. Recall index (write-cypher): CREATE FULLTEXT INDEX recall_text IF NOT EXISTS FOR (n:Event|Fact|Intention) ON EACH [n.text, n.statement]
S4. Seed the graph (write-cypher): {{seed}}
S5. Ask the user in one message: the name to call them, pronouns (she/her, he/him, they/them or other), time zone (IANA, e.g. Asia/Kolkata) and language. Then (write-cypher): MATCH (p:Person {{id:'me'}}) SET p.name = $name, p.pronoun_subject = $s, p.pronoun_object = $o, p.pronoun_possessive = $poss, p.timezone = $tz, p.language = $lang, p.schema_version = {{schema}}, p.updated_at = datetime() WITH p MATCH (c:JarvisConfig) SET c.active = (c.version = {{version}}) RETURN p.name, COUNT {{ (:Sphere) }} AS spheres, COUNT {{ ()-[:TRUSTS]->() }} AS trusts, COUNT {{ (m:Migration) WHERE m.applied_at IS NULL AND m.to_schema <= {{schema}} }} AS pending
    Expect spheres 7, trusts 7, pending 0. Then greet the user with jarvis help."""

release = {
    "format": 1,
    "version": 9,
    "schema_version": 3,
    "notes": "v9: generic public release of v8 (schema 3) + upgrade fetches this release from its URL.",
    "md5": hashlib.md5(ins.encode("utf-8")).hexdigest(),
    "instructions": ins,
    "migrations": migrations,
    "setup": {
        "indexes": {"Event": [["type", "at"]]},
        "constraints": {"Person": ["id"], "Sphere": ["name"], "Intention": ["id"], "Event": ["id", "key"], "Fact": ["id"],
                        "Contact": ["name"], "Topic": ["name"], "JarvisConfig": ["version"], "Migration": ["id"],
                        "Resolution": ["id"], "Item": ["id"], "Store": ["name"]},
        "seed": None,
    },
}
release["setup"]["seed"] = (
    "MERGE (p:Person {id:'me'}) ON CREATE SET p.trust_phase = 'new' "
    "WITH p UNWIND ['health','work','money','relationships','home','learning','self'] AS s "
    "MERGE (x:Sphere {name:s}) ON CREATE SET x.version = 0 "
    "MERGE (p)-[t:TRUSTS]->(x) ON CREATE SET t.level = 0.3, t.updated_at = datetime() "
    "WITH count(x) AS spheres OPTIONAL MATCH (m:Migration) WHERE m.to_schema <= " + str(release["schema_version"]) + " AND m.applied_at IS NULL "
    "SET m.applied_at = datetime(), m.applied_note = 'fast setup' RETURN spheres, count(m) AS migrations_marked"
)
SETUP_TEXT = SETUP_TEXT.replace("{seed}", release["setup"]["seed"]).replace("{schema}", str(release["schema_version"])).replace("{version}", str(release["version"]))
json.dump(release, open("release.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(release["md5"], len(ins), len(migrations))

# Gemini copy: Gemini refuses skills that load instructions from a database, so it gets them inline,
# with a version check that warns when a newer release is live in the graph.
gem = f"""GEMINI COPY OF JARVIS v{release['version']} (schema {release['schema_version']}). Source: {url}

FIRST, EVERY TURN: using the Jarvis Memory connector (the user does not need to tag it), run read-cypher: OPTIONAL MATCH (p:Person {{id:'me'}}) OPTIONAL MATCH (c:JarvisConfig {{active:true}}) RETURN p.name, p.pronoun_subject, p.pronoun_object, p.pronoun_possessive, p.timezone, p.language, p.schema_version, c.version AS live
- If there is no Person or no active JarvisConfig, the graph is not set up yet: run SETUP below, then stop for this turn.
- If live is higher than {release['version']}, start your reply with one line: "Your Gemini Jarvis is v{release['version']} but v<live> is live: paste the newer skills/gemini/INSTRUCTIONS.txt into the Gemini skill." Then continue.
- Use only Task mode for anything with @jarvis. If you cannot reach the Jarvis Memory tools, say so plainly and suggest Task mode; never pretend anything was saved.
- The profile read above replaces the loader read mentioned below. jarvis upgrade in Gemini only updates the graph; this Gemini copy itself must be re-pasted.

""" + SETUP_TEXT + "\n\n"
import os
os.makedirs("skills/gemini", exist_ok=True)
open("skills/gemini/INSTRUCTIONS.txt", "w", encoding="utf-8").write(gem + ins)
print("gemini", len(gem + ins))

# Claude loader: keep its Setup section identical to the Gemini one.
sk = open("skills/claude/SKILL.md", encoding="utf-8").read()
a, b = sk.index("## Setup"), sk.index("## Recovery")
sk = sk[:a] + "## Setup (empty graph, or \"jarvis setup\")\n" + SETUP_TEXT.split("\n", 1)[1].replace("Tell the user", "Tell the user", 1) + "\n\n" + sk[b:]
open("skills/claude/SKILL.md", "w", encoding="utf-8").write(sk)
print("claude skill setup synced")
