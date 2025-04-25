
import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Form, FormControl, FormField, FormItem, FormLabel, FormMessage } from '@/components/ui/form';
import { toast } from '@/components/ui/sonner';
import { APISettings } from '@/types/settings';

const settingsSchema = z.object({
  githubToken: z.string().min(1, 'GitHub token is required'),
  jiraToken: z.string().min(1, 'JIRA token is required'),
  jiraUser: z.string().email('Must be a valid email'),
  jiraUrl: z.string().url('Must be a valid URL'),
});

interface SettingsFormProps {
  currentSettings?: APISettings | null;
  onSave: (settings: APISettings) => void;
}

export function SettingsForm({ currentSettings, onSave }: SettingsFormProps) {
  const form = useForm<APISettings>({
    resolver: zodResolver(settingsSchema),
    defaultValues: currentSettings || {
      githubToken: '',
      jiraToken: '',
      jiraUser: '',
      jiraUrl: '',
    },
  });

  const onSubmit = (data: APISettings) => {
    onSave(data);
    toast.success('Settings saved successfully');
  };

  return (
    <Card className="w-full max-w-2xl mx-auto">
      <CardHeader>
        <CardTitle>API Configuration</CardTitle>
        <CardDescription>
          Enter your GitHub and JIRA credentials to enable integration features.
          These will be stored securely in your browser's local storage.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
            <FormField
              control={form.control}
              name="githubToken"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>GitHub Personal Access Token</FormLabel>
                  <FormControl>
                    <Input type="password" placeholder="ghp_..." {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            
            <FormField
              control={form.control}
              name="jiraToken"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>JIRA API Token</FormLabel>
                  <FormControl>
                    <Input type="password" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            
            <FormField
              control={form.control}
              name="jiraUser"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>JIRA Email</FormLabel>
                  <FormControl>
                    <Input type="email" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            
            <FormField
              control={form.control}
              name="jiraUrl"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>JIRA URL</FormLabel>
                  <FormControl>
                    <Input type="url" placeholder="https://your-domain.atlassian.net" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            
            <Button type="submit" className="w-full">
              Save Settings
            </Button>
          </form>
        </Form>
      </CardContent>
    </Card>
  );
}
