import { useState } from 'react';
import { Header } from '@/components/layout/Header';
import { cn } from '@/lib/utils';

type SettingsTab = 'general' | 'alerts' | 'storage' | 'models' | 'privacy' | 'system';

interface TabItem {
  id: SettingsTab;
  label: string;
}

const tabs: TabItem[] = [
  { id: 'general', label: 'General' },
  { id: 'alerts', label: 'Alerts' },
  { id: 'storage', label: 'Storage' },
  { id: 'models', label: 'Models' },
  { id: 'privacy', label: 'Privacy' },
  { id: 'system', label: 'System' },
];

const systemInfo = {
  version: '2.0.1',
  build: '20241226-prod',
  uptime: '7d 14h 23m',
};

export default function Settings() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('system');

  return (
    <div className="min-h-screen">
      <Header title="Settings" showDateNav={false} />
      <div className="p-6">
        <div className="dashboard-card">
          <div className="flex flex-col md:flex-row">
            {/* Sidebar Navigation */}
            <div className="w-full md:w-48 border-b md:border-b-0 md:border-r border-border p-4">
              <nav className="flex md:flex-col gap-1 overflow-x-auto md:overflow-visible">
                {tabs.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setActiveTab(tab.id)}
                    className={cn(
                      'px-4 py-2 text-sm font-medium rounded-lg text-left whitespace-nowrap transition-colors',
                      activeTab === tab.id
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:bg-secondary/50 hover:text-foreground'
                    )}
                  >
                    {tab.label}
                  </button>
                ))}
              </nav>
            </div>

            {/* Content Area */}
            <div className="flex-1 p-6">
              {activeTab === 'system' && (
                <div className="animate-fade-in">
                  <h2 className="text-2xl font-bold mb-6">System Information</h2>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="rounded-xl bg-secondary/30 p-4">
                      <p className="text-sm text-muted-foreground mb-1">Version</p>
                      <p className="text-xl font-semibold">{systemInfo.version}</p>
                    </div>
                    <div className="rounded-xl bg-secondary/30 p-4">
                      <p className="text-sm text-muted-foreground mb-1">Build</p>
                      <p className="text-xl font-semibold">{systemInfo.build}</p>
                    </div>
                    <div className="rounded-xl bg-secondary/30 p-4">
                      <p className="text-sm text-muted-foreground mb-1">Uptime</p>
                      <p className="text-xl font-semibold">{systemInfo.uptime}</p>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'general' && (
                <div className="animate-fade-in">
                  <h2 className="text-2xl font-bold mb-6">General Settings</h2>
                  <p className="text-muted-foreground">
                    General configuration options will be available here when connected to the backend.
                  </p>
                </div>
              )}

              {activeTab === 'alerts' && (
                <div className="animate-fade-in">
                  <h2 className="text-2xl font-bold mb-6">Alert Settings</h2>
                  <p className="text-muted-foreground">
                    Configure notification preferences and alert thresholds when connected to the backend.
                  </p>
                </div>
              )}

              {activeTab === 'storage' && (
                <div className="animate-fade-in">
                  <h2 className="text-2xl font-bold mb-6">Storage Settings</h2>
                  <p className="text-muted-foreground">
                    Configure data retention and storage policies when connected to the backend.
                  </p>
                </div>
              )}

              {activeTab === 'models' && (
                <div className="animate-fade-in">
                  <h2 className="text-2xl font-bold mb-6">AI Model Settings</h2>
                  <p className="text-muted-foreground">
                    Configure AI detection models and confidence thresholds when connected to the backend.
                  </p>
                </div>
              )}

              {activeTab === 'privacy' && (
                <div className="animate-fade-in">
                  <h2 className="text-2xl font-bold mb-6">Privacy Settings</h2>
                  <p className="text-muted-foreground">
                    Configure privacy options and data anonymization settings when connected to the backend.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
