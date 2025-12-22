create database acme_bot;
create text search configuration pg ( copy = pg_catalog.english );

create table track (
    path   text primary key,
    title  varchar(255),
    artist varchar(255),
    album  varchar(255),
    mtime  timestamptz,
    search_vector tsvector
    generated always as (
        setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('english', coalesce(artist, '')), 'B') ||
        setweight(to_tsvector('english', coalesce(album, '')), 'D')
    ) stored
);

create index track_search_idx on track using gin (search_vector);
