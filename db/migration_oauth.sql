-- OAuth token storage for Microsoft Graph device code flow
-- Run this in Supabase SQL editor

create table if not exists oauth_tokens (
    key          text        primary key,   -- e.g. 'graph'
    access_token text        not null,
    refresh_token text,
    expires_at   bigint      not null,      -- unix timestamp
    updated_at   timestamptz default now()
);
