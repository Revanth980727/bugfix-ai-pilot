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
  const [patchMode, setPatchMode] = useState<'unified_diff' | 'line-by-line' | 'direct' | 'intelligent'>('unified_diff');
  const [gitHubSource, setGitHubSource] = useState<GitHubSource | null>(null);
  const [fileContext, setFileContext] = useState<Record<string, string>>({});
  const [fileRetrievalErrors, setFileRetrievalErrors] = useState<Record<string, string>>({});
  const [diagnosisLogs, setDiagnosisLogs] = useState<string[]>([]);
  const [fileAccessAttempts, setFileAccessAttempts] = useState<{file: string, success: boolean, error?: string}[]>([]);
  const [patchValidation, setPatchValidation] = useState<{validated: boolean, valid: boolean, errors: string[]}>({
    validated: false,
    valid: false,
    errors: []
  });
  const [preferDiffs, setPreferDiffs] = useState(true);
  const [allowFullReplace, setAllowFullReplace] = useState(true);
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
            default_branch: config.default_branch || 'main',
            patch_mode: config.patch_mode || 'unified_diff'
          };
          
          setGitHubSource(source);
          setPatchMode(config.patch_mode as 'unified_diff' | 'line-by-line' | 'direct' | 'intelligent' || 'unified_diff');
          
          // Set diff preferences based on config - fix the type comparison
          const diffModes: Array<'unified_diff' | 'line-by-line' | 'direct' | 'intelligent'> = ['unified_diff', 'line-by-line', 'intelligent'];
          setPreferDiffs(diffModes.includes(config.patch_mode as any));
          
          // Validate the GitHub source
          const isValid = isValidGitHubSource(source);
          console.log(`GitHub config validation result: ${isValid ? 'Valid' : 'Invalid'}`);
          setDiagnosisLogs(prev => [...prev, `GitHub config validation: ${isValid ? 'Valid' : 'Invalid'}`]);
          setDiagnosisLogs(prev => [...prev, `Diff-first mode: ${preferDiffs ? 'Enabled' : 'Disabled'}`]);
          
          // Attempt to fetch some example files to verify access
          if (isValid) {
            await testRepositoryAccess(source);
          } else {
            // Try from environment as fallback
            setDiagnosisLogs(prev => [...prev, "Config invalid, trying environment variables as fallback"]);
            console.log("Config invalid, trying environment variables as fallback...");
            const envSource = extractGitHubSourceFromEnv();
            const envValid = isValidGitHubSource(envSource);
            
            if (envValid) {
              setGitHubSource(envSource);
              setPatchMode(envSource.patch_mode as 'unified_diff' | 'line-by-line' | 'direct' | 'intelligent' || 'unified_diff');
              await testRepositoryAccess(envSource);
            } else {
              setDiagnosisLogs(prev => [...prev, "Neither config nor env provides valid GitHub source information"]);
              console.error("Neither config nor env provides valid GitHub source information");
            }
          }
        } else {
          setDiagnosisLogs(prev => [...prev, "No GitHub config returned, will try environment variables as fallback"]);
          console.warn("No GitHub config returned, will try environment variables as fallback");
          const envSource = extractGitHubSourceFromEnv();
          const isValid = isValidGitHubSource(envSource);
          
          if (isValid) {
            setGitHubSource(envSource);
            setPatchMode(envSource.patch_mode as 'unified_diff' | 'line-by-line' | 'direct' | 'intelligent' || 'unified_diff');
            await testRepositoryAccess(envSource);
          } else {
            setDiagnosisLogs(prev => [...prev, "Environment variables do not provide valid GitHub source information"]);
            console.error("Environment variables do not provide valid GitHub source information");
          }
        }
      } catch (error) {
        setDiagnosisLogs(prev => [...prev, `Error fetching GitHub config: ${error}`]);
        console.error('Error fetching GitHub config:', error);
        setFileRetrievalErrors(prev => ({
          ...prev,
          'config': `Failed to fetch GitHub configuration: ${error}`
        }));
      }
    };
    
    fetchGitHubConfig();
  }, [preferDiffs]);

  /**
   * Test repository access by trying to fetch a common file
   */
  const testRepositoryAccess = async (source: GitHubSource) => {
    try {
      setDiagnosisLogs(prev => [...prev, `Testing repository access for ${source.repo_owner}/${source.repo_name}`]);
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
      const attempts: {file: string, success: boolean, error?: string}[] = [];
      
      for (const file of commonFiles) {
        try {
          setDiagnosisLogs(prev => [...prev, `Testing access to file: ${file}`]);
          console.log(`Testing access to file: ${file}`);
          const exists = await checkFileExists(file);
          if (exists) {
            console.log(`Found file in repository: ${file}`);
            const content = await getFileContent(file);
            if (content) {
              setDiagnosisLogs(prev => [...prev, `Successfully retrieved content for ${file} (${content.length} bytes)`]);
              console.log(`Successfully retrieved content for ${file} (${content.length} bytes)`);
              // Store this file content in our context
              setFileContext(prev => ({
                ...prev,
                [file]: content
              }));
              accessSuccessful = true;
              attempts.push({file, success: true});
            } else {
              const errorMsg = `File exists but content is empty or null`;
              errors[file] = errorMsg;
              attempts.push({file, success: false, error: errorMsg});
              setDiagnosisLogs(prev => [...prev, `File ${file} exists but content could not be retrieved`]);
              console.warn(`File ${file} exists but content could not be retrieved`);
            }
          } else {
            const errorMsg = 'File does not exist in repository';
            errors[file] = errorMsg;
            attempts.push({file, success: false, error: errorMsg});
            setDiagnosisLogs(prev => [...prev, `File ${file} does not exist in repository`]);
            console.log(`File ${file} does not exist in repository`);
          }
        } catch (err) {
          const errorMsg = `Error accessing file: ${err}`;
          errors[file] = errorMsg;
          attempts.push({file, success: false, error: errorMsg});
          setDiagnosisLogs(prev => [...prev, `Error accessing file ${file}: ${err}`]);
          console.error(`Error accessing file ${file}:`, err);
        }
      }
      
      setFileRetrievalErrors(errors);
      setFileAccessAttempts(attempts);
      
      if (!accessSuccessful) {
        setDiagnosisLogs(prev => [...prev, "Could not access any common files in the repository"]);
        console.warn("Could not access any common files in the repository");
      } else {
        setDiagnosisLogs(prev => [...prev, "Repository access test: SUCCESS"]);
        console.log("Repository access test: SUCCESS");
      }
      
    } catch (error) {
      setDiagnosisLogs(prev => [...prev, `Repository access test failed: ${error}`]);
      console.error("Repository access test failed:", error);
      setFileRetrievalErrors(prev => ({
        ...prev, 
        'access_test': `Repository access test failed: ${error}`
      }));
    }
  };

  /**
   * Try to access a specific file
   * @param filePath The path to the file
   */
  const tryAccessFile = async (filePath: string): Promise<{success: boolean, content?: string, error?: string}> => {
    if (!gitHubSource || !gitHubSource.repo_owner || !gitHubSource.repo_name) {
      return {
        success: false,
        error: "No valid GitHub source configuration"
      };
    }
    
    try {
      setDiagnosisLogs(prev => [...prev, `Explicitly trying to access file: ${filePath}`]);
      console.log(`Explicitly trying to access file: ${filePath}`);
      
      const exists = await checkFileExists(filePath);
      if (!exists) {
        const error = `File does not exist: ${filePath}`;
        setDiagnosisLogs(prev => [...prev, error]);
        return {
          success: false,
          error
        };
      }
      
      const content = await getFileContent(filePath);
      if (!content) {
        const error = `Failed to get content for file: ${filePath}`;
        setDiagnosisLogs(prev => [...prev, error]);
        return {
          success: false,
          error
        };
      }
      
      setDiagnosisLogs(prev => [...prev, `Successfully retrieved ${filePath} (${content.length} bytes)`]);
      
      // Add this file to our context
      setFileContext(prev => ({
        ...prev,
        [filePath]: content
      }));
      
      return {
        success: true,
        content
      };
    } catch (error) {
      const errorMsg = `Error accessing file ${filePath}: ${error}`;
      setDiagnosisLogs(prev => [...prev, errorMsg]);
      setFileRetrievalErrors(prev => ({
        ...prev,
        [filePath]: errorMsg
      }));
      
      return {
        success: false,
        error: errorMsg
      };
    }
  };
  
  /**
   * Validate a patch against expected changes
   */
  const validatePatch = async (patch: string, patchedFiles: string[], expectedCode: Record<string, string>) => {
    try {
      setDiagnosisLogs(prev => [...prev, `Validating patch for ${patchedFiles.length} files`]);
      
      const errors: string[] = [];
      let isValid = true;
      
      // For each file in the patch, check if the expected code matches
      for (const file of patchedFiles) {
        // Get the original content
        const originalContent = fileContext[file];
        if (!originalContent) {
          setDiagnosisLogs(prev => [...prev, `Warning: No original content available for ${file}, can't validate`]);
          continue;
        }
        
        // Get the expected content
        const expected = expectedCode[file];
        if (!expected) {
          setDiagnosisLogs(prev => [...prev, `Warning: No expected content provided for ${file}, can't validate`]);
          continue;
        }
        
        // Simple comparison for now - normalize both to account for line ending differences
        const normalizeContent = (content: string) => 
          content.replace(/\r\n/g, '\n').trim();
        
        if (normalizeContent(originalContent) !== normalizeContent(expected)) {
          // We would need to extract file-specific patches and apply them, but for now
          // just check if the file is mentioned in the patch
          if (!patch.includes(file)) {
            errors.push(`File ${file} is expected to change but not included in the patch`);
            isValid = false;
          }
        }
      }
      
      setPatchValidation({
        validated: true,
        valid: isValid,
        errors
      });
      
      return { isValid, errors };
    } catch (error) {
      setDiagnosisLogs(prev => [...prev, `Error validating patch: ${error}`]);
      setPatchValidation({
        validated: true,
        valid: false,
        errors: [`Error validating patch: ${error}`]
      });
      return { isValid: false, errors: [`${error}`] };
    }
  };

  /**
   * Simulate developer agent work with diff-first approach
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
      patchMode?: 'unified_diff' | 'line-by-line' | 'direct' | 'intelligent';
      expectedCode?: Record<string, string>;
    }
  ) => {
    setStatus('working');
    setAttempt(currentAttempt);
    console.log(`Developer agent starting work (attempt ${currentAttempt}/${maxAttempts})`);
    console.log(`Using diff-first approach with patch mode: ${options?.patchMode || patchMode}`);
    console.log(`Prefer diffs: ${preferDiffs}, Allow full replace: ${allowFullReplace}`);
    
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
      
      // Update diff preferences based on patch mode - fix the comparison
      const diffModes: Array<'unified_diff' | 'line-by-line' | 'direct' | 'intelligent'> = ['unified_diff', 'line-by-line', 'intelligent'];
      const usesDiffs = diffModes.includes(options.patchMode);
      setPreferDiffs(usesDiffs);
      setDiagnosisLogs(prev => [...prev, `Patch mode set to: ${options.patchMode}`]);
      setDiagnosisLogs(prev => [...prev, `Diff-first approach: ${usesDiffs ? 'Enabled' : 'Disabled'}`]);
    }
    
    // If we have expected code, validate the patch
    if (options?.expectedCode && mockDiffs && mockDiffs.length > 0) {
      const patchContent = mockDiffs.map(diff => diff.diff).join('\n');
      const patchedFiles = mockDiffs.map(diff => diff.filename);
      
      // Run validation asynchronously
      validatePatch(patchContent, patchedFiles, options.expectedCode).then(({ isValid, errors }) => {
        if (!isValid) {
          console.warn("Patch validation failed:", errors);
          setDiagnosisLogs(prev => [...prev, `Patch validation failed: ${errors.join(', ')}`]);
        } else {
          console.log("Patch validation succeeded");
          setDiagnosisLogs(prev => [...prev, "Patch validation succeeded"]);
        }
      });
    }

    // If GitHub source isn't set yet from config, try from env
    if (!gitHubSource) {
      console.log("No GitHub source yet, extracting from environment...");
      const source = extractGitHubSourceFromEnv();
      // Ensure default_branch and patch_mode have fallback values
      source.default_branch = source.default_branch || 'main';
      source.patch_mode = source.patch_mode || 'unified_diff';
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
          console.log(`Strategy used: ${preferDiffs ? 'Diff-first' : 'Full-replacement'}`);
          onComplete();
          return 100;
        }
        return Math.min(prev + 2, 100);
      });
    }, 100);
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
    setPatchValidation({
      validated: false,
      valid: false,
      errors: []
    });
    setGitHubSource(null);
    setFileContext({});
    setPatchMode('unified_diff');
    setPreferDiffs(true);
    setAllowFullReplace(true);
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
    diagnosisLogs,
    fileAccessAttempts,
    patchValidation,
    preferDiffs,
    allowFullReplace,
    simulateWork,
    tryAccessFile,
    validatePatch,
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
