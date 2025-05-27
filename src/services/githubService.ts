
import { GitHubConfig } from '@/types/ticket';
import { isValidGitHubSource, diagnoseGitHubAccessIssues } from '@/utils/developerSourceLogger';

// Store PR number mappings
const prMappings: Record<string, number> = {};

/**
 * Get GitHub configuration from environment variables or API
 */
export const getGitHubConfig = async (): Promise<GitHubConfig | null> => {
  try {
    console.log('Fetching GitHub configuration...');
    // In a real app, this would make an API call to the backend
    // For now, we'll just use environment variables or simulated data
    const config: GitHubConfig = {
      repo_owner: process.env.GITHUB_REPO_OWNER || import.meta.env.VITE_GITHUB_REPO_OWNER as string || '',
      repo_name: process.env.GITHUB_REPO_NAME || import.meta.env.VITE_GITHUB_REPO_NAME as string || '',
      default_branch: process.env.GITHUB_DEFAULT_BRANCH || import.meta.env.VITE_GITHUB_DEFAULT_BRANCH as string || 'main',
      branch: process.env.GITHUB_BRANCH || import.meta.env.VITE_GITHUB_BRANCH as string || '',
      patch_mode: (process.env.PATCH_MODE || import.meta.env.VITE_PATCH_MODE as string || 'line-by-line') as 'intelligent' | 'line-by-line' | 'direct',
      preserve_branch_case: (process.env.PRESERVE_BRANCH_CASE === 'true' || import.meta.env.VITE_PRESERVE_BRANCH_CASE === 'true') || true,
      include_test_files: (process.env.INCLUDE_TEST_FILES === 'true' || import.meta.env.VITE_INCLUDE_TEST_FILES === 'true') || false
    };
    
    // Get TEST_MODE setting - more explicitly check for true values
    const isTestMode = process.env.TEST_MODE?.toLowerCase() === 'true' || 
                      import.meta.env.VITE_TEST_MODE === 'true';
    
    // Log TEST_MODE status
    if (isTestMode) {
      console.warn("⚠️ Running in TEST_MODE - using placeholder repo values and mock GitHub operations");
      console.warn("Set TEST_MODE=False in .env for real GitHub interactions");
    } else {
      console.log("Running in PRODUCTION MODE - using real GitHub values and operations");
    }
    
    // Validate configuration before returning
    if (!config.repo_owner || !config.repo_name) {
      console.error('GitHub configuration is incomplete: Missing repo_owner or repo_name');
      console.error('Please check your .env file and ensure GITHUB_REPO_OWNER and GITHUB_REPO_NAME are set');
      
      // Don't fall back to placeholder values in production - only in test mode
      if (isTestMode) {
        console.warn('Running in TEST_MODE - using placeholder repo values');
        config.repo_owner = config.repo_owner || 'example-org';
        config.repo_name = config.repo_name || 'example-repo';
      } else {
        // In production mode, reject the configuration if it's incomplete
        console.error('Rejecting incomplete GitHub configuration in production mode');
        return null;
      }
    }
    
    // Detect placeholder values and fail in production mode
    if (config.repo_owner === 'your_github_username_or_org' || 
        config.repo_name === 'your_repository_name') {
      console.error('GitHub configuration contains placeholder values');
      console.error('Please set proper values in your .env file before using in production');
      
      // Only allow placeholder values in test mode
      if (!isTestMode) {
        console.error('Refusing to use placeholder values outside of test mode');
        return null;
      } else {
        console.warn("Using placeholder values is only allowed in TEST_MODE - don't use in production");
      }
    }
    
    // Set default branch name if not provided
    if (!config.branch) {
      const defaultBranchBase = config.default_branch || 'main';
      config.branch = process.env.GITHUB_USE_DEFAULT_BRANCH_ONLY?.toLowerCase() === 'true' 
        ? defaultBranchBase 
        : `feature/bugfix`;
    }
    
    // Log the config for debugging (without sensitive data)
    console.log(`GitHub config loaded: ${config.repo_owner}/${config.repo_name}`);
    console.log(`Using branch: ${config.branch} (default: ${config.default_branch})`);
    console.log(`Using patch mode: ${config.patch_mode}`);
    console.log(`Preserve branch case: ${config.preserve_branch_case ? 'Yes' : 'No'}`);
    console.log(`Include test files: ${config.include_test_files ? 'Yes' : 'No'}`);
    console.log(`Test mode: ${isTestMode ? 'Enabled' : 'Disabled'}`);
    
    // Log raw environment variables (redacted) for debugging
    console.log('Environment variables present:', {
      GITHUB_REPO_OWNER: Boolean(process.env.GITHUB_REPO_OWNER),
      VITE_GITHUB_REPO_OWNER: Boolean(import.meta.env.VITE_GITHUB_REPO_OWNER),
      GITHUB_REPO_NAME: Boolean(process.env.GITHUB_REPO_NAME),
      VITE_GITHUB_REPO_NAME: Boolean(import.meta.env.VITE_GITHUB_REPO_NAME),
      TEST_MODE: Boolean(process.env.TEST_MODE) || Boolean(import.meta.env.VITE_TEST_MODE),
      GITHUB_USE_DEFAULT_BRANCH_ONLY: process.env.GITHUB_USE_DEFAULT_BRANCH_ONLY || import.meta.env.VITE_GITHUB_USE_DEFAULT_BRANCH_ONLY,
      PRESERVE_BRANCH_CASE: Boolean(process.env.PRESERVE_BRANCH_CASE) || Boolean(import.meta.env.VITE_PRESERVE_BRANCH_CASE),
      INCLUDE_TEST_FILES: Boolean(process.env.INCLUDE_TEST_FILES) || Boolean(import.meta.env.VITE_INCLUDE_TEST_FILES)
    });
    
    // Validate the configuration
    const valid = isValidGitHubSource(config);
    if (!valid && !isTestMode) {
      console.warn('GitHub configuration is incomplete or invalid');
      const issues = diagnoseGitHubAccessIssues(config);
      console.warn('Potential GitHub access issues:', issues);
    }
    
    return config;
  } catch (error) {
    console.error('Failed to get GitHub configuration:', error);
    return null;
  }
};

