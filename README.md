# jarvis-memory

A personal **Jarvis** that lives in **your own Neo4j graph** and works from Claude (and Gemini). It keeps a living model of you — what you want to be true, what happened, what it has learned about you — and does the single most useful thing to help, or deliberately stays quiet.

This repo is the **public release**: Jarvis's instructions plus the database migrations that create and evolve the graph. It contains nothing personal; your data stays in your database.

## How it works
- Your graph holds a versioned `JarvisConfig` node (the instructions) and `Migration` nodes (schema changes).
- The `jarvis` skill in Claude is a thin **loader**: each turn it reads the active instructions from your graph and follows them.
- **Setup** and **upgrades** pull [`release.json`](release.json) straight into your database (`apoc.load.json`), check its md5, run only the migrations you haven't had, and switch versions. Migrations are additive and idempotent; `jarvis rollback` switches back without touching data.

## Setup (about 10 minutes)
1. **Neo4j:** create a free [Aura](https://console.neo4j.io) instance. In Organization → Security, turn on *Tool authentication with Aura user* and tick the instance.
2. **Connector:** in claude.ai → Settings → Connectors → *Add custom connector*: name `Jarvis Memory`, URL `https://<your-instance-id>.mcp-instances.neo4j.io`, leave client ID/secret empty, sign in with Neo4j Aura.
3. **Skill:** in Claude, create a skill from [`skills/claude/SKILL.md`](skills/claude/SKILL.md).
4. In a chat with the connector on, say **`jarvis setup`**. Jarvis imports the release, builds the graph, asks your name, pronouns, time zone and language, and greets you.

Then just talk to it, or use `jarvis help`.

## Upgrading
Say `jarvis upgrade`. It fetches the latest release, verifies it, runs pending migrations, compares node/relationship counts before and after, and activates the new version. `jarvis version` shows what's live; `jarvis rollback` goes back.

## The Charter (what Jarvis must always do)
- **Active:** plan backward from every deadline; help *today's* attempt while it can still succeed; offer things on its own when it notices room.
- **Purposeful:** every unprompted suggestion names the goal it serves; staying quiet is a judgement; a "stop" is permanent.
- **Understanding:** learns from outcomes; everything it believes about you is visible and deletable.
- **Gradual:** assertiveness rises with success and falls with rejection, per life area.
- **Honest:** every decision carries its reason; never claims an outcome you didn't confirm.

## Files
| File | Purpose |
|---|---|
| `release.json` | Latest release: instructions, md5, migrations from an empty graph |
| `releases/vN.json` | Frozen copy of each version |
| `instructions.txt` | Instructions source (the release URL is filled in by `build.py`) |
| `build.py` | `python3 build.py <release url> instructions.txt` → `release.json` |
| `skills/claude/SKILL.md` | The loader skill for Claude |
| `skills/gemini/INSTRUCTIONS.txt` | Paste into a Gemini skill named `jarvis` (Gemini needs the instructions inline) |

## Gemini
Gemini refuses skills that load instructions from a database, so there the instructions are pasted in directly. Each turn the Gemini copy checks the live version in your graph and tells you when a newer release needs re-pasting.

**Set it up (once):**
1. **Set up the graph from Claude first** (steps 1–4 above). Gemini uses the same database.
2. **Add the connector in Gemini:** gemini.google.com → **More** → **Customize** → **Connectors** → **+ Custom**. URL `https://<your-instance-id>.mcp-instances.neo4j.io`, leave client ID/secret empty, sign in with **Continue with Neo4j Aura**, and name it `Jarvis Memory` (the name can't be changed later, only deleted and re-added).
3. **Create the skill manually:** **More** → **Customize** → **Skills** → **Create** → **Create manually**, then fill in:
   - **Name:** `jarvis`
   - **Description:** `Your Jarvis, backed by the Jarvis Memory connector. Use whenever the user tells you something about their life, asks what you know or remember, asks what you can do, mentions routines, reminders, plans, habits or things they want to be true, or types a command starting with 'jarvis'.`
   - **Instructions:** open [`skills/gemini/INSTRUCTIONS.txt`](https://raw.githubusercontent.com/kbhatiya999/jarvis-memory/main/skills/gemini/INSTRUCTIONS.txt), select all (`Cmd/Ctrl+A`), copy, and paste it into the Instructions box.
   - Click **Save** and wait until the button says **Saved**.
4. **Confirm it stuck:** go back to Skills → **⋯** next to `jarvis` → **Edit manually**. The instructions must start with `GEMINI COPY OF JARVIS v…`. If you see the old text, the save didn't persist — paste and save again.
5. **Use it:** new chat → switch **Chat** to **Task** under the message box → model **Hydrogen** (Everyday help; Neon can't reach connectors) → type `@jar`, pick **jarvis**, add your message. Click **Allow once** when it asks to write. Try `@jarvis jarvis version` first.

**Updating Gemini:** when Gemini says a newer version is live, open Skills → **⋯** next to `jarvis` → **Edit manually**, select all in Instructions, paste the latest [`INSTRUCTIONS.txt`](https://raw.githubusercontent.com/kbhatiya999/jarvis-memory/main/skills/gemini/INSTRUCTIONS.txt), Save, and confirm as in step 4. Your data is untouched; only Gemini's copy of the instructions changes.
