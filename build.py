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

release = {
    "format": 1,
    "version": 9,
    "schema_version": 3,
    "notes": "v9: generic public release of v8 (schema 3) + upgrade fetches this release from its URL.",
    "md5": hashlib.md5(ins.encode("utf-8")).hexdigest(),
    "instructions": ins,
    "migrations": migrations,
}
json.dump(release, open("release.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(release["md5"], len(ins), len(migrations))
