"use client";

import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ArrowLeft, BarChart2, Zap, Activity, Clock } from "lucide-react";
import { apiFetch } from "@/lib/api";

interface DailyStat {
  date: string;
  total_events: number;
  total_tokens: number;
  events_by_type: Record<string, number>;
}

interface AnalyticsSummary {
  total_events: number;
  total_tokens: number;
  events_by_type: Record<string, number>;
  daily_stats: DailyStat[];
  recent_events: Array<{
    id: string;
    event_type: string;
    provider: string | null;
    model: string | null;
    tokens_used: number | null;
    latency_ms: number | null;
    created_at: string;
  }>;
}

function StatCard({
  title,
  value,
  icon: Icon,
  sub,
}: {
  title: string;
  value: string | number;
  icon: React.ElementType;
  sub?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className="text-2xl font-bold">{value.toLocaleString()}</p>
            {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
          </div>
          <Icon className="h-8 w-8 text-muted-foreground/40" />
        </div>
      </CardContent>
    </Card>
  );
}

function MiniBar({
  label,
  value,
  max,
}: {
  label: string;
  value: number;
  max: number;
}) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground truncate max-w-[120px]">{label}</span>
        <span className="font-medium">{value}</span>
      </div>
      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
        <div
          className="h-full rounded-full bg-primary"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function AnalyticsPage() {
  const router = useRouter();

  const { data, isLoading, isError } = useQuery<AnalyticsSummary>({
    queryKey: ["analytics", "summary"],
    queryFn: () => apiFetch<AnalyticsSummary>(`/api/v1/analytics/summary?limit=200`),
    staleTime: 60_000,
  });

  return (
    <div className="flex min-h-screen justify-center bg-background p-4">
      <div className="w-full max-w-4xl py-10 space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => router.push("/")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">Analytics</h1>
            <p className="text-sm text-muted-foreground">Usage overview</p>
          </div>
        </div>

        {/* Error state */}
        {isError && (
          <Card>
            <CardContent className="p-8 text-center text-muted-foreground">
              Failed to load analytics. Please try again later.
            </CardContent>
          </Card>
        )}

        {/* Loading skeleton */}
        {isLoading && (
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            {[...Array(4)].map((_, i) => (
              <Card key={i}>
                <CardContent className="pt-6">
                  <div className="space-y-2 animate-pulse">
                    <div className="h-3 w-24 rounded bg-muted" />
                    <div className="h-7 w-16 rounded bg-muted" />
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {data && (
          <>
            {/* Summary stats */}
            <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
              <StatCard
                title="Total Events"
                value={data.total_events}
                icon={Activity}
              />
              <StatCard
                title="Total Tokens"
                value={data.total_tokens}
                icon={Zap}
              />
              <StatCard
                title="Avg Tokens/Event"
                value={
                  data.total_events > 0
                    ? Math.round(data.total_tokens / data.total_events)
                    : 0
                }
                icon={BarChart2}
              />
              <StatCard
                title="Unique Event Types"
                value={Object.keys(data.events_by_type).length}
                icon={Clock}
                sub="across all time"
              />
            </div>

            {/* Events by type */}
            <div className="grid gap-4 md:grid-cols-2">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Events by Type</CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {Object.entries(data.events_by_type)
                    .sort(([, a], [, b]) => b - a)
                    .map(([type, count]) => (
                      <MiniBar
                        key={type}
                        label={type}
                        value={count as number}
                        max={data.total_events}
                      />
                    ))}
                  {Object.keys(data.events_by_type).length === 0 && (
                    <p className="text-sm text-muted-foreground">No events yet.</p>
                  )}
                </CardContent>
              </Card>

              {/* Daily activity chart */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Daily Activity</CardTitle>
                </CardHeader>
                <CardContent>
                  {data.daily_stats.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No daily data yet.</p>
                  ) : (
                    <div className="flex items-end gap-1 h-32">
                      {(() => {
                        const maxEvents = Math.max(
                          ...data.daily_stats.map((s) => s.total_events),
                          1,
                        );
                        return data.daily_stats.slice(-14).map((stat) => {
                          const pct = (stat.total_events / maxEvents) * 100;
                          return (
                            <div
                              key={stat.date}
                              className="flex-1 group relative"
                              title={`${stat.date}: ${stat.total_events} events`}
                            >
                              <div
                                className="w-full rounded-sm bg-primary/70 group-hover:bg-primary transition-colors"
                                style={{ height: `${Math.max(pct, 4)}%` }}
                              />
                            </div>
                          );
                        });
                      })()}
                    </div>
                  )}
                  <p className="text-xs text-muted-foreground mt-2">Last 14 days</p>
                </CardContent>
              </Card>
            </div>

            {/* Recent events table */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Recent Events</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {data.recent_events.slice(0, 20).map((ev) => (
                    <div
                      key={ev.id}
                      className="flex items-center justify-between text-sm py-1 border-b last:border-0"
                    >
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs py-0">
                          {ev.event_type}
                        </Badge>
                        {ev.provider && (
                          <span className="text-muted-foreground">{ev.provider}</span>
                        )}
                        {ev.model && (
                          <span className="text-muted-foreground text-xs">{ev.model}</span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-muted-foreground text-xs">
                        {ev.tokens_used != null && (
                          <span>{ev.tokens_used.toLocaleString()} tok</span>
                        )}
                        {ev.latency_ms != null && (
                          <span>{ev.latency_ms} ms</span>
                        )}
                        <span>
                          {new Date(ev.created_at).toLocaleDateString()}
                        </span>
                      </div>
                    </div>
                  ))}
                  {data.recent_events.length === 0 && (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      No recent events.
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
