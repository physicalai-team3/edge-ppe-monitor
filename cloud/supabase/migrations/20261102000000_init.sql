-- [contract] edge-ppe-monitor 초기 스키마 (docs/03-contracts.md §6)
-- 👤 팀원 4 가 Supabase SQL Editor 에서 실행하거나: supabase db push
-- 쓰기는 secret 키(RLS 우회)를 가진 gateway / cloud-seed 만. 웹(publishable 키)은 읽기만.

-- ── 위반 기록 ────────────────────────────────────────────
create table if not exists public.violations (
  id               uuid primary key,                 -- gateway 가 생성 (재시도해도 중복 없음)
  created_at       timestamptz not null default now(),
  captured_at      timestamptz not null,             -- 촬영 시각(UTC). 웹은 이 값으로 정렬·통계
  device_id        text not null check (device_id ~ '^[a-z0-9-]{1,32}$'),
  gateway_id       text not null,
  frame_seq        integer,
  person_count     smallint not null check (person_count >= 1),
  no_helmet_count  smallint not null default 0 check (no_helmet_count between 0 and person_count),
  no_vest_count    smallint not null default 0 check (no_vest_count between 0 and person_count),
  violation_types  text[] not null
                   check (cardinality(violation_types) >= 1
                          and violation_types <@ array['no_helmet', 'no_vest']::text[]),
  image_path       text not null,                    -- <device_id>/<YYYY-MM-DD>/<id>.jpg
  image_w          smallint,
  image_h          smallint,
  persons          jsonb not null default '[]'::jsonb,
  detections       jsonb not null default '[]'::jsonb,
  model            text,
  infer_ms         integer
);

create index if not exists violations_captured_at_idx on public.violations (captured_at desc);
create index if not exists violations_device_captured_idx on public.violations (device_id, captured_at desc);

alter table public.violations enable row level security;

drop policy if exists "dashboard reads violations" on public.violations;
create policy "dashboard reads violations"
  on public.violations for select
  to anon, authenticated
  using (true);

-- ── 장치 상태 (2차) ──────────────────────────────────────
create table if not exists public.devices (
  device_id   text primary key check (device_id ~ '^[a-z0-9-]{1,32}$'),
  gateway_id  text,
  last_seen   timestamptz not null default now(),   -- gateway 가 하트비트를 받은 시각
  fw_version  text,
  rssi        integer,
  uptime_s    integer,
  free_heap   integer,
  last_error  text
);

alter table public.devices enable row level security;

drop policy if exists "dashboard reads devices" on public.devices;
create policy "dashboard reads devices"
  on public.devices for select
  to anon, authenticated
  using (true);

-- ── Realtime: 웹이 INSERT/UPDATE 를 바로 받는다 ───────────
do $$
begin
  if not exists (select 1 from pg_publication_tables
                 where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'violations') then
    alter publication supabase_realtime add table public.violations;
  end if;
  if not exists (select 1 from pg_publication_tables
                 where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'devices') then
    alter publication supabase_realtime add table public.devices;
  end if;
end $$;

-- ── Storage: 위반 사진 (private 버킷, 웹은 서명 URL 로 읽기) ──
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('violation-images', 'violation-images', false, 1048576, array['image/jpeg'])
on conflict (id) do nothing;

-- 데모용: publishable 키로 서명 URL 발급 허용. 실제 운영에서는 to authenticated 로 좁힌다 (작업자 얼굴 = 개인정보)
drop policy if exists "dashboard reads violation images" on storage.objects;
create policy "dashboard reads violation images"
  on storage.objects for select
  to anon, authenticated
  using (bucket_id = 'violation-images');
