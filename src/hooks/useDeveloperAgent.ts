import { useState, useEffect } from 'react';
import { CodeDiff } from '../types/ticket';
import { AgentStatus } from './useDashboardState';
import { extractGitHubSourceFromEnv, logGitHubSource, GitHubSource, isValidGitHubSource } from '../utils/developerSourceLogger';
import { getGitHubConfig, checkFileExists, getFileContent } from '../services/githubService';

export function useDeveloperAgent() {
  const [status, setStatus] = useState<AgentStatus>('idle');
  const [progress, setProgress] = useState(0);
  const [diffs, setDiffs] = useState<CodeDiff[] | undefined>(undefined);
  const [attempt, setAttempt] = useState(1);
  const [confidenceScore, setConfidenceScore] = useState<number | undefined>(undefined);
  const [escalationReason, setEscalationReason] = useState<string | undefined>(undefined);
  const [earlyEscalation, setEarlyEscalation] = useState(false);
  const [patchAnalytics, setPatchAnalytics] = useState<any>(null);
  const [rawOpenAIResponse, setRawOpenAIResponse] = useState<string | null>(null);
  const [responseQuality, setResponseQuality] = useState<'good' | 'generic' | 'invalid' | undefined>(undefined);
  const [patchMode, setPatchMode] = useState<'intelligent' | 'line-by-line' | 'direct'>('line-by-line');
  const [gitHubSource, setGitHubSource] = useState<GitHubSource | null>(null);
  const [fileContext, setFileContext] = useState<Record<string, string>>({});
  const [fileRetrievalErrors, setFileRetrievalErrors] = useState<Record<string, string>>({});
  const maxAttempts = 4;

  // Get GitHub configuration on component mount
  useEffect(() => {
    const fetchGitHubConfig = async () => {
      try {
        console.log("Initializing developer agent: Fetching GitHub config...");
        const config = await getGitHubConfig();
        if (config) {
          const source = {
            repo_owner: config.repo_owner,
            repo_name: config.repo_name,
            branch: config.branch,
            default_branch: config.default_branch || 'main', // Provide default value
            patch_mode: config.patch_mode || 'line-by-line' // Provide default value
          };
          
          setGitHubSource(source);
          setPatchMode(config.patch_mode || 'line-by-line');
          
          // Validate the GitHub source
          const isValid = isValidGitHubSource(source);
          console.log(`GitHub config validation result: ${isValid ? 'Valid' : 'Invalid'}`);
          
          // Attempt to fetch some example files to verify access
          if (isValid) {
            await testRepositoryAccess(source);
          } else {
            // Try from environment as fallback
            console.log("Config invalid, trying environment variables as fallback...");
            const envSource = extractGitHubSourceFromEnv();
            const envValid = isValidGitHubSource(envSource);
            
            if (envValid) {
              setGitHubSource(envSource);
              setPatchMode(envSource.patch_mode as 'intelligent' | 'line-by-line' | 'direct' || 'line-by-line');
              await testRepositoryAccess(envSource);
            } else {
              console.error("Neither config nor env provides valid GitHub source information");
            }
          }
        } else {
          console.warn("No GitHub config returned, will try environment variables as fallback");
          const envSource = extractGitHubSourceFromEnv();
          const isValid = isValidGitHubSource(envSource);
          
          if (isValid) {
            setGitHubSource(envSource);
            setPatchMode(envSource.patch_mode as 'intelligent' | 'line-by-line' | 'direct' || 'line-by-line');
            await testRepositoryAccess(envSource);
          } else {
            console.error("Environment variables do not provide valid GitHub source information");
          }
        }
      } catch (error) {
        console.error('Error fetching GitHub config:', error);
        setFileRetrievalErrors(prev => ({
          ...prev,
          'config': `Failed to fetch GitHub configuration: ${error}`
        }));
      }
    };
    
    fetchGitHubConfig();
  }, []);
  
  /**
   * Test repository access by trying to fetch a common file
   */
  const testRepositoryAccess = async (source: GitHubSource) => {
    try {
      console.log(`Testing repository access for ${source.repo_owner}/${source.repo_name}...`);
      
      // Try to access some common files
      const commonFiles = [
        'README.md',
        'package.json',
        'src/index.js',
        'src/index.ts',
        'src/App.js',
        'src/App.tsx',
        'GraphRAG.py' // Specific file from logs
      ];
      
      let accessSuccessful = false;
      const errors: Record<string, string> = {};
      
      for (const file of commonFiles) {
        try {
          console.log(`Testing access to file: ${file}`);
          const exists = await checkFileExists(file);
          if (exists) {
            console.log(`Found file in repository: ${file}`);
            const content = await getFileContent(file);
            if (content) {
              console.log(`Successfully retrieved content for ${file} (${content.length} bytes)`);
              // Store this file content in our context
              setFileContext(prev => ({
                ...prev,
                [file]: content
              }));
              accessSuccessful = true;
            } else {
              errors[file] = `File exists but content is empty or null`;
              console.warn(`File ${file} exists but content could not be retrieved`);
            }
          } else {
            errors[file] = 'File does not exist in repository';
            console.log(`File ${file} does not exist in repository`);
          }
        } catch (err) {
          errors[file] = `Error accessing file: ${err}`;
          console.error(`Error accessing file ${file}:`, err);
        }
      }
      
      setFileRetrievalErrors(errors);
      
      if (!accessSuccessful) {
        console.warn("Could not access any common files in the repository");
      } else {
        console.log("Repository access test: SUCCESS");
      }
      
    } catch (error) {
      console.error("Repository access test failed:", error);
      setFileRetrievalErrors(prev => ({
        ...prev, 
        'access_test': `Repository access test failed: ${error}`
      }));
    }
  };

  /**
   * Simulate developer agent work
   */
  const simulateWork = (
    onComplete: () => void, 
    mockDiffs: CodeDiff[], 
    currentAttempt: number = 1,
    patchConfidence?: number,
    analytics?: any,
    options?: {
      responseQuality?: 'good' | 'generic' | 'invalid';
      rawResponse?: string;
      patchMode?: 'intelligent' | 'line-by-line' | 'direct';
    }
  ) => {
    setStatus('working');
    setAttempt(currentAttempt);
    console.log(`Developer agent starting work (attempt ${currentAttempt}/${maxAttempts})`);
    console.log(`Using patch mode: ${options?.patchMode || patchMode}`);
    
    if (patchConfidence !== undefined) {
      setConfidenceScore(patchConfidence);
    }
    
    if (analytics) {
      setPatchAnalytics(analytics);
    }
    
    if (options?.responseQuality) {
      setResponseQuality(options.responseQuality);
    }
    
    if (options?.rawResponse) {
      setRawOpenAIResponse(options.rawResponse);
    }
    
    if (options?.patchMode) {
      setPatchMode(options.patchMode);
    }

    // If GitHub source isn't set yet from config, try from env
    if (!gitHubSource) {
      console.log("No GitHub source yet, extracting from environment...");
      const source = extractGitHubSourceFromEnv();
      // Ensure default_branch and patch_mode have fallback values
      source.default_branch = source.default_branch || 'main';
      source.patch_mode = source.patch_mode || 'line-by-line';
      setGitHubSource(source);
      logGitHubSource(source);
      
      // Validate the GitHub source
      const isValid = isValidGitHubSource(source);
      console.log(`GitHub environment variables validation: ${isValid ? 'Valid' : 'Invalid'}`);
    } else {
      console.log("Using existing GitHub source information");
      logGitHubSource(gitHubSource);
    }
    
    // Log the available file context
    const fileCount = Object.keys(fileContext).length;
    console.log(`Available file context: ${fileCount} files`);
    if (fileCount > 0) {
      console.log("Files in context:", Object.keys(fileContext));
    }
    
    const interval = setInterval(() => {
      setProgress(prev => {
        if (prev >= 100) {
          clearInterval(interval);
          setStatus('success');
          setDiffs(mockDiffs);
          console.log(`Developer agent completed work successfully with ${mockDiffs.length} diffs`);
          onComplete();
          return 100;
        }
        return Math.min(prev + 2, 100);
      });
    }, 100);
  };

  /**
   * Simulate a failure in the developer agent
   */
  const simulateFailure = (reason?: string, responseQuality?: 'good' | 'generic' | 'invalid') => {
    setStatus('error');
    if (reason) {
      setEscalationReason(reason);
    }
    if (responseQuality) {
      setResponseQuality(responseQuality);
    }
  };
  
  /**
   * Simulate an early escalation due to low confidence or complexity
   */
  const simulateEarlyEscalation = (
    reason: string, 
    confidence?: number, 
    options?: {
      responseQuality?: 'good' | 'generic' | 'invalid';
      rawResponse?: string;
    }
  ) => {
    setStatus('escalated');
    setEarlyEscalation(true);
    setEscalationReason(reason);
    if (confidence !== undefined) {
      setConfidenceScore(confidence);
    }
    if (options?.responseQuality) {
      setResponseQuality(options.responseQuality);
    }
    if (options?.rawResponse) {
      setRawOpenAIResponse(options.rawResponse);
    }
  };

  /**
   * Reset the agent state
   */
  const reset = () => {
    setStatus('idle');
    setProgress(0);
    setDiffs(undefined);
    setAttempt(1);
    setConfidenceScore(undefined);
    setEscalationReason(undefined);
    setEarlyEscalation(false);
    setPatchAnalytics(null);
    setRawOpenAIResponse(null);
    setResponseQuality(undefined);
    setGitHubSource(null);
    setFileContext({});
  };

  return {
    status,
    progress,
    diffs,
    attempt,
    maxAttempts,
    confidenceScore,
    escalationReason,
    earlyEscalation,
    patchAnalytics,
    rawOpenAIResponse,
    responseQuality,
    patchMode,
    gitHubSource,
    fileContext,
    fileRetrievalErrors,
    simulateWork,
    simulateFailure: (reason?: string, responseQuality?: 'good' | 'generic' | 'invalid') => {
      setStatus('error');
      if (reason) {
        setEscalationReason(reason);
      }
      if (responseQuality) {
        setResponseQuality(responseQuality);
      }
    },
    simulateEarlyEscalation: (
      reason: string, 
      confidence?: number, 
      options?: {
        responseQuality?: 'good' | 'generic' | 'invalid';
        rawResponse?: string;
      }
    ) => {
      setStatus('escalated');
      setEarlyEscalation(true);
      setEscalationReason(reason);
      if (confidence !== undefined) {
        setConfidenceScore(confidence);
      }
      if (options?.responseQuality) {
        setResponseQuality(options.responseQuality);
      }
      if (options?.rawResponse) {
        setRawOpenAIResponse(options.rawResponse);
      }
    },
    reset
  };
}