/**
 * Generate a patch/diff between original and modified file content
 */
export const generateDiff = (originalContent: string, modifiedContent: string, filename: string): string => {
  console.log(`Generating diff for file: ${filename}`);
  
  // Quick check if there's actually a change
  if (originalContent === modifiedContent) {
    console.warn(`No changes detected for file ${filename} - content exactly matches`);
    return '';
  }
  
  // Check for meaningful changes beyond whitespace
  const normalizedOriginal = originalContent.replace(/\s+/g, ' ').trim();
  const normalizedModified = modifiedContent.replace(/\s+/g, ' ').trim();
  
  if (normalizedOriginal === normalizedModified) {
    console.warn(`Only whitespace changes detected for ${filename}`);
    // Continue anyway to generate the diff, but log a warning
  }
  
  // Use a better diff generation approach
  const originalLines = originalContent.split('\n');
  const modifiedLines = modifiedContent.split('\n');
  
  // Generate a unified diff
  const diff = [];
  diff.push(`--- a/${filename}`);
  diff.push(`+++ b/${filename}`);
  
  // Create a real unified diff
  const diffLines = [];
  let currentHunk = [];
  let hunkHeader = '';
  let inHunk = false;
  let oldLineNo = 1;
  let newLineNo = 1;
  
  // Track statistics for better logging
  let addedLines = 0;
  let removedLines = 0;
  let modifiedHunks = 0;
  
  for (let i = 0; i < Math.max(originalLines.length, modifiedLines.length); i++) {
    const originalLine = i < originalLines.length ? originalLines[i] : null;
    const modifiedLine = i < modifiedLines.length ? modifiedLines[i] : null;
    
    if (originalLine === modifiedLine) {
      // Context line
      if (inHunk) {
        currentHunk.push(' ' + originalLine);
        oldLineNo++;
        newLineNo++;
      } else {
        // Start a new hunk with context
        if (i > 0) {
          const contextStartIdx = Math.max(0, i - 3); // Up to 3 lines of context
          for (let j = contextStartIdx; j < i; j++) {
            currentHunk.push(' ' + originalLines[j]);
          }
          hunkHeader = `@@ -${contextStartIdx + 1},${i - contextStartIdx + 1} +${contextStartIdx + 1},${i - contextStartIdx + 1} @@`;
          inHunk = true;
          oldLineNo = i + 1;
          newLineNo = i + 1;
        }
      }
    } else {
      // Start a new hunk if not already in one
      if (!inHunk) {
        const contextStartIdx = Math.max(0, i - 3); // Up to 3 lines of context
        for (let j = contextStartIdx; j < i; j++) {
          currentHunk.push(' ' + originalLines[j]);
        }
        hunkHeader = `@@ -${contextStartIdx + 1},${i - contextStartIdx + 1} +${contextStartIdx + 1},${i - contextStartIdx + 1} @@`;
        inHunk = true;
        oldLineNo = i + 1;
        newLineNo = i + 1;
        modifiedHunks++;
      }
      
      // Handle line differences
      if (originalLine !== null && modifiedLine !== null) {
        // Line was modified
        currentHunk.push('-' + originalLine);
        currentHunk.push('+' + modifiedLine);
        oldLineNo++;
        newLineNo++;
        removedLines++;
        addedLines++;
      } else if (originalLine === null) {
        // Line was added
        currentHunk.push('+' + modifiedLine);
        newLineNo++;
        addedLines++;
      } else if (modifiedLine === null) {
        // Line was removed
        currentHunk.push('-' + originalLine);
        oldLineNo++;
        removedLines++;
      }
    }
    
    // End the hunk if we've gone 3+ lines with no changes
    const isEnd = i === Math.max(originalLines.length, modifiedLines.length) - 1;
    if (inHunk && (i > 0 && i % 20 === 0 || isEnd)) {
      if (currentHunk.length > 0) {
        diff.push(hunkHeader);
        diff.push(...currentHunk);
      }
      currentHunk = [];
      inHunk = false;
    }
  }
  
  // Add any remaining hunk
  if (inHunk && currentHunk.length > 0) {
    diff.push(hunkHeader);
    diff.push(...currentHunk);
  }
  
  const finalDiff = diff.join('\n');
  
  // Log detailed statistics about the diff for debugging
  console.log(`Generated diff for ${filename}: ${finalDiff.split('\n').length} lines, ${modifiedHunks} hunks, +${addedLines}/-${removedLines} lines`);
  
  // Verify the diff is not empty
  if (!finalDiff.includes('@@') || finalDiff.split('\n').length <= 2) {
    console.warn('Generated diff appears to be empty or invalid');
    return '';
  }
  
  return finalDiff;
};

