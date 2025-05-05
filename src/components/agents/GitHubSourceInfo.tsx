
import React from 'react';
import { GitHubSource } from '../../utils/developerSourceLogger';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';

interface GitHubSourceInfoProps {
  source: GitHubSource | null;
}

const GitHubSourceInfo = ({ source }: GitHubSourceInfoProps) => {
  if (!source) return null;
  
  return (
    <Card className="mb-4">
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium">GitHub Source</CardTitle>
      </CardHeader>
      <CardContent className="pb-2">
        <div className="flex flex-col space-y-1">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Repository:</span>
            <Badge variant="outline" className="font-mono text-xs">
              {source.repo_owner}/{source.repo_name}
            </Badge>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted-foreground">Branch:</span>
            <Badge variant="outline" className="font-mono text-xs">
              {source.branch}
            </Badge>
          </div>
          {source.file_path && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">File:</span>
              <Badge variant="outline" className="font-mono text-xs truncate max-w-[200px]" title={source.file_path}>
                {source.file_path}
              </Badge>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default GitHubSourceInfo;
