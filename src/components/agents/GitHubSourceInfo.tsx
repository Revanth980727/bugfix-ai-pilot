
import React from 'react';
import { GitHubSource } from '@/utils/developerSourceLogger';
import { Github } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

interface GitHubSourceInfoProps {
  source: GitHubSource | null;
}

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

  // Ensure we have a branch to display, using fallbacks
  const displayBranch = source.branch || source.default_branch || 'main';
  // Ensure we have a patch_mode to display, using fallback
  const displayPatchMode = source.patch_mode || 'line-by-line';

  return (
    <Alert className="mb-4 bg-muted/50">
      <div className="flex items-center gap-2">
        <Github size={16} />
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
                {displayBranch}
              </a>
            ) : (
              <span>{displayBranch}</span>
            )}
          </div>
          <div className="flex justify-between">
            <span className="font-medium">Patch Mode:</span>
            <span>{displayPatchMode}</span>
          </div>
        </div>
      </AlertDescription>
    </Alert>
  );
};

export default GitHubSourceInfo;