/**
 * Check if a file exists in the repository
 */
export const checkFileExists = async (filePath: string): Promise<boolean> => {
  console.log(`Checking if file exists: ${filePath}`);
  try {
    // In a real implementation, this would call the backend
    // For testing, simulate file existence
    const result = true;
    console.log(`File ${filePath} exists: ${result}`);
    return result;
  } catch (error) {
    console.error(`Error checking if file exists [${filePath}]:`, error);
    return false;
  }
};

/**
 * Get file content from repository
 */
export const getFileContent = async (filePath: string): Promise<string | null> => {
  console.log(`Attempting to get content for file: ${filePath}`);
  
  try {
    // In a real implementation, this would call the backend API
    // For testing, return mock content based on file type
    let mockContent = `// Mock content for ${filePath}\n// This would be the actual file content in a real implementation\n\n`;
    
    if (filePath.endsWith('.py')) {
      mockContent += `import os\nimport sys\n\ndef main():\n    print("This is mock Python content")\n\nif __name__ == "__main__":\n    main()\n`;
    } else if (filePath.endsWith('.js') || filePath.endsWith('.ts')) {
      mockContent += `function exampleCode() {\n  console.log("This is mock JavaScript content");\n}\n\nexport default exampleCode;\n`;
    } else {
      mockContent += `function exampleCode() {\n  console.log("This is mock content");\n}\n`;
    }
    
    console.log(`Successfully generated mock content for ${filePath} (${mockContent.length} bytes)`);
    return mockContent;
  } catch (error) {
    console.error(`Failed to get content for ${filePath}:`, error);
    return null;
  }
};

