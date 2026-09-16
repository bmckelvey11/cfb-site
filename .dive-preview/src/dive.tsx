import { useDiveState, useSQLQuery } from '@motherduck/react-sql-query';
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

export const REQUIRED_DATABASES = [
  { type: 'database', path: 'md:cfb', alias: 'cfb' },
];

const N = (value: unknown): number => (value == null ? 0 : Number(value));
const SCHEMAS = ['raw', 'stg', 'core', 'meta'] as const;
const INK = '#231f20';
const MUTED = '#6a6a6a';
const BLUE = '#0777b3';
const GREY = '#adadad';

const compact = (n: number): string =>
  n >= 1_000_000
    ? `${(n / 1_000_000).toFixed(1)}M`
    : n >= 1_000
      ? `${(n / 1_000).toFixed(0)}K`
      : String(n);

const esc = (s: string): string => s.replace(/'/g, "''");

export default function CfbWarehouseExplorer() {
  const [view, setView] = useDiveState<'catalog' | 'coverage'>('view', 'catalog');
  const [schema, setSchema] = useDiveState<string>('schema', 'core');
  const [table, setTable] = useDiveState<string | null>('table', 'fact_game');
  const [search, setSearch] = useDiveState<string>('search', '');

  const summary = useSQLQuery(`
    SELECT
      (SELECT count(*) FROM duckdb_tables() WHERE database_name = 'cfb') AS n_tables,
      (SELECT sum(estimated_size) FROM duckdb_tables() WHERE database_name = 'cfb') AS n_rows,
      (SELECT count(*) FROM duckdb_columns() WHERE database_name = 'cfb') AS n_cols,
      (SELECT strftime(max(promoted_at), '%Y-%m-%d') FROM "cfb"."meta"."warehouse_version") AS promoted
  `);

  const seasons = useSQLQuery(`
    SELECT min(season) AS min_season, max(season) AS max_season
    FROM "cfb"."core"."fact_game"
  `);

  const tables = useSQLQuery(`
    SELECT table_name, estimated_size AS n_rows, column_count AS n_cols
    FROM duckdb_tables()
    WHERE database_name = 'cfb' AND schema_name = '${esc(schema)}'
    ORDER BY estimated_size DESC, table_name
  `);

  const columns = useSQLQuery(
    `
    SELECT column_name, data_type
    FROM duckdb_columns()
    WHERE database_name = 'cfb'
      AND schema_name = '${esc(schema)}'
      AND table_name = '${esc(table ?? '')}'
    ORDER BY column_index
  `,
    { enabled: table != null },
  );

  const bySeason = useSQLQuery(
    `
    SELECT
      season,
      count(*) AS games,
      sum(has_line::INT) AS lined,
      count(*) - sum(has_line::INT) AS unlined,
      sum(completed::INT) AS completed
    FROM "cfb"."core"."fact_game"
    GROUP BY 1
    ORDER BY 1
  `,
    { enabled: view === 'coverage' },
  );

  const sources = useSQLQuery(
    `
    SELECT
      CASE
        WHEN table_name ILIKE 'actionnetwork%' THEN 'ActionNetwork'
        WHEN table_name ILIKE '%massey%' THEN 'Massey'
        WHEN table_name ILIKE 'oddsapi%' OR table_name ILIKE 'odds_%' THEN 'Odds API'
        WHEN table_name ILIKE 'pff%' THEN 'PFF'
        ELSE 'CFBD'
      END AS source,
      count(*) AS n_tables,
      sum(estimated_size) AS n_rows
    FROM duckdb_tables()
    WHERE database_name = 'cfb' AND schema_name = 'raw'
    GROUP BY 1
    ORDER BY n_rows DESC
  `,
    { enabled: view === 'coverage' },
  );

  const summaryRow = (Array.isArray(summary.data) ? summary.data : [])[0];
  const seasonRow = (Array.isArray(seasons.data) ? seasons.data : [])[0];

  const tableRows = (Array.isArray(tables.data) ? tables.data : []).map((r) => ({
    name: String(r.table_name),
    rows: N(r.n_rows),
    cols: N(r.n_cols),
  }));
  const needle = search.trim().toLowerCase();
  const visibleTables = needle
    ? tableRows.filter((t) => t.name.toLowerCase().includes(needle))
    : tableRows;

  const columnRows = (Array.isArray(columns.data) ? columns.data : []).map((r) => ({
    name: String(r.column_name),
    type: String(r.data_type),
  }));

  const seasonRows = (Array.isArray(bySeason.data) ? bySeason.data : []).map((r) => ({
    season: String(r.season),
    games: N(r.games),
    lined: N(r.lined),
    completed: N(r.completed),
    line_pct: N(r.games) > 0 ? Math.round((N(r.lined) / N(r.games)) * 100) : 0,
  }));

  const sourceRows = (Array.isArray(sources.data) ? sources.data : []).map((r) => ({
    source: String(r.source),
    tables: N(r.n_tables),
    rows: N(r.n_rows),
  }));

  const selected = tableRows.find((t) => t.name === table);

  return (
    <div className="p-6" style={{ background: '#f8f8f8', minHeight: '100%' }}>
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-2xl font-semibold" style={{ color: INK }}>
            CFB Warehouse Explorer
          </h1>
          <p className="text-sm" style={{ color: MUTED }}>
            md:cfb — MotherDuck mirror of the local warehouse
            {summaryRow?.promoted ? `, promoted ${String(summaryRow.promoted)}` : ''}
          </p>
        </div>
        <div className="flex gap-1 text-sm">
          {(['catalog', 'coverage'] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className="px-3 py-1 rounded"
              style={{
                background: view === v ? BLUE : 'transparent',
                color: view === v ? '#fff' : MUTED,
                border: view === v ? 'none' : '1px solid #ddd',
              }}
            >
              {v === 'catalog' ? 'Catalog' : 'Coverage'}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-8 mt-6 mb-6">
        <Kpi
          loading={summary.isLoading}
          value={String(N(summaryRow?.n_tables))}
          label="Tables"
        />
        <Kpi
          loading={summary.isLoading}
          value={compact(N(summaryRow?.n_rows))}
          label="Rows"
        />
        <Kpi
          loading={summary.isLoading}
          value={String(N(summaryRow?.n_cols))}
          label="Columns"
        />
        <Kpi
          loading={seasons.isLoading}
          value={
            seasonRow
              ? `${N(seasonRow.min_season)}–${String(N(seasonRow.max_season)).slice(2)}`
              : '—'
          }
          label="Seasons in core.fact_game"
        />
      </div>

      {view === 'catalog' ? (
        <div className="grid grid-cols-2 gap-6">
          <section>
            <div className="flex items-center justify-between mb-2">
              <div className="flex gap-1 text-xs">
                {SCHEMAS.map((s) => (
                  <button
                    key={s}
                    onClick={() => {
                      setSchema(s);
                      setTable(null);
                    }}
                    className="px-2 py-1 rounded"
                    style={{
                      background: schema === s ? '#e6eff5' : 'transparent',
                      color: schema === s ? BLUE : MUTED,
                      fontWeight: schema === s ? 600 : 400,
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="filter tables…"
                className="text-xs px-2 py-1 rounded border"
                style={{ borderColor: '#ddd', width: 130 }}
              />
            </div>
            {tables.isLoading ? (
              <div className="animate-pulse rounded bg-gray-200" style={{ height: 260 }} />
            ) : tables.isError ? (
              <p role="alert" className="text-sm text-red-600">
                {String(tables.error)}
              </p>
            ) : (
              <div className="overflow-y-auto" style={{ height: 260 }}>
                <table className="w-full text-xs">
                  <thead>
                    <tr style={{ color: MUTED }}>
                      <th className="text-left font-normal pb-1">
                        table ({visibleTables.length})
                      </th>
                      <th className="text-right font-normal pb-1">rows</th>
                      <th className="text-right font-normal pb-1">cols</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleTables.map((t) => (
                      <tr
                        key={t.name}
                        onClick={() => setTable(t.name)}
                        className="cursor-pointer"
                        style={{
                          background: t.name === table ? '#e6eff5' : 'transparent',
                        }}
                      >
                        <td
                          className="py-1 pr-2 truncate"
                          style={{ color: t.name === table ? BLUE : INK, maxWidth: 190 }}
                        >
                          {t.name}
                        </td>
                        <td className="py-1 text-right" style={{ color: MUTED }}>
                          {compact(t.rows)}
                        </td>
                        <td className="py-1 text-right" style={{ color: MUTED }}>
                          {t.cols}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section>
            <p className="text-xs mb-2" style={{ color: MUTED }}>
              {table ? (
                <>
                  <span style={{ color: INK, fontWeight: 600 }}>
                    cfb.{schema}.{table}
                  </span>
                  {selected
                    ? ` — ${selected.rows.toLocaleString()} rows, ${selected.cols} columns`
                    : ''}
                </>
              ) : (
                'Select a table to see its columns'
              )}
            </p>
            {table == null ? null : columns.isLoading ? (
              <div className="animate-pulse rounded bg-gray-200" style={{ height: 260 }} />
            ) : columns.isError ? (
              <p role="alert" className="text-sm text-red-600">
                {String(columns.error)}
              </p>
            ) : (
              <div className="overflow-y-auto" style={{ height: 260 }}>
                <table className="w-full text-xs">
                  <thead>
                    <tr style={{ color: MUTED }}>
                      <th className="text-left font-normal pb-1">column</th>
                      <th className="text-left font-normal pb-1">type</th>
                    </tr>
                  </thead>
                  <tbody>
                    {columnRows.map((c) => (
                      <tr key={c.name}>
                        <td className="py-1 pr-2 truncate" style={{ color: INK, maxWidth: 170 }}>
                          {c.name}
                        </td>
                        <td className="py-1 truncate" style={{ color: MUTED, maxWidth: 190 }}>
                          {c.type}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      ) : (
        <div>
          <p className="text-sm font-semibold mb-1" style={{ color: INK }}>
            Games per season, betting-line coverage (core.fact_game)
          </p>
          {bySeason.isLoading ? (
            <div className="animate-pulse rounded bg-gray-200" style={{ height: 240 }} />
          ) : bySeason.isError ? (
            <p role="alert" className="text-sm text-red-600">
              {String(bySeason.error)}
            </p>
          ) : (
            <ResponsiveContainer width="100%" height={230}>
              <ComposedChart data={seasonRows} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
                <XAxis dataKey="season" fontSize={10} interval={2} />
                <YAxis
                  yAxisId="games"
                  tickFormatter={(v) => compact(Number(v))}
                  fontSize={10}
                  width={38}
                />
                <YAxis
                  yAxisId="pct"
                  orientation="right"
                  domain={[0, 100]}
                  tickFormatter={(v) => `${v}%`}
                  fontSize={10}
                  width={38}
                />
                <Tooltip
                  formatter={(v: unknown, name: unknown) =>
                    name === 'line coverage'
                      ? `${Number(v)}%`
                      : Number(v).toLocaleString()
                  }
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Bar
                  yAxisId="games"
                  dataKey="games"
                  name="games"
                  fill={GREY}
                  isAnimationActive={false}
                />
                <Line
                  yAxisId="pct"
                  type="linear"
                  dataKey="line_pct"
                  name="line coverage"
                  stroke={BLUE}
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          )}

          <p className="text-sm font-semibold mt-4 mb-1" style={{ color: INK }}>
            raw schema by vendor
          </p>
          {sources.isLoading ? (
            <div className="animate-pulse rounded bg-gray-200" style={{ height: 90 }} />
          ) : (
            <table className="text-xs" style={{ width: 320 }}>
              <thead>
                <tr style={{ color: MUTED }}>
                  <th className="text-left font-normal pb-1">source</th>
                  <th className="text-right font-normal pb-1">tables</th>
                  <th className="text-right font-normal pb-1">rows</th>
                </tr>
              </thead>
              <tbody>
                {sourceRows.map((s) => (
                  <tr key={s.source}>
                    <td className="py-1" style={{ color: INK }}>
                      {s.source}
                    </td>
                    <td className="py-1 text-right" style={{ color: MUTED }}>
                      {s.tables}
                    </td>
                    <td className="py-1 text-right" style={{ color: MUTED }}>
                      {compact(s.rows)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

function Kpi({
  loading,
  value,
  label,
}: {
  loading: boolean;
  value: string;
  label: string;
}) {
  return (
    <div>
      {loading ? (
        <div className="h-12 w-24 bg-gray-200 animate-pulse rounded" />
      ) : (
        <p className="text-4xl font-bold" style={{ color: INK }}>
          {value}
        </p>
      )}
      <p className="text-xs mt-1" style={{ color: MUTED }}>
        {label}
      </p>
    </div>
  );
}
