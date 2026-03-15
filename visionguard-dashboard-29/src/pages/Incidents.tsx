import { useState } from 'react';
import { Header } from '@/components/layout/Header';
import { Button } from '@/components/ui/button';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Checkbox } from '@/components/ui/checkbox';
import { SeverityBadge, StatusBadge } from '@/components/common/StatusBadge';
import { Download, Loader2, RefreshCw } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { buildApiUrl, API_ENDPOINTS } from '@/config/api';
import type { Incident, IncidentFilters, Severity, IncidentStatus } from '@/types';

// Backend event type
interface BackendEvent {
  id: string;
  camera_id: string;
  event_type: string;
  severity: string;
  start_ts: number;
  end_ts: number;
  confidence: number;
  model_version: string;
  created_at: number;
}

interface EventsListResponse {
  total: number;
  limit: number;
  offset: number;
  events: BackendEvent[];
}

// Adapt backend event to frontend Incident
function adaptEventToIncident(event: BackendEvent): Incident {
  return {
    id: event.id,
    time: new Date(event.start_ts * 1000).toLocaleTimeString(),
    camera: {
      id: event.camera_id,
      name: event.camera_id,
      location: 'Camera',
      status: 'online',
      aiActive: true,
    },
    type: event.event_type as Incident['type'],
    severity: event.severity as Incident['severity'],
    status: 'active',
    createdAt: new Date(event.start_ts * 1000).toISOString(),
    updatedAt: new Date(event.end_ts * 1000).toISOString(),
  };
}

async function fetchJson<T>(endpoint: string, params?: Record<string, string>): Promise<T> {
  let url = buildApiUrl(endpoint);
  if (params) {
    url += '?' + new URLSearchParams(params).toString();
  }
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
  return res.json();
}

export default function Incidents() {
  const [filters, setFilters] = useState<IncidentFilters>({
    severity: 'all',
    type: 'all',
    status: 'all',
    camera: 'all',
  });
  const [selectedIncidents, setSelectedIncidents] = useState<string[]>([]);

  // Build query params from filters
  const queryParams: Record<string, string> = { limit: '50' };
  if (filters.severity && filters.severity !== 'all') {
    queryParams.severity = filters.severity;
  }
  if (filters.type && filters.type !== 'all') {
    queryParams.event_type = filters.type;
  }
  if (filters.camera && filters.camera !== 'all') {
    queryParams.camera_id = filters.camera;
  }

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['incidents', filters],
    queryFn: () => fetchJson<EventsListResponse>(API_ENDPOINTS.incidents.list, queryParams),
    refetchInterval: 10000,
  });

  const incidents = data?.events?.map(adaptEventToIncident) ?? [];

  const toggleSelectAll = () => {
    if (selectedIncidents.length === incidents.length) {
      setSelectedIncidents([]);
    } else {
      setSelectedIncidents(incidents.map((i) => i.id));
    }
  };

  const toggleSelect = (id: string) => {
    if (selectedIncidents.includes(id)) {
      setSelectedIncidents(selectedIncidents.filter((i) => i !== id));
    } else {
      setSelectedIncidents([...selectedIncidents, id]);
    }
  };

  return (
    <div className="min-h-screen">
      <Header title="Incidents" showDateNav={false} />
      <div className="p-6">
        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3 mb-6">
          <Select
            value={filters.severity as string}
            onValueChange={(value) => setFilters({ ...filters, severity: value as Severity | 'all' })}
          >
            <SelectTrigger className="w-40 bg-secondary/50">
              <SelectValue placeholder="All Severities" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Severities</SelectItem>
              <SelectItem value="critical">Critical</SelectItem>
              <SelectItem value="high">High</SelectItem>
              <SelectItem value="medium">Medium</SelectItem>
            </SelectContent>
          </Select>

          <Select
            value={filters.type as string}
            onValueChange={(value) => setFilters({ ...filters, type: value as Incident['type'] | 'all' })}
          >
            <SelectTrigger className="w-36 bg-secondary/50">
              <SelectValue placeholder="All Types" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              <SelectItem value="fire">Fire</SelectItem>
              <SelectItem value="weapon">Weapon</SelectItem>
              <SelectItem value="fall">Fall</SelectItem>
            </SelectContent>
          </Select>

          <Select
            value={filters.status as string}
            onValueChange={(value) => setFilters({ ...filters, status: value as IncidentStatus | 'all' })}
          >
            <SelectTrigger className="w-36 bg-secondary/50">
              <SelectValue placeholder="All Statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Statuses</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="acknowledged">Acknowledged</SelectItem>
              <SelectItem value="resolved">Resolved</SelectItem>
            </SelectContent>
          </Select>

          <Select defaultValue="7days">
            <SelectTrigger className="w-36 bg-secondary/50">
              <SelectValue placeholder="Time Period" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="24h">Last 24 Hours</SelectItem>
              <SelectItem value="7days">Last 7 Days</SelectItem>
              <SelectItem value="30days">Last 30 Days</SelectItem>
              <SelectItem value="custom">Custom Range</SelectItem>
            </SelectContent>
          </Select>

          <div className="ml-auto flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              {data?.total ?? 0} total events
            </span>
            <Button variant="outline" className="gap-2">
              <Download className="h-4 w-4" />
              Export
            </Button>
          </div>
        </div>

        {/* Loading state */}
        {isLoading && (
          <div className="flex items-center justify-center min-h-[40vh]">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
          </div>
        )}

        {/* Error state */}
        {error && (
          <div className="flex flex-col items-center justify-center gap-4 min-h-[40vh]">
            <p className="text-severity-critical text-lg">Failed to load incidents</p>
            <p className="text-muted-foreground text-sm">{(error as Error).message}</p>
            <Button variant="outline" className="gap-2" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
              Retry
            </Button>
          </div>
        )}

        {/* Incidents Table */}
        {!isLoading && !error && (
          <div className="dashboard-card">
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th className="w-12">
                      <Checkbox
                        checked={incidents.length > 0 && selectedIncidents.length === incidents.length}
                        onCheckedChange={toggleSelectAll}
                      />
                    </th>
                    <th>ID</th>
                    <th>Time</th>
                    <th>Camera</th>
                    <th>Type</th>
                    <th>Severity</th>
                    <th>Confidence</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {incidents.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="text-center text-muted-foreground py-8">
                        No incidents found
                      </td>
                    </tr>
                  ) : (
                    incidents.map((incident) => (
                      <tr key={incident.id} className="hover:bg-secondary/30 transition-colors">
                        <td>
                          <Checkbox
                            checked={selectedIncidents.includes(incident.id)}
                            onCheckedChange={() => toggleSelect(incident.id)}
                          />
                        </td>
                        <td className="text-sm font-mono">#{incident.id.slice(0, 8)}</td>
                        <td className="text-sm">{incident.time}</td>
                        <td>
                          <div>
                            <div className="text-sm font-medium">{incident.camera.name}</div>
                            <div className="text-xs text-muted-foreground">
                              {incident.camera.location}
                            </div>
                          </div>
                        </td>
                        <td className="text-sm capitalize">{incident.type}</td>
                        <td>
                          <SeverityBadge severity={incident.severity} />
                        </td>
                        <td className="text-sm font-mono">
                          {/* Confidence is stored on the original event, show from adapted data */}
                          -
                        </td>
                        <td>
                          <StatusBadge status={incident.status} />
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