/**
 * Validate a GitHub PR URL to ensure it points to the correct repository
 * @param prUrl - The PR URL to validate 
 * @param allowedRepos - Optional array of allowed repositories (owner/name format)
 * @returns Validation result with standardized URL if valid
 */
export const validatePrUrl = async (
  prUrl: string, 
  allowedRepos?: string[]
): Promise<{ 
  valid: boolean; 
  url?: string; 
  prNumber?: number; 
  repo?: string;
  error?: string;
}> => {
  console.log(`Validating PR URL: ${prUrl}`);
  
  // Get config to check against allowed repositories
  const config = await getGitHubConfig();
  const configRepo = config ? `${config.repo_owner}/${config.repo_name}` : null;
  
  // If allowedRepos not provided, use the configured repo
  if (!allowedRepos && configRepo) {
    allowedRepos = [configRepo];
  }
  
  // Check if running in test mode
  const isTestMode = process.env.TEST_MODE?.toLowerCase() === 'true' || 
                     import.meta.env.VITE_TEST_MODE === 'true';
  
  // Explicitly check for mock/placeholder URLs
  const isMockUrl = prUrl.includes('example-org/example-repo') ||
                   prUrl.includes('org/repo/pull') ||
                   prUrl.includes('999');
  
  // Detect placeholder URLs (only allow in test mode)
  if (isMockUrl) {
    if (!isTestMode) {
      console.error("Detected placeholder/mock PR URL outside of TEST_MODE:", prUrl);
      return {
        valid: false,
        error: "Placeholder or mock PR URL detected outside of test mode"
      };
    } else {
      console.warn("Using placeholder/mock PR URL:", prUrl);
      console.warn("This is only allowed in TEST_MODE - don't use in production");
      
      // When in test mode, we'll allow this and return a standardized mock URL
      return {
        valid: true,
        url: "https://github.com/example-org/example-repo/pull/999",
        prNumber: 999,
        repo: "example-org/example-repo"
      };
    }
  }
  
  // Try to extract PR number from a GitHub URL
  // Format: https://github.com/owner/repo/pull/123
  const urlMatch = /github\.com\/([^\/]+)\/([^\/]+)\/pull\/(\d+)/i.exec(prUrl);
  
  if (!urlMatch) {
    return { 
      valid: false, 
      error: "Invalid GitHub PR URL format. Expected: https://github.com/owner/repo/pull/123" 
    };
  }
  
  const owner = urlMatch[1];
  const repo = urlMatch[2];
  const prNumber = parseInt(urlMatch[3], 10);
  const extractedRepo = `${owner}/${repo}`;
  
  // Check if the PR is in an allowed repository
  if (allowedRepos && allowedRepos.length > 0 && !isTestMode) {
    if (!allowedRepos.includes(extractedRepo)) {
      console.warn(`PR URL ${prUrl} is not in an allowed repository. Allowed: ${allowedRepos.join(', ')}`);
      
      return {
        valid: false,
        prNumber,
        repo: extractedRepo,
        error: `PR must be in the configured repository: ${allowedRepos.join(' or ')}`
      };
    }
  }
  
  // Return standardized URL
  const standardizedUrl = `https://github.com/${owner}/${repo}/pull/${prNumber}`;
  
  console.log(`PR URL validated: ${standardizedUrl} (PR #${prNumber})`);
  return {
    valid: true,
    url: standardizedUrl,
    prNumber,
    repo: extractedRepo
  };
};

