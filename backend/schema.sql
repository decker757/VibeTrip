CREATE TABLE IF NOT EXISTS trips (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    author_name TEXT,
    title TEXT NOT NULL,
    post_caption TEXT NOT NULL DEFAULT '',
    start_location TEXT NOT NULL,
    destination TEXT NOT NULL,
    route_mode TEXT NOT NULL,
    adventure_level INTEGER NOT NULL DEFAULT 50,
    budget_per_person INTEGER NOT NULL DEFAULT 0,
    travellers INTEGER NOT NULL DEFAULT 1,
    start_date TEXT,
    end_date TEXT,
    start_time TEXT,
    end_time TEXT,
    preferences JSONB NOT NULL DEFAULT '[]'::jsonb,
    route JSONB NOT NULL DEFAULT '{}'::jsonb,
    itinerary JSONB NOT NULL DEFAULT '[]'::jsonb,
    candidate_places JSONB NOT NULL DEFAULT '[]'::jsonb,
    cost_breakdown JSONB NOT NULL DEFAULT '{}'::jsonb,
    media JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE trips ADD COLUMN IF NOT EXISTS is_completed BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS media JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE trips ADD COLUMN IF NOT EXISTS post_caption TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS trip_events (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    trip_id TEXT,
    event_type TEXT NOT NULL,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS trip_events_owner_created_idx
    ON trip_events (owner_id, created_at DESC);
