
import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Progress } from '../ui/progress';
import { Badge } from '../ui/badge';
import { Separator } from '../ui/separator';
import { Button } from '../ui/button';
import { useDeveloperAgent } from '../../hooks/useDeveloperAgent';
import GitHubSourceInfo from './GitHubSourceInfo';
import { AlertCircle, File, FileX, GitBranch, Eye, AlertTriangle } from 'lucide-react';
import { Alert, AlertDescription } from '../ui/alert';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '../ui/collapsible';

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
    fileContext,
    fileRetrievalErrors,
    diagnosisLogs,
    simulateWork,
    tryAccessFile
  } = useDeveloperAgent();

  const [specificFile, setSpecificFile] = useState('');
  const [fileAccessResult, setFileAccessResult] = useState<{success: boolean, content?: string, error?: string} | null>(null);
  const [isTestingFile, setIsTestingFile] = useState(false);
  const [showDiffDetails, setShowDiffDetails] = useState(false);

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
            diff: `--- a/src/components/BuggyComponent.js
+++ b/src/components/BuggyComponent.js
@@ -1,7 +1,7 @@
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
          patchMode: 'unified_diff'
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

  // Check if we have file context data
  const fileCount = Object.keys(fileContext).length;
  const errorCount = Object.keys(fileRetrievalErrors).length;

  // Handle specific file access test
  const handleSpecificFileTest = async () => {
    if (!specificFile) return;
    setIsTestingFile(true);
    setFileAccessResult(null);
    
    try {
      const result = await tryAccessFile(specificFile);
      setFileAccessResult(result);
    } catch (error) {
      setFileAccessResult({
        success: false,
        error: `Unexpected error: ${error}`
      });
    } finally {
      setIsTestingFile(false);
    }
  };

  // Check if current mode uses full file replacement
  const isUsingFullReplacement = patchMode !== 'unified_diff' && patchMode !== 'line-by-line';

  return (
    <Card className="w-full">
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-medium">Developer Agent</CardTitle>
          <div className="flex items-center gap-2">
            {getStatusDisplay()}
            {patchMode === 'unified_diff' && (
              <Badge variant="outline" className="text-xs">
                <GitBranch className="w-3 h-3 mr-1" />
                Diff Mode
              </Badge>
            )}
          </div>
        </div>
        <CardDescription>
          Generates minimal code fixes using unified diffs
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/* GitHub Source Information */}
        <GitHubSourceInfo source={gitHubSource} fileErrors={fileRetrievalErrors} />

        {/* Diff-first approach warning */}
        {isUsingFullReplacement && (
          <Alert className="mb-4 bg-amber-50 border-amber-300">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            <AlertDescription className="text-xs text-amber-800">
              <div className="font-medium">Using full file replacement mode</div>
              <div className="mt-1">
                Consider switching to unified diff mode for safer, more precise changes.
                Current mode: {patchMode}
              </div>
            </AlertDescription>
          </Alert>
        )}

        {/* File Access Diagnostics */}
        {(errorCount > 0 || fileCount === 0) && (
          <Alert className="mb-4 bg-amber-50 border-amber-300">
            <AlertCircle className="h-4 w-4 text-amber-600" />
            <AlertDescription className="text-xs text-amber-800">
              {fileCount === 0 ? (
                <div className="font-medium">No files could be retrieved from the repository.</div>
              ) : (
                <div className="font-medium">{fileCount} files retrieved, {errorCount} file access errors.</div>
              )}
              <div className="mt-1">
                This may result in generic responses from the LLM as it lacks context about your code.
                Please check your GitHub configuration and repository access.
              </div>
              
              {/* Specific file test feature */}
              <div className="mt-2 pt-2 border-t border-amber-200">
                <div className="mb-1">Test specific file access:</div>
                <div className="flex gap-2 items-center">
                  <input
                    type="text"
                    value={specificFile}
                    onChange={(e) => setSpecificFile(e.target.value)}
                    placeholder="Enter file path (e.g., GraphRAG.py)"
                    className="flex-1 px-2 py-1 text-xs border rounded"
                  />
                  <Button 
                    size="sm" 
                    className="h-7 text-xs" 
                    onClick={handleSpecificFileTest}
                    disabled={isTestingFile || !specificFile}
                  >
                    {isTestingFile ? 'Testing...' : 'Test'}
                  </Button>
                </div>
                
                {fileAccessResult && (
                  <div className={`mt-2 p-2 rounded text-xs ${fileAccessResult.success ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                    <div className="flex items-center gap-1">
                      {fileAccessResult.success ? 
                        <File size={12} className="text-green-500" /> : 
                        <FileX size={12} className="text-red-500" />
                      }
                      <span>{fileAccessResult.success ? `Successfully accessed ${specificFile}` : fileAccessResult.error}</span>
                    </div>
                    {fileAccessResult.success && fileAccessResult.content && (
                      <div className="mt-1 p-1 bg-white/50 rounded border border-green-200 max-h-32 overflow-auto">
                        <pre className="text-xs whitespace-pre-wrap">{fileAccessResult.content.substring(0, 200)}...</pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </AlertDescription>
          </Alert>
        )}

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
                Attempt {attempt} of {maxAttempts} • Mode: {patchMode}
              </div>
            </>
          )}

          {status === 'success' && diffs && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-medium">Fix Generated</span>
                <div className="flex items-center gap-2">
                  {confidenceScore !== undefined && (
                    <Badge variant={confidenceScore > 75 ? "success" : "default"}>
                      {confidenceScore}% Confidence
                    </Badge>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowDiffDetails(!showDiffDetails)}
                    className="h-8 px-2 text-xs"
                  >
                    <Eye className="w-3 h-3 mr-1" />
                    {showDiffDetails ? 'Hide' : 'View'} Diff
                  </Button>
                </div>
              </div>
              
              <Separator />
              
              {/* Diff Summary */}
              <div className="text-sm space-y-2">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Mode: {patchMode}</span>
                  <span>{diffs.length} file{diffs.length !== 1 ? 's' : ''} changed</span>
                </div>
                
                {/* Diff Details */}
                {showDiffDetails && (
                  <div className="bg-muted p-3 rounded-md">
                    {diffs.map((diff, index) => (
                      <div key={index} className="mb-4 last:mb-0">
                        <div className="flex items-center gap-2 mb-2">
                          <GitBranch className="w-4 h-4 text-muted-foreground" />
                          <span className="text-xs font-medium text-muted-foreground">
                            {diff.filename}
                          </span>
                          <div className="flex gap-1">
                            <Badge variant="outline" className="text-xs px-1 py-0">
                              +{diff.linesAdded}
                            </Badge>
                            <Badge variant="outline" className="text-xs px-1 py-0">
                              -{diff.linesRemoved}
                            </Badge>
                          </div>
                        </div>
                        <div className="bg-black/90 p-2 rounded text-xs font-mono overflow-auto max-h-48">
                          <pre className="text-green-400 whitespace-pre-wrap">{diff.diff}</pre>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                
                {/* Simplified view when collapsed */}
                {!showDiffDetails && (
                  <div className="text-xs text-muted-foreground">
                    Files: {diffs.map(d => d.filename).join(', ')}
                  </div>
                )}
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
          
          {/* Debug Information */}
          <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
            <Collapsible>
              <CollapsibleTrigger asChild>
                <Button variant="ghost" className="text-xs text-muted-foreground p-0 h-auto">
                  <span className="font-medium">Debug Information</span>
                </Button>
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-2 space-y-2 bg-muted p-2 rounded-md text-xs">
                <div>
                  <strong>File Access:</strong> {fileCount} files retrieved, {errorCount} errors
                </div>
                <div>
                  <strong>Patch Mode:</strong> {patchMode}
                </div>
                <div>
                  <strong>Files:</strong> {Object.keys(fileContext).join(', ') || 'None'}
                </div>
                <div>
                  <strong>Errors:</strong> {Object.keys(fileRetrievalErrors).length > 0 
                    ? Object.entries(fileRetrievalErrors).map(([file, error]) => 
                        <div key={file} className="ml-2 text-red-500">{file}: {error}</div>
                      )
                    : 'None'}
                </div>
                <div>
                  <strong>Diagnosis Logs:</strong>
                  <div className="mt-1 p-1 bg-black/90 text-green-400 rounded max-h-48 overflow-auto">
                    {diagnosisLogs.map((log, i) => (
                      <div key={i}>{log}</div>
                    ))}
                  </div>
                </div>
              </CollapsibleContent>
            </Collapsible>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default DeveloperAgent;