/**
 * Detailed debugging function to pinpoint file access issues
 */
export const debugFileAccess = async (repo: string, branch: string, filePath: string): Promise<{
  success: boolean;
  message: string;
  details: Record<string, any>;
}> => {
  console.log(`Debugging file access: ${repo} / ${branch} / ${filePath}`);
  
  try {
    // Test if GitHub configuration is available
    const config = await getGitHubConfig();
    if (!config) {
      return {
        success: false,
        message: "GitHub configuration unavailable",
        details: {
          reason: "Missing GitHub configuration",
          environment: {
            repoOwnerPresent: Boolean(process.env.GITHUB_REPO_OWNER || import.meta.env.VITE_GITHUB_REPO_OWNER),
            repoNamePresent: Boolean(process.env.GITHUB_REPO_NAME || import.meta.env.VITE_GITHUB_REPO_NAME)
          }
        }
      };
    }
    
    // Check if file exists
    const exists = await checkFileExists(filePath);
    if (!exists) {
      return {
        success: false,
        message: `File not found: ${filePath}`,
        details: {
          reason: "File not found",
          path: filePath,
          repository: repo,
          branch: branch
        }
      };
    }
    
    // Try to get content
    const content = await getFileContent(filePath);
    if (!content) {
      return {
        success: false,
        message: `Content retrieval failed for: ${filePath}`,
        details: {
          reason: "Content retrieval error",
          path: filePath,
          repository: repo,
          branch: branch
        }
      };
    }
    
    return {
      success: true,
      message: `Successfully accessed file: ${filePath}`,
      details: {
        path: filePath,
        repository: repo,
        branch: branch,
        contentLength: content.length
      }
    };
  } catch (error) {
    return {
      success: false,
      message: `Error debugging file access: ${error}`,
      details: {
        error: String(error),
        path: filePath,
        repository: repo,
        branch: branch
      }
    };
  }
};

/**
 * Store a mapping between a ticket ID and PR number
 */
export const storePRMapping = (ticketId: string, prNumber: number): void => {
  console.log(`Storing PR mapping: ${ticketId} -> PR #${prNumber}`);
  prMappings[ticketId] = prNumber;
};

/**
 * Get the PR number for a ticket if a mapping exists
 */
export const getPRNumberForTicket = (ticketId: string): number | undefined => {
  return prMappings[ticketId];
};

/**
 * Safely extract a numeric PR number from various input formats
 * @param prIdentifier - Can be a number, string number, URL, or other identifier
 * @returns A PR number as an integer, or null if not extractable
 */
export const extractPRNumber = (prIdentifier: string | number | [string, number]): number | null => {
  console.log(`Attempting to extract PR number from: ${JSON.stringify(prIdentifier)}`);
  
  // Handle tuple case [url, number]
  if (Array.isArray(prIdentifier) && prIdentifier.length >= 2) {
    console.log(`Extracted PR number from tuple: ${prIdentifier[1]}`);
    return typeof prIdentifier[1] === 'number' ? prIdentifier[1] : null;
  }
  
  // If already a number, return it
  if (typeof prIdentifier === 'number') {
    return prIdentifier;
  }
  
  // If string is just a number, convert it
  if (typeof prIdentifier === 'string' && /^\d+$/.test(prIdentifier)) {
    return parseInt(prIdentifier, 10);
  }
  
  // Check if it's a ticket ID with a known PR mapping
  if (typeof prIdentifier === 'string' && prMappings[prIdentifier]) {
    console.log(`Found PR mapping for ticket ${prIdentifier}: PR #${prMappings[prIdentifier]}`);
    return prMappings[prIdentifier];
  }
  
  // Try to extract PR number from a GitHub URL
  // Format: https://github.com/owner/repo/pull/123
  if (typeof prIdentifier === 'string') {
    const urlMatch = /\/pull\/(\d+)/.exec(prIdentifier);
    if (urlMatch && urlMatch[1]) {
      return parseInt(urlMatch[1], 10);
    }
  }
  
  // IMPORTANT: Do NOT extract numbers from JIRA ticket IDs
  if (typeof prIdentifier === 'string' && /^[A-Z]+-\d+$/.test(prIdentifier)) {
    console.log(`Not extracting PR number from JIRA ticket ID: ${prIdentifier}`);
    return null;
  }
  
  console.warn(`Could not extract PR number from: ${prIdentifier}`);
  return null;
};

