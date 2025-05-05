
import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Progress } from '../ui/progress';
import { Badge } from '../ui/badge';
import { Separator } from '../ui/separator';
import { useDeveloperAgent } from '../../hooks/useDeveloperAgent';
import GitHubSourceInfo from './GitHubSourceInfo';

interface DeveloperAgentProps {
  onStart?: () => void;
  onComplete?: () => void;
}

const DeveloperAgent = ({ onStart, onComplete }: DeveloperAgentProps) => {
  const {
    status,
    progress,
    diffs,
    attempt,
    maxAttempts,
    confidenceScore,
    escalationReason,
    earlyEscalation,
    patchMode,
    gitHubSource,
    simulateWork
  } = useDeveloperAgent();

  // For demonstration purposes, simulate work when status is idle and component mounts
  React.useEffect(() => {
    if (status === 'idle') {
      onStart?.();
      simulateWork(
        () => {
          if (onComplete) onComplete();
        }, 
        [
          { 
            filename: 'src/components/BuggyComponent.js', 
            diff: `@@ -1,7 +1,7 @@
 const BuggyComponent = () => {
-  const handleClick = () => {
-    console.log("This has a bug");
+  const handleClick = (event) => {
+    console.log("Bug fixed", event);
     return true;
   };
 
@@ -9,7 +9,7 @@
   return (
     <div>
       <h2>Component</h2>
-      <button onClick={handleClick()}>Click me</button>
+      <button onClick={handleClick}>Click me</button>
     </div>
   );
 };`,
            linesAdded: 2,
            linesRemoved: 2
          }
        ],
        1,
        85,
        { 
          patchSize: 'medium', 
          changedFiles: 1, 
          linesChanged: 4 
        },
        {
          responseQuality: 'good',
          patchMode: patchMode
        }
      );
    }
  }, []);

  const getStatusDisplay = () => {
    switch (status) {
      case 'working':
        return <Badge>Working</Badge>;
      case 'success':
        return <Badge variant="success">Success</Badge>;
      case 'error':
        return <Badge variant="destructive">Failed</Badge>;
      case 'escalated':
        return <Badge variant="default">Escalated</Badge>;
      default:
        return <Badge variant="outline">Idle</Badge>;
    }
  };

  return (
    <Card className="w-full">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-medium">Developer Agent</CardTitle>
          {getStatusDisplay()}
        </div>
        <CardDescription>
          Generates code fixes for identified bugs
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/* GitHub Source Information */}
        {gitHubSource && <GitHubSourceInfo source={gitHubSource} />}

        {/* Agent Status */}
        <div className="space-y-4">
          {status === 'working' && (
            <>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm">Generating fix...</span>
                <span className="text-sm font-medium">{progress}%</span>
              </div>
              <Progress value={progress} className="h-2" />
              <div className="text-xs text-muted-foreground">
                Attempt {attempt} of {maxAttempts}
              </div>
            </>
          )}

          {status === 'success' && diffs && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span>Fix Generated</span>
                {confidenceScore !== undefined && (
                  <Badge variant={confidenceScore > 75 ? "success" : "default"}>
                    {confidenceScore}% Confidence
                  </Badge>
                )}
              </div>
              <Separator />
              <div className="text-sm">
                <div className="font-medium mb-1">Patch Mode: {patchMode}</div>
                <div className="bg-muted p-2 rounded-md text-xs font-mono overflow-auto max-h-48">
                  {diffs.map((diff, index) => (
                    <div key={index} className="mb-2">
                      <div className="text-xs text-muted-foreground mb-1">
                        {diff.filename}
                      </div>
                      <pre className="whitespace-pre-wrap">{diff.diff}</pre>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {(status === 'error' || status === 'escalated') && (
            <div className="bg-destructive/10 p-3 rounded-md">
              <div className="font-medium text-destructive mb-1">
                {earlyEscalation ? "Early Escalation" : "Error Occurred"}
              </div>
              <p className="text-sm">{escalationReason || "Unknown error"}</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default DeveloperAgent;
