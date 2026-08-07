-- BrassOps trade show lead capture.
-- Run once in the Supabase SQL Editor (Database > SQL Editor > New query).

create table if not exists public.leads (
  id          bigint generated always as identity primary key,
  created_at  timestamptz not null default now(),
  name        text,
  email       text,
  agency      text,
  role        text,
  temperature text,
  notes       text,
  source      text not null,
  ip          text,
  user_agent  text,
  flags       text[] not null default '{}'
);

-- Export and the booth list are both ordered newest first.
create index if not exists leads_created_at_idx on public.leads (created_at desc);
-- Supports the per-IP rate check without scanning the table.
create index if not exists leads_ip_created_idx on public.leads (ip, created_at desc);

-- Row level security ON with NO policies means the anon and authenticated keys
-- can neither read nor write this table. Only the service role key, which is
-- held server side in a Vercel environment variable and never sent to a
-- browser, bypasses RLS. Leads are therefore unreadable publicly even if the
-- anon key is exposed, which it always is in client side code.
alter table public.leads enable row level security;