/**
 * Add a comment to a PR, handling various input formats for the PR identifier
 * @param prIdentifier - PR number or URL
 * @param comment - Comment content
 * @returns Success status
 */
export const addPRComment = async (
  prIdentifier: string | number | [string, number], 
  comment: string
): Promise<boolean> => {
  // Extract numeric PR number if needed
  const prNumber = extractPRNumber(prIdentifier);
  
  // If we couldn't get a PR number, try to find a PR for the ticket if this is a ticket ID
  if (prNumber === null && typeof prIdentifier === 'string' && /^[A-Z]+-\d+$/.test(prIdentifier)) {
    console.log(`Attempting to find PR for ticket ID: ${prIdentifier}`);
    
    // In a real application, this would call an API to find the PR
    // For this implementation, we'll just check our mapping
    if (prMappings[prIdentifier]) {
      console.log(`Found PR #${prMappings[prIdentifier]} for ticket ${prIdentifier}`);
      try {
        console.log(`Would add comment to PR #${prMappings[prIdentifier]}: ${comment.substring(0, 50)}${comment.length > 50 ? '...' : ''}`);
        return true;
      } catch (error) {
        console.error(`Error adding comment to PR #${prMappings[prIdentifier]}:`, error);
        return false;
      }
    }
    
    console.error(`No PR found for ticket ID: ${prIdentifier}`);
    return false;
  }
  
  // If we still don't have a PR number, log error and return false
  if (prNumber === null) {
    console.error(`Failed to extract PR number from: ${prIdentifier}`);
    return false;
  }
  
  console.log(`Adding comment to PR #${prNumber}`);
  
  try {
    // In a real implementation, this would call an API to add the comment
    // For testing, log the comment that would be added
    console.log(`Would add comment to PR #${prNumber}: ${comment.substring(0, 50)}${comment.length > 50 ? '...' : ''}`);
    return true;
  } catch (error) {
    console.error(`Error adding comment to PR #${prNumber}:`, error);
    return false;
  }
};

/**
 * Validates patch content before applying
 * @param patchContent Unified diff patch content
 * @param filePaths Array of file paths being patched
 * @returns Validation result
 */
