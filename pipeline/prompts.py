"""Claude prompt templates for each pipeline generation step."""


def store_listing(name: str, description: str, file_types: list) -> str:
    types_str = ", ".join(file_types[:8]) if file_types else "unknown"
    return f"""You are a professional game marketer writing Itch.io store listings.

Game Name: {name}
Description: {description or "An indie game"}
File Types Detected: {types_str}

Create exactly 5 DISTINCT store listing variants. Requirements:
- Each variant: 400–500 characters max
- Each takes a different angle:
  1. Action & excitement (high energy, verbs)
  2. Atmosphere & mood (evocative, immersive)
  3. Feature highlights (bullet-point style compressed)
  4. Player empowerment ("You are...", "Your mission...")
  5. Mystery & intrigue (cryptic, pulls curiosity)
- Write for Itch.io's indie dev community — skip generic phrases like "embark on an adventure"
- No placeholder brackets

Return ONLY valid JSON:
{{
  "variants": [
    "Variant 1 text...",
    "Variant 2 text...",
    "Variant 3 text...",
    "Variant 4 text...",
    "Variant 5 text..."
  ]
}}"""


def social_media(name: str, description: str) -> str:
    return f"""You are a social media manager for an indie game studio.

Game Name: {name}
Description: {description or "An indie game"}

Create exactly 5 DISTINCT Twitter/X announcement thread variants.
Each variant = 3 tweets. Each tweet ≤ 280 characters.
Each thread uses a different hook strategy:
  1. Pure hype — excitement and energy
  2. Dev journey — "we made this" narrative
  3. Feature reveal — show don't tell
  4. Community invite — "come play with us"
  5. Cinematic/dramatic — opens like a film

Use relevant hashtags (#indiegame #gamedev etc.) naturally. No emoji spam.

Return ONLY valid JSON:
{{
  "variants": [
    ["tweet1", "tweet2", "tweet3"],
    ["tweet1", "tweet2", "tweet3"],
    ["tweet1", "tweet2", "tweet3"],
    ["tweet1", "tweet2", "tweet3"],
    ["tweet1", "tweet2", "tweet3"]
  ]
}}"""


def press_release(name: str, description: str) -> str:
    return f"""You are a PR writer for an indie game studio.

Game Name: {name}
Description: {description or "An indie game"}

Write exactly 5 DISTINCT press release snippets, each ~180–220 words.
Each targets a different editorial angle:
  1. General gaming press (broad audience, accessible)
  2. Indie dev community (Itch.io, Game Jolt audience)
  3. Genre enthusiasts (fans of the specific type of game)
  4. Tech/dev angle (interesting technical or creative decisions)
  5. Storytelling & narrative focus (world, lore, characters)

Format each as a proper opening paragraph for a full press release.
Include a dateline placeholder like: [CITY, DATE] —

Return ONLY valid JSON:
{{
  "variants": [
    "Full variant 1 text...",
    "Full variant 2 text...",
    "Full variant 3 text...",
    "Full variant 4 text...",
    "Full variant 5 text..."
  ]
}}"""


def key_art(name: str, description: str) -> str:
    return f"""You are an art director briefing a game artist.

Game Name: {name}
Description: {description or "An indie game"}

Write 5 DISTINCT key art / hero screenshot briefs. Each brief describes one image to create:
- Composition (what's in frame, camera angle)
- Mood & lighting
- Key visual elements / characters / environment
- Color palette (3–4 colors with hex suggestions)
- Style reference (e.g., "painterly like Hades", "pixel art like Shovel Knight")
- Intended use (store header, social media, press kit)

Return ONLY valid JSON:
{{
  "variants": [
    "Brief 1: ...",
    "Brief 2: ...",
    "Brief 3: ...",
    "Brief 4: ...",
    "Brief 5: ..."
  ]
}}"""


def itch_config(name: str, description: str, store_copy: str) -> str:
    copy = store_copy or description or "An indie game"
    return f"""Create a complete Itch.io store page configuration for this game.

Game Name: {name}
Approved Store Copy: {copy}

Return a JSON config object. Fill in sensible defaults based on the game context:
{{
  "title": "{name}",
  "short_description": "(max 200 chars — from the store copy)",
  "description_html": "(HTML-formatted full description, 3–4 paragraphs)",
  "kind": "html",
  "classification": "game",
  "tags": ["tag1", "tag2", "...up to 10 relevant tags"],
  "genre": "action",
  "pricing": {{
    "model": "free",
    "price_usd": 0.00,
    "minimum_usd": 0.00
  }},
  "platforms": {{
    "windows": true,
    "mac": true,
    "linux": true,
    "android": false,
    "ios": false
  }},
  "community": "enabled",
  "visibility": "draft",
  "cover_image_note": "1080x608px, PNG or JPG — show your key art here",
  "screenshots_note": "Upload 3–5 in-game screenshots, 16:9 ratio preferred"
}}"""


def steam_config(name: str, description: str, store_copy: str) -> str:
    copy = store_copy or description or "An indie game"
    return f"""Create a Steam Steamworks store page configuration template for this game.

Game Name: {name}
Approved Store Copy: {copy}

Return a JSON template for use with the Steamworks partner portal:
{{
  "app_name": "{name}",
  "short_description": "(max 300 chars from approved copy)",
  "detailed_description": "(HTML, 800+ words — expand on the store copy)",
  "about_the_game": "(1–2 paragraphs, gameplay-focused)",
  "languages_supported": ["English"],
  "genres": ["RPG", "...based on game type"],
  "tags": ["...up to 20 relevant Steam tags"],
  "categories": ["Single-player"],
  "release_state": "coming_soon",
  "minimum_requirements_windows": {{
    "os": "Windows 10",
    "processor": "1.8 GHz dual-core",
    "memory": "2 GB RAM",
    "graphics": "Integrated graphics",
    "storage": "500 MB"
  }},
  "pricing": {{
    "tier": "free",
    "price_usd": 0.00,
    "launch_discount_percent": 0,
    "launch_discount_duration_days": 7
  }},
  "achievements_count": 0,
  "trading_cards": false,
  "steam_cloud": false,
  "notes": "Fill in your actual Steamworks App ID before publishing"
}}"""


def analytics_js(name: str) -> str:
    return f"""Write a Google Analytics 4 event-tracking setup file for a game called "{name}".

The file should:
1. Define a `GameAnalytics` class with methods for each trackable event
2. Use `gtag()` to fire GA4 events
3. Include a `init(measurementId)` method
4. Cover these events with proper parameter schemas:
   - game_start (difficulty, mode)
   - level_complete (level_name, time_seconds, score)
   - game_over (level_name, score, cause)
   - achievement_unlocked (achievement_id, achievement_name)
   - item_purchased (item_id, item_name, currency, value)
   - tutorial_complete (tutorial_step)
   - game_share (method, content_type)
   - session_end (session_duration_seconds, levels_completed)
5. Add a usage example at the bottom in a comment block

Return ONLY the JavaScript code — no JSON wrapper, no markdown.
Start with: // analytics-setup.js — {name}"""
