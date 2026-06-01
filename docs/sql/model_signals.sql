-- model_signals: time-series storage for all model outputs
-- (commodity overlay, h-model, liquidity composite, p-model, etc.)
--
-- Run in Supabase SQL Editor once, then enable RLS.

create table if not exists public.model_signals (
  id          uuid default gen_random_uuid() primary key,
  model_name  text not null,            -- 'commodity', 'h_model', 'p_model', 'liquidity_composite'
  run_at      timestamptz not null,     -- when the model ran (HKT-aware)
  slot        text,                     -- '0945', '2145', or null
  asset       text,                     -- 'Gold', 'Silver', 'Copper', 'DXY', instrument ticker, or null
  signal      text,                     -- 'GREEN', 'YELLOW', 'RED', 'EXPANDING', 'LONG', etc.
  score       double precision,         -- 0-100 for commodity, -100 to +100 for h_model
  regime      text,                     -- 'RISK_ON', 'RISK_OFF', 'NEUTRAL', 'USD_STRENGTH', etc.
  metadata    jsonb default '{}'::jsonb, -- model-specific extras (alerts, actions, evidence)
  created_at  timestamptz default now()
);

-- Fast lookups for dashboard time-series queries
create index if not exists idx_model_signals_lookup
  on public.model_signals (model_name, asset, run_at desc);

-- RLS: browser reads with anon key, Python inserts with service_role key
alter table public.model_signals enable row level security;

-- Allow anonymous SELECT (dashboard reads via JS client with anon key)
create policy "anon_read_model_signals"
  on public.model_signals for select to anon using (true);

-- Allow service_role INSERT (Python writes with service key)
create policy "service_insert_model_signals"
  on public.model_signals for insert to service_role with check (true);

-- Convenience view: latest signal per model+asset
create or replace view public.latest_model_signals as
select distinct on (model_name, asset)
  id, model_name, run_at, slot, asset, signal, score, regime, metadata, created_at
from public.model_signals
order by model_name, asset, run_at desc;