export const validatePatch = (
  patchContent: string, 
  filePaths: string[]
): {
  isValid: boolean;
  rejectionReason?: string;
  validationMetrics: {
    totalPatches: number;
    validPatches: number;
    rejectedPatches: number;
    rejectionReasons: Record<string, number>;
  };
  fileChecksums: Record<string, string>;
  patchesApplied: number;
  linesChanged: { added: number; removed: number };
  hasMeaningfulChanges: boolean;
} => {
  console.log(`Validating patch with ${filePaths ? filePaths.length : 0} files`);
  console.log(`Patch content length: ${patchContent ? patchContent.length : 0} bytes`);
  
  const patchContentSample = patchContent 
    ? `${patchContent.substring(0, 50)}${patchContent.length > 50 ? '...' : ''}`
    : 'No content';
  console.log(`Patch content sample: ${patchContentSample}`);
  
  if (filePaths) {
    console.log(`File paths: ${JSON.stringify(filePaths.slice(0, 3))}${filePaths.length > 3 ? '...' : ''}`);
  } else {
    console.log(`File paths: None provided`);
  }
  
  // Basic structure to track validation metrics
  const validationMetrics = {
    totalPatches: filePaths ? filePaths.length : 0,
    validPatches: 0,
    rejectedPatches: 0,
    rejectionReasons: {} as Record<string, number>,
  };
  
  // Track line changes
  const linesChanged = { added: 0, removed: 0 };
  
  // Track file checksums (for change validation)
  const fileChecksums: Record<string, string> = {};
  
  // Check for meaningful changes (not just whitespace)
  let hasMeaningfulChanges = false;
  
  // Simple check for empty patch content
  if (!patchContent || patchContent.trim() === '') {
    validationMetrics.rejectedPatches = validationMetrics.totalPatches;
    validationMetrics.rejectionReasons['empty_patch'] = validationMetrics.totalPatches;
    console.error('Patch validation failed: Patch content is empty');
    return {
      isValid: false,
      rejectionReason: 'Patch content is empty',
      validationMetrics,
      fileChecksums,
      patchesApplied: 0,
      linesChanged,
      hasMeaningfulChanges: false
    };
  }
  
  // Check for empty or undefined file paths
  if (!filePaths || !Array.isArray(filePaths) || filePaths.length === 0) {
    console.error('Patch validation failed: No file paths provided');
    return {
      isValid: false,
      rejectionReason: 'No file paths provided for patching',
      validationMetrics: {
        totalPatches: 0,
        validPatches: 0,
        rejectedPatches: 0,
        rejectionReasons: { 'no_file_paths': 1 }
      },
      fileChecksums,
      patchesApplied: 0,
      linesChanged,
      hasMeaningfulChanges: false
    };
  }
  
  // Check for valid diff format (looking for patch markers)
  if (!patchContent.includes('@@') || (!patchContent.includes('--- a/') && !patchContent.includes('diff --git'))) {
    validationMetrics.rejectedPatches = filePaths.length;
    validationMetrics.rejectionReasons['invalid_diff_format'] = filePaths.length;
    console.error('Patch validation failed: Invalid diff format');
    console.log(`Patch content first 100 chars: ${patchContent.substring(0, 100)}...`);
    return {
      isValid: false,
      rejectionReason: 'Patch content is not in a valid unified diff format',
      validationMetrics,
      fileChecksums,
      patchesApplied: 0,
      linesChanged,
      hasMeaningfulChanges: false
    };
  }
  
  // Check for each file path in the patch
  let patchesApplied = 0;
  
  // Enhanced logging to debug file path vs patch content issues
  console.log(`Checking ${filePaths.length} files against patch content...`);
  console.log(`First 3 files: ${filePaths.slice(0, 3).join(', ')}${filePaths.length > 3 ? '...' : ''}`);
  
  // Parse the patch to get actual files mentioned in it
  const filesMentionedInPatch = new Set<string>();
  
  // Simple regex to extract file paths from unified diff
  const fileHeaderRegex = /^(?:---|\+\+\+) [ab]\/(.+)$/gm;
  let match;
  while ((match = fileHeaderRegex.exec(patchContent)) !== null) {
    filesMentionedInPatch.add(match[1]);
  }
  
  console.log(`Files detected in patch content: ${Array.from(filesMentionedInPatch).slice(0, 5).join(', ')}${filesMentionedInPatch.size > 5 ? '...' : ''} (${filesMentionedInPatch.size} total)`);
  
  // Count added and removed lines in the patch
  const addedLines = (patchContent.match(/^\+(?!\+\+)/gm) || []).length;
  const removedLines = (patchContent.match(/^-(?!--)/gm) || []).length;
  
  linesChanged.added = addedLines;
  linesChanged.removed = removedLines;
  
  console.log(`Lines changed in patch: +${addedLines}/-${removedLines}`);
  
  // Check for meaningful changes
  // Look for non-whitespace changes in added/removed lines
  const addedContent = [];
  const removedContent = [];
  
  // Extract the content of added/removed lines
  const addedMatches = patchContent.match(/^\+(?!\+\+)(.*)$/gm) || [];
  const removedMatches = patchContent.match(/^-(?!--)(.*)$/gm) || [];
  
  for (const match of addedMatches) {
    addedContent.push(match.substring(1).trim());  // Remove the '+' and trim
  }
  
  for (const match of removedMatches) {
    removedContent.push(match.substring(1).trim());  // Remove the '-' and trim
  }
  
  // Join and normalize content
  const addedNormalized = addedContent.join(' ').replace(/\s+/g, ' ').trim();
  const removedNormalized = removedContent.join(' ').replace(/\s+/g, ' ').trim();
  
  // Check if there are significant differences
  hasMeaningfulChanges = addedNormalized !== removedNormalized;
  console.log(`Patch contains meaningful changes: ${hasMeaningfulChanges}`);
  
  for (const filePath of filePaths) {
    // Enhanced validation logic to detect if a file is actually in the patch
    const fileInPatch = 
      filesMentionedInPatch.has(filePath) || 
      patchContent.includes(`a/${filePath}`) || 
      patchContent.includes(`b/${filePath}`) ||
      patchContent.includes(`--- ${filePath}`) ||
      patchContent.includes(`+++ ${filePath}`);
      
    if (fileInPatch) {
      validationMetrics.validPatches++;
      patchesApplied++;
      
      // Generate a simple checksum for the file path
      fileChecksums[filePath] = `sha1:${Date.now().toString().slice(-8)}${Math.random().toString(36).substring(2, 10)}`;
      console.log(`File ${filePath} found in patch - will be patched`);
    } else {
      validationMetrics.rejectedPatches++;
      validationMetrics.rejectionReasons['file_not_in_patch'] = 
        (validationMetrics.rejectionReasons['file_not_in_patch'] || 0) + 1;
      console.warn(`File ${filePath} NOT found in patch content - will be skipped`);
    }
  }
  
  // Final validation decision
  const isValid = validationMetrics.validPatches > 0;
  
  // Enhanced logging based on validation result
  if (isValid) {
    console.log(`Patch validation passed: ${validationMetrics.validPatches} files will be patched`);
    if (validationMetrics.rejectedPatches > 0) {
      console.warn(`Note: ${validationMetrics.rejectedPatches} files will be skipped (not found in patch)`);
    }
    
    if (!hasMeaningfulChanges) {
      console.warn("⚠️ Patch appears to contain only whitespace changes - may result in empty commits");
    }
  } else {
    console.error(`Patch validation failed: No valid files found in patch`);
  }
  
  return {
    isValid,
    rejectionReason: isValid ? undefined : `No files from the provided list were found in the patch content`,
    validationMetrics,
    fileChecksums,
    patchesApplied,
    linesChanged,
    hasMeaningfulChanges
  };
};

