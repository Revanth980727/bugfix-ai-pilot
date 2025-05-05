
import React from 'react';
import { GitHubSource } from '@/utils/developerSourceLogger';
import { GitHubIcon } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

interface GitHubSourceInfoProps {
  source: GitHubSource | null;
}

const GitHubIcon = () => (
  <svg 
    xmlns="http://www.w3.org/2000/svg" 
    width="16" 
    height="16" 
    viewBox="0 0 24 24" 
    fill="none" 
    stroke="currentColor" 
    strokeWidth="2" 
    strokeLinecap="round" 
    strokeLinejoin="round" 
    className="lucide lucide-github"
  >
    <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
    <path d="M9 18c-4.51 2-5-2-7-2" />
  </svg>
);

const GitHubSourceInfo: React.FC<GitHubSourceInfoProps> = ({ source }) => {
  if (!source || (!source.repo_owner && !source.repo_name)) {
    return null;
  }

  const repoUrl = source.repo_owner && source.repo_name 
    ? `https://github.com/${source.repo_owner}/${source.repo_name}` 
    : null;
  
  const branchUrl = repoUrl && source.branch 
    ? `${repoUrl}/tree/${source.branch}` 
    : null;

  return (
    <Alert className="mb-4 bg-muted/50">
      <div className="flex items-center gap-2">
        <GitHubIcon />
        <AlertTitle>GitHub Source</AlertTitle>
      </div>
      <AlertDescription className="mt-2 text-xs">
        <div className="space-y-1">
          <div className="flex justify-between">
            <span className="font-medium">Repository:</span>
            {repoUrl ? (
              <a 
                href={repoUrl} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline dark:text-blue-400"
              >
                {source.repo_owner}/{source.repo_name}
              </a>
            ) : (
              <span>{source.repo_owner}/{source.repo_name}</span>
            )}
          </div>
          <div className="flex justify-between">
            <span className="font-medium">Branch:</span>
            {branchUrl ? (
              <a 
                href={branchUrl} 
                target="_blank" 
                rel="noopener noreferrer"
                className="text-blue-600 hover:underline dark:text-blue-400"
              >
                {source.branch || source.default_branch}
              </a>
            ) : (
              <span>{source.branch || source.default_branch}</span>
            )}
          </div>
          {source.patch_mode && (
            <div className="flex justify-between">
              <span className="font-medium">Patch Mode:</span>
              <span>{source.patch_mode}</span>
            </div>
          )}
        </div>
      </AlertDescription>
    </Alert>
  );
};

export default GitHubSourceInfo;
