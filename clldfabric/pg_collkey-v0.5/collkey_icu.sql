CREATE OR REPLACE FUNCTION collkey (text, text, bool, int4, bool) RETURNS bytea
  LANGUAGE 'c' IMMUTABLE STRICT AS
  '$libdir/collkey_icu.so',
  'pgsqlext_collkey';

CREATE OR REPLACE FUNCTION collkey (text, text) RETURNS bytea
  LANGUAGE SQL IMMUTABLE STRICT AS $$
  SELECT collkey ($1, $2, false, 0, true);
  $$;

CREATE OR REPLACE FUNCTION collkey (text) RETURNS bytea
  LANGUAGE SQL IMMUTABLE STRICT AS $$
  SELECT collkey ($1, 'root', false, 0, true);
  $$;