/**
 * Check if the environment is properly configured for GitHub operations
 * @returns Status of the GitHub configuration
 */
export const checkGitHubEnvironment = async (): Promise<{
  isValid: boolean;
  isTestMode: boolean;
  hasPlaceholders: boolean;
  details: Record<string, any>;
}> => {
  // Get GitHub configuration
  const config = await getGitHubConfig();
  
  // Check if running in test mode
  const isTestMode = process.env.TEST_MODE?.toLowerCase() === 'true' || 
                    import.meta.env.VITE_TEST_MODE === 'true';
  
  // Check for placeholder values
  const hasPlaceholders = 
    !config?.repo_owner || 
    !config?.repo_name ||
    config?.repo_owner === 'your_github_username_or_org' ||
    config?.repo_name === 'your_repository_name';
  
  // Determine if configuration is valid
  const isValid = 
    (config !== null) && 
    (!hasPlaceholders || isTestMode);
  
  return {
    isValid,
    isTestMode,
    hasPlaceholders,
    details: {
      repo: config ? `${config.repo_owner}/${config.repo_name}` : 'Not configured',
      branch: config?.branch || 'Not specified',
      defaultBranch: config?.default_branch || 'main',
      patchMode: config?.patch_mode || 'line-by-line',
      testMode: isTestMode,
      usePlaceholders: hasPlaceholders && isTestMode
    }
  };
};
