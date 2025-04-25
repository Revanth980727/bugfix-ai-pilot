
import { Layout } from '@/components/layout/Layout';
import { Dashboard } from '@/components/dashboard/Dashboard';
import { SettingsForm } from '@/components/settings/SettingsForm';
import { useSettings } from '@/hooks/useSettings';

const Index = () => {
  const { settings, updateSettings, isConfigured } = useSettings();

  return (
    <Layout>
      <h1 className="text-3xl font-bold mb-8">Bug Fix AI Pilot</h1>
      {isConfigured ? (
        <Dashboard />
      ) : (
        <div className="max-w-4xl mx-auto">
          <SettingsForm currentSettings={settings} onSave={updateSettings} />
        </div>
      )}
    </Layout>
  );
};

export default Index;
