
import React from 'react';
import { Alert, AlertDescription } from '../ui/alert';
import { Badge } from '../ui/badge';
import { Github, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';

interface GitHubSourceInfoProps {
  source?: {
    repo: string;
    branch: string;
    commit: string;
    filesRetrieved: number;
    totalFiles: number;
    lastSync: string;
  };
  fileErrors?: Record<string, string>;
}

const GitHubSourceInfo: React.FC<GitHubSourceInfoProps> = ({ source, fileErrors }) => {
  if (!source) {
    return (
      <Alert className="mb-4 bg-gray-50 border-gray-300">
        <Github className="h-4 w-4 text-gray-600" />
        <AlertDescription className="text-xs text-gray-700">
          <div className="font-medium">Repository not initialized</div>
          <div className="mt-1">
            Waiting for repository to be cloned from GitHub configuration...
          </div>
        </AlertDescription>
      </Alert>
    );
  }

  const errorCount = Object.keys(fileErrors || {}).length;
  const hasErrors = errorCount > 0;
  const retrievalRate = source.totalFiles > 0 ? (source.filesRetrieved / source.totalFiles) * 100 : 0;

  return (
    <Alert className={`mb-4 ${hasErrors ? 'bg-amber-50 border-amber-300' : 'bg-green-50 border-green-300'}`}>
      <Github className={`h-4 w-4 ${hasErrors ? 'text-amber-600' : 'text-green-600'}`} />
      <AlertDescription className={`text-xs ${hasErrors ? 'text-amber-800' : 'text-green-800'}`}>
        <div className="flex items-center justify-between">
          <div className="font-medium">Repository: {source.repo}</div>
          <div className="flex gap-1">
            <Badge variant="outline" className="text-xs">
              {source.branch}
            </Badge>
            <Badge variant="outline" className="text-xs">
              {source.commit.substring(0, 7)}
            </Badge>
          </div>
        </div>
        
        <div className="mt-1 flex items-center justify-between">
          <div>
            Files: {source.filesRetrieved}/{source.totalFiles} ({retrievalRate.toFixed(0)}%)
          </div>
          <div className="text-xs text-gray-600">
            Last sync: {new Date(source.lastSync).toLocaleTimeString()}
          </div>
        </div>

        {hasErrors && (
          <div className="mt-2 pt-2 border-t border-amber-200">
            <div className="flex items-center gap-1 text-amber-700">
              <AlertTriangle className="h-3 w-3" />
              <span className="font-medium">{errorCount} file access error{errorCount !== 1 ? 's' : ''}</span>
            </div>
            <div className="mt-1 space-y-1">
              {Object.entries(fileErrors).slice(0, 3).map(([file, error]) => (
                <div key={file} className="flex items-center gap-1 text-xs">
                  <XCircle className="h-3 w-3 text-red-500" />
                  <span className="font-mono">{file}</span>
                  <span>: {error}</span>
                </div>
              ))}
              {errorCount > 3 && (
                <div className="text-xs">...and {errorCount - 3} more</div>
              )}
            </div>
          </div>
        )}

        {!hasErrors && (
          <div className="mt-1 flex items-center gap-1 text-green-700">
            <CheckCircle className="h-3 w-3" />
            <span className="text-xs">All repository files accessible</span>
          </div>
        )}
      </AlertDescription>
    </Alert>
  );
};

export default GitHubSourceInfo;
